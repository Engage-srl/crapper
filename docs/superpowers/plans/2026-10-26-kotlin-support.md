# crapper — Kotlin (Maven) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `crapper` riconosce i sorgenti `.kt`, ne calcola complessità e coverage JaCoCo, e li riporta in tabella e in `.metrics/crap.edn` come fa per Java.

**Architecture:** Un modulo nuovo `languages/kotlin.py` (tree-sitter, sul modello di `languages/java.py`) e un modulo nuovo `kotlin_coverage.py` per il lookup JaCoCo specifico di Kotlin (lambda, mangling, `DefaultImpls`). I file upstream esistenti ricevono solo righe di aggancio.

**Tech Stack:** Python ≥ 3.11, `tree-sitter`, `tree-sitter-language-pack` (grammatica `kotlin`, v1.22.1 verificata), pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-kotlin-support-design.md`

## Global Constraints

- Nessuna nuova dipendenza in `pyproject.toml`.
- Codice Kotlin in file nuovi; nei file upstream solo righe di aggancio (registri, `if language in ...`, help). Nessun test esistente modificato, salvo aggiunta di casi.
- Ogni funzione nuova con `CRAP < 10` (verificato nel Task 6 lanciando `crapper` su sé stesso).
- `language="kotlin"` è la stringa del linguaggio ovunque.
- Ambiente: `.venv/bin/pytest`. Baseline: 145 pass, 1 fail preesistente (`tests/test_cli.py::test_project_snapshot_is_readable_as_crap4clj_edn`, manca `bb` sulla macchina). Quel fail non va toccato né contato come regressione.

## Nodi tree-sitter Kotlin (verificati)

| Concetto | Nodo |
|---|---|
| package | `package_header` → `identifier` (testo `a.b.c`) |
| `@file:JvmName("X")` | `file_annotation` → `constructor_invocation` (`user_type` `JvmName`) → `string_content` |
| funzione | `function_declaration`: nome `simple_identifier`, corpo `function_body` (assente se astratta), `modifiers`/`function_modifier` `inline` |
| tipi con nome | `class_declaration` (class/interface/enum, nome `type_identifier`), `object_declaration`, `companion_object` (`type_identifier` opzionale) |
| tipo anonimo | `object_literal` (membri in `class_body`) |
| getter/setter | `property_declaration` → `getter`/`setter` con `function_body`; nome proprietà in `variable_declaration` → `simple_identifier` |
| lambda | `lambda_literal` |
| decisioni | `if_expression`, `when_entry` (escluso quello con figlio token `else`), `for_statement`, `while_statement`, `do_while_statement`, `catch_block`, `elvis_expression`, figli token `&&` di `conjunction_expression` e `\|\|` di `disjunction_expression` |

Nota: `interface` è un `class_declaration`; distinguerla dal token figlio `interface`.

## Nomi JaCoCo osservati in eARTS

`pkg/FileKt` (top-level), `Outer$Companion`, `Iface$DefaultImpls`, metodi `name$lambda$0`, `name$lambda$0$lambda$1`, `name$default` (non filtrati da JaCoCo), `name$<modulo>` per `internal` (es. `$mySDK_ui`, `$gateway`), `name$<locale>` per funzioni locali.

## Review Focus

1. File Kotlin senza `package` → namespace solo classe/`FileKt`, nessun crash. (Task 1)
2. Funzione con corpo espressione `fun f() = x ?: 0` → riconosciuta, complessità 2. (Task 1)
3. Overload con lo stesso nome nella stessa classe → coverage scelta per riga più vicina, lambda attribuite alla funzione giusta. (Task 3)
4. Funzione `internal` (`name$modulo`) con anche `name$default` e `name$lambda$0` nella stessa classe → il fallback sceglie `name$modulo`. (Task 3)
5. Progetto misto `.java` + `.kt` nello stesso modulo Maven → Maven lanciato una sola volta. (Task 4)

---

### Task 1: Estrazione funzioni e complessità Kotlin

**Files:**
- Create: `src/crapper/languages/kotlin.py`
- Create: `tests/test_kotlin.py`

**Interfaces:**
- Consumes: helper di `crapper.languages.treesitter` (`parse`, `node_text`, `child_of_type`, `complexity`, `start_line`, `end_line`); `crapper.model.Function`.
- Produces: `functions_in_source(source: str, path: str, project_root: str | None = None) -> list[Function]`, con `language="kotlin"`, `namespace` e `jacoco_class` secondo la tabella della spec (`pkg.Foo.Inner` / `pkg.Foo$Inner`, `pkg.Foo.Companion` / `pkg.Foo$Companion`, `pkg.BarKt` / `pkg.BarKt`, `pkg.X` / `pkg.X` con `@file:JvmName("X")`). Le funzioni dichiarate in un'`interface` portano `jacoco_class="pkg.I"`; il fallback `$DefaultImpls` è nel Task 3. Il nome file per `FileKt` è `Path(path).stem`. `start_byte`/`end_byte` valorizzati (mutator li userà).

- [ ] **Step 1: Write the failing tests** in `tests/test_kotlin.py` (sorgenti multilinea, formattazione realistica: la grammatica sbaglia su `object`/`enum` compressi su una riga)

```python
def test_counts_kotlin_decisions():
    # fun score(a: Boolean, b: Boolean, v: Int?, xs: List<Int>): Int con:
    # if (a && b || a) {} else if (b) {}            -> if, &&, ||, if = 4
    # when (v) { 1, 2 -> {} \n 3 -> {} \n else -> {} } -> 2 rami
    # for, while, do-while, try/catch/finally        -> 4
    # val n = v ?: 0                                 -> 1
    # v?.let { it!! }                                -> 0
    # xs.map { if (it > 0) 1 else 2 }                -> 1 (lambda inclusa)
    assert [(f.name, f.complexity) for f in functions_in_source(SCORE, "Sample.kt")] == [("score", 13)]

