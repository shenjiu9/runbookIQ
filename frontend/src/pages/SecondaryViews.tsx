import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode
} from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  CloudUpload,
  Copy,
  Database,
  Download,
  FileCode2,
  FileText,
  Gauge,
  LoaderCircle,
  MailPlus,
  Palette,
  Play,
  ShieldCheck,
  ServerCog,
  Trash2,
  RefreshCw,
  UserRound,
  Users
} from "lucide-react";
import type {
  CreatedTenantInvitation,
  EvaluationReport,
  EvaluationSuite,
  IngestionJob,
  KnowledgeBase,
  OrganizationMember,
  OrganizationBranding,
  RuntimeConfig,
  SourceDocument,
  TenantInvitation,
  TenantRole,
  UploadQueueItem
} from "../types";
import { documentDownloadUrl } from "../api";

type KnowledgeProps = {
  knowledgeBases: KnowledgeBase[];
  selectedKnowledgeBaseId: string;
  loading: boolean;
  error: string | null;
  role: TenantRole;
  onSelect: (knowledgeBaseId: string) => void;
  onCreate: (name: string, description: string) => void;
  onDelete: (knowledgeBaseId: string) => void;
  onStartUpload: () => void;
  onStartAsk: () => void;
};

export function KnowledgeView({
  knowledgeBases,
  selectedKnowledgeBaseId,
  loading,
  error,
  role,
  onSelect,
  onCreate,
  onDelete,
  onStartUpload,
  onStartAsk
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
      {knowledgeBases.length === 1 ? (
        <section className="panel onboarding-card">
          <div className="onboarding-heading">
            <span className="eyeline">首次使用引导</span>
            <h2>用三步获得第一条可核验回答</h2>
            <p>默认知识库已经准备好。上传一份真实企业资料，再用业务问题验证回答与原文引用。</p>
          </div>
          <div className="onboarding-steps">
            <div className="is-complete">
              <span><CheckCircle2 size={18} /></span>
              <div><strong>企业空间已创建</strong><small>默认知识库与成员权限已就绪</small></div>
            </div>
            <button type="button" onClick={onStartUpload} disabled={role === "viewer"}>
              <span>2</span>
              <div><strong>上传第一份文档</strong><small>制度、手册、PDF 或 DOCX</small></div>
            </button>
            <button type="button" onClick={onStartAsk}>
              <span>3</span>
              <div><strong>提出第一个问题</strong><small>核对答案和证据引用</small></div>
            </button>
          </div>
        </section>
      ) : null}
      <section className="panel knowledge-create">
        <div>
          <strong>创建知识库</strong>
          <span>例如“财务制度”“产品文档”或“运维手册”</span>
        </div>
        <input aria-label="知识库名称" placeholder="知识库名称" value={name} onChange={(event) => setName(event.target.value)} />
        <input aria-label="知识库描述" placeholder="用途与内容范围" value={description} onChange={(event) => setDescription(event.target.value)} />
        <button className="primary-small" onClick={submit} disabled={loading || !name.trim() || role === "viewer"}>{loading ? "处理中…" : role === "viewer" ? "只读账号不可创建" : "创建知识库"}</button>
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
              <button className="delete-knowledge" aria-label={`删除 ${knowledgeBase.name}`} disabled={knowledgeBase.id === "platform" || loading || !["owner", "admin"].includes(role)} onClick={() => onDelete(knowledgeBase.id)}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      </section>
    </Section>
  );
}

