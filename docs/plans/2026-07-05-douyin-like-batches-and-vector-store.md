# 2026-07-05 抖音喜欢分批导入与本地向量库状态

本文记录本地 `D:\BiliClaw` 实例对第一个抖音账号的喜欢/收藏导入、续跑 checkpoint、已知问题和本地向量库接入状态。

## 当前范围

- 当前只继续处理第一个/当前浏览器登录的抖音账号。
- 第二个抖音账号和小红书喜欢/收藏今天暂停，不继续抓取。
- 目标是把第一个抖音账号的喜欢慢速分批导入画像，并且每一批都能从上一次位置继续。

## 本地数据状态

截至 2026-07-05 12:03 左右，本地事件层和 `source_bootstrap_state.json` 中已经记录：

- `dy_like`: 595 条。
- `dy_collect`: 946 条。
- `dy_follow`: 3 条。

当前 `dy_like` checkpoint：

- `seen_count`: 595。
- `last_batch_new_count`: 8。
- `last_task_id`: `b7713354-84e9-4a0b-91c5-0a80e0fb5264`。
- `last_aweme_id`: `7414772484764945702`。
- `api_error`: `HTTP 404`，表示本轮主动 API 抓取不可用，实际依赖页面/DOM 抓取和已见 key 跳过。

## 已验证的续跑方式

后端下发 `bootstrap_profile` 任务时，如果 payload 带：

```json
{
  "scopes": ["dy_like"],
  "max_items_per_scope": 5000,
  "max_new_items_per_scope": 100,
  "max_scroll_rounds": 30,
  "max_stagnant_scroll_rounds": 15,
  "skip_existing_bootstrap_keys": true
}
```

后端会从 `source_bootstrap_state.json` 取出已经处理过的 `dy_like:*` key，并以 `skip_item_keys` 下发给扩展。扩展新版本会：

- 跳过已处理 key。
- 已处理 key 不占用 `max_new_items_per_scope` 新增名额。
- 在 debug 中返回 `skip_item_key_count`、`skipped_existing_items`、`max_new_items_per_scope`。

2026-07-05 的验证批次中：

- `skip_item_key_count = 587`，说明扩展已加载新 bundle。
- `skipped_existing_items = 2866`，说明已处理条目被跳过。
- 本批新增 8 条喜欢，`dy_like` 从 587 增至 595。

## 已修复的问题

1. 扩展未重载时，任务会重复从顶部扫描，debug 中没有 `skip_item_key_count`。现在需要确认扩展已加载新 bundle；若没有，手动在 `chrome://extensions` 刷新 OpenBiliClaw 扩展。
2. `DyTaskQueue.fail()` 原来会在任务超时时把已有 partial 结果覆盖成 `{ "error": "task_timeout" }`。现在改为保留已抓到的 `videos`、`scope_counts` 和 `debug`，只追加失败原因。
3. 后端 checkpoint 写入调整到 profile update 之前，避免 profile update 失败后事件已传播但 checkpoint 没保存。
4. YouTube task handler 中误粘贴的抖音向量库写入代码已移除，避免 `added_videos` 未定义。
5. 扩展设置页的“本地扫描 & 向量化喜欢”按钮改为续跑任务，不再发起无 checkpoint 的全量重扫。

## 本地向量库

本地向量库作为可重建索引，不替代 SQLite 事件层。真实事实仍以 `data/openbiliclaw.db` 和 `data/memory/source_bootstrap_state.json` 为准。

已接入：

- 依赖：`chromadb>=0.4`。
- 模块：`src/openbiliclaw/memory/vector_store.py`。
- 持久化目录：`data/vector_db`。
- collection：`dy_likes`。
- 运行时优先跟随 `[llm.embedding]`：当 provider 为 `ollama` 时，使用该段的 `model` 和 `base_url`。
- 当前 setup 可选择本机或服务器 embedding；选择服务器时可使用 `qwen3-embedding:8b` 和服务器 Ollama 地址。
- 未注入配置时的默认 embedding：Ollama `qwen3-embedding:8b`。
- 未注入配置时的默认 Ollama host：`http://127.0.0.1:11434`。
- 未注入配置时可用环境变量覆盖：
  - `OPENBILICLAW_VECTOR_OLLAMA_MODEL`
  - `OPENBILICLAW_VECTOR_OLLAMA_HOST`

数据流：

1. 扩展上报 `dy_like`。
2. 后端 dedupe，确认是新喜欢。
3. SQLite 事件层和画像管线照常写入。
4. 后端后台线程把新 `dy_like` 批量 upsert 到 ChromaDB。
5. ChromaDB/Ollama 失败只记录 warning，不阻断导入。

## 尚未完成

