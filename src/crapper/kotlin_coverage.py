"""Join Kotlin functions to JaCoCo methods.

Kotlin compiles one function into several JVM methods, and renames some:

- top-level functions live in `pkg.FileKt` (the function's `jacoco_class`);
- interface bodies live in `Iface$DefaultImpls`;
- `internal` functions become `name$module`, functions taking a value class
  become `name-hash`;
- each lambda becomes a method `name$lambda$N` (`name$lambda-N` before
  Kotlin 1.8; nested `name$lambda$N$lambda$M`), or, before Kotlin 2.0, a class
  `Outer$name$N` (nested `Outer$name$N$M`) whose code is in `invoke`;
- default arguments add a synthetic `name$default`, which JaCoCo keeps.

The function's coverage is its own method plus its lambdas, because its
complexity counts the decisions inside those lambdas. Anonymous objects also
compile to `Outer$name$N`; only methods inside the function's lines are added.
"""

import re
from dataclasses import dataclass, field

from crapper.model import Function

_LAMBDA_MARKERS = ("$lambda$", "$lambda-")


def _candidate_classes(function: Function) -> list[str]:
    names = []
    if function.jacoco_class:
        names += [function.jacoco_class, f"{function.jacoco_class}$DefaultImpls"]
    if function.namespace not in names:
        names.append(function.namespace)
    return names


_LAMBDA_CLASS = re.compile(r"^(.*?)\$([^$\d][^$]*)\$\d+(?:\$.*)?$")


@dataclass
class KotlinIndex:
    """A JaCoCo index regrouped for Kotlin lookups."""

    methods: dict[str, list[tuple[str, object]]] = field(default_factory=dict)
    # `(outer class, function name)` -> methods of its lambda classes
    lambda_classes: dict[tuple[str, str], list[object]] = field(default_factory=dict)


def by_class(index) -> KotlinIndex:
    """Regroup a JaCoCo index (`class#method` keys) by class and by lambda class."""

    found = KotlinIndex()
    for key, methods in index.items():
        class_name, method_name = key.split("#", 1)
        found.methods.setdefault(class_name, []).extend((method_name, each) for each in methods)
        match = _LAMBDA_CLASS.match(class_name)
        if match:
            found.lambda_classes.setdefault(match.groups(), []).extend(methods)
    return found


def _methods_named(classes: KotlinIndex, class_name: str, name: str):
    """Every `(method name, JacocoMethod)` of `class_name` starting with `name`."""

    for method_name, method in classes.methods.get(class_name, []):
        if method_name.startswith(name):
            yield method_name, method


def _is_renamed(method_name: str, name: str) -> bool:
    suffix = method_name[len(name) :]
    if suffix.startswith("-"):
        return True
    rest = suffix[1:]
    return suffix.startswith("$") and rest != "default" and "$" not in rest and "-" not in rest


def _own_method(classes, function: Function):
    """The class and JaCoCo method for `function`, nearest line first."""

    exact, renamed = [], []
    for class_name in _candidate_classes(function):
        for method_name, method in _methods_named(classes, class_name, function.name):
            if method_name == function.name:
                exact.append((class_name, method))
            elif _is_renamed(method_name, function.name):
                renamed.append((class_name, method))
    pool = exact or renamed
    if not pool:
        return None
    return min(pool, key=lambda found: abs(found[1].line - function.start_line))


def _lambdas(classes, class_name: str, function: Function):
    for method_name, method in _methods_named(classes, class_name, function.name):
        suffix = method_name[len(function.name) :]
        if suffix.startswith(_LAMBDA_MARKERS) and (
            function.start_line <= method.line <= function.end_line
        ):
            yield method
    for method in classes.lambda_classes.get((class_name, function.name), []):
        if function.start_line <= method.line <= function.end_line:
            yield method


def kotlin_percent(classes, function: Function) -> float | None:
    """Coverage of `function` from a `by_class` index, or None when JaCoCo has no method."""

    found = _own_method(classes, function)
    if found is None:
        return None
    class_name, method = found
    methods = [method, *_lambdas(classes, class_name, function)]
    covered = sum(each.covered for each in methods)
    total = sum(each.covered + each.missed for each in methods)
    return 100.0 * covered / total if total > 0 else 0.0
