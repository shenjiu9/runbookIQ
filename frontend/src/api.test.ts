import { afterEach, describe, expect, it, vi } from "vitest";

import {
  askRunbook,
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  QUERY_TIMEOUT_MS
} from "./api";

describe("askRunbook", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("aborts a query that exceeds the browser deadline", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = askRunbook("kb-operations", "为什么 Deployment 一直重启？");
    const init = fetchMock.mock.calls[0]?.[1];
    const rejected = expect(request).rejects.toThrow("调查超时");

    expect(init?.signal).toBeInstanceOf(AbortSignal);
    await vi.advanceTimersByTimeAsync(QUERY_TIMEOUT_MS + 1);
    await rejected;
  });

  it("sends the selected knowledge base with each investigation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "证据回答",
          confidence: 0.9,
          citations: [],
          trace: { query_id: "q-1", stages: [] }
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    await askRunbook("kb-finance", "住宿标准是多少？");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      knowledge_base_id: "kb-finance",
      question: "住宿标准是多少？"
    });
  });

  it("manages the knowledge base catalog through public endpoints", async () => {
    const knowledgeBase = {
      id: "kb-finance",
      name: "财务制度",
      description: "报销与预算",
      created_at: "2026-07-24T00:00:00Z"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([knowledgeBase]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(knowledgeBase), {
          status: 201,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    expect(await listKnowledgeBases()).toEqual([knowledgeBase]);
    expect(await createKnowledgeBase("财务制度", "报销与预算")).toEqual(knowledgeBase);
    await deleteKnowledgeBase("kb-finance");

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["http://127.0.0.1:8004/api/knowledge-bases", "GET"],
      ["http://127.0.0.1:8004/api/knowledge-bases", "POST"],
      ["http://127.0.0.1:8004/api/knowledge-bases/kb-finance", "DELETE"]
    ]);
  });
});
