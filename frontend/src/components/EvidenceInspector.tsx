import { ExternalLink, FileSearch, Route } from "lucide-react";
import type { Citation, TraceStage } from "../types";

type Props = {
  citation: Citation | undefined;
  stages: TraceStage[];
  tab: "evidence" | "trace";
  onTabChange: (tab: "evidence" | "trace") => void;
};

const traceStageLabels: Record<string, string> = {
  query_rewrite: "查询改写",
  hybrid_search: "混合检索",
  rrf_fusion: "RRF 融合",
  rerank: "结果重排",
  grounded_answer: "证据生成"
};

const scoreLabels: Record<string, string> = {
  bm25: "BM25",
  vector: "向量",
  rerank: "重排"
};

export function EvidenceInspector({ citation, stages, tab, onTabChange }: Props) {
  return (
    <aside className="evidence-inspector">
      <div className="inspector-tabs">
        <button className={tab === "evidence" ? "is-active" : ""} onClick={() => onTabChange("evidence")}>证据</button>
        <button className={tab === "trace" ? "is-active" : ""} onClick={() => onTabChange("trace")}>执行链路</button>
      </div>
      {tab === "evidence" && citation ? (
        <div className="inspector-body">
          <span className="eyeline">证据来源 {citation.number}</span>
          <label>来源标题</label>
          <h3>{citation.title}</h3>
          <label>章节路径</label>
          <p className="section-path">{citation.section_path}</p>
          <div className="score-section">
            <label>检索得分</label>
            <div className="score-grid">
              {["bm25", "vector", "rerank"].map((key) => (
                <div key={key}><span>{scoreLabels[key] ?? key}</span><code>{(citation.scores[key] ?? 0).toFixed(2)}</code></div>
              ))}
            </div>
          </div>
          <label>证据原文</label>
          <blockquote>{citation.excerpt}</blockquote>
          {citation.source_url.startsWith("http") ? (
            <a className="open-source" href={citation.source_url} target="_blank" rel="noreferrer">
              打开原始来源 <ExternalLink size={15} />
            </a>
          ) : (
            <div className="local-source-note">该来源由本地文档上传，原文件链接暂不可用。</div>
          )}
        </div>
      ) : tab === "trace" && stages.length ? (
        <div className="inspector-body">
          <span className="eyeline">查询执行过程</span>
          <h3>检索执行链路</h3>
          <div className="inspector-trace">
            {stages.map((stage, index) => (
              <div key={stage.name}>
                <i>{index + 1}</i>
                <span><strong>{traceStageLabels[stage.name] ?? stage.name.replaceAll("_", " ")}</strong><small>{stage.candidate_count} 个候选项</small></span>
                <code>{stage.duration_ms} 毫秒</code>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="inspector-empty">
          {tab === "evidence" ? <FileSearch size={24} /> : <Route size={24} />}
          <strong>{tab === "evidence" ? "尚未选择证据" : "尚无执行链路"}</strong>
          <p>{tab === "evidence"
            ? "调查完成后，可从答案引用或证据列表中查看原文。"
            : "提交问题后，这里会显示各阶段执行详情。"}</p>
        </div>
      )}
    </aside>
  );
}
