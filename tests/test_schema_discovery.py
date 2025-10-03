from backend.api.services.schema_discovery import SchemaDiscovery

def test_schema_discovery_basic(demo_db_url):
    sd = SchemaDiscovery()
    schema = sd.analyze_database(demo_db_url)
    assert 'tables' in schema and len(schema['tables']) >= 2
    hints = schema.get('hints', {})
    assert isinstance(hints.get('employee_tables'), list)
    # Should detect employees table
    assert any('emp' in t or 'employee' in t for t in hints.get('employee_tables', []) + list(schema['tables'].keys()))


def test_map_nl_to_schema(demo_db_url):
    sd = SchemaDiscovery()
    schema = sd.analyze_database(demo_db_url)
    mapped = sd.map_natural_language_to_schema('Average salary by department', schema)
    assert mapped.get('table') is not None
