export type Citation = {
  number: number;
  source_id: string;
  title: string;
  section_path: string;
  excerpt: string;
  source_url: string;
  scores: Record<string, number>;
};

export type TraceStage = {
  name: string;
  duration_ms: number;
  candidate_count: number;
};

export type QueryResponse = {
  answer: string;
  confidence: number;
  citations: Citation[];
  trace: {
    query_id: string;
    stages: TraceStage[];
  };
};

export type KnowledgeBase = {
  id: string;
  name: string;
  description: string;
  created_at: string;
};

export type EvaluationSuite = {
  id: string;
  knowledge_base_id: string;
  name: string;
  description: string;
  case_count: number;
};

export type EvaluationReport = {
  run_id: string;
  knowledge_base_id: string;
  suite_id: string;
  suite_total: number;
  case_count: number;
  evaluated_at: string;
  duration_ms: number;
  judge: string;
  metrics: Record<string, number>;
  metric_definitions: Record<string, string>;
  cases: Array<{
    question: string;
    expected_source_ids: string[];
    retrieved_source_ids: string[];
    first_relevant_rank: number | null;
    metrics: Record<string, number>;
  }>;
};

export type IngestionJob = {
  id: string;
  knowledge_base_id: string;
  filename: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  chunks_created: number;
  error: string | null;
};

export type RuntimeConfig = {
  mode: string;
  chat_provider: string;
  chat_base_url: string | null;
  chat_model: string;
  embedding_provider: string;
  embedding_base_url: string | null;
  embedding_model: string;
  embedding_dimensions: number;
  rerank_provider: string;
  query_timeout_seconds: number;
  ocr_languages: string;
  max_document_mib: number;
};

export type NavKey = "ask" | "knowledge" | "ingestion" | "evaluation" | "settings";
