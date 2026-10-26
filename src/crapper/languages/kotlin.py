"""Kotlin functions and cyclomatic complexity, in the spirit of crap4java.

Functions are `fun` declarations in classes, interfaces, objects, companion
objects, and at the top level of a file, plus custom property accessors.
Abstract functions, `inline` functions, constructors, `init` blocks, local
functions, and members of anonymous objects are not entries. Local functions
and lambdas count toward the complexity of the function that holds them.

Top-level functions live in the file's JVM class (`pkg.FileKt`, or the name
given by `@file:JvmName`). Nested types become their own namespace
(`pkg.Outer.Inner`); JaCoCo's binary name (`pkg.Outer$Inner`) is kept for
coverage lookup.
"""

import re
from pathlib import Path

from crapper.languages.treesitter import (
    child_of_type,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_NAMED_TYPES = {"class_declaration", "object_declaration", "companion_object", "enum_entry"}
_SKIPPED_TYPES = _NAMED_TYPES | {"object_literal"}
_EXECUTABLES = {
    "function_declaration",
    "getter",
    "setter",
    "lambda_literal",
    "anonymous_initializer",
    "object_literal",
}
_DECISIONS = {
    "if_expression",
    "for_statement",
    "while_statement",
    "do_while_statement",
    "catch_block",
    "elvis_expression",
}
_IS_PROPERTY = re.compile(r"is[^a-z]")
_LOGIC = {"conjunction_expression": "&&", "disjunction_expression": "||"}


def _decision_count(node) -> int:
    if node.type in _DECISIONS:
        return 1
    if node.type == "when_entry":
        return 0 if child_of_type(node, "else") else 1
    operator = _LOGIC.get(node.type)
    if operator:
        return sum(1 for child in node.children if child.type == operator)
    return 0


def _complexity(node) -> int:
    """McCabe complexity. Unlike `treesitter.complexity`, one node can hold
    several decisions: `a && b && c` is one node with two operators."""

    score = 1
    stack = [node]
    while stack:
        current = stack.pop()
        if _skip(current):
            continue
        score += _decision_count(current)
        stack.extend(current.children)
    return score


def _skip(node) -> bool:
    return node.type in _SKIPPED_TYPES


def _inside_executable(node) -> bool:
    current = node.parent
    while current is not None:
        if current.type in _EXECUTABLES:
            return True
        current = current.parent
    return False


def _is_inline(node) -> bool:
    modifiers = child_of_type(node, "modifiers")
    if modifiers is None:
        return False
    return any(
        child.type == "function_modifier" and child.text == b"inline"
        for child in modifiers.children
    )


def _package_name(data: bytes, root) -> str | None:
    header = child_of_type(root, "package_header")
    if header is None:
        return None
    ident = child_of_type(header, "identifier")
    return node_text(data, ident) if ident is not None else None


def _jvm_name(data: bytes, root) -> str | None:
    for annotation in root.children:
        if annotation.type != "file_annotation":
            continue
        text = node_text(data, annotation)
        if "JvmName" not in text:
            continue
        for node in _walk(annotation):
            if node.type == "string_content":
                return node_text(data, node)
    return None


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _type_name(data: bytes, node) -> str:
    ident = child_of_type(node, "type_identifier", "simple_identifier")
    if ident is not None:
        return node_text(data, ident)
    return "Companion"


def _type_chain(data: bytes, node) -> list[str]:
    names: list[str] = []
    current = node.parent
    while current is not None:
        if current.type in _NAMED_TYPES:
            names.append(_type_name(data, current))
        current = current.parent
    names.reverse()
    return names


def _owning_property(node):
    """An accessor on its own line parses as a sibling after its property."""

    if node.parent.type == "property_declaration":
        return node.parent
    current = node.prev_named_sibling
    while current is not None and current.type in {"getter", "setter"}:
        current = current.prev_named_sibling
    if current is not None and current.type == "property_declaration":
        return current
    return None


def _accessor_name(data: bytes, node) -> str | None:
    owner = _owning_property(node)
    declaration = child_of_type(owner, "variable_declaration") if owner else None
    ident = child_of_type(declaration, "simple_identifier") if declaration else None
    if ident is None:
        return None
    prop = node_text(data, ident)
    if _IS_PROPERTY.match(prop):
        return prop if node.type == "getter" else "set" + prop[2:]
    prefix = "get" if node.type == "getter" else "set"
    return prefix + prop[:1].upper() + prop[1:]


def _entry_name(data: bytes, node) -> str | None:
    if child_of_type(node, "function_body") is None or _inside_executable(node):
        return None
    if node.type in {"getter", "setter"}:
        return _accessor_name(data, node)
    if _is_inline(node):
        return None
    ident = child_of_type(node, "simple_identifier")
    return node_text(data, ident) if ident is not None else None


def _file_class(path: str) -> str:
    """kotlinc's facade class: `main.kt` is `MainKt`, `my-file.kt` is `My_fileKt`."""

    stem = re.sub(r"\W", "_", Path(path).stem)
    return f"{stem[:1].upper()}{stem[1:]}Kt"


def _qualify(package: str | None, names: list[str], nested: str) -> str:
    body = nested.join(names)
    return f"{package}.{body}" if package else body


class _File:
    def __init__(self, data: bytes, root, path: str):
        self.data = data
        self.path = path
        self.package = _package_name(data, root)
        self.file_class = _jvm_name(data, root) or _file_class(path)

    def function(self, node, name: str) -> Function:
        names = _type_chain(self.data, node) or [self.file_class]
        return Function(
            name=name,
            namespace=_qualify(self.package, names, "."),
            complexity=_complexity(node),
            start_line=start_line(node),
            end_line=end_line(node),
            path=self.path,
            language="kotlin",
            jacoco_class=_qualify(self.package, names, "$"),
            start_byte=node.start_byte,
            end_byte=node.end_byte,
        )


def functions_in_source(
    source: str, path: str, project_root: str | None = None
) -> list[Function]:
    del project_root
    data, tree = parse(source, "kotlin")
    file = _File(data, tree.root_node, path)
    found: list[Function] = []
    for node in _walk(tree.root_node):
        if node.type not in {"function_declaration", "getter", "setter"}:
            continue
        name = _entry_name(data, node)
        if name is not None:
            found.append(file.function(node, name))
    return found
