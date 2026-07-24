import { ExternalLink, LoaderCircle } from "lucide-react";
import type { EvaluationReport } from "../types";

const labels: Record<string, string> = {
  recall_at_5: "召回率 Recall@5",
  mrr_at_5: "平均倒数排名 MRR@5",
  precision_at_5: "检索准确率 Precision@5",
  faithfulness: "答案忠实度"
};

export function EvaluationSummary({
  report,
  loading,
  onRun
}: {
  report: EvaluationReport | null;
  loading: boolean;
  onRun: () => void;
}) {
  const metrics = report ? Object.entries(report.metrics) : [];
  return (
    <section className="panel evaluation-summary">
      <div className="panel-heading">
        <strong>真实评测摘要</strong>
        <span>{report ? `${report.case_count} / ${report.suite_total} 个黄金问题` : "尚未运行"}</span>
      </div>
      <div className="metric-head"><span>指标</span><span>得分</span><span>类型</span></div>
      {metrics.map(([key, value]) => (
        <div className="metric-row" key={key} title={report?.metric_definitions[key]}>
          <span>{labels[key] ?? key}</span>
          <code>{value.toFixed(2)}</code>
          <span className="metric-delta">实测</span>
        </div>
      ))}
      {!report ? <p className="empty-metric-copy">运行快速黄金集后显示真实指标。</p> : null}
      <button className="text-action summary-action" onClick={onRun} disabled={loading}>
        {loading ? <LoaderCircle className="spin" size={13} /> : <ExternalLink size={13} />}
        {loading ? "正在评测…" : report ? "重新运行快速评测" : "运行快速评测"}
      </button>
    </section>
  );
}
