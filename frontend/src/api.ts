import type {
  EvaluationReport,
  IngestionJob,
  KnowledgeBase,
  QueryResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ?? (import.meta.env.DEV ? "http://127.0.0.1:8004" : "");

export const QUERY_TIMEOUT_MS = 65_000;

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
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("调查超时：模型响应过慢，请稍后重试。");
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

export async function uploadDocument(
  knowledgeBaseId: string,
  file: File
): Promise<IngestionJob> {
  const body = new FormData();
  body.append("knowledge_base_id", knowledgeBaseId);
  body.append("file", file);
  return decode<IngestionJob>(
    await fetch(`${API_BASE_URL}/api/documents`, { method: "POST", body })
  );
}

export async function runEvaluation(knowledgeBaseId: string): Promise<EvaluationReport> {
  return decode<EvaluationReport>(
    await fetch(`${API_BASE_URL}/api/evaluations/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: knowledgeBaseId,
        suite_id: "platform-operations-v1",
        max_cases: 6
      })
    })
  );
}

export async function fetchLatestEvaluation(): Promise<EvaluationReport | null> {
  return decode<EvaluationReport | null>(
    await fetch(`${API_BASE_URL}/api/evaluations/latest`)
  );
}

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return decode<KnowledgeBase[]>(
    await fetch(`${API_BASE_URL}/api/knowledge-bases`)
  );
}

export async function createKnowledgeBase(
  name: string,
  description: string
): Promise<KnowledgeBase> {
  return decode<KnowledgeBase>(
    await fetch(`${API_BASE_URL}/api/knowledge-bases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description })
    })
  );
}

export async function deleteKnowledgeBase(knowledgeBaseId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    await decode(response);
  }
}
