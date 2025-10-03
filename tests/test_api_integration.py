import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from tests.conftest import demo_db_url


def test_connect_and_query(demo_db_url):
    client = TestClient(app)
    # Connect DB
    r = client.post('/api/connect-database', json={"connection_string": demo_db_url})
    assert r.status_code == 200
    schema = r.json()["schema"]
    assert "tables" in schema

    # Simple query
    r2 = client.post('/api/query', json={"query": "How many employees do we have?"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["query_type"] == "sql"
    assert "results" in data

@pytest.mark.skip(reason="Avoid heavy embedding downloads in CI")
def test_upload_documents_skipped():
    assert True
