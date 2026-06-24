/**
 * Zhihu content-script executor for fetch-only bootstrap_events tasks.
 *
 * Runs inside zhihu.com with the user's active browser session, so requests use
 * `credentials: "include"` without exporting cookies to the backend.
 */

export type ZhihuScope = "zhihu_read_history" | "zhihu_activity" | "zhihu_collection";

export interface ZhihuBootstrapItem {
  scope: ZhihuScope;
  content_type: string;
  content_id: string;
  title: string;
  author: string;
  url: string;
  question_id?: string;
  summary?: string;
  interaction_action?: string;
  interaction_time?: string;
  voteup?: number;
  collection_id?: string;
  collection_name?: string;
}

export interface ZhihuExecuteMessage {
  task_id: string;
  scopes?: ZhihuScope[];
  profile_slug?: string;
  max_items_per_scope?: number;
  max_collections?: number;
}

export interface ZhihuTaskResult {
  task_id: string;
  status: "ok" | "empty" | "failed";
  items: ZhihuBootstrapItem[];
  scope_counts: Record<string, number>;
  error?: string;
  debug?: Record<string, unknown>;
}

interface ZhihuCollectionMeta {
  id: string;
  name: string;
}

const DEFAULT_SCOPES: readonly ZhihuScope[] = [
  "zhihu_read_history",
  "zhihu_collection",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function str(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function num(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}

function absoluteZhihuUrl(url: string): string {
  if (!url) return "";
  if (url.startsWith("//")) return `https:${url}`;
  if (url.startsWith("/")) return `https://www.zhihu.com${url}`;
  return url;
}

function answerUrl(questionId: string, answerId: string): string {
  return questionId && answerId
    ? `https://www.zhihu.com/question/${questionId}/answer/${answerId}`
    : "";
}

function articleUrl(articleId: string, fallback = ""): string {
  if (fallback.includes("zhuanlan.zhihu.com/p/")) return fallback.split("?")[0]!;
  return articleId ? `https://zhuanlan.zhihu.com/p/${articleId}` : fallback;
}

export function normalizeZhihuReadHistory(raw: unknown): ZhihuBootstrapItem | null {
  const row = asRecord(raw);
  const data = asRecord(row.data);
  const header = asRecord(data.header);
  const content = asRecord(data.content);
  const action = asRecord(data.action);
  const extra = asRecord(data.extra);

  const contentType = str(extra.content_type);
  const contentId = str(extra.content_token);
  const questionId = str(extra.question_token);
  const title = str(header.title) || str(content.title) || str(content.summary) || contentId;
  const url = absoluteZhihuUrl(str(action.url));
  if (!contentType || !contentId || (!title && !url)) return null;

  const item: ZhihuBootstrapItem = {
    scope: "zhihu_read_history",
    content_type: contentType,
    content_id: contentId,
    title,
    author: str(content.author_name),
    url,
  };
  if (questionId) item.question_id = questionId;
  const summary = str(content.summary);
  if (summary) item.summary = summary;
  const readTime = str(extra.read_time);
  if (readTime) item.interaction_time = readTime;
  return item;
}

export function normalizeZhihuActivity(raw: unknown): ZhihuBootstrapItem | null {
  const activity = asRecord(raw);
  const action = str(activity.action_text) || str(activity.verb) || str(activity.action);
  if (!action.startsWith("赞同了") && !action.startsWith("喜欢了") && !action.startsWith("收藏了")) {
    return null;
  }

  const target = asRecord(activity.target);
  const contentType = str(target.type);
  if (contentType !== "answer" && contentType !== "article") return null;
  const contentId = str(target.id);
  if (!contentId) return null;

  const question = asRecord(target.question);
  const questionId = str(question.id);
  const fallbackUrl = absoluteZhihuUrl(str(target.url));
  const url =
    contentType === "answer"
      ? answerUrl(questionId, contentId)
      : articleUrl(contentId, fallbackUrl);
  if (!url) return null;

  const author = asRecord(target.author);
  const title =
    contentType === "answer"
      ? str(question.title) || `answer_${contentId}`
      : str(target.title) || `article_${contentId}`;

  const item: ZhihuBootstrapItem = {
    scope: "zhihu_activity",
    content_type: contentType,
    content_id: contentId,
    title,
    author: str(author.name),
    url,
    interaction_action: action,
  };
  if (questionId) item.question_id = questionId;
  const voteup = num(target.voteup_count);
  if (voteup !== undefined) item.voteup = voteup;
  const activityId = str(activity.id);
  if (activityId) item.interaction_time = activityId;
  return item;
}

export function normalizeZhihuCollectionItem(
  raw: unknown,
  collection: ZhihuCollectionMeta,
): ZhihuBootstrapItem | null {
  const row = asRecord(raw);
  const content = asRecord(row.content || raw);
  const contentType = str(content.type);
  if (contentType !== "answer" && contentType !== "article") return null;
  const contentId = str(content.id);
  if (!contentId) return null;

  const question = asRecord(content.question);
  const questionId = str(question.id);
  const fallbackUrl = absoluteZhihuUrl(str(content.url));
  const url =
    contentType === "answer"
      ? answerUrl(questionId, contentId) || fallbackUrl
      : articleUrl(contentId, fallbackUrl);
  if (!url) return null;

  const author = asRecord(content.author);
  const title =
    contentType === "answer"
      ? str(question.title) || str(content.title) || `answer_${contentId}`
      : str(content.title) || `article_${contentId}`;

  const item: ZhihuBootstrapItem = {
    scope: "zhihu_collection",
    content_type: contentType,
    content_id: contentId,
    title,
    author: str(author.name),
    url,
    collection_id: collection.id,
    collection_name: collection.name,
  };
  if (questionId) item.question_id = questionId;
  const summary = str(content.excerpt) || str(content.summary);
  if (summary) item.summary = summary;
  const voteup = num(content.voteup_count);
  if (voteup !== undefined) item.voteup = voteup;
  return item;
}

async function fetchJson(url: string): Promise<Record<string, unknown>> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return asRecord(await response.json());
}

async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.text();
}

