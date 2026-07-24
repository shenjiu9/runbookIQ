import { Check, LoaderCircle } from "lucide-react";

export function IngestionRail() {
  return (
    <section className="ingestion-rail">
      <div className="rail-title">文档摄取状态</div>
      <div className="ingestion-item">
        <div className="status-orb complete"><Check size={18} /></div>
        <div><strong>Kubernetes 文档同步</strong><span>kubernetes.io/docs</span><small>25,431 个分块</small></div>
        <em>已完成</em>
      </div>
      <div className="ingestion-item">
        <div className="status-orb processing"><LoaderCircle size={18} /></div>
        <div><strong>内部运行手册</strong><span>runbooks://</span><small>8,317 / 19,512 个分块</small></div>
        <em className="processing-label">42%</em>
      </div>
    </section>
  );
}