- 远程重度推荐分析接口目前只返回“尚未接入”。下一阶段应从 `dy_likes` collection 做 Top-K 检索，再把检索结果作为 context 发给服务器上的 `qwen3:30b`。
- 抖音主动 API 抓取当前返回 `HTTP 404`，还不能依赖 cursor 直接翻页；当前可用方案是扩展页面抓取 + 已见 key 跳过。
- 第二个抖音账号的数据隔离和小红书喜欢/收藏导入暂停。

## 下次继续

下次继续第一个抖音账号喜欢导入时，直接排同样的 `dy_like` 续跑任务即可。成功的一批应看到：

- `skip_item_key_count` 等于当前已见 `dy_like` 数量。
- `dy_bootstrap_like` 对应事件数量继续增长。
- `source_bootstrap_state.json` 的 `dy_scope_progress.dy_like.seen_count` 同步增长。

## 2026-07-05 追加：任务页超时与多账号隔离

- 页面“运行一会自己消失”的根因是扩展后台把抖音导入页当成临时任务页，任务超时后 `cleanupTask()` 会执行 `chrome.tabs.remove()`。现在已改为：`bootstrap_profile` 前台导入任务超时时保留抖音页面，搜索/热点/feed 等后台临时页仍自动清理。
- 抖音喜欢很多时，原来的超时预算按 `scope_count * max_scroll_rounds * 3s + 30s` 计算；当前 `dy_like` 单 scope、30 轮只有约 120 秒，容易在大量旧喜欢需要跳过时超时。现在 bootstrap 任务改为每滚动轮 10 秒，并按 `skip_item_keys` 数量追加预算，最高 20 分钟。
- 多账号不是并发抓取。正确流程是：同一个后端实例支持多个账号槽位；当前浏览器登录第一个账号时排 `account_id=primary` 任务，切到第二个抖音账号或另一个浏览器 Profile 后排 `account_id=account2` 任务。
- `source_bootstrap_state.json` 新增 `dy_accounts.<account_id>`。每个抖音账号都有独立的 `dy_seen_video_keys` 和 `dy_scope_progress`，第二个账号不会被第一个账号的已见 key 跳过。旧的顶层 `dy_seen_video_keys` / `dy_scope_progress` 继续镜像 `primary`，兼容旧代码和旧文档。
- 画像事件和向量库 metadata 现在写入 `source_account_id` / `account_id`。`primary` 继续使用旧向量 doc id；非 primary 账号使用 `<account_id>:<aweme_id>`，避免两个账号喜欢同一个视频时互相覆盖。

继续第一个账号时使用 `account_id=primary`；切换到第二个账号后使用 `account_id=account2`。两个账号会分别续跑，但最终都会进入同一个总画像。

## 2026-07-05 17:21-17:27 续跑记录

- 已重新加载一次扩展后，排入 `primary` 的 `dy_like` 续跑任务 `7367bed3-74ea-47e7-bd26-93848247f77c`。任务完成，页面没有再被超时清理；扩展采到 660 个页面条目，后端去重后实际新增 90 条喜欢。
- 第一批完成后，`dy_accounts.primary.dy_scope_progress.dy_like.seen_count` 从 624 增至 714；`last_aweme_id=7650818979431314875`，`last_batch_new_count=90`。
- 继续排入第二批 `e75ad33e-4902-4b45-b40c-1fcc96ecd67b`。任务完成，扩展采到 195 个页面条目，后端去重后实际新增 8 条喜欢。
- 第二批完成后，`dy_accounts.primary.dy_scope_progress.dy_like.seen_count` 增至 722；`last_aweme_id=7572532507057409299`，`last_batch_new_count=8`。
- SQLite `events` 表中抖音 `like` 事件总数为 722，最近新增记录均带 `source_platform=douyin`、`source_account_id=primary`、`account_id=primary`。
- 本地 ChromaDB 持久化目录为 `data/vector_db`，collection 为 `dy_likes`，当前向量文档数为 107；向量库使用本机 Ollama `qwen3-embedding:8b`，embedding dimension 为 4096。

## 2026-07-05 追加修复：浏览器端 skip 未生效

第二批只新增 8 条，暴露出一个续跑效率问题：后台已经把 `skip_item_keys` 发送给 content script，但 `runScope()` 创建 `BootstrapItemSink` 时没有传入 `msg.skip_item_keys`，导致浏览器端没有真正跳过已处理喜欢，只能依赖后端最终去重。因此每一批都会重新扫描大量顶部旧内容。

已修复为：

- `ScopeExecuteMessage` 显式声明 `max_new_items_per_scope` 和 `skip_item_keys`。
- `runScope()` 创建 `BootstrapItemSink` 时传入 `skipItemKeys`。
- `BootstrapItemSink` 的容量改用 `max_new_items_per_scope`，让已处理条目不占用本批新增名额。
- scroll 停止条件也按本批新增数判断；`max_items_per_scope=5000` 继续表示“最多看多少页面条目”，`max_new_items_per_scope=100` 表示“本批最多收多少新喜欢”。
- 调试信息增加 `skipped_existing`，后续验证时应能看到浏览器端跳过数量。

