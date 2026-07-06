# BiliClaw Extended Documentation

This directory is split into current operating docs and historical archives. Current docs describe the repository as it runs today under `Yan-ShiBo/BiliClaw-Extended`; archived docs preserve old design discussions and upstream planning context.

## Current Docs

| Area | Document | Purpose |
| --- | --- | --- |
| Project overview | [README](../README.md) | Main Chinese project introduction and quick start |
| English overview | [README_EN](../README_EN.md) | Short English project introduction |
| Architecture | [architecture.md](architecture.md) | Current runtime modules and data flow |
| Product spec | [spec.md](spec.md) | Goals, requirements, source policy, and architecture diagram |
| Local setup | [setup/local-deployment.md](setup/local-deployment.md) | Windows local deployment, extension loading, Ollama setup |
| Multi-source profile | [features/multi-source-profile.md](features/multi-source-profile.md) | Douyin multi-account, XHS/Bilibili weighting, vector use |
| Recommendation operations | [operations/recommendation-refresh.md](operations/recommendation-refresh.md) | How the profile/recommendation refresh was run and verified |
| Soul module | [modules/soul.md](modules/soul.md) | Preference, profile, cognition, and weighting APIs |
| Config module | [modules/config.md](modules/config.md) | Config fields and runtime behavior |
| CLI module | [modules/cli.md](modules/cli.md) | CLI command reference |
| Extension module | [modules/extension.md](modules/extension.md) | Browser extension behavior and manual verification |
| Changelog | [changelog.md](changelog.md) | Active project change log |

## Runtime Folders

These folders are intentionally not committed:

- `data/`: SQLite database, ChromaDB vector store, profile JSON/Markdown snapshots.
- `logs/`: backend and task logs.
- `config.toml`: local credentials, model endpoints, platform toggles.
- `.tmp/`: one-off scripts, model download logs, and local operation scratch.

## Archive

- [archive/README.md](archive/README.md): archive policy.
- `archive/plans/`: historical implementation plans.
- `archive/superpowers/`: historical planning/review notes.
- `archive/changelogs/`: old upstream/full changelog snapshots.

Archived files are reference material. Do not treat them as the current deployment contract unless a current doc links to a specific archived decision.
