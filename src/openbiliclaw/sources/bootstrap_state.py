"""Shared state helpers for extension bootstrap source deduplication."""

from __future__ import annotations

from typing import Any

SOURCE_BOOTSTRAP_STATE_KEYS: dict[str, str] = {
    "xhs": "xhs_seen_note_keys",
    "xiaohongshu": "xhs_seen_note_keys",
    "dy": "dy_seen_video_keys",
    "douyin": "dy_seen_video_keys",
    "yt": "yt_seen_item_keys",
    "youtube": "yt_seen_item_keys",
    "zhihu": "zhihu_seen_item_keys",
    "zh": "zhihu_seen_item_keys",
}


def default_source_bootstrap_state() -> dict[str, object]:
    """Return the persisted-source bootstrap dedupe state shape."""
    return {
        "xhs_seen_note_keys": [],
        "dy_seen_video_keys": [],
        "dy_scope_progress": {},
        "yt_seen_item_keys": [],
        "zhihu_seen_item_keys": [],
        "last_source_bootstrap_sync_at": "",
    }


def source_bootstrap_state_key(source: str) -> str:
    """Return the state-list key for a short or platform source name."""
    normalized = str(source).strip().lower()
    try:
        return SOURCE_BOOTSTRAP_STATE_KEYS[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown source bootstrap state: {source}") from exc


def as_string_list(value: Any) -> list[str]:
    """Normalize a persisted list-like value into non-empty strings."""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _as_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(float(value)))
        except ValueError:
            return 0
    return 0


def normalize_dy_scope_progress(value: Any) -> dict[str, object]:
    """Normalize per-scope Douyin resumable bootstrap progress."""
    if not isinstance(value, dict):
        return {}
    progress: dict[str, object] = {}
    for raw_scope, raw_entry in value.items():
        scope = str(raw_scope).strip()
        if not scope or not isinstance(raw_entry, dict):
            continue
        entry = raw_entry
        normalized_entry: dict[str, object] = {
            "seen_count": _as_non_negative_int(entry.get("seen_count", 0)),
            "last_batch_new_count": _as_non_negative_int(
                entry.get("last_batch_new_count", 0)
            ),
            "last_scope_count": _as_non_negative_int(entry.get("last_scope_count", 0)),
            "last_key": str(entry.get("last_key", "")),
            "last_aweme_id": str(entry.get("last_aweme_id", "")),
            "last_task_id": str(entry.get("last_task_id", "")),
            "last_batch_at": str(entry.get("last_batch_at", "")),
            "end_of_feed": str(entry.get("end_of_feed", "")),
            "page_url": str(entry.get("page_url", "")),
            "api_error": str(entry.get("api_error", "")),
        }
        if "next_cursor" in entry:
            normalized_entry["next_cursor"] = _as_non_negative_int(entry.get("next_cursor", 0))
        progress[scope] = normalized_entry
    return progress


def normalize_source_bootstrap_state(loaded: Any) -> dict[str, object]:
    """Coerce arbitrary JSON into the stable source-bootstrap state shape."""
    default = default_source_bootstrap_state()
    if not isinstance(loaded, dict):
        return default
    return {
        "xhs_seen_note_keys": as_string_list(loaded.get("xhs_seen_note_keys", [])),
        "dy_seen_video_keys": as_string_list(loaded.get("dy_seen_video_keys", [])),
        "dy_scope_progress": normalize_dy_scope_progress(
            loaded.get("dy_scope_progress", {})
        ),
        "yt_seen_item_keys": as_string_list(loaded.get("yt_seen_item_keys", [])),
        "zhihu_seen_item_keys": as_string_list(loaded.get("zhihu_seen_item_keys", [])),
        "last_source_bootstrap_sync_at": str(loaded.get("last_source_bootstrap_sync_at", "")),
    }