注意：该修复在扩展 `0.3.154` bundle 中，继续跑下一批前需要在 `chrome://extensions` 重新加载 OpenBiliClaw，使 Chrome 使用新的 content script 和 service worker。

## 2026-07-05 追加修复：复用抖音导入页和滚动位置

问题：即使浏览器端已经能按 `skip_item_keys` 跳过旧喜欢，旧实现仍然会在每一批完成后清理任务页签，下一批重新打开 `https://www.douyin.com/`，然后 content script 再点击进入“我 / 喜欢”。这会让页面从顶部重新加载，喜欢很多时需要反复跳过大量旧条目，实际不可持续。

本次修复：

- `bootstrap_profile` 任务完成后继续保留前台抖音导入页签，并把页签 ID 写入 `chrome.storage.session`。
- 下一批 `bootstrap_profile` 任务优先复用这个页签，而不是重新打开主页。
- 如果刚重载扩展导致 `chrome.storage.session` 中没有旧页签 ID，后台会主动查找已打开的 `douyin.com` 页签，并优先选择 `/user/...?...showTab=like` 这类 profile tab。
- content script 新增当前 scope route 判定：如果页面已经在 `/user/...?...showTab=like`，就不再重新点击“喜欢”，直接继续当前页面上的滚动与采集。
- 浏览器关闭、扩展重载、用户手动关闭该抖音页签，或 Douyin 自己刷新/虚拟列表回收时，仍可能失去滚动上下文；这种情况下会自动退回新开页签，并继续依靠已见 key 跳过旧条目。

版本：该修复随扩展 `0.3.155` 打包。继续跑下一批前需要在 `chrome://extensions` 重新加载 OpenBiliClaw，确认版本显示为 `0.3.155`。

截至本次修复前的最新本地状态：

- 第一个抖音账号 `primary` 的 `dy_like.seen_count` 已到 840。
- SQLite 中抖音 `like` 事件数为 840。
- 本地 ChromaDB `dy_likes` 向量文档数为 225。
- 最近一批任务为 `13709578-2711-4f34-b253-6c7331e8e363`，本批新增 8 条，`skipped_existing=4397`，仍说明当前可用路径是页面/DOM 抓取加已见 key 跳过；主动 API 仍返回 `HTTP 404`。

## 2026-07-05 18:30 续跑记录与 task-result 卡顿修复

- 排入 `primary` 的 `dy_like` 续跑任务 `3925f368-4ac0-4e4c-bc4b-20544885ffc0`，payload 使用 `skip_existing_bootstrap_keys=true`、`max_new_items_per_scope=100`、`max_scroll_rounds=60`。
- 本批 partial 已成功写入 8 条新喜欢，`dy_accounts.primary.dy_scope_progress.dy_like.seen_count` 从 840 增至 848，SQLite `events` 表中抖音 `like` 事件数同步增至 848。
- 本批 debug 显示 `skipped_existing=7958`、`dom_items_harvested=8`、`fetch_tap_install_status=installed`，主动 API 仍返回 `HTTP 404`，当前仍依赖页面/DOM 抓取加已见 key 跳过。
- 本批暴露出后端 ack 卡顿：partial 结果入库后，`/api/sources/dy/task-result` 同步等待 `ProfileUpdatePipeline` 调用画像 LLM；当 Ollama 连接失败时，扩展会等待该 HTTP 请求返回，导致 final ok 延迟。
- 后端已改为：task-result 在事件/向量入库后立即返回，增量画像更新通过后台任务 best-effort 执行；即使画像 LLM 暂时不可用，也不会阻塞扩展继续滚动或提交 final ok。

## 2026-07-05 18:47 复用页签后的 content script 断连记录

- 热重载扩展后继续排入 `a0ae2dca-6383-42f0-a39c-c133249708a8`，dispatcher 已成功复用原抖音喜欢页签：debug 出现 `executeTask:tab_reused`，`tabId=910917706`。
- 本批没有新增数据，原因不是后端 checkpoint 或去重，而是 Chrome 扩展热重载会让旧页面里的 content script 失效；复用页签后 `sendMessage` 返回 `Receiving end does not exist`，后端记录为 `sendMessage_failed`。
- 修复随扩展 `0.3.156`：bootstrap 任务在复用/新开抖音页签后会显式注入 `dist/content/douyin.js`，再注入 `dist/main/dy-fetch-tap.js`；content script 自身增加注册哨兵，避免重复注入造成多份监听器。
- 继续跑下一批前需要热重载或手动重载 OpenBiliClaw 扩展到 `0.3.156`。
