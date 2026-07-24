import { ArrowUp, Search, ShieldCheck } from "lucide-react";
import { AnswerPanel } from "../components/AnswerPanel";
import { EvaluationSummary } from "../components/EvaluationSummary";
import { EvidenceInspector } from "../components/EvidenceInspector";
import { IngestionRail } from "../components/IngestionRail";
import { TracePanel } from "../components/TracePanel";
import type { EvaluationReport, KnowledgeBase, QueryResponse } from "../types";

type Props = {
  question: string;
  onQuestionChange: (value: string) => void;
  response: QueryResponse;
  loading: boolean;
  error: string | null;
  selected: number;
  onSelectedChange: (value: number) => void;
  inspectorTab: "evidence" | "trace";
  onInspectorTabChange: (tab: "evidence" | "trace") => void;
  onSubmit: () => void;
  evaluationReport: EvaluationReport | null;
  evaluationLoading: boolean;
  onEvaluate: () => void;
  knowledgeBases: KnowledgeBase[];
  selectedKnowledgeBaseId: string;
  onKnowledgeBaseChange: (knowledgeBaseId: string) => void;
};

export function AskView({
  question,
  onQuestionChange,
  response,
  loading,
  error,
  selected,
  onSelectedChange,
  inspectorTab,
  onInspectorTabChange,
  onSubmit,
  evaluationReport,
  evaluationLoading,
  onEvaluate,
  knowledgeBases,
  selectedKnowledgeBaseId,
  onKnowledgeBaseChange
}: Props) {
  return (
    <div className="ask-view">
      <div className="page-intro">
        <div>
          <span className="eyeline">知识辅助运维</span>
          <h1>调查线上故障</h1>
          <p>检索运行手册、事故复盘与平台文档，获得可追溯、可核验的排查建议。</p>
        </div>
        <div className="scope-badge"><ShieldCheck size={15} />仅基于证据回答</div>
      </div>

      <div className="query-shell">
        <div className="query-toolbar">
          <label className="knowledge-base-select">
            <Search size={14} />
            <select
              aria-label="选择知识库"
              value={selectedKnowledgeBaseId}
              onChange={(event) => onKnowledgeBaseChange(event.target.value)}
            >
              {knowledgeBases.map((knowledgeBase) => (
                <option value={knowledgeBase.id} key={knowledgeBase.id}>
                  {knowledgeBase.name}
                </option>
              ))}
            </select>
          </label>
          <span>混合检索</span>
        </div>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") onSubmit();
          }}
          aria-label="故障问题"
        />
        <div className="query-footer">
          <span>按 Ctrl + Enter 开始调查</span>
          <button className="investigate-button" onClick={onSubmit} disabled={loading || !question.trim() || !selectedKnowledgeBaseId}>
            {loading ? "正在调查…" : "开始调查"}<ArrowUp size={15} />
          </button>
        </div>
      </div>
      {error ? <div className="error-banner">{error}</div> : null}

      <div className="workspace-grid">
        <div className="result-column">
          <AnswerPanel response={response} selected={selected} onSelect={onSelectedChange} />
          <div className="lower-grid">
            <TracePanel stages={response.trace.stages} />
            <EvaluationSummary
              report={evaluationReport}
              loading={evaluationLoading}
              onRun={onEvaluate}
            />
          </div>
        </div>
        <div className="evidence-column">
          <EvidenceInspector
            citation={response.citations[selected]}
            stages={response.trace.stages}
            tab={inspectorTab}
            onTabChange={onInspectorTabChange}
          />
          <IngestionRail />
        </div>
      </div>
    </div>
  );
}