async function fetchReadHistory(maxItems: number): Promise<ZhihuBootstrapItem[]> {
  const out: ZhihuBootstrapItem[] = [];
  let offset = 0;
  const limit = 20;
  for (let i = 0; i < 20 && out.length < maxItems; i++) {
    const payload = await fetchJson(
      `/api/v4/unify-consumption/read_history?offset=${offset}&limit=${limit}`,
    );
    const data = Array.isArray(payload.data) ? payload.data : [];
    for (const row of data) {
      const item = normalizeZhihuReadHistory(row);
      if (item) out.push(item);
      if (out.length >= maxItems) break;
    }
    const paging = asRecord(payload.paging);
    if (paging.is_end === true || data.length === 0) break;
    offset += limit;
  }
  return out;
}

async function fetchActivity(
  profileSlug: string,
  maxItems: number,
): Promise<ZhihuBootstrapItem[]> {
  if (!profileSlug) return [];
  const out: ZhihuBootstrapItem[] = [];
  let nextUrl = `/api/v3/moments/${encodeURIComponent(profileSlug)}/activities?limit=10&desktop=true&ws_qiangzhisafe=0`;
  for (let i = 0; i < 40 && out.length < maxItems && nextUrl; i++) {
    const payload = await fetchJson(nextUrl);
    const data = Array.isArray(payload.data) ? payload.data : [];
    for (const row of data) {
      const item = normalizeZhihuActivity(row);
      if (item) out.push(item);
      if (out.length >= maxItems) break;
    }
    const paging = asRecord(payload.paging);
    if (paging.is_end === true || data.length === 0) break;
    nextUrl = str(paging.next);
  }
  return out;
}

function extractCollectionsFromHtml(html: string, maxCollections: number): ZhihuCollectionMeta[] {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const seen = new Set<string>();
  const collections: ZhihuCollectionMeta[] = [];
  const anchors = Array.from(doc.querySelectorAll<HTMLAnchorElement>('a[href*="/collection/"]'));
  for (const anchor of anchors) {
    const match = anchor.href.match(/\/collection\/(\d+)/);
    const id = match?.[1] ?? "";
    if (!id || seen.has(id)) continue;
    seen.add(id);
    collections.push({ id, name: (anchor.textContent ?? "").trim() || `collection_${id}` });
    if (collections.length >= maxCollections) break;
  }
  return collections;
}

