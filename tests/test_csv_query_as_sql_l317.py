"""L317: a CSV document has a panel action that loads it as a SQL table.

The SQL run already loads a CSV document whose name the query uses (`docSqlCsvTables`); what was missing
was a way to it from the CSV. The panel's Query as SQL makes a SQL document asking for the table's first
rows and runs it, and shows only on a CSV document.
"""

from __future__ import annotations

from tests.test_code_documents import JS


def _panel() -> str:
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    start = code.index("function docRunPanel(")
    return code[start : code.index("\nfunction ", start + 10)]


def test_query_as_sql_is_a_panel_action_only_a_csv_shows():
    panel = _panel()
    assert 'button("Query as SQL", "ph-database"' in panel
    assert 'query.classList.toggle("hidden", docFileType().ext !== "csv")' in panel
    assert "tests, query, again" in panel


def test_it_makes_a_sql_document_of_the_tables_name_and_runs_it():
    panel = _panel()
    assert "docSqlTableName(currentDoc?.title)" in panel
    assert 'file_type: "sql"' in panel and "select * from ${table} limit 50;" in panel
    assert "await loadDocuments(made.id);" in panel and "docRunCode();" in panel


def test_the_panel_help_and_the_guide_name_the_action():
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    assert "on a CSV, Query as SQL starts one" in code
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "code-run"))
    assert "Query as SQL" in body