def test_expression_body_function():
    src = "package a\n\nfun pick(x: Int?): Int = x ?: 0\n"
    [f] = functions_in_source(src, "src/a/Pick.kt")
    assert (f.namespace, f.name, f.complexity, f.jacoco_class) == ("a.PickKt", "pick", 2, "a.PickKt")

def test_names_classes_objects_and_companions():
    # package demo.pkg; class Board { fun place(); class Inner { fun tick() }; companion object { fun make() } }
    # object Registry { fun find() }; interface Shape { fun area(): Int { return 1 } ; fun abstractOne() }
    # fun String.shout() = uppercase()   (file Board.kt)
    assert [(f.namespace, f.name, f.jacoco_class) for f in found] == [
        ("demo.pkg.Board", "place", "demo.pkg.Board"),
        ("demo.pkg.Board.Inner", "tick", "demo.pkg.Board$Inner"),
        ("demo.pkg.Board.Companion", "make", "demo.pkg.Board$Companion"),
        ("demo.pkg.Registry", "find", "demo.pkg.Registry"),
        ("demo.pkg.Shape", "area", "demo.pkg.Shape"),
        ("demo.pkg.BoardKt", "shout", "demo.pkg.BoardKt"),
    ]

def test_named_companion_and_file_jvm_name():
    # @file:JvmName("Utils") + package a; fun top() {}; class C { companion object Factory { fun of() {} } }
    assert [(f.namespace, f.name, f.jacoco_class) for f in found] == [
        ("a.Utils", "top", "a.Utils"),
        ("a.C.Factory", "of", "a.C$Factory"),
    ]

def test_custom_accessors_are_functions():
    # class Box { val size: Int get() { return if (full) 1 else 0 } ; var label: String = "" set(value) { field = value } ; val plain = 1 }
    assert [(f.name, f.complexity) for f in found] == [("getSize", 2), ("setLabel", 1)]

