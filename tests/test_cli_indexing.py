from __future__ import annotations

import sqlite3

from localast.docs.ingest import ingest_documents
from localast.indexer.pipeline import index_code_paths
from localast.storage.schema import apply_schema


def _make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    apply_schema(connection)
    return connection


def test_index_code_paths_extracts_symbols(tmp_path) -> None:
    module = tmp_path / "example.py"
    module.write_text(
        """
def alpha():
    pass


class Beta:
    def method(self):
        return 1
""",
        encoding="utf-8",
    )

    connection = _make_connection()
    summary = index_code_paths(connection, [module])
    cursor = connection.cursor()
    files = cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = cursor.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    connection.close()

    assert summary == {"files": 1, "symbols": 2}
    assert files == 1
    assert symbols == 2


def test_ingest_documents_creates_links(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    code_dir = repo_root / "src"
    code_dir.mkdir()
    module = code_dir / "sample.py"
    module.write_text("def run():\n    return True\n", encoding="utf-8")

    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    doc_file = doc_dir / "guide.md"
    doc_file.write_text(
        "This references src/sample.py so it should link to code.",
        encoding="utf-8",
    )

    connection = _make_connection()
    index_code_paths(connection, [module])
    summary = ingest_documents(connection, [doc_dir], repo_root=repo_root)

    cursor = connection.cursor()
    doc_count = cursor.execute("SELECT COUNT(*) FROM blob WHERE kind = 'doc'").fetchone()[0]
    link_count = cursor.execute("SELECT COUNT(*) FROM edges WHERE etype = 'DOCS'").fetchone()[0]
    connection.close()

    assert summary == {"documents": 1}
    assert doc_count == 1
    assert link_count == 1