type IngestionProps = {
  knowledgeBaseId: string;
  knowledgeBaseName: string;
  documents: SourceDocument[];
  documentsLoading: boolean;
  documentActionId: string | null;
  queue: UploadQueueItem[];
  loading: boolean;
  error: string | null;
  role: TenantRole;
  maxBatchFiles: number;
  maxDocumentMib: number;
  onUpload: (files: File[]) => void;
  onReplace: (documentId: string, file: File) => Promise<void>;
  onDelete: (documentId: string) => Promise<void>;
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

export function IngestionView({
  knowledgeBaseId,
  knowledgeBaseName,
  documents,
  documentsLoading,
  documentActionId,
  queue,
  loading,
  error,
  onUpload,
  onReplace,
  onDelete,
  role,
  maxBatchFiles,
  maxDocumentMib
}: IngestionProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const replacementInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [replacementTarget, setReplacementTarget] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const disabled = role === "viewer" || loading;

  function selectFiles(files: FileList | null) {
    const selected = Array.from(files ?? []);
    if (selected.length) onUpload(selected);
  }

  useEffect(() => {
    setReplacementTarget(null);
    setDeleteTarget(null);
  }, [knowledgeBaseId]);

  return (
    <Section title="文档管理" eyebrow={`当前知识库：${knowledgeBaseName}`} description="上传企业资料，系统会完成解析、OCR、分块与索引，并保留章节上下文。">
      <button
        className={`upload-zone ${dragActive ? "is-dragging" : ""}`}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) setDragActive(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          if (!disabled) selectFiles(event.dataTransfer.files);
        }}
      >
        {loading ? <LoaderCircle className="spin" size={32} /> : <CloudUpload size={32} />}
        <strong>{loading ? "正在按顺序处理文件…" : role === "viewer" ? "只读账号不可上传文档" : "拖放文件到这里，或点击批量选择"}</strong>
        <span>每批最多 {maxBatchFiles} 个 · 单个最大 {maxDocumentMib} MiB · 支持文档、图片 OCR，以及 JSON、JSONL、CSV 聊天记录</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".md,.markdown,.txt,.pdf,.docx,.json,.jsonl,.ndjson,.csv,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
          hidden
          onChange={(event) => {
            selectFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </button>
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="document-catalog" aria-live="polite">
        <div className="document-catalog-heading">
          <div>
            <strong>已入库文档</strong>
            <span>每个文件独立管理；替换成功后才会切换检索版本。</span>
          </div>
          <b>{documents.length} 个文件</b>
        </div>
        <input
          ref={replacementInputRef}
          type="file"
          accept=".md,.markdown,.txt,.pdf,.docx,.json,.jsonl,.ndjson,.csv,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            const documentId = replacementTarget;
            event.target.value = "";
            if (!file || !documentId) return;
            void onReplace(documentId, file)
              .catch(() => undefined)
              .finally(() => setReplacementTarget(null));
          }}
        />
        {documentsLoading ? (
          <div className="document-empty">
            <LoaderCircle className="spin" size={22} />
            <span>正在读取文档目录…</span>
          </div>
        ) : documents.length ? (
          <div className="document-list">
            {documents.map((document) => {
              const busy = documentActionId === document.id;
              const confirmingDelete = deleteTarget === document.id;
              return (
                <div className={`document-row ${confirmingDelete ? "is-confirming" : ""}`} key={document.id}>
                  <span className="document-file-icon"><FileText size={20} /></span>
                  <div className="document-identity">
                    <strong title={document.filename}>{document.filename}</strong>
                    <span>{formatDocumentType(document.content_type)} · {formatFileSize(document.size_bytes)}</span>
                  </div>
                  <div className="document-index-state">
                    <strong>版本 {document.version}</strong>
                    <span>{document.chunks_count} 个检索分块</span>
                  </div>
                  <div className="document-updated">
                    <strong>{formatDocumentDate(document.updated_at)}</strong>
                    <span>最近更新</span>
                  </div>
                  <div className="document-actions">
                    {document.original_available ? (
                      <a
                        className="document-action"
                        href={documentDownloadUrl(knowledgeBaseId, document.id)}
                        title="下载当前原文件"
                      >
                        <Download size={17} />下载
                      </a>
                    ) : (
                      <span className="document-action is-disabled" title="迁移前文件没有保留原件">
                        <Download size={17} />无原件
                      </span>
                    )}
                    {role !== "viewer" ? (
                      <>
                        <button
                          className="document-action"
                          disabled={busy}
                          onClick={() => {
                            setReplacementTarget(document.id);
                            replacementInputRef.current?.click();
                          }}
                        >
                          {busy ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}
                          替换
                        </button>
                        <button
                          className="document-action is-danger"
                          disabled={busy}
                          onClick={() => setDeleteTarget(document.id)}
                        >
                          <Trash2 size={17} />删除
                        </button>
                      </>
                    ) : null}
                  </div>
                  {confirmingDelete ? (
                    <div className="document-delete-confirmation">
                      <span>删除后，该文件的原件、文本分块和向量索引都会移除。确定继续吗？</span>
                      <button disabled={busy} onClick={() => setDeleteTarget(null)}>取消</button>
                      <button
                        className="confirm-danger"
                        disabled={busy}
                        onClick={() => {
                          void onDelete(document.id)
                            .then(() => setDeleteTarget(null))
                            .catch(() => undefined);
                        }}
                      >
                        {busy ? "正在删除…" : "确认删除"}
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="document-empty">
            <FileText size={24} />
            <div><strong>这个知识库还没有文档</strong><span>上传完成后，文件会长期显示在这里。</span></div>
          </div>
        )}
      </section>
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
      {queue.length ? (
        <section className="panel upload-queue" aria-live="polite">
          <div className="panel-heading">
            <strong>本批上传队列</strong>
            <span>{queue.filter((item) => item.status === "completed").length} / {queue.length} 已完成</span>
          </div>
          <div className="upload-queue-list">
            {queue.map((item) => (
              <div className={`upload-queue-row is-${item.status}`} key={item.id}>
                <span className="upload-status-icon">
                  {item.status === "uploading"
                    ? <LoaderCircle className="spin" size={18} />
                    : item.status === "completed"
                      ? <CheckCircle2 size={18} />
                      : <FileText size={18} />}
                </span>
                <div>
                  <strong>{item.filename}</strong>
                  <small>{formatFileSize(item.size)} · {item.error ?? (item.job ? `${item.job.chunks_created} 个分块` : statusLabel(item.status))}</small>
                </div>
                <span>{item.job ? jobStatusLabel(item.job.status) : statusLabel(item.status)}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </Section>
  );
}

function statusLabel(status: UploadQueueItem["status"]) {
  return {
    queued: "等待上传",
    uploading: "正在上传",
    completed: "处理完成",
    failed: "处理失败"
  }[status];
}

function formatFileSize(size: number) {
  if (size === 0) return "大小未知";
  return size >= 1024 * 1024
    ? `${(size / (1024 * 1024)).toFixed(1)} MiB`
    : `${Math.max(1, Math.round(size / 1024))} KiB`;
}

function formatDocumentType(contentType: string) {
  const labels: Record<string, string> = {
    "text/markdown": "Markdown",
    "text/plain": "TXT",
    "text/csv": "聊天记录 CSV",
    "application/json": "聊天记录 JSON",
    "application/x-ndjson": "聊天记录 JSONL",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX"
  };
  return labels[contentType] ?? contentType.split("/").pop()?.toUpperCase() ?? "文件";
}

function formatDocumentDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知时间";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}

type EvaluationProps = {
  knowledgeBaseName: string;
  suites: EvaluationSuite[];
  selectedSuiteId: string;
  catalogLoading: boolean;
  report: EvaluationReport | null;
  loading: boolean;
  error: string | null;
  role: TenantRole;
  onSuiteChange: (suiteId: string) => void;
  onRun: () => void;
};

export function EvaluationView({
  knowledgeBaseName,
  suites,
  selectedSuiteId,
  catalogLoading,
  report,
  loading,
  error,
  role,
  onSuiteChange,
  onRun
}: EvaluationProps) {
  const metrics = report?.metrics ?? {};
  const selectedSuite = suites.find((suite) => suite.id === selectedSuiteId);
  const hasSuites = suites.length > 0;
  return (
    <Section title="质量评测" eyebrow="RAG 质量门禁" description="在发布 RAG 变更前，分别衡量检索质量与答案忠实度。">
      <div className="evaluation-hero panel">
        <div className="evaluation-hero-copy">
          <span className="eyeline">当前知识库 · {knowledgeBaseName}</span>
          <h2>
            {catalogLoading
              ? "正在加载评测配置"
              : selectedSuite?.name ?? "尚未配置评测集"}
          </h2>
          <p>
            {selectedSuite
              ? `${selectedSuite.description}。共 ${selectedSuite.case_count} 个标注问题，本次运行 6 个快速样本。`
              : "此知识库没有绑定黄金评测集，因此不会运行其他知识库的评测数据。"}
          </p>
          {hasSuites ? (
            <label className="suite-picker">
              <span>选择本次评测集</span>
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
        </div>
        <button
          className="investigate-button"
          onClick={onRun}
          disabled={loading || catalogLoading || !selectedSuiteId || role === "viewer"}
        >
          <Play size={14} />
          {loading ? "正在评测…" : role === "viewer" ? "只读账号不可运行" : hasSuites ? "运行真实评测" : "尚未配置评测集"}
        </button>
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
      </div> : (
        <section className="panel evaluation-empty">
          {catalogLoading
            ? "正在读取当前知识库的评测配置…"
            : hasSuites
              ? "尚无真实评测结果。选择评测集并运行后才会显示指标。"
              : "尚未配置评测集。请先为当前知识库准备独立的黄金问题与期望来源。"}
        </section>
      )}
      <section className="panel run-detail">
        <BookOpenCheck size={22} /><div><strong>{report ? `评测任务 ${report.run_id}` : hasSuites ? "尚未运行评测" : "当前知识库没有评测集"}</strong><p>{report ? `${report.case_count} / ${report.suite_total} 个用例已完成，耗时 ${(report.duration_ms / 1000).toFixed(1)} 秒，裁判：${report.judge}。` : hasSuites ? "运行所选快速基准，将当前检索与生成链路和该知识库的黄金集进行对比。" : "系统已启用归属校验，不允许把平台运维黄金集运行到当前知识库。"}</p></div>
      </section>
    </Section>
  );
}

type TeamProps = {
  organizationName: string;
  organizationUrl: string;
  currentRole: TenantRole;
  members: OrganizationMember[];
  invitations: TenantInvitation[];
  createdInvitation: CreatedTenantInvitation | null;
  loading: boolean;
  error: string | null;
  onInvite: (
    email: string,
    role: Exclude<TenantRole, "owner">
  ) => Promise<void>;
  onRevoke: (invitationId: string) => Promise<void>;
};

export function TeamView({
  organizationName,
  organizationUrl,
  currentRole,
  members,
  invitations,
  createdInvitation,
  loading,
  error,
  onInvite,
  onRevoke
}: TeamProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Exclude<TenantRole, "owner">>("viewer");
  const [copyLabel, setCopyLabel] = useState("复制统一入口");
  const canManage = currentRole === "owner" || currentRole === "admin";

  async function copy(value: string, successLabel: string) {
    await navigator.clipboard.writeText(value);
    setCopyLabel(successLabel);
    window.setTimeout(() => setCopyLabel("复制统一入口"), 1800);
  }

  async function submit() {
    if (!email.trim()) return;
    await onInvite(email.trim(), role);
    setEmail("");
  }

  return (
    <Section
      title="成员与权限"
      eyebrow="企业协作与权限"
      description="邀请同事进入同一企业空间，并通过角色控制知识库管理与只读问答权限。"
    >
      <div className="stat-strip team-stats">
        <Stat label="正式成员" value={String(members.length)} />
        <Stat label="待接受邀请" value={String(invitations.length)} />
        <Stat label="当前角色" value={roleLabel(currentRole)} />
        <Stat label="数据边界" value="仅本企业" />
      </div>

      <section className="panel tenant-url-card">
        <div>
          <span className="tenant-url-icon"><Users size={22} /></span>
          <div>
            <strong>RunbookIQ 统一访问入口</strong>
            <p>{organizationName} 的成员通过同一地址登录，系统会依据账号自动进入本企业空间。</p>
          </div>
        </div>
        <code>{organizationUrl}</code>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void copy(organizationUrl, "统一入口已复制")}
        >
          <Copy size={16} />{copyLabel}
        </button>
      </section>

      {canManage ? (
        <section className="panel invite-panel">
          <div className="invite-heading">
            <span><MailPlus size={20} /></span>
            <div>
              <strong>邀请企业成员</strong>
              <p>邀请链接 7 天内有效且只能使用一次。当前版本由管理员安全地发送链接。</p>
            </div>
          </div>
          <div className="invite-form">
            <label>
              <span>成员邮箱</span>
              <input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              <span>加入后的角色</span>
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as Exclude<TenantRole, "owner">)}
              >
                <option value="viewer">只读成员 · 问答与查看证据</option>
                <option value="editor">内容编辑者 · 上传与评测</option>
                <option value="admin">管理员 · 管理知识库与成员</option>
              </select>
            </label>
            <button
              className="primary-small"
              type="button"
              disabled={loading || !email.trim()}
              onClick={() => void submit()}
            >
              {loading ? "正在生成…" : "生成邀请链接"}
            </button>
          </div>
          {createdInvitation ? (
            <div className="invite-result" role="status">
              <div>
                <strong>邀请已创建</strong>
                <span>{createdInvitation.email} · {roleLabel(createdInvitation.role)}</span>
              </div>
              <code>{createdInvitation.accept_url}</code>
              <button
                className="secondary-button"
                type="button"
                onClick={() => void copy(createdInvitation.accept_url, "邀请链接已复制")}
              >
                <Copy size={16} />复制邀请链接
              </button>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="panel settings-notice">
          <ShieldCheck size={22} />
          <div>
            <strong>当前账号为{roleLabel(currentRole)}</strong>
            <p>你可以查看同企业成员；生成和撤销邀请需要企业所有者或管理员权限。</p>
          </div>
        </section>
      )}

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="team-grid">
        <section className="panel table-panel">
          <div className="panel-heading">
            <strong>企业成员</strong><span>{members.length} 人</span>
          </div>
          <div className="member-list">
            {members.map((member) => (
              <div className="member-row" key={member.user_id}>
                <span className="member-avatar"><UserRound size={18} /></span>
                <div><strong>{member.email}</strong><small>{new Date(member.joined_at).toLocaleDateString("zh-CN")} 加入</small></div>
                <span className={`role-badge role-${member.role}`}>{roleLabel(member.role)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel table-panel">
          <div className="panel-heading">
            <strong>待接受邀请</strong><span>{invitations.length} 条</span>
          </div>
          <div className="member-list">
            {invitations.length ? invitations.map((invitation) => (
              <div className="member-row" key={invitation.id}>
                <span className="member-avatar"><MailPlus size={18} /></span>
                <div>
                  <strong>{invitation.email}</strong>
                  <small>{new Date(invitation.expires_at).toLocaleDateString("zh-CN")} 到期</small>
                </div>
                <span className={`role-badge role-${invitation.role}`}>{roleLabel(invitation.role)}</span>
                {canManage ? (
                  <button
                    className="delete-knowledge"
                    aria-label={`撤销 ${invitation.email} 的邀请`}
                    disabled={loading}
                    onClick={() => void onRevoke(invitation.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                ) : null}
              </div>
            )) : <div className="team-empty">当前没有待接受邀请。</div>}
          </div>
        </section>
      </div>
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
  error,
  branding,
  role,
  onSaveBranding
}: {
  config: RuntimeConfig | null;
  error: string | null;
  branding: OrganizationBranding;
  role: TenantRole;
  onSaveBranding: (branding: OrganizationBranding) => Promise<OrganizationBranding>;
}) {
  const [draft, setDraft] = useState(branding);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const canManageBranding = role === "owner" || role === "admin";

  useEffect(() => setDraft(branding), [branding]);

  function updateDraft<K extends keyof OrganizationBranding>(
    key: K,
    value: OrganizationBranding[K]
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function save() {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const next = await onSaveBranding(draft);
      setDraft(next);
      setSaved(true);
    } catch (nextError) {
      setSaveError(nextError instanceof Error ? nextError.message : "企业品牌保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section
      title="企业设置"
      eyebrow="企业界面与平台配置"
      description="在统一产品模板中维护企业名称、品牌色和欢迎内容；底层模型配置仍由服务器安全托管。"
    >
      <div className="branding-layout">
        <section className="panel branding-form">
          <div className="settings-title">
            <Palette size={21} />
            <span>
              <strong>企业品牌</strong>
              <small>保存后立即对本企业所有成员生效</small>
            </span>
          </div>
          <div className="branding-fields">
            <label>
              <span>企业显示名称</span>
              <input
                value={draft.display_name}
                minLength={2}
                maxLength={80}
                disabled={!canManageBranding}
                onChange={(event) => updateDraft("display_name", event.target.value)}
              />
            </label>
            <label>
              <span>Logo 地址</span>
              <input
                value={draft.logo_url ?? ""}
                maxLength={500}
                disabled={!canManageBranding}
                placeholder="https://example.com/logo.png"
                onChange={(event) => updateDraft("logo_url", event.target.value || null)}
              />
              <small>支持 HTTPS 图片地址或站内相对路径，留空时显示企业首字。</small>
            </label>
            <label>
              <span>品牌主色</span>
              <div className="color-field">
                <input
                  type="color"
                  value={draft.primary_color}
                  disabled={!canManageBranding}
                  onChange={(event) => updateDraft("primary_color", event.target.value.toUpperCase())}
                />
                <input
                  value={draft.primary_color}
                  pattern="^#[0-9A-Fa-f]{6}$"
                  maxLength={7}
                  disabled={!canManageBranding}
                  onChange={(event) => updateDraft("primary_color", event.target.value)}
                />
              </div>
            </label>
            <label>
              <span>知识问答欢迎标题</span>
              <input
                value={draft.welcome_title}
                minLength={2}
                maxLength={80}
                disabled={!canManageBranding}
                onChange={(event) => updateDraft("welcome_title", event.target.value)}
              />
            </label>
            <label className="branding-message-field">
              <span>欢迎说明</span>
              <textarea
                value={draft.welcome_message}
                minLength={2}
                maxLength={240}
                disabled={!canManageBranding}
                onChange={(event) => updateDraft("welcome_message", event.target.value)}
              />
            </label>
          </div>
          {saveError ? <div className="error-banner">{saveError}</div> : null}
          {!canManageBranding ? (
            <p className="permission-note">当前角色只能查看品牌配置，修改需要企业所有者或管理员权限。</p>
          ) : null}
          <div className="settings-actions">
            <span>{saved ? "企业品牌已保存并生效。" : "修改仅影响当前企业空间。"}</span>
            <button
              className="primary-small"
              type="button"
              disabled={
                !canManageBranding
                || saving
                || !draft.display_name.trim()
                || !/^#[0-9A-Fa-f]{6}$/.test(draft.primary_color)
                || !draft.welcome_title.trim()
                || !draft.welcome_message.trim()
              }
              onClick={() => void save()}
            >
              {saving ? "正在保存…" : "保存企业品牌"}
            </button>
          </div>
        </section>

        <section
          className="branding-preview"
          style={{ "--preview-brand": draft.primary_color } as CSSProperties}
        >
          <span className="preview-label">实时预览</span>
          <div className="preview-window">
            <div className="preview-sidebar">
              <span className="preview-logo">
                {draft.logo_url
                  ? <img src={draft.logo_url} alt="" />
                  : draft.display_name.slice(0, 1).toUpperCase()}
              </span>
              <strong>{draft.display_name || "企业名称"}</strong>
              <i />
              <i />
              <i />
            </div>
            <div className="preview-content">
              <small>企业知识 · 证据问答</small>
              <h3>{draft.welcome_title || "企业知识空间"}</h3>
              <p>{draft.welcome_message || "欢迎说明"}</p>
              <button type="button">提交问题</button>
            </div>
          </div>
        </section>
      </div>

      <section className="panel settings-notice">
        <ShieldCheck size={22} />
        <div>
          <strong>底层配置采用只读展示</strong>
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
              <ConfigRow label="批量上传" value={`每批最多 ${config.max_batch_files} 个文件`} />
            </dl>
          ) : (
            <div className="settings-empty">
              <strong>正在读取运行配置</strong>
              <p>配置加载完成后会显示当前服务器实际使用的模型与检索参数。</p>
            </div>
          )}
        </section>
        <section className="panel settings-card">
          <div className="settings-title"><ShieldCheck size={20} /><span><strong>免费阶段使用限制</strong><small>服务端强制执行 · 防止模型与存储资源被滥用</small></span></div>
          {config ? (
            <dl className="runtime-config-list">
              <ConfigRow label="企业问答" value={`每个企业每天 ${config.query_limit_per_day} 次`} />
              <ConfigRow label="文档上传" value={`每个企业每天 ${config.upload_limit_per_day} 份`} />
              <ConfigRow label="质量评测" value={`每个企业每小时 ${config.evaluation_limit_per_hour} 次`} />
              <ConfigRow label="知识库" value={`每个企业最多 ${config.max_knowledge_bases} 个`} />
              <ConfigRow label="企业成员" value={`含待接受邀请最多 ${config.max_organization_members} 人`} />
              <ConfigRow label="机器人防护" value={config.turnstile_enabled ? "Cloudflare Turnstile 已启用" : "应用限流已启用，Turnstile 待配置"} />
            </dl>
          ) : <div className="settings-empty"><strong>正在读取限制配置</strong></div>}
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
    faithfulness: "答案忠实度",
    section_recall_at_5: "会话/章节召回率",
    evidence_term_recall_at_5: "证据关键事实覆盖率",
    answer_term_coverage: "答案关键事实覆盖率"
  };
  return labels[key] ?? key.replaceAll("_", " ");
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function roleLabel(role: TenantRole) {
  return {
    owner: "企业所有者",
    admin: "管理员",
    editor: "内容编辑者",
    viewer: "只读成员"
  }[role];
}