def test_excluded_declarations():
    # init { if }, constructor(), abstract fun, inline fun, fun local() dentro outer,
    # val o = object : Runnable { override fun run() { if (x) {} } } dentro outer
    assert [(f.name, f.complexity) for f in found] == [("outer", 2)]  # if del local conta, run no

def test_no_package_and_keywords_in_strings():
    # niente package; fun stable(): String { val s = "if && || ?: when"; // if && ||
    #   return s }   in Stable.kt
    assert [(f.namespace, f.name, f.complexity) for f in found] == [("StableKt", "stable", 1)]
```

Le sorgenti complete vanno scritte nei test; i commenti sopra fissano il contenuto e i valori attesi. In `test_excluded_declarations` `fun local()` contiene un `if` (conta in `outer`, 1+1=2), `run()` dentro `object_literal` contiene un `if` (non conta).

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_kotlin.py -v` — Expected: FAIL `ModuleNotFoundError: crapper.languages.kotlin`.

- [ ] **Step 3: Implement `functions_in_source` in `src/crapper/languages/kotlin.py`**, sul modello di `java.py` (walk iterativo con stack, docstring di modulo). Regole:
  - entry: `function_declaration` con `function_body`, non `inline`, non dentro un'altra funzione/getter/setter/lambda/`object_literal`/`anonymous_initializer`; `getter`/`setter` con `function_body` → `get`/`set` + nome proprietà con iniziale maiuscola.
  - catena di tipi: antenati `class_declaration`/`object_declaration` (nome `type_identifier`) e `companion_object` (nome `type_identifier` o `"Companion"`); nessun tipo → `<stem>Kt` o il `JvmName`.
  - `complexity(node, _is_decision, _skip)` con `_skip` = `class_declaration`, `object_declaration`, `companion_object`, `object_literal`. Le funzioni locali e le lambda NON sono saltate.
  - `&&`/`||`: +1 per ogni token figlio nei nodi `conjunction_expression`/`disjunction_expression` (non per nodo).
  - package da `package_header`, non con regex.

- [ ] **Step 4: Run** `.venv/bin/pytest tests/test_kotlin.py -v` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crapper/languages/kotlin.py tests/test_kotlin.py
git commit -m "Add Kotlin function extraction and complexity"
```

### Task 2: Aggancio discovery e registro linguaggi

**Files:**
- Modify: `src/crapper/discover.py` (`EXTENSIONS`, `SKIP_DIRS`)
- Modify: `src/crapper/languages/__init__.py` (`_READERS`)
- Test: `tests/test_languages.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `kotlin.functions_in_source` (Task 1).
- Produces: `language_of("X.kt") == "kotlin"`, `language_of("build.gradle.kts") is None`; `functions_in_file("kotlin", ...)`; directory `.claude` saltata.

