import { useRef, useState, type ReactNode } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  CloudUpload,
  Database,
  FileCode2,
  FileText,
  Gauge,
  LoaderCircle,
  Play,
  ShieldCheck,
  ServerCog,
  Trash2
} from "lucide-react";
import type { EvaluationReport, IngestionJob, KnowledgeBase, RuntimeConfig } from "../types";

type KnowledgeProps = {
  knowledgeBases: KnowledgeBase[];
  selectedKnowledgeBaseId: string;
  loading: boolean;
  error: string | null;
  onSelect: (knowledgeBaseId: string) => void;
  onCreate: (name: string, description: string) => void;
  onDelete: (knowledgeBaseId: string) => void;
};

export function KnowledgeView({
  knowledgeBases,
  selectedKnowledgeBaseId,
  loading,
  error,
  onSelect,
  onCreate,
  onDelete
}: KnowledgeProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function submit() {
    if (!name.trim()) return;
    onCreate(name.trim(), description.trim());
    setName("");
    setDescription("");
  }

  return (
    <Section title="知识库" eyebrow="隔离语义空间" description="每个知识库拥有独立的来源、全文索引、向量和问答上下文。">
      <div className="stat-strip">
        <Stat label="知识库数量" value={String(knowledgeBases.length)} />
        <Stat label="当前知识库" value={knowledgeBases.find((item) => item.id === selectedKnowledgeBaseId)?.name ?? "未选择"} />
        <Stat label="隔离策略" value="严格按库" />
        <Stat label="持久化" value="PostgreSQL" />
      </div>
      <section className="panel knowledge-create">
        <div>
          <strong>创建知识库</strong>
          <span>例如“财务制度”“产品文档”或“运维手册”</span>
        </div>
        <input aria-label="知识库名称" placeholder="知识库名称" value={name} onChange={(event) => setName(event.target.value)} />
        <input aria-label="知识库描述" placeholder="用途与内容范围" value={description} onChange={(event) => setDescription(event.target.value)} />
        <button className="primary-small" onClick={submit} disabled={loading || !name.trim()}>{loading ? "处理中…" : "创建知识库"}</button>
      </section>
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="panel table-panel">
        <div className="panel-heading"><strong>知识库目录</strong><span>{knowledgeBases.length} 个隔离空间</span></div>
        <div className="data-table">
          <div className="data-row knowledge-row data-head"><span>名称</span><span>描述</span><span>标识</span><span>操作</span></div>
          {knowledgeBases.map((knowledgeBase) => (
            <div className={`data-row knowledge-row ${knowledgeBase.id === selectedKnowledgeBaseId ? "is-selected" : ""}`} key={knowledgeBase.id}>
              <button className="knowledge-name" onClick={() => onSelect(knowledgeBase.id)}><Database size={15} />{knowledgeBase.name}</button>
              <span>{knowledgeBase.description || "暂无描述"}</span>
              <code>{knowledgeBase.id}</code>
              <button className="delete-knowledge" aria-label={`删除 ${knowledgeBase.name}`} disabled={knowledgeBase.id === "platform" || loading} onClick={() => onDelete(knowledgeBase.id)}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      </section>
    </Section>
  );
}

type IngestionProps = {
  knowledgeBaseName: string;
  job: IngestionJob | null;
  loading: boolean;
  error: string | null;
  onUpload: (file: File) => void;
};

function jobStatusLabel(status: IngestionJob["status"]) {
  const labels: Record<IngestionJob["status"], string> = {
    queued: "排队中",
    processing: "处理中",
    completed: "已完成",
    failed: "失败"
  };
  return labels[status];
}

export function IngestionView({ knowledgeBaseName, job, loading, error, onUpload }: IngestionProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <Section title="文档摄取" eyebrow={`目标：${knowledgeBaseName}`} description="解析、OCR、父子分块并向量化文档，同时保留完整章节上下文。">
      <button className="upload-zone" onClick={() => inputRef.current?.click()}>
        {loading ? <LoaderCircle className="spin" size={32} /> : <CloudUpload size={32} />}
        <strong>{loading ? "正在处理文档…" : "上传运行手册、事故复盘或参考文档"}</strong>
        <span>支持 Markdown、TXT、PDF、DOCX 和图片 OCR · 最大 20 MiB</span>
        <input
          ref={inputRef}
          type="file"
          accept=".md,.markdown,.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
      </button>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="pipeline-grid">
        {[
          ["解析", "提取标题、章节与页面元数据", FileText],
          ["结构化", "建立父子分块关系", FileCode2],
          ["向量化", "生成语义检索向量", Gauge],
          ["写入索引", "写入向量和关键词索引", Database]
        ].map(([title, copy, Icon], index) => (
          <section className="panel pipeline-card" key={String(title)}>
            <span>0{index + 1}</span>
            <Icon size={20} />
            <strong>{String(title)}</strong><p>{String(copy)}</p>
          </section>
        ))}
      </div>
      {job ? (
        <section className="panel job-card">
          <div><CheckCircle2 size={19} /><span><strong>{job.filename}</strong><small>任务 {job.id}</small></span></div>
          <div className="job-progress"><i style={{ width: `${job.progress}%` }} /></div>
          <code>{job.chunks_created} 个分块 · {jobStatusLabel(job.status)}</code>
        </section>
      ) : null}
    </Section>
  );
}

type EvaluationProps = {
  report: EvaluationReport | null;
  loading: boolean;
  error: string | null;
  onRun: () => void;
};

export function EvaluationView({ report, loading, error, onRun }: EvaluationProps) {
  const metrics = report?.metrics ?? {};
  return (
    <Section title="质量评测" eyebrow="RAG 质量门禁" description="在发布 RAG 变更前，分别衡量检索质量与答案忠实度。">
      <div className="evaluation-hero panel">
        <div><span className="eyeline">黄金评测集</span><h2>平台故障调查基准 v1</h2><p>60 个中英文标注问题；页面默认运行跨三个知识来源的 6 个快速样本。</p></div>
        <button className="investigate-button" onClick={onRun} disabled={loading}><Play size={14} />{loading ? "正在评测…" : "运行真实评测"}</button>
      </div>
      {error ? <div className="error-banner">{error}</div> : null}
      {report ? <div className="metric-cards">
        {Object.entries(metrics).map(([key, value]) => (
          <section className="panel metric-card" key={key}>
            <span>{metricLabel(key)}</span><strong>{(value * 100).toFixed(0)}%</strong>
            <div className="meter"><i style={{ width: `${value * 100}%` }} /></div>
            <small title={report.metric_definitions[key]}>基于 {report.case_count} 个实际用例</small>
          </section>
        ))}
      </div> : <section className="panel evaluation-empty">尚无真实评测结果。运行后才会显示指标，不再使用演示分数。</section>}
      <section className="panel run-detail">
        <BookOpenCheck size={22} /><div><strong>{report ? `评测任务 ${report.run_id}` : "尚未运行评测"}</strong><p>{report ? `${report.case_count} / ${report.suite_total} 个用例已完成，耗时 ${(report.duration_ms / 1000).toFixed(1)} 秒，裁判：${report.judge}。` : "运行快速基准，将当前检索与生成链路和后端黄金集进行对比。"}</p></div>
      </section>
    </Section>
  );
}

const providerLabels: Record<string, string> = {
  openai_compatible: "OpenAI-compatible",
  ollama: "Ollama",
  fastembed: "FastEmbed",
  chat: "对话模型重排",
  token_overlap: "词元重叠重排",
  local: "本地内置"
};

export function SettingsView({
  config,
  error
}: {
  config: RuntimeConfig | null;
  error: string | null;
}) {
  return (
    <Section title="系统设置" eyebrow="安全的运行时配置" description="生产配置由服务器环境变量管理，页面不展示或缓存任何 API 密钥。">
      <section className="panel settings-notice">
        <ShieldCheck size={22} />
        <div>
          <strong>配置采用只读展示</strong>
          <p>为避免把模型密钥暴露到浏览器，供应商、模型和检索参数由服务器统一管理。下方信息来自后端脱敏接口，不包含任何 API 密钥。</p>
        </div>
      </section>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="settings-grid">
        <section className="panel settings-card">
          <div className="settings-title"><ServerCog size={20} /><span><strong>模型与检索配置</strong><small>服务器托管 · 修改后需重新部署服务</small></span></div>
          {config ? (
            <dl className="runtime-config-list">
              <ConfigRow label="运行模式" value={config.mode === "production" ? "生产模式" : "本地模式"} />
              <ConfigRow label="对话模型" value={`${providerLabels[config.chat_provider] ?? config.chat_provider} · ${config.chat_model}`} />
              <ConfigRow label="向量模型" value={`${providerLabels[config.embedding_provider] ?? config.embedding_provider} · ${config.embedding_model} · ${config.embedding_dimensions} 维`} />
              <ConfigRow label="重排策略" value={providerLabels[config.rerank_provider] ?? config.rerank_provider} />
              <ConfigRow label="查询超时" value={`${config.query_timeout_seconds} 秒`} />
              <ConfigRow label="OCR 语言" value={config.ocr_languages} />
              <ConfigRow label="文档上限" value={`${config.max_document_mib} MiB`} />
            </dl>
          ) : (
            <div className="settings-empty">
              <strong>正在读取运行配置</strong>
              <p>配置加载完成后会显示当前服务器实际使用的模型与检索参数。</p>
            </div>
          )}
        </section>
      </div>
    </Section>
  );
}

function Section({ title, eyebrow, description, children }: { title: string; eyebrow: string; description: string; children: ReactNode }) {
  return (
    <div className="secondary-view">
      <div className="page-intro"><div><span className="eyeline">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div></div>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function metricLabel(key: string) {
  const labels: Record<string, string> = {
    recall_at_5: "召回率 Recall@5",
    mrr_at_5: "平均倒数排名 MRR@5",
    precision_at_5: "检索准确率 Precision@5",
    faithfulness: "答案忠实度"
  };
  return labels[key] ?? key.replaceAll("_", " ");
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
