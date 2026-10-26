from crapper.coverage import CoverageBundle, parse_jacoco_index
from crapper.kotlin_coverage import by_class, kotlin_percent
from crapper.model import Function


def jacoco_xml(classes: dict[str, list[tuple[str, int, int, int]]]) -> str:
    """`{class: [(method, line, missed, covered)]}` as JaCoCo XML."""

    parts = ["<report><package>"]
    for class_name, methods in classes.items():
        parts.append(f'<class name="{class_name}">')
        for method, line, missed, covered in methods:
            parts.append(
                f'<method name="{method}" line="{line}">'
                f'<counter type="INSTRUCTION" missed="{missed}" covered="{covered}"/>'
                "</method>"
            )
        parts.append("</class>")
    parts.append("</package></report>")
    return "".join(parts)


def jacoco(classes):
    return by_class(parse_jacoco_index(jacoco_xml(classes)))


def kotlin(name, start_line, end_line, jacoco_class="demo.Board", namespace=None):
    return Function(
        name=name,
        namespace=namespace or jacoco_class.replace("$", "."),
        complexity=1,
        start_line=start_line,
        end_line=end_line,
        path="src/demo/Board.kt",
        language="kotlin",
        jacoco_class=jacoco_class,
    )


def test_lambdas_add_to_their_function():
    index = jacoco(
        {"demo/Board": [("place", 10, 0, 10), ("place$lambda$0", 12, 10, 0)]}
    )
    assert kotlin_percent(index, kotlin("place", 10, 15)) == 50.0


def test_nested_lambdas_add_to_their_function():
    index = jacoco(
        {
            "demo/Board": [
                ("place", 10, 0, 2),
                ("place$lambda$0", 11, 0, 2),
                ("place$lambda$0$lambda$1", 12, 4, 0),
            ]
        }
    )
    assert kotlin_percent(index, kotlin("place", 10, 15)) == 50.0


def test_lambda_outside_the_function_lines_is_ignored():
    index = jacoco(
        {
            "demo/Board": [
                ("place", 10, 0, 4),
                ("place", 20, 0, 4),
                ("place$lambda$0", 22, 10, 0),
            ]
        }
    )
    assert kotlin_percent(index, kotlin("place", 10, 15)) == 100.0
    assert kotlin_percent(index, kotlin("place", 20, 25)) == 100.0 * 4 / 14


def test_top_level_function_uses_the_file_class():
    index = jacoco({"demo/BoardKt": [("shout", 3, 1, 3)]})
    function = kotlin("shout", 3, 3, jacoco_class="demo.BoardKt")
    assert kotlin_percent(index, function) == 75.0


def test_interface_body_lives_in_default_impls():
    index = jacoco({"demo/Shape$DefaultImpls": [("area", 4, 0, 2)]})
    function = kotlin("area", 4, 6, jacoco_class="demo.Shape")
    assert kotlin_percent(index, function) == 100.0


def test_internal_mangling_beats_default_and_lambda():
    index = jacoco(
        {
            "demo/Board": [
                ("find$default", 5, 4, 0),
                ("find$lambda$0", 7, 0, 4),
                ("find$mySDK_ui", 5, 0, 4),
            ]
        }
    )
    assert kotlin_percent(index, kotlin("find", 5, 9)) == 100.0


def test_value_class_mangling_is_found():
    index = jacoco({"demo/Board": [("move-abc123", 5, 1, 1)]})
    assert kotlin_percent(index, kotlin("move", 5, 6)) == 50.0


def test_missing_class_is_none():
    index = jacoco({"demo/Other": [("place", 10, 0, 1)]})
    assert kotlin_percent(index, kotlin("place", 10, 15)) is None


def test_bundle_routes_kotlin_to_kotlin_lookup():
    xml = jacoco_xml(
        {"demo/Board": [("place", 10, 0, 10), ("place$lambda$0", 12, 10, 0)]}
    )
    bundle = CoverageBundle(jacoco=parse_jacoco_index(xml))
    assert bundle.percent_for(kotlin("place", 10, 15)) == 50.0