- [ ] **Step 1: Write failing tests**: aggiungi a `_SOURCES` in `tests/test_languages.py` la tupla `("kotlin", "package a\n\nfun place() {\n    if (true) return\n}\n", "src/a/Board.kt", "place")`; in `tests/test_cli.py` aggiungi `test_kotlin_files_are_detected` (`language_of("Board.kt") == "kotlin"`, `language_of("build.gradle.kts") is None`) e `test_claude_worktrees_are_skipped` (un `.kt` sotto `tmp_path/.claude/worktrees/x/src/A.kt` e uno sotto `tmp_path/src/B.kt`; `iter_source_files([tmp_path])` restituisce solo `B.kt`).
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_languages.py tests/test_cli.py -v` — Expected: i 3 nuovi FAIL.
- [ ] **Step 3: Implement**: `".kt": "kotlin"` in `EXTENSIONS`; `".claude"` in `SKIP_DIRS`; `"kotlin": kotlin_functions` in `_READERS`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: tutti PASS tranne il fail baseline `bb`.
- [ ] **Step 5: Commit** `git commit -m "Detect Kotlin sources and skip .claude"`.

### Task 3: Coverage JaCoCo per Kotlin

**Files:**
- Create: `src/crapper/kotlin_coverage.py`
- Modify: `src/crapper/coverage.py` (solo `CoverageBundle.percent_for`: delega per `kotlin`)
- Test: `tests/test_kotlin_coverage.py`

**Interfaces:**
- Consumes: `JacocoMethod`, `coverage_percent`, l'indice `dict[str, list[JacocoMethod]]` con chiavi `"binary.class#method"` (già esistente).
- Produces: `kotlin_percent(index: dict[str, list[JacocoMethod]], function: Function) -> float | None` in `kotlin_coverage.py`. `percent_for` chiama `kotlin_percent(self.jacoco or {}, function)` quando `function.language == "kotlin"`.

Algoritmo (non determinato dai test, va seguito):
1. Classi candidate: `function.jacoco_class`, poi `function.jacoco_class + "$DefaultImpls"`, poi `function.namespace` se diverso.
2. Metodo principale: tra le classi candidate, metodi con nome esatto `function.name`; se nessuno, metodi `name$<suffisso>` con `<suffisso>` senza `$`/`-` e diverso da `default` (mangling `internal`). Poi metodi `name-<hash>` (value class). Scegli quello con `line` più vicina a `function.start_line`. Nessuno → `None`.
3. Lambda: nella classe del metodo scelto, metodi il cui nome inizia con `name$lambda$` o `name$lambda-`, con `line` tra `function.start_line` e `function.end_line`. Il filtro per righe risolve overload e ambiguità.
4. Coverage = `coverage_percent(Σcovered, Σ(missed+covered))` su metodo principale + lambda.

Le chiavi `f"{class_name}#{method}"` già prodotte da `parse_jacoco_index` bastano: si scorrono quelle con prefisso `f"{class_name}#{name}"`. `parse_jacoco_index` non va modificato.

- [ ] **Step 1: Write failing tests** in `tests/test_kotlin_coverage.py`, con XML JaCoCo minimale scritto nel test (stessa forma di `tests/test_coverage.py::test_jacoco_instruction_coverage_joins_on_class_and_method`):
  - `test_lambdas_add_to_their_function`: `demo/Board#place` line 10 missed 0 covered 10; `place$lambda$0` line 12 missed 10 covered 0; `Function(name="place", start_line=10, end_line=15, jacoco_class="demo.Board", language="kotlin", ...)` → `50.0`.
  - `test_lambda_outside_the_function_lines_is_ignored`: overload `place` line 10 (fine 15) e `place` line 20 (fine 25), lambda `place$lambda$0` line 22 missed 10; la funzione a riga 10 resta `100.0`.
  - `test_top_level_function_uses_the_file_class`: classe `demo/BoardKt`, `jacoco_class="demo.BoardKt"` → percentuale del metodo.
  - `test_interface_body_lives_in_default_impls`: classe `demo/Shape$DefaultImpls`, metodo `area`; `jacoco_class="demo.Shape"` → trovata.
  - `test_internal_mangling_beats_default_and_lambda`: metodi `find$default` line 5 (0%), `find$lambda$0` line 7 (in range, 100%, 4 istr.), `find$mySDK_ui` line 5 (100%, 4 istr.), nessun `find` esatto → `100.0` (mangled + lambda), `find$default` escluso.
  - `test_missing_class_is_none`: → `None`.
  - In `tests/test_coverage.py`: `test_bundle_routes_kotlin_to_kotlin_lookup`: `CoverageBundle(jacoco=parse_jacoco_index(xml)).percent_for(kotlin_function)` restituisce lo stesso valore di `kotlin_percent`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_kotlin_coverage.py tests/test_coverage.py -v` — Expected: nuovi FAIL.
- [ ] **Step 3: Implement** `kotlin_percent` e il ramo `if function.language == "kotlin": return kotlin_percent(self.jacoco or {}, function)` in `percent_for` (prima del ramo `java`).
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS (salvo baseline `bb`).
- [ ] **Step 5: Commit** `git commit -m "Join Kotlin functions to JaCoCo coverage with their lambdas"`.

### Task 4: Runner Maven anche per Kotlin

**Files:**
- Modify: `src/crapper/runners.py` (`_cover_java`, `run_coverage`)
- Test: `tests/test_runners.py`

**Interfaces:**
- Produces: `run_coverage` lancia il runner Maven se `"java"` o `"kotlin"` sono tra i linguaggi; `_cover_java` raccoglie i moduli dal `pom.xml` più vicino a file `.java` **e** `.kt`, deduplicati (un `mvn` per modulo). Messaggi di warning invariati per Java.

- [ ] **Step 1: Write failing tests**:
  - `test_kotlin_only_module_runs_maven`: `pom.xml` + `src/main/kotlin/Board.kt`; `run_coverage(tmp_path, [kt], None)` → un comando che inizia con `mvn`.
  - `test_mixed_module_runs_maven_once`: `pom.xml` + un `.java` + un `.kt` nello stesso modulo → esattamente un comando `mvn`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_runners.py -v` — Expected: nuovi FAIL.
