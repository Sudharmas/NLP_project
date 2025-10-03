import os
from typing import Any, Dict, Optional
from cachetools import TTLCache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import yaml
from pathlib import Path
from .query_cache import QueryCache


class AppState:
    def __init__(self):
        self.connection_string: Optional[str] = None
        self.engine: Optional[Engine] = None
        self.schema: Optional[Dict[str, Any]] = None
        self.cache: Optional[QueryCache] = None
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.storage_dirs = {}
        self.vectorstore = None
        self.query_history = []
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        cfg_path = Path("config.yml")
        if cfg_path.exists():
            with open(cfg_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
        else:
            cfg = {}
        # Env override for DATABASE_URL
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            cfg.setdefault("database", {})["connection_string"] = db_url
        return cfg

    def set_connection(self, conn_str: str, schema: Dict[str, Any]):
        # Create engine with pooling
        pool_size = int(self.config.get("database", {}).get("pool_size", 10))
        self.engine = create_engine(
            conn_str,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=pool_size,
            future=True,
        )
        self.connection_string = conn_str
        self.schema = schema
        # Initialize cache
        ttl = int(self.config.get("cache", {}).get("ttl_seconds", 300))
        max_size = int(self.config.get("cache", {}).get("max_size", 1000))
        self.cache = QueryCache(max_size=max_size, ttl=ttl)
        # Prepare storage dirs
        base_dir = Path(self.config.get("storage", {}).get("base_dir", "./data"))
        chroma_dir = Path(self.config.get("storage", {}).get("chroma_dir", "./data/chroma"))
        base_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dirs = {"base": base_dir, "chroma": chroma_dir, "uploads": base_dir / "uploads"}
        self.storage_dirs["uploads"].mkdir(parents=True, exist_ok=True)

    def is_initialized(self) -> bool:
        return self.engine is not None and self.schema is not None and self.cache is not None

    def ensure_storage_dirs(self):
        # Initialize storage directories even without DB connection
        base_dir = Path(self.config.get("storage", {}).get("base_dir", "./data"))
        chroma_dir = Path(self.config.get("storage", {}).get("chroma_dir", "./data/chroma"))
        base_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dirs = {"base": base_dir, "chroma": chroma_dir, "uploads": base_dir / "uploads"}
        self.storage_dirs["uploads"].mkdir(parents=True, exist_ok=True)


_state: Optional[AppState] = None


def get_app_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state
