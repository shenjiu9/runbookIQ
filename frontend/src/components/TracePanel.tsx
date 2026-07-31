import { useState } from "react";
import { Check, Code2, Route } from "lucide-react";
import type { TraceStage } from "../types";

const labels: Record<string, string> = {
  query_rewrite: "查询改写",
  hybrid_search: "混合检索",
  rrf_fusion: "RRF 融合",
  rerank: "结果重排",
  grounded_answer: "证据生成"
};

export function TracePanel({ stages }: { stages: TraceStage[] }) {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <section className="panel trace-panel">
      <div className="panel-heading">
        <strong>检索与生成链路</strong>
        <span>{stages.length ? `${stages.length} 个阶段` : "尚未执行"}</span>
      </div>
      {stages.length ? (
        <>
          <div className="trace-timeline">
            {stages.map((stage) => (
              <div className="trace-step" key={stage.name}>
                <div className="trace-dot"><Check size={13} /></div>
                <strong>{labels[stage.name] ?? stage.name}</strong>
                <span>{stage.duration_ms} 毫秒</span>
                <small>{stage.candidate_count.toLocaleString()} 个候选项</small>
              </div>
            ))}
          </div>
          {showRaw ? (
            <pre className="raw-trace">{JSON.stringify({
              stages: stages.map((stage) => ({
                name: stage.name,
                duration_ms: stage.duration_ms,
                candidate_count: stage.candidate_count
              }))
            }, null, 2)}</pre>
          ) : null}
          <button className="text-action trace-action" onClick={() => setShowRaw((value) => !value)}>
            <Code2 size={16} />{showRaw ? "收起原始链路" : "查看原始链路"}
          </button>
        </>
      ) : (
        <div className="compact-empty">
          <Route size={20} />
          <span>问答完成后展示每个检索阶段的真实耗时和候选数量。</span>
        </div>
      )}
    </section>
  );
}
