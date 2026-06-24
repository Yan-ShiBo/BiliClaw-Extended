/**
 * Zhihu task dispatcher — background polling for fetch-only bootstrap_events.
 */

import type { ZhihuScope, ZhihuTaskResult } from "../content/zhihu/task-executor.js";
import { apiUrl } from "../shared/backend-endpoint.ts";

const _MUTEX_STALE_MS = 6 * 60 * 1000;
function tryAcquireDispatcherMutex(label: string): boolean {
  const g = globalThis as unknown as {
    __OBC_DISPATCHER_MUTEX_HOLDER__?: string;
    __OBC_DISPATCHER_MUTEX_HELD_SINCE__?: number;
  };
  if (g.__OBC_DISPATCHER_MUTEX_HOLDER__) {
    if (Date.now() - (g.__OBC_DISPATCHER_MUTEX_HELD_SINCE__ ?? 0) > _MUTEX_STALE_MS) {
      g.__OBC_DISPATCHER_MUTEX_HOLDER__ = undefined;
    } else {
      return false;
    }
  }
  g.__OBC_DISPATCHER_MUTEX_HOLDER__ = label;
  g.__OBC_DISPATCHER_MUTEX_HELD_SINCE__ = Date.now();
  return true;
}
function releaseDispatcherMutex(label: string): void {
  const g = globalThis as unknown as {
    __OBC_DISPATCHER_MUTEX_HOLDER__?: string;
    __OBC_DISPATCHER_MUTEX_HELD_SINCE__?: number;
  };
  if (g.__OBC_DISPATCHER_MUTEX_HOLDER__ === label) {
    g.__OBC_DISPATCHER_MUTEX_HOLDER__ = undefined;
    g.__OBC_DISPATCHER_MUTEX_HELD_SINCE__ = undefined;
  }
}

const DEFAULT_POLL_INTERVAL_MS = 60_000;
const POLL_ALARM_NAME = "openbiliclaw-zhihu-task-poll";
const DEFAULT_SCOPES: readonly ZhihuScope[] = [
  "zhihu_read_history",
  "zhihu_collection",
];
const BASE_TIMEOUT_MS = 45_000;
const PER_SCOPE_MS = 45_000;
const MAX_TIMEOUT_MS = 300_000;

export interface ZhihuTask {
  id: string;
  type: "bootstrap_events";
  scopes?: ZhihuScope[];
  profile_slug?: string;
  max_items_per_scope?: number;
  max_collections?: number;
}

export function isValidZhihuTask(task: unknown): task is ZhihuTask {
  if (typeof task !== "object" || task === null) return false;
  const t = task as Record<string, unknown>;
  if (typeof t.id !== "string" || !t.id) return false;
  if (t.type !== "bootstrap_events") return false;
  if (t.scopes !== undefined) {
    if (!Array.isArray(t.scopes)) return false;
    for (const scope of t.scopes) {
      if (!["zhihu_read_history", "zhihu_activity", "zhihu_collection"].includes(String(scope))) {
        return false;
      }
    }
  }
  return true;
}

export function computeZhihuTaskTimeoutMs(task: ZhihuTask): number {
  const scopeCount =
    Array.isArray(task.scopes) && task.scopes.length > 0 ? task.scopes.length : DEFAULT_SCOPES.length;
  return Math.min(Math.max(BASE_TIMEOUT_MS, BASE_TIMEOUT_MS + scopeCount * PER_SCOPE_MS), MAX_TIMEOUT_MS);
}

let taskInFlight = false;
let taskTabId: number | null = null;
let taskTimeoutId: ReturnType<typeof setTimeout> | null = null;
let currentTask: ZhihuTask | null = null;

async function fetchNextTask(): Promise<ZhihuTask | null> {
  try {
    const resp = await fetch(await apiUrl("/sources/zhihu/next-task"));
    if (resp.status === 204) return null;
    if (!resp.ok) return null;
    const payload: unknown = await resp.json();
    return isValidZhihuTask(payload) ? payload : null;
  } catch {
    return null;
  }
}

async function postTaskResult(result: ZhihuTaskResult): Promise<void> {
  try {
    await fetch(await apiUrl("/sources/zhihu/task-result"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(result),
    });
  } catch {
    // Backend transient unavailability — drop rather than crash.
  }
}

