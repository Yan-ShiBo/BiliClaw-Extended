# Multi-source Profile and Weighting

This document explains how BiliClaw Extended combines signals from Douyin, Bilibili, Xiaohongshu, YouTube, and X.

## Source Priority

Current user preference:

| Priority | Sources |
| --- | --- |
| Primary | Douyin, Bilibili |
| Secondary | YouTube, Xiaohongshu |
| Supplemental | X |

Priority affects discovery and review focus, not data ownership. All imported data remains local.

## Two Douyin Accounts

Two Douyin accounts are supported in one backend instance, but they are processed separately:

1. Login to account 1 in the browser.
2. Import likes, collections, follows, and posts.
3. Switch to account 2, or use another browser profile.
4. Import the same task types again.

The backend records source/account metadata and analyzes them together later. It does not require both accounts to be logged in at the same time.

## Douyin Likes and Vector Store

Douyin likes can be large. The current ingestion path is:

1. Browser extension scrolls and reads the liked-video page.
2. Backend stores each item as an event in SQLite.
3. Backend builds a text representation from title, description, tags, author, and source metadata.
4. Local Ollama `qwen3-embedding:8b` embeds the text.
5. ChromaDB stores vectors under `data/vector_db`.

Batch import should resume from prior progress where possible. Very long Douyin pages may hit browser memory pressure or platform risk control, so imports should be split into batches.

## Xiaohongshu Likes and Collections

Xiaohongshu is handled through the extension in a logged-in tab. It should be imported after Douyin if the current goal is to finish one platform before moving to the next. Scan depth is larger in extension `0.3.159`, but the same risk-control rule applies: do not force endless scrolling when the page becomes unstable.

## Weighted Analysis

`PreferenceAnalyzer` writes `metadata.analysis_weight` into compact event metadata. The prompt explicitly tells the LLM to treat this as source-balancing metadata.

Current policy:

| Input | Weighting intent |
| --- | --- |
| First Douyin account | Keep as the largest evidence base, but apply mild time decay to old likes |
| Second Douyin account | Slightly boost so it is visible despite fewer samples |
| Bilibili | Slightly boost because it is a primary source |
| Xiaohongshu | Slightly boost because the sample is usually smaller |
| YouTube | Neutral unless source mix config changes |
| X | Neutral supplemental signal |

The goal is not to fabricate preferences. The goal is to prevent one very large import from hiding smaller but meaningful signals.

## When Recommendations Do Not Change

If profile analysis finishes but `/web` recommendations look unchanged, check:

- Old fresh candidates may still be in the pool.
- The frontend may be showing unread cached cards generated before the new profile.
- The recommendation pool may need a refresh after marking old candidates stale.
- Server LLM may have been unloaded before card reasoning ran.

The operations playbook is documented in [recommendation-refresh.md](../operations/recommendation-refresh.md).
