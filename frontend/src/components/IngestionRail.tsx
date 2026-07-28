import { Check, FileClock, LoaderCircle, TriangleAlert } from "lucide-react";
import type { IngestionJob } from "../types";

const statusLabels: Record<IngestionJob["status"], string> = {
  queued: "等待处理",
  processing: "正在处理",
  completed: "已完成",
  failed: "处理失败"
};

export function IngestionRail({
  job,
  knowledgeBaseName
}: {
  job: IngestionJob | null;
  knowledgeBaseName: string;
}) {
  return (
    <section className="ingestion-rail">
      <div className="rail-title"><span>最近摄取任务</span><small>{knowledgeBaseName}</small></div>
      {job ? (
        <div className="ingestion-item">
          <div className={`status-orb ${job.status}`}>
            {job.status === "completed" ? <Check size={18} /> : null}
            {job.status === "failed" ? <TriangleAlert size={18} /> : null}
            {job.status === "queued" || job.status === "processing"
              ? <LoaderCircle className="spin" size={18} />
              : null}
          </div>
          <div>
            <strong>{job.filename}</strong>
            <span>{statusLabels[job.status]}</span>
            <small>{job.chunks_created} 个分块 · {job.progress}%</small>
          </div>
          <em>{job.progress}%</em>
        </div>
      ) : (
        <div className="rail-empty">
          <FileClock size={20} />
          <div><strong>尚无摄取任务</strong><span>上传文档后，这里会显示真实处理状态。</span></div>
        </div>
      )}
    </section>
  );
}
