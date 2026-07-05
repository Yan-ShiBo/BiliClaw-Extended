"""Local vector store for source bootstrap signals.

The SQLite event log remains the source of truth.  This module builds a
rebuildable ChromaDB index for semantic lookup over high-signal source
items, starting with Douyin liked videos.
"""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from pathlib import Path


class _DisabledCollection:
    def upsert(self, **_kwargs: Any) -> None:
        return None

    def query(self, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def count(self) -> int:
        return 0


class _DisabledClient:
    def get_or_create_collection(self, **_kwargs: Any) -> _DisabledCollection:
        return _DisabledCollection()


try:  # pragma: no cover - exercised through the fallback in lean test envs.
    import chromadb
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
except ModuleNotFoundError:  # pragma: no cover - import-time compatibility.
    Documents = list[str]  # type: ignore[assignment]
    Embeddings = list[list[float]]  # type: ignore[assignment]

    class EmbeddingFunction:  # type: ignore[no-redef]
        pass

    def _missing_persistent_client(*_args: Any, **_kwargs: Any) -> _DisabledClient:
        return _DisabledClient()

    chromadb = SimpleNamespace(PersistentClient=_missing_persistent_client)

logger = logging.getLogger(__name__)

DEFAULT_DY_LIKES_COLLECTION = "dy_likes"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "qwen3-embedding:8b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
VECTOR_OLLAMA_HOST_ENV = "OPENBILICLAW_VECTOR_OLLAMA_HOST"
VECTOR_OLLAMA_MODEL_ENV = "OPENBILICLAW_VECTOR_OLLAMA_MODEL"


def _normalize_ollama_host(value: str) -> str:
    host = str(value or "").strip().rstrip("/")
    if host.endswith("/v1"):
        host = host[:-3].rstrip("/")
    return host or DEFAULT_OLLAMA_HOST


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    return clean


def _dy_like_document_from_video(video: dict[str, Any]) -> tuple[str, str, dict[str, Any]] | None:
    if str(video.get("scope", "")).strip() != "dy_like":
        return None
    aweme_id = str(video.get("aweme_id", "") or "").strip()
    url = str(video.get("url", "") or "").strip()
    doc_id = aweme_id or url
    if not doc_id:
        return None

    title = str(video.get("title", "") or "").strip()
    desc = str(video.get("desc", "") or video.get("description", "") or "").strip()
    author = str(video.get("author", "") or "").strip()
    text_parts = [part for part in (title, desc, author) if part]
    text = "\n".join(text_parts).strip()
    if not text:
        return None

    metadata = {
        "aweme_id": aweme_id,
        "url": url,
        "author": author,
        "author_sec_uid": str(video.get("author_sec_uid", "") or "").strip(),
        "creator_sec_uid": str(video.get("creator_sec_uid", "") or "").strip(),
        "cover_url": str(video.get("cover_url", "") or "").strip(),
        "source_platform": "douyin",
        "import_source": "dy_bootstrap_like",
    }
    return doc_id, text, metadata


def _dy_like_document_from_event(event: dict[str, Any]) -> tuple[str, str, dict[str, Any]] | None:
    if str(event.get("event_type") or event.get("type") or "").strip() != "like":
        return None
    metadata_raw = event.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        metadata_raw = {}
    metadata = dict(metadata_raw)
    if str(metadata.get("source_platform", "")).strip() != "douyin":
        return None
    if str(metadata.get("import_source", "")).strip() != "dy_bootstrap_like":
        return None

    aweme_id = str(metadata.get("aweme_id", "") or "").strip()
    url = str(event.get("url", "") or "").strip()
    doc_id = aweme_id or url
    if not doc_id:
        return None

    title = str(event.get("title", "") or "").strip()
    context = str(event.get("context", "") or "").strip()
    author = str(metadata.get("author", "") or "").strip()
    text_parts = [part for part in (title, context, author) if part]
    text = "\n".join(text_parts).strip()
    if not text:
        return None

    metadata.update(
        {
            "aweme_id": aweme_id,
            "url": url,
            "source_platform": "douyin",
            "import_source": "dy_bootstrap_like",
        }
    )
    return doc_id, text, metadata


class OllamaEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding adapter backed by Ollama's native embeddings API."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.model_name = model_name
        self.host = _normalize_ollama_host(host)
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def name() -> str:
        return "openbiliclaw_ollama"

    def get_config(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "host": self.host,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> OllamaEmbeddingFunction:
        timeout_raw = config.get("timeout_seconds", 120.0)
        try:
            timeout_seconds = float(timeout_raw)
        except (TypeError, ValueError):
            timeout_seconds = 120.0
        return cls(
            model_name=str(config.get("model_name") or DEFAULT_OLLAMA_EMBEDDING_MODEL),
            host=str(config.get("host") or DEFAULT_OLLAMA_HOST),
            timeout_seconds=timeout_seconds,
        )

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: list[list[float]] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for text in input:
                response = client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": self.model_name, "prompt": text},
                )
                response.raise_for_status()
                payload = response.json()
                vector = payload.get("embedding")
                if not isinstance(vector, list):
                    raise RuntimeError("Ollama embedding response did not contain a vector")
                embeddings.append([float(value) for value in vector])
        return embeddings


class VectorStoreManager:
    """Persistent local vector database for source-derived documents."""

    def __init__(
        self,
        data_dir: Path,
        *,
        embedding_model: str | None = None,
        ollama_host: str | None = None,
        collection_name: str = DEFAULT_DY_LIKES_COLLECTION,
    ) -> None:
        self.db_path = data_dir / "vector_db"
        self.db_path.mkdir(parents=True, exist_ok=True)
        model = (
            embedding_model
            or os.environ.get(VECTOR_OLLAMA_MODEL_ENV, "").strip()
            or DEFAULT_OLLAMA_EMBEDDING_MODEL
        )
        host = (
            ollama_host
            or os.environ.get(VECTOR_OLLAMA_HOST_ENV, "").strip()
            or DEFAULT_OLLAMA_HOST
        )
        self.embedding_fn = OllamaEmbeddingFunction(model_name=model, host=host)
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.available = not isinstance(self.client, _DisabledClient)
        if not self.available:
            logger.warning("ChromaDB is not installed; local vector store is disabled.")
        self.dy_likes_collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
        )

    def upsert_dy_like(
        self,
        video_id: str,
        text_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add or update one Douyin liked video in ChromaDB."""
        doc_id = str(video_id or "").strip()
        text = str(text_content or "").strip()
        if not doc_id or not text:
            return False
        if not self.available:
            return False
        clean_metadata = _clean_metadata(metadata or {})
        self.dy_likes_collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[clean_metadata] if clean_metadata else None,
        )
        logger.info("Upserted Douyin liked video into vector store: %s", doc_id)
        return True

    def upsert_dy_like_video(self, video: dict[str, Any]) -> bool:
        """Add or update one extension-collected ``dy_like`` item."""
        document = _dy_like_document_from_video(video)
        if document is None:
            return False
        doc_id, text, metadata = document
        return self.upsert_dy_like(doc_id, text, metadata)

    def upsert_dy_like_videos(self, videos: list[dict[str, Any]]) -> int:
        """Batch upsert extension-collected ``dy_like`` items."""
        count = 0
        for video in videos:
            if isinstance(video, dict) and self.upsert_dy_like_video(video):
                count += 1
        return count

    def upsert_dy_like_event(self, event: dict[str, Any]) -> bool:
        """Add or update one canonical memory event when it is a Douyin like."""
        document = _dy_like_document_from_event(event)
        if document is None:
            return False
        doc_id, text, metadata = document
        return self.upsert_dy_like(doc_id, text, metadata)

    def search_dy_likes(self, query_text: str, n_results: int = 5) -> dict[str, Any]:
        """Search similar Douyin liked videos by natural-language query."""
        query = str(query_text or "").strip()
        if not query or not self.available:
            return {}
        return self.dy_likes_collection.query(
            query_texts=[query],
            n_results=max(1, int(n_results)),
        )

    def count_dy_likes(self) -> int:
        """Return the number of documents in the Douyin likes collection."""
        if not self.available:
            return 0
        return int(self.dy_likes_collection.count())
