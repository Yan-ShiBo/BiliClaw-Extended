# Recommendation Refresh Operations

This is the current operating playbook for rebuilding profile and recommendations after large platform imports.

## Purpose

After importing a large first Douyin account plus smaller second Douyin, Xiaohongshu, and Bilibili signals, the system should:

1. Keep the imported events and vectors.
2. Rebuild the Soul profile with the current source weighting policy.
3. Drain or stale old recommendation candidates that were generated before the new profile.
4. Refresh the candidate pool with the desired source mix.
5. Use the server LLM only when analysis or card reasoning needs it.
6. Unload the server LLM afterward to free GPU memory.

## Pre-flight

```powershell
Invoke-WebRequest http://127.0.0.1:8420/api/health
Invoke-WebRequest http://127.0.0.1:8420/api/runtime-status
```

Make a local backup before destructive runtime operations:

```powershell
Copy-Item data data\backups\runtime-profile-recommend-YYYYMMDD-HHMMSS -Recurse
```

Do not commit the backup.

## Refresh Steps

1. Ensure `config.toml` points chat LLM to the server Ollama model when heavy analysis is needed.
2. Keep embedding pointed to local Ollama unless there is a specific reason to use server embedding.
3. Run or trigger profile analysis.
4. Mark old recommendation pool entries stale if the visible recommendations were generated before the new profile.
5. Run recommendation/candidate refresh.
6. Verify `/api/recommendations` returns new unread items.
7. Open `/web` and confirm the visible cards changed.
8. Unload or stop the server model if GPU memory should be released.

## Verification Endpoints

- `/api/health`: backend and configured service status.
- `/api/runtime-status`: scheduler, initialization, and runtime state.
- `/api/recommendations`: current card output.
- `/web`: user-facing recommendation page.

## Known Issues Encountered

| Issue | Handling |
| --- | --- |
| Douyin liked page consumed too much browser memory | Stop the endless page, keep the already imported sample, continue with other sources |
| Douyin risk-control signs after long scrolling | Pause import and resume later rather than force more requests |
| Recommendations appeared unchanged after profile refresh | Old fresh pool was still available; stale/drain old candidates before refilling |
| Server Ollama held GPU memory after use | Unload model or stop Ollama when analysis is done |
| Multiple sources had very different sample sizes | Added `analysis_weight` to rebalance during preference analysis |

## Current Runtime Snapshot

The latest verified local run used:

- Backend: `http://127.0.0.1:8420`
- Extension: `0.3.159`
- Embedding: local `qwen3-embedding:8b`
- Heavy LLM: server Ollama model on demand
- Recommendation check: `/api/recommendations` returned 10 unread cards after refresh

Runtime data is local-only and is not part of the GitHub commit.
