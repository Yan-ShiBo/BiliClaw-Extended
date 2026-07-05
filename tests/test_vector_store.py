from __future__ import annotations

from typing import Any

from openbiliclaw.memory import vector_store
from openbiliclaw.memory.vector_store import (
    OllamaEmbeddingFunction,
    VectorStoreManager,
)


class FakeCollection:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.upserts.append(
            {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
        )

    def query(self, *, query_texts: list[str], n_results: int) -> dict[str, Any]:
        return {"query_texts": query_texts, "n_results": n_results}

    def count(self) -> int:
        return len(self.upserts)


class FakeClient:
    def __init__(self, path: str) -> None:
        self.path = path
        self.collection = FakeCollection()

    def get_or_create_collection(self, **_kwargs: Any) -> FakeCollection:
        return self.collection


def test_ollama_embedding_function_normalizes_openai_shim_url() -> None:
    fn = OllamaEmbeddingFunction(host="http://10.0.0.5:11434/v1")

    assert fn.host == "http://10.0.0.5:11434"


def test_vector_store_upserts_douyin_like_videos(
    tmp_path,
    monkeypatch,
) -> None:
    fake_client: FakeClient | None = None

    def make_client(path: str) -> FakeClient:
        nonlocal fake_client
        fake_client = FakeClient(path)
        return fake_client

    monkeypatch.setattr(vector_store.chromadb, "PersistentClient", make_client)
    manager = VectorStoreManager(tmp_path, embedding_model="test-embed", ollama_host="http://x")

    count = manager.upsert_dy_like_videos(
        [
            {
                "scope": "dy_like",
                "aweme_id": "aweme-1",
                "title": "萌宠搞笑",
                "author": "creator",
                "url": "https://www.douyin.com/video/aweme-1",
                "cover_url": None,
            },
            {
                "scope": "dy_collect",
                "aweme_id": "collect-1",
                "title": "收藏不进 likes 向量库",
            },
        ]
    )

    assert count == 1
    assert fake_client is not None
    assert fake_client.collection.upserts == [
        {
            "ids": ["aweme-1"],
            "documents": ["萌宠搞笑\ncreator"],
            "metadatas": [
                {
                    "aweme_id": "aweme-1",
                    "url": "https://www.douyin.com/video/aweme-1",
                    "author": "creator",
                    "author_sec_uid": "",
                    "creator_sec_uid": "",
                    "cover_url": "",
                    "source_platform": "douyin",
                    "import_source": "dy_bootstrap_like",
                }
            ],
        }
    ]


def test_vector_store_upserts_douyin_like_events(
    tmp_path,
    monkeypatch,
) -> None:
    fake_client: FakeClient | None = None

    def make_client(path: str) -> FakeClient:
        nonlocal fake_client
        fake_client = FakeClient(path)
        return fake_client

    monkeypatch.setattr(vector_store.chromadb, "PersistentClient", make_client)
    manager = VectorStoreManager(tmp_path)

    inserted = manager.upsert_dy_like_event(
        {
            "event_type": "like",
            "title": "AI 绘画技巧",
            "context": "抖音点赞：AI 绘画技巧",
            "url": "https://www.douyin.com/video/42",
            "metadata": {
                "source_platform": "douyin",
                "import_source": "dy_bootstrap_like",
                "aweme_id": "42",
                "signal_strength": 0.85,
            },
        }
    )

    assert inserted is True
    assert fake_client is not None
    assert fake_client.collection.upserts[0]["ids"] == ["42"]
    assert fake_client.collection.upserts[0]["documents"] == [
        "AI 绘画技巧\n抖音点赞：AI 绘画技巧"
    ]
    assert fake_client.collection.upserts[0]["metadatas"][0]["signal_strength"] == 0.85
