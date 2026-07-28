import { ExternalLink, LoaderCircle } from "lucide-react";
import type { EvaluationReport, EvaluationSuite } from "../types";

const labels: Record<string, string> = {
  recall_at_5: "召回率 Recall@5",
  mrr_at_5: "平均倒数排名 MRR@5",
  precision_at_5: "检索准确率 Precision@5",
  faithfulness: "答案忠实度"
};

export function EvaluationSummary({
  report,
  suites,
  selectedSuiteId,
  catalogLoading,
  loading,
  onSuiteChange,
  onRun
}: {
  report: EvaluationReport | null;
  suites: EvaluationSuite[];
  selectedSuiteId: string;
  catalogLoading: boolean;
  loading: boolean;
  onSuiteChange: (suiteId: string) => void;
  onRun: () => void;
}) {
  const metrics = report ? Object.entries(report.metrics) : [];
  const selectedSuite = suites.find((suite) => suite.id === selectedSuiteId);
  return (
    <section className="panel evaluation-summary">
      <div className="panel-heading">
        <strong>真实评测摘要</strong>
        <span>
          {catalogLoading
            ? "正在加载评测集"
            : suites.length === 0
              ? "尚未配置评测集"
              : report
                ? `${report.case_count} / ${report.suite_total} 个黄金问题`
                : "尚未运行"}
        </span>
      </div>
      {suites.length > 0 ? (
        <label className="suite-picker suite-picker-compact">
          <span>本次评测集</span>
          <select
            aria-label="选择评测集"
            value={selectedSuiteId}
            onChange={(event) => onSuiteChange(event.target.value)}
            disabled={catalogLoading || loading}
          >
            {suites.map((suite) => (
              <option key={suite.id} value={suite.id}>
                {suite.name} · {suite.case_count} 题
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <div className="metric-head"><span>指标</span><span>得分</span><span>类型</span></div>
      {metrics.map(([key, value]) => (
        <div className="metric-row" key={key} title={report?.metric_definitions[key]}>
          <span>{labels[key] ?? key}</span>
          <code>{value.toFixed(2)}</code>
          <span className="metric-delta">实测</span>
        </div>
      ))}
      {!report ? (
        <p className="empty-metric-copy">
          {catalogLoading
            ? "正在读取当前知识库的评测配置…"
            : suites.length === 0
              ? "尚未配置评测集。当前知识库不会误用其他知识库的黄金集。"
              : `运行“${selectedSuite?.name ?? "所选评测集"}”后显示真实指标。`}
        </p>
      ) : null}
      <button
        className="text-action summary-action"
        onClick={onRun}
        disabled={loading || catalogLoading || !selectedSuiteId}
      >
        {loading ? <LoaderCircle className="spin" size={13} /> : <ExternalLink size={13} />}
        {loading
          ? "正在评测…"
          : suites.length === 0
            ? "尚未配置评测集"
            : report
              ? "重新运行快速评测"
              : "运行快速评测"}
      </button>
    </section>
  );
}
