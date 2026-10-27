# crapper — Dart/Flutter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `crapper` legge i sorgenti `.dart`, calcola complessità e coverage LCOV per funzione e produce la tabella CRAP come per le altre lingue.

**Architecture:** Modulo nuovo `languages/dart.py` (entry, nomi, namespace, complessità) e `dart_coverage.py` (comando di test per package e riscrittura `SF:`); righe di aggancio in `discover.py`, `languages/__init__.py`, `runners.py`, `coverage.py`, `cli.py`.

**Tech Stack:** Python ≥ 3.11, `tree-sitter-language-pack` (grammatica `dart`), pytest; `flutter test` / `dart test` per la coverage.

**Spec:** `docs/superpowers/specs/2026-10-27-dart-support-design.md`.

## Global Constraints

- Fork allineabile con upstream: logica nuova in moduli nuovi, righe di aggancio nei file esistenti, nessun test esistente modificato.
- `language="dart"`; estensione `.dart`; generati (`.g.dart .freezed.dart .mocks.dart .gr.dart .config.dart .pb.dart .pbenum.dart .pbjson.dart .pbserver.dart`) ignorati; `.dart_tool` saltata; `integration_test`, `test_driver` e `*_test.dart` sono test.
- Entry, nomi, namespace e complessità esattamente come nello spec.
- Ogni funzione nuova/modificata `CRAP < 10`.
- Baseline: `.venv/bin/pytest -q` → 173 passed, 1 failed (pre-esistente `test_project_snapshot_is_readable_as_crap4clj_edn`, richiede `bb`).

## Review Focus

1. Firma e corpo fratelli: un'annotazione o un commento tra `method_signature` e `function_body` non deve perdere l'entry. (Task 1)
2. Funzione con parse error nel file: niente crash, entry dopo l'errore mantenute se il parser le recupera. (Task 1)
3. Due package con `lib/src/a.dart` e coverage `flutter` relativa: ognuno prende le proprie righe. (Task 2)
4. Package Flutter senza `flutter` nel PATH: avviso chiaro, coverage 0%, nessun crash. (Task 2)
5. Getter/setter con stesso nome nella stessa classe: due entry distinte (`size`, `size=`). (Task 1)

---

### Task 1: Funzioni Dart

**Files:**
- Create: `src/crapper/languages/dart.py`
- Modify: `src/crapper/languages/__init__.py` (`"dart": dart_functions`), `src/crapper/discover.py` (`.dart`, generati, `.dart_tool`, cartelle e suffissi di test)
- Test: `tests/test_dart.py`

**Interfaces:**
- Produces: `functions_in_source(source: str, path: str, project_root: str | None = None) -> list[Function]`, `language="dart"`, `namespace` come da spec, `jacoco_class=None`.

- [ ] **Step 1: Write failing tests** (`tests/test_dart.py`, sorgenti multilinea, `pubspec.yaml` con `name: demo` in `tmp_path`, file in `lib/src/board.dart`):
  - `test_dart_entries_and_names`: top-level `top`, `arrow` (`=>`), classe `Board` con costruttore generativo con corpo (escluso), `factory Board.fromJson(...)` (`fromJson`), getter `size`, setter `size=`, `operator +`, metodo `static s`, metodo astratto in classe astratta (escluso), `external` (escluso), mixin `M.m`, extension `E.shout`, enum `Color.hex` → nomi e namespace esatti (`demo.src.board`, `demo.src.board.Board`, `demo.src.board.M`, `demo.src.board.E`, `demo.src.board.Color`).
  - `test_dart_local_functions_and_closures_stay_inside`: `int s() { var f = (int y) => y > 0 ? 1 : 2; int local() { return 1; } return f(1); }` → un'entry `s`, complessità 2.
  - `test_dart_complexity_counts_each_decision`: una funzione con `if`, `for`, `while`, `do`, `catch`, `?:`, `switch` con 2 `case` + `default`, `switch` expression con 2 arm, `a && b && c`, `a || b`, `x ?? y`, `s?.length`, `[if (ok) 1, for (var x in xs) x]` → valore esatto calcolato a mano.
  - `test_dart_span_starts_at_the_signature`: `@override` su riga propria, firma riga 3, corpo fino a riga 5 → `(3, 5)`; con commento tra firma e corpo l'entry resta.
  - `test_dart_namespace_without_lib`: `bin/tool.dart` → `demo.bin.tool`; senza `pubspec.yaml` → percorso relativo alla root.
  - `test_dart_detection`: `language_of("a.dart") == "dart"`, `a.g.dart` / `a.freezed.dart` → `None`; `is_test_file("lib/a_test.dart")`, `integration_test/x.dart` → `True`; `.dart_tool/` saltata.
  - `test_dart_broken_source_does_not_raise`.
