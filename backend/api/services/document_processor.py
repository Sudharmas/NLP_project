import os
import io
from typing import List, Dict, Any
from fastapi import UploadFile
from pathlib import Path
import aiofiles
from tqdm import tqdm
from .app_state import AppState
import asyncio


SUPPORTED_TYPES = {"pdf", "docx", "txt", "csv"}


class DocumentProcessor:
    def __init__(self, state: AppState):
        self.state = state
        cfg = self.state.config
        self.model_name = cfg.get("embeddings", {}).get("model", "sentence-transformers/all-MiniLM-L6-v2")
        self.batch_size = int(cfg.get("embeddings", {}).get("batch_size", 32))
        self._emb = None
        self._vs = None

    def _embeddings(self):
        if self._emb is None:
            try:
                mod = __import__("langchain_community.embeddings", fromlist=["HuggingFaceEmbeddings"])  # type: ignore
                HuggingFaceEmbeddings = getattr(mod, "HuggingFaceEmbeddings")
            except ModuleNotFoundError:
                raise RuntimeError(
                    "Embeddings backend not installed. Install 'sentence-transformers' and 'langchain-community' to enable document ingestion."
                )
            self._emb = HuggingFaceEmbeddings(model_name=self.model_name)
        return self._emb

    def _vectorstore(self):
        if self._vs is None:
            try:
                mod = __import__("langchain_community.vectorstores", fromlist=["Chroma"])  # type: ignore
                Chroma = getattr(mod, "Chroma")
            except ModuleNotFoundError:
                raise RuntimeError(
                    "Chroma vector store not installed. Install 'chromadb' and 'langchain-community' to enable document ingestion."
                )
            self._vs = Chroma(
                collection_name="employee_docs",
                persist_directory=str(self.state.storage_dirs["chroma"]),
                embedding_function=self._embeddings(),
            )
            self.state.vectorstore = self._vs
        return self._vs

    async def process_uploads(self, job_id: str, files: List[UploadFile]):
        # Deprecated for background tasks: UploadFile may be closed after response.
        # Kept for compatibility; internally save to disk then delegate to path-based processing.
        uploads_dir = self.state.storage_dirs["uploads"]
        saved_paths: List[Path] = []
        for f in files:
            try:
                dest = uploads_dir / f.filename
                async with aiofiles.open(dest, "wb") as out:
                    content = await f.read()
                    await out.write(content)
                saved_paths.append(dest)
            except Exception:
                # If we cannot read the file (likely closed), skip; path list may be empty
                continue
        await self.process_files_from_paths(job_id, saved_paths)

    async def process_files_from_paths(self, job_id: str, file_paths: List[Path]):
        job = self.state.jobs[job_id]
        job["status"] = "processing"
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        for idx, path in enumerate(file_paths, start=1):
            try:
                suffix = path.suffix.lower().strip(".")
                if suffix not in SUPPORTED_TYPES:
                    job["errors"].append(f"Unsupported file type: {path.name}")
                    continue
                text = await self._extract_text(path)
                chunks = self.dynamic_chunking(text, suffix)
                for i, ch in enumerate(chunks):
                    texts.append(ch)
                    metadatas.append({"filename": path.name, "chunk": i, "job_id": job_id, "type": suffix})
                job["processed"] = idx
            except Exception as e:
                job["errors"].append(f"{path.name}: {e}")
        # Embed and index
        if texts:
            vs = self._vectorstore()
            for i in range(0, len(texts), self.batch_size):
                vs.add_texts(texts=texts[i:i+self.batch_size], metadatas=metadatas[i:i+self.batch_size])
            vs.persist()
        job["status"] = "completed"

    async def _extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower().strip(".")
        if suffix == "pdf":
            try:
                import pdfplumber  # type: ignore
            except ModuleNotFoundError:
                raise RuntimeError("PDF support not installed. Install 'pdfplumber' to parse PDFs.")
            with pdfplumber.open(str(file_path)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        elif suffix == "docx":
            try:
                import docx  # type: ignore
            except ModuleNotFoundError:
                raise RuntimeError("DOCX support not installed. Install 'python-docx' to parse .docx files.")
            doc = docx.Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs)
        elif suffix == "txt":
            # Use thread to avoid event-loop/file descriptor issues
            def _read_text():
                with open(str(file_path), "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            return await asyncio.to_thread(_read_text)
        elif suffix == "csv":
            def _read_csv():
                with open(str(file_path), "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            return await asyncio.to_thread(_read_csv)
        return ""

    def dynamic_chunking(self, content: str, doc_type: str) -> List[str]:
        content = content or ""
        doc_type = (doc_type or "").lower()
        # Heuristic chunk sizes by type
        if doc_type == "pdf":
            chunk_size = 1200
            overlap = 150
        elif doc_type == "docx":
            chunk_size = 1000
            overlap = 100
        elif doc_type == "csv":
            chunk_size = 1500
            overlap = 50
        else:  # txt or unknown
            chunk_size = 800
            overlap = 100
        # Try to use LangChain splitter if available
        splitter = None
        try:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore
            except ModuleNotFoundError:
                from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
            splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", ".", " "])
            # Try to preserve sections keywords for resumes/contracts/reviews
            if any(k in content.lower() for k in ["skills", "experience", "work history", "education"]):
                splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120, separators=["\n## ", "\n# ", "\n\n", "\n", ". "])  # resume-like
            if any(k in content.lower() for k in ["clause", "agreement", "party", "terms"]):
                splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80, separators=["\n\n", "\n", "; ", ". "])  # contracts
            if any(k in content.lower() for k in ["review", "feedback", "performance", "goals"]):
                splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100, separators=["\n\n", "\n", ". "])  # reviews
            return splitter.split_text(content)
        except Exception:
            # Fallback: naive splitter by characters
            chunks: List[str] = []
            step = max(1, chunk_size - overlap)
            for i in range(0, len(content), step):
                chunks.append(content[i:i + chunk_size])
            return chunks
