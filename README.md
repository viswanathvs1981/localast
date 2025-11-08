# LocalAST

LocalAST is a scaffolding project that demonstrates how the "Local Code Brain"
architecture can be run entirely on a developer laptop. All resources — from
the SQLite database to optional background services — live on the local
filesystem. No Azure or other cloud infrastructure is required.

## Project layout

```
.
├── db/schema.sql           # SQLite schema for all modules (AST, Prompt Lab, review)
├── examples/               # Sample review policies and prompt metrics
├── scripts/init_db.py      # Helper script to bootstrap the local database
├── src/localast/           # Python package housing modular scaffolding
└── tests/                  # Pytest-based validation of the schema
```

Each package under `src/localast/` mirrors a major component of the design
specification (AST, graph, embeddings, temporal store, review engine, etc.).
The implementations are intentionally lightweight so that new contributors can
extend them without first wiring external services.

## Prerequisites

* Python 3.11+
* `sqlite3` command-line tools (bundled with Python on most platforms)

Optional extras referenced by the spec (e.g. `jinja2`, `hypothesis`,
`networkx`, `gitpython`) can be added later; the core scaffolding does not
require them.

## Installation

Create a virtual environment and install the development dependencies locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

The editable install (`pip install -e .`) adds the `localast` package to your
environment without copying files, making it easy to iterate locally.

## Initialising the local database

The repository ships with a schema file that mirrors the data model from the
spec. To create the SQLite database in `~/.localast/localast.db`, run:

```bash
python scripts/init_db.py
```

You can choose a custom location by passing `--database`:

```bash
python scripts/init_db.py --database ./tmp/localast.db
```

The script does not reach out to the network; it only creates directories and
executes SQL locally.

## Local CLI for indexing and inspection

Installing the package adds a `localast` command with dedicated sub-commands for
code and documentation indexing as well as repository introspection.

### Index source code

```bash
localast index code src/localast
```

The command walks Python files under the provided paths, extracts top-level
classes and functions, and records the results in the local SQLite database. Add
`--reindex` to refresh entries for files that have already been processed.

### Index documentation

```bash
localast index docs docs/ --repo-root .
```

Markdown, reStructuredText, and plain-text files are ingested into the `blob`
table, vectorised with a lightweight heuristic, and linked to code whenever the
text references repository paths. The `--repo-root` flag defaults to the current
directory and is used to resolve relative code references.

### Inspect the indexed repository

```bash
localast repo info
```

This summary lists indexed files, symbols, documentation artefacts, and the
number of documentation-to-code links that were discovered locally.

## Testing and validation

Automated validation relies on `pytest` and the in-memory SQLite engine. Tests
can be executed locally with:

```bash
pytest
```

The suite verifies that the schema can be applied and that key tables are
present. Because everything runs on the local interpreter, no Azure resources
or network calls are involved.

## Next steps

The current codebase focuses on local-first scaffolding. You can gradually
replace the stub implementations in `src/localast/` with real logic (parsers,
policy evaluators, embedding indexes) while keeping execution local. Examples
in `examples/` provide starting points for review policies and prompt metrics
used in higher-level workflows.
