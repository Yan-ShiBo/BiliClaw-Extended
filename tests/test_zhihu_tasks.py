"""Tests for Zhihu bootstrap task helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from openbiliclaw.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_zhihu_bootstrap_items_to_events_maps_history_activity_and_collections() -> None:
    from openbiliclaw.sources.zhihu_tasks import zhihu_bootstrap_items_to_events

    events = zhihu_bootstrap_items_to_events(
        [
            {
                "scope": "zhihu_read_history",
                "title": "最近浏览回答",
                "url": "https://www.zhihu.com/question/1/answer/2",
                "content_type": "answer",
                "content_id": "2",
                "author": "作者 A",
            },
            {
                "scope": "zhihu_activity",
                "interaction_action": "赞同了回答",
                "title": "赞同回答",
                "url": "https://www.zhihu.com/question/3/answer/4",
                "content_type": "answer",
                "content_id": "4",
                "author": "作者 B",
            },
            {
                "scope": "zhihu_collection",
                "title": "收藏文章",
                "url": "https://zhuanlan.zhihu.com/p/5",
                "content_type": "article",
                "content_id": "5",
                "author": "作者 C",
                "collection_name": "我的收藏",
            },
        ]
    )

    assert [event["event_type"] for event in events] == ["view", "like", "favorite"]
    assert [event["metadata"]["source_platform"] for event in events] == [
        "zhihu",
        "zhihu",
        "zhihu",
    ]
    assert [event["metadata"]["import_source"] for event in events] == [
        "zhihu_bootstrap_read_history",
        "zhihu_bootstrap_activity_like",
        "zhihu_bootstrap_collection",
    ]


def test_zhihu_task_queue_claims_pending_task_until_terminal_status(
    database: Database,
) -> None:
    from openbiliclaw.sources.zhihu_tasks import ZhihuTaskQueue

    queue = ZhihuTaskQueue(database)
    task_id = queue.enqueue_with_id(
        "bootstrap_events",
        {"scopes": ["zhihu_read_history"], "max_items_per_scope": 20},
    )
    assert task_id is not None

    first = queue.next_pending()

    assert first is not None
    assert first["id"] == task_id
    assert first["status"] == "in_progress"
    assert queue.next_pending() is None

    queue.merge_result(task_id, items=[], complete=True)
    assert queue.next_pending() is None


def test_zhihu_task_queue_finds_recent_bootstrap_task(database: Database) -> None:
    from openbiliclaw.sources.zhihu_tasks import ZhihuTaskQueue

    queue = ZhihuTaskQueue(database)
    task_id = queue.enqueue_with_id("bootstrap_events", {"scopes": ["zhihu_read_history"]})
    assert task_id is not None

    recent = queue.find_recent_task("bootstrap_events", recent_hours=6)

    assert recent is not None
    assert recent["id"] == task_id
