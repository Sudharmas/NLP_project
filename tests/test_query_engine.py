from backend.api.services.app_state import AppState
from backend.api.services.schema_discovery import SchemaDiscovery
from backend.api.services.query_engine import QueryEngine
from tests.conftest import TEST_DB, setup_demo_db


def setup_state() -> AppState:
    state = AppState()
    conn_str = f"sqlite:///{TEST_DB}"
    schema = SchemaDiscovery().analyze_database(conn_str)
    state.set_connection(conn_str, schema)
    return state


def test_query_classification():
    state = setup_state()
    qe = QueryEngine(state)
    assert qe.classify("How many employees do we have?") == "sql"
    assert qe.classify("Find resumes mentioning Python") in {"document", "hybrid"}
    assert qe.classify("Show me resumes for employees in Engineering") in {"hybrid", "document"}


def test_process_sql_count():
    state = setup_state()
    qe = QueryEngine(state)
    resp = qe.process_query("How many employees do we have?")
    assert resp["query_type"] == "sql"
    assert "results" in resp

