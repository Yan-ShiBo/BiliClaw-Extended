import test from "node:test";
import assert from "node:assert/strict";

import {
  normalizeZhihuActivity,
  normalizeZhihuCollectionItem,
  normalizeZhihuReadHistory,
} from "../src/content/zhihu/task-executor.ts";

test("normalizeZhihuReadHistory maps read_history payload items", () => {
  const item = normalizeZhihuReadHistory({
    data: {
      header: { title: "浏览了回答" },
      content: { author_name: "作者", summary: "摘要" },
      action: { url: "https://www.zhihu.com/question/1/answer/2" },
      extra: {
        content_token: "2",
        content_type: "answer",
        question_token: "1",
        read_time: 1710000000,
      },
    },
  });

  assert.deepEqual(item, {
    scope: "zhihu_read_history",
    content_type: "answer",
    content_id: "2",
    question_id: "1",
    title: "浏览了回答",
    author: "作者",
    summary: "摘要",
    url: "https://www.zhihu.com/question/1/answer/2",
    interaction_time: "1710000000",
  });
});

test("normalizeZhihuActivity maps liked answers", () => {
  const item = normalizeZhihuActivity({
    id: "1710000000000",
    action_text: "赞同了回答",
    target: {
      type: "answer",
      id: "2",
      question: { id: "1", title: "问题标题" },
      author: { name: "作者" },
      voteup_count: 88,
    },
  });

  assert.equal(item?.scope, "zhihu_activity");
  assert.equal(item?.interaction_action, "赞同了回答");
  assert.equal(item?.title, "问题标题");
  assert.equal(item?.url, "https://www.zhihu.com/question/1/answer/2");
});

test("normalizeZhihuCollectionItem maps collection content", () => {
  const item = normalizeZhihuCollectionItem(
    {
      content: {
        type: "article",
        id: "9",
        title: "文章标题",
        url: "https://zhuanlan.zhihu.com/p/9",
        author: { name: "作者" },
        excerpt: "摘要",
      },
    },
    { id: "c1", name: "默认收藏" },
  );

  assert.equal(item?.scope, "zhihu_collection");
  assert.equal(item?.content_type, "article");
  assert.equal(item?.content_id, "9");
  assert.equal(item?.collection_id, "c1");
  assert.equal(item?.collection_name, "默认收藏");
});
