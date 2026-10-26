# crapper — supporto Kotlin (Maven) — design

Data: 2026-10-26
Repo: `Engage-srl/crapper` (fork di `unclebob/crapper`)

## Intento

La skill `ub-mode` impone `CRAP < 10` per ogni funzione usando `crapper`. Su
progetti Kotlin `crapper` non riconosce i sorgenti, quindi la regola non è
applicabile. Vogliamo che `crapper`, lanciato nella root di un progetto Kotlin
costruito con Maven, produca la stessa tabella e lo stesso `.metrics/crap.edn`
che produce oggi per Java.

Questo è il primo di sei interventi (crapper/dryer/mutator × Kotlin/Dart).
Le scelte fatte qui (nomi, namespace, regole di complessità) saranno riusate da
`dryer` e `mutator`, che importano i nomi di funzione da `crapper`.

## Criterio di successo

- Nella root di `~/sviluppo/Artemis/eARTS` (Maven multi-modulo, ~7.750 `.kt`,
  ~129 `.java`, JaCoCo già nel `pom.xml` radice) `crapper` stampa la tabella con
  le funzioni Kotlin: nome, namespace, complessità, coverage, CRAP, ordinata dalla
  peggiore, e scrive `.metrics/crap.edn`.
- La coverage delle funzioni Kotlin non è tutta 0%: le funzioni coperte dai test
  di eARTS mostrano la percentuale JaCoCo reale.
- La suite `pytest` del fork passa, con nuovi test Kotlin sullo stile di
  `tests/test_java.py`.

## Obiettivi

1. Riconoscere i file `.kt` come linguaggio `kotlin` (`.kts` esclusi: script di
   build, non codice di prodotto).
2. Estrarre funzioni e complessità ciclomatica dai sorgenti Kotlin con
   tree-sitter (grammatica `kotlin` di `tree-sitter-language-pack`, già
   dipendenza; verificato che si carica).
3. Collegare ogni funzione Kotlin alla sua coverage JaCoCo (contatore
   `INSTRUCTION`, come Java).
4. Generare la coverage per moduli Maven che contengono Kotlin, riusando il
   runner Maven+JaCoCo esistente.
5. Rispettare le opzioni esistenti (`--no-coverage`,
   `--use-existing-coverage`, `--coverage-command`, `--changed`, `--threshold`).

## Non-obiettivi

- Gradle (Android, Ktor, Spring Boot su Gradle). Possibile estensione futura.
- Kover come sorgente di coverage separata (Kover può emettere XML JaCoCo; se un
  giorno serve, il parser JaCoCo lo legge già).
- File `.kts`, Kotlin Multiplatform, Kotlin/JS, Kotlin/Native.
- Dart/Flutter, `dryer`, `mutator`: design separati.
- uml-viewer: deve continuare a leggere `.metrics/crap.edn`, ma non
  verifichiamo il rendering Kotlin in questo intervento.

## Anti-obiettivi

- **Divergere da upstream.** Il fork deve continuare a fare merge di
  `upstream/master` (unclebob) senza conflitti dolorosi. Il codice Kotlin vive
  in file nuovi; i file esistenti si toccano solo nei punti di aggancio
  (registri, dizionari, `if language == ...`), con modifiche di poche righe.
- **Rompere Java o gli altri linguaggi.** Nessun test esistente deve cambiare.
- **Numeri gonfiati.** Una metrica che segna rosso tutto il codice Kotlin
  idiomatico (es. contando ogni `?.`) è inutile: nessuno la guarderebbe.

## Vincoli

- Python ≥ 3.11, stesse dipendenze del progetto (nessuna nuova).
- Stile del codice coerente con i moduli esistenti (`languages/java.py` è il
  modello: walk iterativo, helper in `languages/treesitter.py`).
- Il codice nuovo deve rispettare a sua volta `CRAP < 10` (upstream lo fa:
  commit "bring CRAP under 10"). `crapper` si può lanciare su sé stesso.

## Cosa conta come funzione

- `fun` dichiarate in: `class`, `interface` (solo con corpo), `object`,
  `companion object`, `enum class`, top-level del file. Incluse le funzioni di
  estensione (`fun String.foo()`), `suspend`, `operator`, `infix`.
