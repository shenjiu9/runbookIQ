import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acceptInvitation,
  askRunbook,
  createOrganizationInvitation,
  createKnowledgeBase,
  deleteKnowledgeBase,
  fetchLatestEvaluation,
  fetchCurrentUser,
  fetchOrganizationBranding,
  fetchRuntimeConfig,
  listEvaluationSuites,
  listKnowledgeBases,
  listOrganizationInvitations,
  listOrganizationMembers,
  login,
  previewInvitation,
  QUERY_TIMEOUT_MS,
  register,
  revokeOrganizationInvitation,
  runEvaluation,
  updateOrganizationBranding
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
    const rejected = expect(request).rejects.toThrow("问答超时");

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
    vi.stubGlobal("document", { cookie: "runbookiq_csrf=csrf-browser-token" });

    expect(await listKnowledgeBases()).toEqual([knowledgeBase]);
    expect(await createKnowledgeBase("财务制度", "报销与预算")).toEqual(knowledgeBase);
    await deleteKnowledgeBase("kb-finance");

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["http://127.0.0.1:8004/api/knowledge-bases", "GET"],
      ["http://127.0.0.1:8004/api/knowledge-bases", "POST"],
      ["http://127.0.0.1:8004/api/knowledge-bases/kb-finance", "DELETE"]
    ]);
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("X-CSRF-Token")).toBe(
      "csrf-browser-token"
    );
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get("X-CSRF-Token")).toBe(
      "csrf-browser-token"
    );
  });

  it("reads the browser-safe runtime configuration", async () => {
    const runtimeConfig = {
      mode: "production",
      chat_provider: "openai_compatible",
      chat_base_url: "https://api.example.com",
      chat_model: "chat-model",
      embedding_provider: "fastembed",
      embedding_base_url: null,
      embedding_model: "embedding-model",
      embedding_dimensions: 768,
      rerank_provider: "chat",
      query_timeout_seconds: 60,
      ocr_languages: "chi_sim+eng",
      max_document_mib: 20
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(runtimeConfig), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchRuntimeConfig()).toEqual(runtimeConfig);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8004/api/runtime-config",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("registers and authenticates an enterprise with cookie credentials", async () => {
    const context = {
      user: { id: "user-1", email: "owner@alpha.example" },
      organization: {
        id: "org-1",
        name: "Alpha Manufacturing",
        slug: "alpha",
        url: "https://knowledge.test",
        branding: {
          display_name: "Alpha Manufacturing",
          logo_url: null,
          primary_color: "#0F766E",
          welcome_title: "欢迎进入 Alpha 知识空间",
          welcome_message: "检索企业资料并核验原文证据。"
        }
      },
      role: "owner"
    };
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(context), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    await register({
      email: "owner@alpha.example",
      password: "Strong-password-2026",
      organization_name: "Alpha Manufacturing"
    });
    await login("owner@alpha.example", "Strong-password-2026");
    await fetchCurrentUser();

    expect(fetchMock.mock.calls[0]).toEqual([
      "http://127.0.0.1:8004/api/auth/register",
      expect.objectContaining({
        method: "POST",
        credentials: "include"
      })
    ]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      email: "owner@alpha.example",
      password: "Strong-password-2026",
      organization_name: "Alpha Manufacturing"
    });
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
    expect(fetchMock.mock.calls[2][1]).toEqual(
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("reads and updates tenant-scoped enterprise branding", async () => {
    const branding = {
      display_name: "Alpha 知识中心",
      logo_url: "https://assets.example.com/alpha.png",
      primary_color: "#335CFF",
      welcome_title: "欢迎进入 Alpha 知识中心",
      welcome_message: "检索制度与业务资料，并核验每条原文证据。"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(branding), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(branding), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "runbookiq_csrf=csrf-browser-token" });

    expect(await fetchOrganizationBranding()).toEqual(branding);
    expect(await updateOrganizationBranding(branding)).toEqual(branding);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8004/api/organization/branding"
    );
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({ method: "PATCH", credentials: "include" })
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(branding);
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("X-CSRF-Token")).toBe(
      "csrf-browser-token"
    );
  });

  it("manages one-time enterprise invitations through tenant-scoped endpoints", async () => {
    const member = {
      user_id: "user-1",
      email: "owner@alpha.example",
      role: "owner",
      joined_at: "2026-07-31T00:00:00Z"
    };
    const invitation = {
      id: "invite-1",
      email: "viewer@alpha.example",
      role: "viewer" as const,
      expires_at: "2026-08-07T00:00:00Z",
      created_at: "2026-07-31T00:00:00Z",
      token: "secure-invitation-token",
      accept_url: "https://knowledge.test/#invite=secure-invitation-token"
    };
    const acceptedContext = {
      user: { id: "user-2", email: invitation.email },
      organization: {
        id: "org-1",
        name: "Alpha Manufacturing",
        slug: "alpha",
        url: "https://knowledge.test",
        branding: {
          display_name: "Alpha Manufacturing",
          logo_url: null,
          primary_color: "#0F766E",
          welcome_title: "欢迎进入 Alpha 知识空间",
          welcome_message: "检索企业资料并核验原文证据。"
        }
      },
      role: "viewer"
    };
    const preview = {
      email: invitation.email,
      role: invitation.role,
      organization_name: "Alpha Manufacturing",
      organization_url: "https://knowledge.test",
      expires_at: invitation.expires_at
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([member]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(invitation), {
          status: 201,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(preview), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(acceptedContext), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "runbookiq_csrf=csrf-browser-token" });

    expect(await listOrganizationMembers()).toEqual([member]);
    expect(await listOrganizationInvitations()).toEqual([]);
    expect(
      await createOrganizationInvitation(invitation.email, invitation.role)
    ).toEqual(invitation);
    expect(await previewInvitation(invitation.token)).toEqual(preview);
    expect(
      await acceptInvitation(invitation.token, "Invited-password-2026")
    ).toEqual(acceptedContext);
    await revokeOrganizationInvitation(invitation.id);

    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      email: "viewer@alpha.example",
      role: "viewer"
    });
    expect(fetchMock.mock.calls[3][0]).toBe(
      "http://127.0.0.1:8004/api/auth/invitations/preview"
    );
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toEqual({
      token: "secure-invitation-token"
    });
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toEqual({
      token: "secure-invitation-token",
      password: "Invited-password-2026"
    });
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get("X-CSRF-Token")).toBe(
      "csrf-browser-token"
    );
  });

  it("loads and runs only an explicitly selected suite for the current knowledge base", async () => {
    const suite = {
      id: "retail-operations-v1",
      knowledge_base_id: "kb-retail",
      name: "零售运营基准 v1",
      description: "冷链与门店运营黄金问题",
      case_count: 20
    };
    const report = {
      run_id: "eval-retail",
      knowledge_base_id: "kb-retail",
      suite_id: suite.id,
      suite_total: 20,
      case_count: 6,
      evaluated_at: "2026-07-28T00:00:00Z",
      duration_ms: 100,
      judge: "fixed",
      metrics: {},
      metric_definitions: {},
      cases: []
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([suite]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(report), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(report), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    expect(await listEvaluationSuites("kb-retail")).toEqual([suite]);
    expect(await runEvaluation("kb-retail", "retail-operations-v1")).toEqual(report);
    expect(await fetchLatestEvaluation("kb-retail")).toEqual(report);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8004/api/knowledge-bases/kb-retail/evaluation-suites"
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      knowledge_base_id: "kb-retail",
      suite_id: "retail-operations-v1",
      max_cases: 6
    });
    expect(fetchMock.mock.calls[2][0]).toBe(
      "http://127.0.0.1:8004/api/evaluations/latest?knowledge_base_id=kb-retail"
    );
  });
});
