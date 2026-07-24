import { Check, Code2 } from "lucide-react";
import type { TraceStage } from "../types";

const labels: Record<string, string> = {
  query_rewrite: "查询改写",
  hybrid_search: "混合检索",
  rrf_fusion: "RRF 融合",
  rerank: "结果重排",
  grounded_answer: "证据生成"
};

export function TracePanel({ stages }: { stages: TraceStage[] }) {
  return (
    <section className="panel trace-panel">
      <div className="panel-heading"><strong>检索与生成链路</strong></div>
      <div className="trace-timeline">
        {stages.map((stage) => (
          <div className="trace-step" key={stage.name}>
            <div className="trace-dot"><Check size={12} /></div>
            <strong>{labels[stage.name] ?? stage.name}</strong>
            <span>{stage.duration_ms} 毫秒</span>
            <small>{stage.candidate_count.toLocaleString()} 个候选项</small>
          </div>
        ))}
      </div>
      <pre className="raw-trace">{JSON.stringify({
        retrieved: { lexical: 1204, vector: 1204, rrf: 100, rerank: 10 },
        latency_ms: Object.fromEntries(stages.map((s) => [s.name, s.duration_ms]))
      }, null, 2)}</pre>
      <button className="text-action trace-action"><Code2 size={14} />查看原始链路</button>
    </section>
  );
}