- Getter/setter custom di proprietà con corpo (`get() { ... }`, `get() = ...`).
  Nome: `getX` / `setX`, come in bytecode, così JaCoCo li trova.
- Funzioni con corpo espressione (`fun f() = ...`) contano come funzioni.
- **Escluse:** funzioni astratte o senza corpo, costruttori e blocchi `init`
  (coerente con crap4java che esclude i costruttori), funzioni locali dichiarate
  dentro un'altra funzione, membri di `object` anonimi (`object : Foo { ... }`),
  lambda. Le lambda contribuiscono alla complessità della funzione che le
  contiene, come in Java.
- **Escluse anche le funzioni `inline`** (decisione dell'utente). Il loro corpo
  viene copiato nei punti di chiamata, quindi JaCoCo le segna quasi sempre 0%
  anche se testate: sarebbero falsi peggiori in cima alla tabella.

## Complessità ciclomatica

`1 +` ogni occorrenza di:

- `if` (ogni `if`, incluso `else if` che è un `if` annidato; `if` usato come
  espressione incluso)
- ogni ramo di `when` tranne `else`; un ramo con più condizioni
  (`1, 2 ->`) conta una volta
- `for`, `while`, `do-while`
- `catch`
- `&&`, `||`
- elvis `?:`

**Non contano:** `?.` (safe call), `!!`, `try`/`finally`, `return`/`break`
etichettati, scope function (`let`, `apply`, ...), ternario (non esiste).

Come in Java, il conteggio non scende dentro classi annidate / `object`
annidati; scende dentro le lambda.

## Nomi e namespace

`crapper` scrive `:namespace` e `:name` in `.metrics/crap.edn`; uml-viewer,
`dryer` e `mutator` fanno join su questi.

| Dove è dichiarata | `namespace` | `jacoco_class` (lookup coverage) |
|---|---|---|
| `class Foo` / `object Foo` / `interface Foo` | `pkg.Foo` | `pkg.Foo` |
| classe annidata `Inner` in `Foo` | `pkg.Foo.Inner` | `pkg.Foo$Inner` |
| `companion object` (anonimo) in `Foo` | `pkg.Foo.Companion` | `pkg.Foo$Companion` |
| `companion object Named` in `Foo` | `pkg.Foo.Named` | `pkg.Foo$Named` |
| top-level in `Bar.kt` | `pkg.BarKt` | `pkg.BarKt` |
| top-level in file con `@file:JvmName("X")` | `pkg.X` | `pkg.X` |

*Scelta del builder (non dell'utente):* le funzioni top-level usano il nome
della classe JVM sintetica (`BarKt`), non `Bar`. Motivo: un file `Bar.kt`
contiene spesso sia `class Bar` sia funzioni top-level/estensioni; con
`pkg.Bar` per entrambi, uml-viewer/dryer/mutator (join su `:namespace`)
mostrerebbero le top-level come metodi di `class Bar`. `BarKt` è anche ciò che
la JVM vede davvero.

`name` è il nome della funzione come scritto nel sorgente. Il package viene da
`package a.b.c` (senza `;`, a differenza di Java). Senza `package`, namespace
senza prefisso.

Nota per il builder: Kotlin modifica alcuni nomi in bytecode (funzioni
`internal` → `nome$nomeModulo`; funzioni con value class nei parametri →
`nome-hash`). Il lookup deve tollerarlo: se il nome esatto non c'è, provare i
metodi della stessa classe il cui nome inizia con `nome$` o `nome-`, scegliendo
quello con la riga più vicina (la logica "riga più vicina" esiste già in
`_jacoco_from_index`). Il fallback deve **escludere** i metodi sintetici
`nome$default` e `nome$lambda$N` (presenti nei `jacoco.xml` reali di eARTS:
JaCoCo non li filtra), altrimenti verrebbero scelti al posto della funzione.
Corpi delle interfacce senza `-Xjvm-default` (eARTS: Kotlin 1.9.22) stanno in
`Iface$DefaultImpls`: includerlo tra i candidati di lookup.

## Coverage

- **Sorgente:** stesso `jacoco.xml` letto oggi per Java
  (`target/site/jacoco/jacoco.xml`, nella root e fino a due livelli di moduli).
  `CoverageBundle.percent_for` deve trattare `kotlin` come `java` (lookup per
  `jacoco_class` + `name` + riga).
- **Generazione:** il runner Maven esistente (`_cover_java`) individua i moduli
  dal `pom.xml` più vicino ai file `.java`. Va esteso perché consideri anche i
  `.kt`, **eseguendo Maven una sola volta per modulo** anche se il modulo
  contiene entrambi i linguaggi (eARTS è misto).
- **Lambda nella coverage** (decisione dell'utente). Kotlin compila ogni
  lambda in un metodo separato della stessa classe (`foo$lambda$0`,
  `foo$lambda$1$lambda$2` per lambda annidate; `foo$lambda-0` con Kotlin < 1.8).
  Poiché la complessità di `foo` include i rami delle lambda, la coverage di
  `foo` è calcolata **sommando i contatori `INSTRUCTION` (missed/covered) del
  metodo `foo` e di tutti i suoi metodi lambda**, così complessità e coverage
  misurano lo stesso codice. Se ci sono più `foo` in overload nella stessa
  classe, le lambda vanno attribuite a quella con la riga più vicina
  precedente (il builder sceglie il criterio esatto, documentandolo).
- Le funzioni Kotlin senza dati JaCoCo valgono 0%, come Java oggi.
- Su progetti grandi (eARTS) il run completo dei test è lungo: il flusso
  consigliato è `mvn ... jacoco:report` una volta, poi
  `crapper --use-existing-coverage`. Va scritto nell'help/README.
- *Scelta del builder:* il runner per-modulo **non** viene riprogettato.
  eARTS ha moduli che dipendono da moduli fratelli via `${revision}` e un
  JaCoCo 0.8.13 già legato alla fase `test` nel `pom.xml` radice: lanciare
  `mvn` dentro ogni modulo con il JaCoCo 0.8.12 del runner rischia sibling
  stantii da `~/.m2` e due agent sullo stesso `jacoco.exec`. Per progetti
  multi-modulo con JaCoCo proprio il flusso documentato è
  `crapper --coverage-command "mvn -q test"` (opzione già esistente) oppure
  `--use-existing-coverage`. Il runner automatico si limita ad attivarsi anche
  per i `.kt`, senza cambiare il comportamento Java. Il criterio di successo su
  eARTS si verifica con uno di questi due flussi.

## File da ignorare

`discover.SKIP_DIRS` non salta `.claude`: in eARTS
`.claude/worktrees/feature-77-observability/` è una seconda copia completa del
progetto (~7.700 `.kt`, 24 `pom.xml`), che duplicherebbe ogni funzione.
*Scelta del builder:* aggiungere `.claude` a `SKIP_DIRS` (una riga in un file
upstream, utile a tutti i linguaggi). Altre cartelle sporche specifiche del
progetto (es. `.codex_tmp_removed/`) si escludono con `-s/--source-root`, non
con regole nel tool.

## Aggancio al codice esistente (superficie di conflitto con upstream)

File nuovi:
- `src/crapper/languages/kotlin.py`
- `tests/test_kotlin.py` (+ eventuali fixture)

File esistenti, modifiche minime:
- `discover.py`: `".kt": "kotlin"` in `EXTENSIONS`.
- `languages/__init__.py`: voce `"kotlin"` in `_READERS`.
- `coverage.py`: `percent_for` tratta `kotlin` come `java`; eventuale fallback
  di nome per il mangling (preferibilmente in una funzione nuova).
- `runners.py`: il runner JVM parte se ci sono `java` o `kotlin`, una volta
  per modulo.
- `cli.py`: help (lingue, coverage, namespace).
- `README.md`: sezione Kotlin. `pyproject.toml`: descrizione.

Upstream valida sui test-file pattern; i test Kotlin di Maven stanno in
`src/test/kotlin`, già esclusi perché `test` è in `TEST_DIRS`. Nessun suffisso
nuovo da aggiungere.

## Lasciato al builder

- Mappatura esatta dei nodi tree-sitter Kotlin (nomi dei tipi di nodo della
  grammatica) alle regole sopra; verificarla con `tree.root_node` su esempi.
- Struttura interna di `kotlin.py` e dei test, fixture.
- Se estendere `_cover_java` o introdurre un `_cover_jvm` che lo sostituisce
  (scegliere il diff più piccolo verso upstream).
- Verifica su eARTS: quale modulo usare per una prova rapida prima del run
  completo.
