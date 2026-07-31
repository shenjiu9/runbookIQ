import type {
  EvaluationReport,
  EvaluationSuite,
  CreatedTenantInvitation,
  IngestionJob,
  KnowledgeBase,
  OrganizationMember,
  OrganizationBranding,
  QueryResponse,
  RegistrationInput,
  TenantInvitation,
  TenantInvitationPreview,
  TenantRole,
  TenantContext,
  RuntimeConfig
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ?? (import.meta.env.DEV ? "http://127.0.0.1:8004" : "");

export const QUERY_TIMEOUT_MS = 65_000;

export type HealthResponse = {
  status: string;
};

function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = typeof document === "undefined"
      ? null
      : document.cookie
          .split("; ")
          .find((item) => item.startsWith("runbookiq_csrf="))
          ?.slice("runbookiq_csrf=".length);
    if (csrfToken) headers.set("X-CSRF-Token", decodeURIComponent(csrfToken));
  }
  return fetch(input, { ...init, headers, credentials: "include" });
}

async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? "请求失败");
  }
  return response.json() as Promise<T>;
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await apiFetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("问答超时：模型响应过慢，请稍后重试。");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function askRunbook(
  knowledgeBaseId: string,
  question: string
): Promise<QueryResponse> {
  return decode<QueryResponse>(
    await fetchWithTimeout(
      `${API_BASE_URL}/api/query`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ knowledge_base_id: knowledgeBaseId, question })
      },
      QUERY_TIMEOUT_MS
    )
  );
}

export async function fetchHealth(): Promise<HealthResponse> {
  return decode<HealthResponse>(
    await apiFetch(`${API_BASE_URL}/api/health`)
  );
}

export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  return decode<RuntimeConfig>(
    await apiFetch(`${API_BASE_URL}/api/runtime-config`)
  );
}

export async function register(input: RegistrationInput): Promise<TenantContext> {
  return decode<TenantContext>(
    await apiFetch(`${API_BASE_URL}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    })
  );
}

export async function login(
  email: string,
  password: string
): Promise<TenantContext> {
  return decode<TenantContext>(
    await apiFetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    })
  );
}

export async function fetchCurrentUser(): Promise<TenantContext> {
  return decode<TenantContext>(
    await apiFetch(`${API_BASE_URL}/api/auth/me`)
  );
}

export async function previewInvitation(
  token: string
): Promise<TenantInvitationPreview> {
  return decode<TenantInvitationPreview>(
    await apiFetch(`${API_BASE_URL}/api/auth/invitations/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token })
    })
  );
}

export async function acceptInvitation(
  token: string,
  password: string
): Promise<TenantContext> {
  return decode<TenantContext>(
    await apiFetch(`${API_BASE_URL}/api/auth/invitations/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password })
    })
  );
}

export async function listOrganizationMembers(): Promise<OrganizationMember[]> {
  return decode<OrganizationMember[]>(
    await apiFetch(`${API_BASE_URL}/api/organization/members`)
  );
}

export async function fetchOrganizationBranding(): Promise<OrganizationBranding> {
  return decode<OrganizationBranding>(
    await apiFetch(`${API_BASE_URL}/api/organization/branding`)
  );
}

export async function updateOrganizationBranding(
  branding: OrganizationBranding
): Promise<OrganizationBranding> {
  return decode<OrganizationBranding>(
    await apiFetch(`${API_BASE_URL}/api/organization/branding`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(branding)
    })
  );
}

export async function listOrganizationInvitations(): Promise<TenantInvitation[]> {
  return decode<TenantInvitation[]>(
    await apiFetch(`${API_BASE_URL}/api/organization/invitations`)
  );
}

export async function createOrganizationInvitation(
  email: string,
  role: Exclude<TenantRole, "owner">
): Promise<CreatedTenantInvitation> {
  return decode<CreatedTenantInvitation>(
    await apiFetch(`${API_BASE_URL}/api/organization/invitations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role })
    })
  );
}

export async function revokeOrganizationInvitation(
  invitationId: string
): Promise<void> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/organization/invitations/${encodeURIComponent(invitationId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) await decode(response);
}

export async function logout(): Promise<void> {
  const response = await apiFetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST"
  });
  if (!response.ok) await decode(response);
}

export async function uploadDocument(
  knowledgeBaseId: string,
  file: File
): Promise<IngestionJob> {
  const body = new FormData();
  body.append("knowledge_base_id", knowledgeBaseId);
  body.append("file", file);
  return decode<IngestionJob>(
    await apiFetch(`${API_BASE_URL}/api/documents`, { method: "POST", body })
  );
}

export async function listEvaluationSuites(
  knowledgeBaseId: string
): Promise<EvaluationSuite[]> {
  return decode<EvaluationSuite[]>(
    await apiFetch(
      `${API_BASE_URL}/api/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/evaluation-suites`
    )
  );
}

export async function runEvaluation(
  knowledgeBaseId: string,
  suiteId: string
): Promise<EvaluationReport> {
  return decode<EvaluationReport>(
    await apiFetch(`${API_BASE_URL}/api/evaluations/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: knowledgeBaseId,
        suite_id: suiteId,
        max_cases: 6
      })
    })
  );
}

export async function fetchLatestEvaluation(
  knowledgeBaseId: string
): Promise<EvaluationReport | null> {
  return decode<EvaluationReport | null>(
    await apiFetch(
      `${API_BASE_URL}/api/evaluations/latest?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`
    )
  );
}

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return decode<KnowledgeBase[]>(
    await apiFetch(`${API_BASE_URL}/api/knowledge-bases`)
  );
}

export async function createKnowledgeBase(
  name: string,
  description: string
): Promise<KnowledgeBase> {
  return decode<KnowledgeBase>(
    await apiFetch(`${API_BASE_URL}/api/knowledge-bases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description })
    })
  );
}

export async function deleteKnowledgeBase(knowledgeBaseId: string): Promise<void> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    await decode(response);
  }
}
