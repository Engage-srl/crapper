# Supporto Dart/Flutter per crapper, dryer e mutator — design

Data: 2026-10-27. Epic: Engage-srl/crapper#1. Segue lo spec Kotlin (`2026-10-26-kotlin-support-design.md`): stessi vincoli di fork (solo righe di aggancio nei file upstream, logica nuova in moduli nuovi, nessun test esistente modificato).

## Perché

ub-mode usato su un progetto Flutter (`~/sviluppo/gap_fleet`, pub workspace con ~20 package, ~2.400 file `.dart`) ha risposto che i tool non supportano Dart. Obiettivo: le stesse tabelle che i tool danno per Java/Kotlin (funzioni, complessità, coverage, CRAP; duplicati; mutanti), su codice Dart e Flutter.

## Non obiettivi

- Codice generato (`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, `*.gr.dart`, `*.config.dart`, `*.pb.dart`, `*.pbenum.dart`, `*.pbjson.dart`, `*.pbserver.dart`): non analizzato.
- Test (`test/`, `integration_test/`, `test_driver/`, `*_test.dart`): non analizzati come codice di produzione.
- Golden test, test d'integrazione su device, coverage web.
- Branch coverage come metrica separata (si usa se c'è, come per LCOV di altre lingue).

## Grammatica

`tree-sitter-language-pack`, grammatica `dart` (già installata con crapper). Particolarità verificate:

- Una funzione è una **coppia di fratelli**: firma (`function_signature`, oppure `method_signature` che contiene `function_signature` / `getter_signature` / `setter_signature` / `operator_signature` / `constructor_signature` / `factory_constructor_signature`) seguita da `function_body`. Senza `function_body` (astratta, `external`, dichiarazione in `declaration`) non c'è corpo.
- Classi: `class_definition` (`class_body`), `mixin_declaration` (`class_body`), `extension_declaration` (`extension_body`), `enum_declaration` (`enum_body`).
- Funzioni locali: `local_function_declaration`; closure: `function_expression`.
- Chiamate e accessi membro sono una sequenza piatta: `identifier`, poi `selector` (`unconditional_assignable_selector` `.x`, `conditional_assignable_selector` `?.x`, `argument_part` `(...)`, `!`).
- Operatori: alcuni sono foglie con nome (`additive_operator` `+`, `equality_operator` `==`, `minus_operator` `-`), altri nodi che avvolgono il token (`relational_operator` → `<=`, `logical_and_operator` → `&&`, `multiplicative_operator` → `%`, `negation_operator` → `!`).

## Cosa conta come funzione (tutti e tre i tool)

Entry = firma con corpo, fuori da altre funzioni:

- funzioni top-level, metodi di classe/mixin/extension/enum (statici inclusi), getter, setter, operatori;
- **factory constructor** con corpo (decisione mia: spesso contengono logica, es. `fromJson`); i costruttori generativi **no** (come Java e Kotlin);
- non entry: astratte/`external`, funzioni locali, closure (contano nella complessità della funzione che le contiene).

Span: dalla riga della firma (annotazioni escluse) alla fine di `function_body`.

Nomi: identificatore della funzione; getter `size`, setter `size=`, operatore `operator +`, factory `A.fromJson` → `fromJson`, factory senza nome `A` → `A`.

Namespace: modulo = `nome_package` (da `pubspec.yaml` più vicino) + percorso sotto `lib/` senza `.dart`, separato da punti (`gap_core.src.models.user`). File fuori da `lib/` (es. `bin/`): percorso relativo alla cartella del package. Senza `pubspec.yaml`: percorso relativo alla root. Membri di classe/mixin/extension/enum: `modulo.Tipo`. Extension senza nome: `modulo.extension`.

## Complessità (crapper)

1 + un punto per: `if_statement`, `if_element`, `for_statement`, `for_element`, `while_statement`, `do_statement`, `catch_clause`, `conditional_expression` (`?:`), ogni `switch_statement_case` e `switch_statement_default`, ogni `switch_expression_case`, ogni `&&` / `||`, `??` (`if_null_expression`), `?.` (`conditional_assignable_selector`). Come TypeScript in crapper.

## Coverage (crapper, poi mutator)

LCOV, già letto da crapper. Comando per package (`pubspec.yaml` più vicino ai file):

- package con dipendenza `flutter: sdk: flutter` → `flutter test --coverage --coverage-path <report>`;
- altrimenti → `dart test --coverage-path <report>`;
- `<report>` = `target/coverage/dart/<slug>/lcov.info` (già raccolto da crapper).

`dart test` scrive `SF:` assoluti; `flutter test` scrive `SF:` relativi al package (`lib/...`). Dopo il run crapper riscrive gli `SF:` relativi come assoluti, così file omonimi in package diversi non si confondono. Con `--use-existing-coverage` crapper legge anche `<package>/coverage/lcov.info` (output di default di `flutter test --coverage`), con la stessa riscrittura.

Dart marca solo le righe con codice eseguibile per la VM: `return 1;` può non avere `DA`. In crapper conta la percentuale sul range (invariato). In mutator una riga senza `DA` usa la riga di ancora (statement) come per le altre lingue.

## dryer

Picker Dart con le stesse entry. Si normalizza il `function_body`; inizio = riga della firma. Normalizzazione: in una sequenza `identifier`/`selector`, il nome seguito da `argument_part` è il nome chiamato e resta; gli altri nomi diventano `symbol`. `?.` resta nella forma. Letterali Dart (`decimal_integer_literal`, `decimal_floating_point_literal`, `string_literal` senza `template_substitution`, `true`/`false`, `null_literal`) diventano `literal`.

## mutator

Set Java scritto in Dart: `+`/`-`, `*`/`/`, `<`/`<=`, `>`/`>=`, `==`/`!=`, `&&`/`||`, rimozione di `!` (negazione) e `-` unario, `true`/`false`, `0`/`1`.

Non mutati: `??`, `?.`, `!` di null assertion (`x!`), `%`, `~/`, `is`/`as`, spread `...?`; tipi, annotazioni, testo delle stringhe (codice in `${}` sì).

Test: `flutter test` / `dart test` nel package più vicino (come sopra). Privato: nome che inizia con `_`.

## Ambiente

Su questa macchina `flutter` (puro) non parte: `~/.puro/bin/puro` è x86_64 e manca Rosetta ("Bad CPU type"). `dart` funziona direttamente da `~/.puro/envs/stable/flutter/bin/cache/dart-sdk/bin/dart`. I tool usano `flutter`/`dart` dal `PATH`; la verifica su gap_fleet userà `dart test` dove possibile e riporterà cosa serve per i package Flutter.

## Ordine

crapper (base: funzioni, namespace, coverage) → dryer → mutator, ognuno con la sua issue sotto l'epic e il suo piano.