- [ ] **Step 2: Run** `.venv/bin/pytest -q tests/test_dart.py` — Expected: FAIL (lingua sconosciuta).
- [ ] **Step 3: Implement** `languages/dart.py`: walk dei nodi firma (`function_signature` non dentro `method_signature`, e `method_signature`); corpo = prossimo fratello con nome che sia `function_body` (saltando `comment`/`annotation`); escludere firme dentro `function_body`/`function_expression`; nome/namespace/complessità da spec (decisioni come nodi o token; `&&`/`||` contati per operatore). Namespace: `pubspec.yaml` più vicino (`name:` letto con regex, niente dipendenza YAML).
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: tutti PASS tranne il pre-esistente.
- [ ] **Step 5: Commit** `Read Dart functions`.

### Task 2: Coverage Dart

**Files:**
- Create: `src/crapper/dart_coverage.py`
- Modify: `src/crapper/runners.py` (`_cover_dart`, aggancio in `run_coverage`), `src/crapper/coverage.py` (letture `<package>/coverage/lcov.info` con riscrittura `SF:`)
- Test: `tests/test_dart_coverage.py`

**Interfaces:**
- Consumes: `functions_in_source` del Task 1; `_modules_with(files, ".dart", "pubspec.yaml", root)`, `_coverage_report(root, package, "dart")`.
- Produces: `dart_command(package: Path, report: Path) -> list[str]` (`flutter test --coverage --coverage-path <report>` se `pubspec.yaml` dipende da `flutter: sdk: flutter`, altrimenti `dart test --coverage-path <report>`); `absolute_sources(text: str, package: Path) -> str` (`SF:` relativi resi assoluti).

- [ ] **Step 1: Write failing tests:**
  - `test_dart_command_for_flutter_and_plain_packages` (due `pubspec.yaml`).
  - `test_relative_sources_become_absolute` (`SF:lib/a.dart` → `SF:<package>/lib/a.dart`; `SF:/abs/x.dart` invariato).
  - `test_two_packages_with_the_same_relative_file` (Review Focus 3): due package con `coverage/lcov.info` relativi, `--use-existing-coverage` → coverage diversa per le due funzioni omonime.
  - `test_missing_flutter_warns_and_continues` (Review Focus 4): `shutil.which` assente → avviso, nessuna eccezione.
  - `test_cli_reports_dart_functions_with_coverage`: progetto `tmp_path` con LCOV pronto, `crapper --use-existing-coverage` → riga con nome, namespace, CC, coverage, CRAP.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; dopo ogni run riscrivere `SF:` nel report. In `coverage.py` aggiungere ai path LCOV `**/coverage/lcov.info` dei package con `pubspec.yaml`, letti con `absolute_sources`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS (tranne il pre-esistente).
- [ ] **Step 5: Commit** `Run and read Dart coverage`.

### Task 3: Documentazione e verifica

- [ ] **Step 1:** HELP (`Dart (.dart)`), README (sezione Dart: entry, comandi di coverage, generati esclusi, workspace con più package), description in `pyproject.toml`; test `test_help_mentions_dart`. Commit `Document Dart support`.
- [ ] **Step 2:** `crapper --threshold 10` sui file toccati — Expected: exit 0.
- [ ] **Step 3:** su `~/sviluppo/gap_fleet`, `crapper --no-coverage packages/gap_core` e poi su un package puro Dart (se c'è) con coverage `dart test`. Riportare: numero di funzioni, file con parse error, tempi, e cosa serve per i package Flutter (flutter non eseguibile qui, vedi spec).
- [ ] **Step 4:** `CLOSE=1` sull'ultimo commit.