function cleanupTask(): void {
  if (taskTimeoutId !== null) {
    clearTimeout(taskTimeoutId);
    taskTimeoutId = null;
  }
  if (taskTabId !== null) {
    try {
      chrome.tabs.remove(taskTabId);
    } catch {
      // Tab may already be closed.
    }
  }
  taskTabId = null;
  currentTask = null;
  taskInFlight = false;
  releaseDispatcherMutex("zhihu");
}

function armTaskTimeout(task: ZhihuTask): void {
  const ms = computeZhihuTaskTimeoutMs(task);
  taskTimeoutId = setTimeout(async () => {
    await postTaskResult({
      task_id: task.id,
      status: "failed",
      items: [],
      scope_counts: {},
      error: "task_timeout",
    });
    cleanupTask();
  }, ms);
}

function onTabReady(tabId: number, callback: () => void, fallbackMs = 10_000): void {
  let completed = false;
  let fallbackTimer: ReturnType<typeof setTimeout> | null = null;
  const runOnce = (): void => {
    if (completed) return;
    completed = true;
    if (fallbackTimer !== null) clearTimeout(fallbackTimer);
    chrome.tabs.onUpdated.removeListener(listener);
    callback();
  };
  const listener = (updatedId: number, info: { status?: string }): void => {
    if (updatedId === tabId && info.status === "complete") runOnce();
  };
  chrome.tabs.onUpdated.addListener(listener);
  fallbackTimer = setTimeout(runOnce, fallbackMs);
  void chrome.tabs.get(tabId).then((tab) => {
    if (tab.status === "complete") runOnce();
  }).catch(() => {});
}

function sendExecuteMessage(): void {
  if (!currentTask || taskTabId === null) return;
  void chrome.tabs
    .sendMessage(taskTabId, {
      action: "ZHIHU_BOOTSTRAP_EXECUTE",
      data: {
        task_id: currentTask.id,
        scopes: currentTask.scopes,
        profile_slug: currentTask.profile_slug,
        max_items_per_scope: currentTask.max_items_per_scope,
        max_collections: currentTask.max_collections,
      },
    })
    .catch(() => {
      void postTaskResult({
        task_id: currentTask!.id,
        status: "failed",
        items: [],
        scope_counts: {},
        error: "sendMessage_failed",
      });
      cleanupTask();
    });
}

export async function executeTask(task: ZhihuTask): Promise<void> {
  if (taskInFlight) return;
  if (!tryAcquireDispatcherMutex("zhihu")) return;

  taskInFlight = true;
  currentTask = task;

  let tab: chrome.tabs.Tab;
  try {
    tab = await chrome.tabs.create({ url: "https://www.zhihu.com/", active: true });
  } catch {
    await postTaskResult({
      task_id: task.id,
      status: "failed",
      items: [],
      scope_counts: {},
      error: "tab_create_failed",
    });
    cleanupTask();
    return;
  }

  taskTabId = tab.id ?? null;
  if (taskTabId === null) {
    await postTaskResult({
      task_id: task.id,
      status: "failed",
      items: [],
      scope_counts: {},
      error: "tab_id_unknown",
    });
    cleanupTask();
    return;
  }

  armTaskTimeout(task);
  onTabReady(taskTabId, sendExecuteMessage, 12_000);
}

export async function handleZhihuTaskResult(result: ZhihuTaskResult): Promise<void> {
  if (!currentTask || result.task_id !== currentTask.id) return;
  await postTaskResult(result);
  cleanupTask();
}

async function pollNextTask(): Promise<void> {
  if (taskInFlight) return;
  const task = await fetchNextTask();
  if (!task) return;
  await executeTask(task);
}

export function startZhihuTaskPolling(): void {
  if (typeof chrome === "undefined" || !chrome.alarms) return;
  chrome.alarms.create(POLL_ALARM_NAME, { periodInMinutes: DEFAULT_POLL_INTERVAL_MS / 60_000 });
}

export function handleZhihuTaskAlarm(alarmName: string): void {
  if (alarmName === POLL_ALARM_NAME) {
    void pollNextTask();
  }
}

export function pollZhihuTaskNow(): void {
  void pollNextTask();
}