async function fetchCollections(
  maxItems: number,
  maxCollections: number,
): Promise<ZhihuBootstrapItem[]> {
  const all: ZhihuBootstrapItem[] = [];
  const collections: ZhihuCollectionMeta[] = [];
  for (let page = 1; page <= 20 && collections.length < maxCollections; page++) {
    const html = await fetchText(`/collections/mine?page=${page}`);
    const pageCollections = extractCollectionsFromHtml(html, maxCollections - collections.length);
    if (pageCollections.length === 0) break;
    collections.push(...pageCollections);
  }

  for (const collection of collections) {
    let offset = 0;
    const limit = 20;
    for (let i = 0; i < 20 && all.length < maxItems; i++) {
      const payload = await fetchJson(
        `/api/v4/collections/${collection.id}/items?offset=${offset}&limit=${limit}`,
      );
      const data = Array.isArray(payload.data) ? payload.data : [];
      for (const row of data) {
        const item = normalizeZhihuCollectionItem(row, collection);
        if (item) all.push(item);
        if (all.length >= maxItems) break;
      }
      const paging = asRecord(payload.paging);
      if (paging.is_end === true || data.length === 0) break;
      offset += limit;
    }
    if (all.length >= maxItems) break;
  }
  return all;
}

function dedupeItems(items: ZhihuBootstrapItem[]): ZhihuBootstrapItem[] {
  const seen = new Set<string>();
  const out: ZhihuBootstrapItem[] = [];
  for (const item of items) {
    const key = `${item.scope}:${item.content_type}:${item.content_id || item.url}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function countItems(items: ZhihuBootstrapItem[]): Record<string, number> {
  const counts: Record<string, number> = {
    zhihu_read_history: 0,
    zhihu_collection: 0,
    zhihu_activity_like: 0,
    zhihu_activity_favorite: 0,
  };
  for (const item of items) {
    if (item.scope === "zhihu_read_history") counts.zhihu_read_history += 1;
    if (item.scope === "zhihu_collection") counts.zhihu_collection += 1;
    if (item.scope === "zhihu_activity") {
      const action = item.interaction_action ?? "";
      if (action.startsWith("赞同了") || action.startsWith("喜欢了")) {
        counts.zhihu_activity_like += 1;
      }
      if (action.startsWith("收藏了")) counts.zhihu_activity_favorite += 1;
    }
  }
  return counts;
}

export async function executeZhihuTask(msg: ZhihuExecuteMessage): Promise<ZhihuTaskResult> {
  const taskId = msg.task_id;
  const scopes = msg.scopes && msg.scopes.length > 0 ? msg.scopes : [...DEFAULT_SCOPES];
  const maxItems = Math.max(1, Math.floor(msg.max_items_per_scope ?? 300));
  const maxCollections = Math.max(1, Math.floor(msg.max_collections ?? 20));
  const items: ZhihuBootstrapItem[] = [];
  const debug: Record<string, unknown> = {};

  try {
    if (scopes.includes("zhihu_read_history")) {
      const rows = await fetchReadHistory(maxItems);
      debug.zhihu_read_history = rows.length;
      items.push(...rows);
    }
    if (scopes.includes("zhihu_activity")) {
      const rows = await fetchActivity(str(msg.profile_slug), maxItems);
      debug.zhihu_activity = rows.length;
      items.push(...rows);
    }
    if (scopes.includes("zhihu_collection")) {
      const rows = await fetchCollections(maxItems, maxCollections);
      debug.zhihu_collection = rows.length;
      items.push(...rows);
    }
    const deduped = dedupeItems(items).slice(0, maxItems * scopes.length);
    return {
      task_id: taskId,
      status: deduped.length > 0 ? "ok" : "empty",
      items: deduped,
      scope_counts: countItems(deduped),
      debug,
    };
  } catch (error) {
    return {
      task_id: taskId,
      status: "failed",
      items: [],
      scope_counts: countItems([]),
      error: error instanceof Error ? error.message : String(error),
      debug,
    };
  }
}

export function installZhihuMessageListener(): void {
  chrome.runtime.onMessage.addListener(
    (
      message: { action?: string; data?: ZhihuExecuteMessage },
      _sender,
      sendResponse,
    ) => {
      if (message.action !== "ZHIHU_BOOTSTRAP_EXECUTE") return false;
      void executeZhihuTask(message.data as ZhihuExecuteMessage).then((result) => {
        chrome.runtime.sendMessage({ action: "ZHIHU_TASK_RESULT", data: result });
        sendResponse({ ok: true });
      });
      return true;
    },
  );
}
