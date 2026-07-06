# Changelog

## v0.3.159: BiliClaw Extended documentation and identity cleanup (2026-07-06)

- Rewrote the Chinese and English README files for `Yan-ShiBo/BiliClaw-Extended`.
- Moved historical implementation plans and superpower planning notes under `docs/archive/`.
- Rebuilt the current documentation map, architecture document, project spec, Soul module document, local deployment guide, multi-source profile guide, and recommendation refresh operations guide.
- Updated repository metadata and extension/package versions to `0.3.159`.
- Preserved the previous long changelog as `docs/archive/changelogs/changelog-before-biliclaw-extended-docs.md`.

## v0.3.158: multi-source profile rebalancing (2026-07-06)

- Added `metadata.analysis_weight` into preference analysis so platform/account weighting is explicit and visible to prompts.
- Slightly increased Bilibili, Xiaohongshu, and secondary Douyin account contribution during profile analysis.
- Added a mild recency decay floor for the first Douyin account so old long-tail likes do not dominate the profile.
- Increased Xiaohongshu extension scan depth for small-but-complete account imports.
- Verified `PreferenceAnalyzer` with targeted Ruff, MyPy, and Pytest checks.

## v0.3.157: Douyin like vector ingestion baseline (2026-07-05)

- Added local ChromaDB persistence for Douyin liked-video vectors.
- Used local Ollama `qwen3-embedding:8b` for embedding by default.
- Documented batch scanning, resume behavior, browser memory pressure, and Douyin risk-control limits.
- Kept server LLM usage separate from embedding so heavy analysis can wait until the server model is available.

## Archive

Earlier upstream and planning history is kept under `docs/archive/`. Current user-facing behavior should be read from the root README and the active documents under `docs/`.