- [ ] **Step 3: Implement** con il diff più piccolo: `_modules_with` accetta una tupla di suffissi (o `_cover_java` unisce due chiamate in un `set`), e `run_coverage` usa `if languages & {"java", "kotlin"}:`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS (salvo baseline `bb`).
- [ ] **Step 5: Commit** `git commit -m "Run Maven JaCoCo coverage for Kotlin modules"`.

### Task 5: Help, README, descrizione

**Files:**
- Modify: `src/crapper/cli.py` (`HELP`), `README.md`, `pyproject.toml` (`description`)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test** `test_help_mentions_kotlin`: `"Kotlin (.kt)" in HELP`; `"package.FileKt" in HELP`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**: in `HELP` aggiungi `Kotlin (.kt)` alle lingue; riga coverage `Kotlin       Maven JaCoCo, as Java; lambdas count toward their function`; riga namespace `Kotlin       package.Class, or package.FileKt for top-level functions`. In `README.md` una sezione "Kotlin" con: cosa conta come decisione, funzioni escluse (inline, costruttori, init, locali, anonimi), namespace, flusso consigliato per multi-modulo (`crapper --coverage-command "mvn -q test"` o `--use-existing-coverage`). Aggiorna `description` in `pyproject.toml` aggiungendo Kotlin.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS (salvo baseline `bb`).
- [ ] **Step 5: Commit** `git commit -m "Document Kotlin support"`.

### Task 6: Verifica su eARTS e CRAP del codice nuovo

Nessun file di prodotto; solo verifica. Non modificare eARTS.

- [ ] **Step 1:** `cd ~/sviluppo/crapper && ./crapper --threshold 10 src/crapper/languages/kotlin.py src/crapper/kotlin_coverage.py` (coverage Python via pytest, generata dal tool stesso) — Expected: exit 0, ogni riga `CRAP < 10`. Se no, spezzare la funzione o aggiungere test, ripetere, commit `Bring Kotlin code under CRAP 10`.
- [ ] **Step 2:** In eARTS, con i `jacoco.xml` già presenti in `*/target/site/jacoco/`: `cd ~/sviluppo/Artemis/eARTS && ~/sviluppo/crapper/crapper --use-existing-coverage | head -40` — Expected: righe con namespace Kotlin (es. `gsdk....Kt`), complessità, coverage non tutta `0.0`, CRAP; nessuna riga da `.claude/`; `.metrics/crap.edn` scritto.
- [ ] **Step 3:** `git -C ~/sviluppo/Artemis/eARTS status --short .metrics` — riportare all'utente che `.metrics/` è stato creato in eARTS (non committarlo lì).
- [ ] **Step 4:** riportare in chat: numero funzioni Kotlin trovate, % con coverage > 0, le 10 peggiori.
