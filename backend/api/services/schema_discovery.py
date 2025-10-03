from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from rapidfuzz import process as fuzz_process, fuzz
import re


EMPLOYEE_SYNONYMS = [
    "employee", "employees", "emp", "staff", "personnel", "person", "people"
]
DEPT_SYNONYMS = [
    "dept", "department", "division", "team"
]
SALARY_SYNONYMS = [
    "salary", "compensation", "pay", "pay_rate", "annual_salary"
]
NAME_SYNONYMS = [
    "name", "full_name", "employee_name"
]
DATE_SYNONYMS = [
    "join_date", "hired_on", "start_date"
]
MANAGER_SYNONYMS = [
    "manager", "manager_id", "head_id", "reports_to"
]


def best_match(token: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    match, score, _ = fuzz_process.extractOne(token, candidates, scorer=fuzz.WRatio)
    return match if score >= 75 else None


class SchemaDiscovery:
    def analyze_database(self, connection_string: str) -> Dict[str, Any]:
        engine = create_engine(connection_string, future=True)
        insp = inspect(engine)
        tables = insp.get_table_names()
        schema: Dict[str, Any] = {"tables": {}, "relationships": [], "hints": {}}
        for t in tables:
            cols = []
            for c in insp.get_columns(t):
                cols.append({
                    "name": c["name"],
                    "type": str(c.get("type")),
                    "nullable": c.get("nullable", True),
                    "default": str(c.get("default")) if c.get("default") is not None else None,
                })
            # Collect samples
            sample_rows = []
            try:
                with engine.connect() as conn:
                    rs = conn.execute(text(f"SELECT * FROM {t} LIMIT 3"))
                    for row in rs:
                        sample_rows.append(dict(row._mapping))
            except Exception:
                pass
            schema["tables"][t] = {"columns": cols, "samples": sample_rows}

        # Foreign keys / relationships
        for t in tables:
            for fk in insp.get_foreign_keys(t):
                if not fk:
                    continue
                rel = {
                    "table": t,
                    "constrained_columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns", []),
                }
                schema["relationships"].append(rel)

        # Heuristic role detection
        schema["hints"]["employee_tables"] = self._find_tables(tables, EMPLOYEE_SYNONYMS)
        schema["hints"]["department_tables"] = self._find_tables(tables, DEPT_SYNONYMS)

        # Column synonym maps per table
        col_maps: Dict[str, Dict[str, str]] = {}
        for t in tables:
            col_names = [c["name"] for c in schema["tables"][t]["columns"]]
            col_maps[t] = {
                "name": (best_match_from_list(NAME_SYNONYMS, col_names) or (col_names[0] if col_names else None)),
                "salary": best_match_from_list(SALARY_SYNONYMS, col_names),
                "department": best_match_from_list(DEPT_SYNONYMS, col_names),
                "date": best_match_from_list(DATE_SYNONYMS, col_names),
                "manager": best_match_from_list(MANAGER_SYNONYMS, col_names),
            }
        schema["hints"]["column_maps"] = col_maps
        return schema

    def _find_tables(self, tables: List[str], synonyms: List[str]) -> List[str]:
        matches = []
        for t in tables:
            if any(s in t.lower() for s in synonyms):
                matches.append(t)
        return matches

    def map_natural_language_to_schema(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        # Extract tokens and try to map to tables/columns
        q = query.lower()
        tables = list(schema.get("tables", {}).keys())
        tokens = re.findall(r"[a-zA-Z_]+", q)
        # Choose main employee table
        employee_candidates = schema.get("hints", {}).get("employee_tables") or tables
        main_table = None
        if employee_candidates:
            # prefer tables with more name-like columns
            main_table = employee_candidates[0]
        # Map columns
        col_map = schema.get("hints", {}).get("column_maps", {}).get(main_table or "", {})
        mapped = {
            "table": main_table,
            "columns": col_map,
        }
        return mapped


def best_match_from_list(synonyms: List[str], candidates: List[str]) -> Optional[str]:
    cands_lower = {c.lower(): c for c in candidates}
    # Try direct contains
    for syn in synonyms:
        for cand_lower, orig in cands_lower.items():
            if syn in cand_lower:
                return orig
    # Fuzzy match
    bm = best_match(" ".join(synonyms), list(cands_lower.keys()))
    return cands_lower.get(bm) if bm else None
