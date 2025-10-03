from typing import Any, Dict, List, Tuple
from time import perf_counter
from sqlalchemy import text
from sqlalchemy.engine import Engine
from .schema_discovery import SchemaDiscovery
from .app_state import AppState
from .query_cache import QueryCache
import math
import re


class QueryEngine:
    def __init__(self, state: AppState):
        self.state = state
        self.discovery = SchemaDiscovery()
        self.cache: QueryCache = state.cache

    def classify(self, user_query: str) -> str:
        q = user_query.lower()
        # Very simple classifier
        doc_keywords = ["resume", "document", "policy", "contract", "review", "pdf", "doc"]
        sql_keywords = ["count", "average", "avg", "sum", "list", "show", "who", "employees", "department"]
        is_doc = any(k in q for k in doc_keywords)
        is_sql = any(k in q for k in sql_keywords)
        if is_doc and is_sql:
            return "hybrid"
        if is_doc:
            return "document"
        return "sql"

    def process_query(self, user_query: str, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        start = perf_counter()
        cache_key = f"{user_query}|{page}|{page_size}"
        cached = self.cache.get(cache_key)
        if cached:
            duration = (perf_counter() - start)
            cached["performance"]["response_time_ms"] = int(duration * 1000)
            cached["cache"]["hit"] = True
            return cached

        qtype = self.classify(user_query)
        results = None
        sources: List[Dict[str, Any]] = []
        try:
            if qtype == "document":
                results, sources = self._search_documents(user_query, page, page_size)
            elif qtype == "sql":
                results = self._run_sql_query(user_query, page, page_size)
            else:  # hybrid
                sql_results = self._run_sql_query(user_query, page, page_size)
                doc_results, doc_sources = self._search_documents(user_query, page, page_size)
                results = {"table": sql_results, "documents": doc_results}
                sources = doc_sources
        except Exception as e:
            results = {"error": str(e)}
            qtype = "error"

        duration = (perf_counter() - start)
        payload = {
            "query_type": qtype,
            "results": results,
            "sources": sources,
            "performance": {"response_time_ms": int(duration * 1000)},
            "cache": {"hit": False, **self.cache.stats()},
        }
        # Save to history (keep last 50)
        self.state.query_history.append({"query": user_query, "type": qtype, "ts": perf_counter()})
        self.state.query_history = self.state.query_history[-50:]
        self.cache.set(cache_key, payload)
        return payload

    def _run_sql_query(self, user_query: str, page: int, page_size: int) -> Dict[str, Any]:
        # Map NL to schema and create a safe SQL template for common patterns
        mapping = self.discovery.map_natural_language_to_schema(user_query, self.state.schema)
        table = mapping.get("table")
        if not table:
            raise ValueError("Could not determine main table. Ensure database has an employee-like table.")
        cols = self.state.schema["tables"][table]["columns"]
        col_names = [c["name"] for c in cols]
        hints = self.state.schema.get("hints", {}).get("column_maps", {}).get(table, {})
        name_col = hints.get("name") or col_names[0]
        salary_col = hints.get("salary")
        dept_col = hints.get("department")
        date_col = hints.get("date")

        # Supported simple patterns
        q = user_query.lower()
        sql = None
        params = {}
        if "how many" in q or ("count" in q and "employees" in q):
            sql = f"SELECT COUNT(*) as count FROM {table}"
        elif "average" in q and ("salary" in q or "pay" in q or "compensation" in q) and dept_col:
            sql = f"SELECT {dept_col} as department, AVG({salary_col}) as average_salary FROM {table} GROUP BY {dept_col} ORDER BY average_salary DESC"
        elif any(k in q for k in ["hired this year", "joined this year", "hired in", "join date"]):
            if date_col:
                sql = f"SELECT * FROM {table} WHERE strftime('%Y', {date_col}) = strftime('%Y','now') ORDER BY {date_col} DESC"
            else:
                sql = f"SELECT * FROM {table} LIMIT 100"
        else:
            # Generic search by tokens in name or department
            tokens = [t for t in re.findall(r"[a-zA-Z_]+", q) if t not in {"show", "list", "me", "all"}]
            like_filters = []
            for tkn in tokens:
                like_filters.append(f"LOWER({name_col}) LIKE :{tkn}")
                if dept_col:
                    like_filters.append(f"LOWER({dept_col}) LIKE :{tkn}_d")
                    params[f"{tkn}_d"] = f"%{tkn}%"
                params[tkn] = f"%{tkn}%"
            if like_filters:
                where = " OR ".join(like_filters)
                sql = f"SELECT * FROM {table} WHERE {where}"
            else:
                sql = f"SELECT * FROM {table}"
        sql = self.optimize_sql_query(sql, page, page_size)
        with self.state.engine.connect() as conn:
            rs = conn.execute(text(sql), params)
            rows = [dict(r._mapping) for r in rs]
        return {"columns": list(rows[0].keys()) if rows else col_names, "rows": rows, "page": page, "page_size": page_size}

    def _search_documents(self, user_query: str, page: int, page_size: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        vs = self.state.vectorstore
        if vs is None:
            return [], []
        # LangChain Chroma retriever
        retriever = vs.as_retriever(search_kwargs={"k": page_size})
        docs = retriever.get_relevant_documents(user_query)
        start = (page - 1) * page_size
        end = start + page_size
        docs = docs[start:end]
        results = []
        sources = []
        for d in docs:
            results.append({"text": d.page_content, "metadata": d.metadata})
            s = dict(d.metadata)
            s["score"] = getattr(d, "score", None)
            sources.append(s)
        return results, sources

    def optimize_sql_query(self, sql: str, page: int, page_size: int) -> str:
        # Add pagination safely
        page = max(1, int(page))
        page_size = max(1, min(200, int(page_size)))
        offset = (page - 1) * page_size
        # If query already has LIMIT/OFFSET, leave as-is
        ql = sql.lower()
        if " limit " in ql:
            return sql
        return f"{sql} LIMIT {page_size} OFFSET {offset}"
