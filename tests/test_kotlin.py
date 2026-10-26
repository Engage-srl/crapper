from crapper.languages.kotlin import functions_in_source

SCORE = """
package demo

class Sample {
    fun score(a: Boolean, b: Boolean, v: Int?, xs: List<Int>): Int {
        if (a && b || a) {
        } else if (b) {
        }
        when (v) {
            1, 2 -> {}
            3 -> {}
            else -> {}
        }
        for (x in xs) {
        }
        while (a) {
        }
        do {
        } while (b)
        try {
        } catch (e: Exception) {
        } finally {
        }
        val n = v ?: 0
        v?.let { it!! }
        xs.map { if (it > 0) 1 else 2 }
        return n
    }
}
"""

NAMES = """
package demo.pkg

class Board {
    fun place() {
    }

    class Inner {
        fun tick() {
        }
    }

    companion object {
        fun make() {
        }
    }
}

object Registry {
    fun find() {
    }
}

interface Shape {
    fun area(): Int {
        return 1
    }

    fun abstractOne()
}

fun String.shout() = uppercase()
"""

JVM_NAME = """
@file:JvmName("Utils")

package a

fun top() {
}

class C {
    companion object Factory {
        fun of() {
        }
    }
}
"""

ACCESSORS = """
package a

class Box(val full: Boolean) {
    val size: Int
        get() {
            return if (full) 1 else 0
        }

    var label: String = ""
        set(value) {
            field = value
        }

    val plain = 1
}
"""

EXCLUDED = """
package a

abstract class Holder(val x: Boolean) {
    init {
        if (x) {
        }
    }

    constructor() : this(true)

    abstract fun abs()

    inline fun <reified T> inl() {
        if (x) {
        }
    }

    fun outer() {
        fun local() {
            if (x) {
            }
        }
        val o = object : Runnable {
            override fun run() {
                if (x) {
                }
            }
        }
        local()
    }
}
"""

STABLE = """
fun stable(): String {
    val s = "if && || ?: when"
    // if && || ?: when
    /* if && || */
    return s
}
"""


def _rows(found, *fields):
    return [tuple(getattr(function, field) for field in fields) for function in found]


def test_counts_kotlin_decisions():
    found = functions_in_source(SCORE, "Sample.kt")
    assert _rows(found, "name", "complexity") == [("score", 13)]


def test_expression_body_function():
    source = "package a\n\nfun pick(x: Int?): Int = x ?: 0\n"
    [function] = functions_in_source(source, "src/a/Pick.kt")
    assert (function.namespace, function.name, function.complexity, function.jacoco_class) == (
        "a.PickKt",
        "pick",
        2,
        "a.PickKt",
    )
    assert function.language == "kotlin"
    assert function.start_byte < function.end_byte


def test_names_classes_objects_and_companions():
    found = functions_in_source(NAMES, "src/demo/pkg/Board.kt")
    assert _rows(found, "namespace", "name", "jacoco_class") == [
        ("demo.pkg.Board", "place", "demo.pkg.Board"),
        ("demo.pkg.Board.Inner", "tick", "demo.pkg.Board$Inner"),
        ("demo.pkg.Board.Companion", "make", "demo.pkg.Board$Companion"),
        ("demo.pkg.Registry", "find", "demo.pkg.Registry"),
        ("demo.pkg.Shape", "area", "demo.pkg.Shape"),
        ("demo.pkg.BoardKt", "shout", "demo.pkg.BoardKt"),
    ]


def test_named_companion_and_file_jvm_name():
    found = functions_in_source(JVM_NAME, "src/a/Top.kt")
    assert _rows(found, "namespace", "name", "jacoco_class") == [
        ("a.Utils", "top", "a.Utils"),
        ("a.C.Factory", "of", "a.C$Factory"),
    ]


def test_custom_accessors_are_functions():
    found = functions_in_source(ACCESSORS, "src/a/Box.kt")
    assert _rows(found, "name", "complexity") == [("getSize", 2), ("setLabel", 1)]


def test_excluded_declarations():
    found = functions_in_source(EXCLUDED, "src/a/Holder.kt")
    assert _rows(found, "name", "complexity") == [("outer", 2)]


def test_no_package_and_keywords_in_strings():
    found = functions_in_source(STABLE, "Stable.kt")
    assert _rows(found, "namespace", "name", "complexity") == [("StableKt", "stable", 1)]


def test_each_chained_operator_is_a_decision():
    source = "fun g(a: Boolean, b: Boolean, c: Boolean) {\n    if (a && b && c || a || b) {\n    }\n}\n"
    assert _rows(functions_in_source(source, "G.kt"), "name", "complexity") == [("g", 6)]
