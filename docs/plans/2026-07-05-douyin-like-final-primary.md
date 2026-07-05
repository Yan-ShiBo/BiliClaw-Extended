# 2026-07-05 Final Douyin Like Import: Primary Account

## Scope

- Account slot: `primary`.
- Browser page: `https://www.douyin.com/user/self?from_tab_name=main&showTab=like`.
- Paused by request: the second Douyin account and Xiaohongshu like/favorite import.
- Embedding path: local Ollama with `qwen3-embedding:8b`.
- Vector store: ChromaDB under `data/vector_db`, collection `dy_likes`.

## Final Result

The first Douyin account's currently browser-exposed liked videos were processed in batches and then confirmed with a zero-new follow-up task.

- Last non-empty task: `e7944cd5-36c9-4874-bea8-60bb63a49f0b`.
- Last non-empty batch size: 33 new `dy_like` items.
- Last recorded aweme id: `7508638477139856651`.
- Last batch timestamp: `2026-07-05T14:02:30.709043+00:00`.
- Confirmation task: `fcdb4f91-61f8-4ae3-bb74-20f00a27c829`.
- Confirmation result: 0 new videos, `scope_status=empty`, `dom_items_harvested=0`, `skipped_existing=210000`.

## Final Counts

- `dy_accounts.primary.dy_scope_progress.dy_like.seen_count`: 5099.
- `dy_like:*` seen keys in `source_bootstrap_state.json`: 5099.
- SQLite Douyin like events: 5099.
- Distinct Douyin `aweme_id` values in SQLite events: 5099.
- ChromaDB `dy_likes` documents: 5099.
- Missing vector documents after ID comparison: 0.
- Extra vector documents after ID comparison: 0.

## Backfill

After the page import reached the bottom, SQLite already contained all 5099 Douyin like events, but ChromaDB had only 4483 documents. The missing 616 vectors were older imports that were saved before vector upsert was fully active.

The missing vectors were backfilled from SQLite events into ChromaDB with local Ollama `qwen3-embedding:8b`, in chunks of 50, until the missing count reached 0.

## Known Limitations

- The direct Douyin API path still reports `HTTP 404`.
- The successful import used the logged-in browser page, fetch-tap capture, DOM extraction, and seen-key skipping.
- The zero-new confirmation means there were no more liked videos exposed by the current browser session at that time. It cannot prove private, deleted, hidden, or platform-withheld items that Douyin does not expose to the web session.
- Multi-account support is separate by `account_id`. The second Douyin account should be processed later as `account2` after logging into that account or using another browser profile.
