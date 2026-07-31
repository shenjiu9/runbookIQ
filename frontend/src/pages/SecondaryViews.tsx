import { useRef, useState, type ReactNode } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  CloudUpload,
  Copy,
  Database,
  FileCode2,
  FileText,
  Gauge,
  LoaderCircle,
  MailPlus,
  Play,
  ShieldCheck,
  ServerCog,
  Trash2,
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
  RuntimeConfig,
  TenantInvitation,
  TenantRole
} from "../types";

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
              <div><strong>企业空间已创建</strong><small>默认知识库与专属网址已生成</small></div>
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
  knowledgeBaseName: string;
  job: IngestionJob | null;
  loading: boolean;
  error: string | null;
  role: TenantRole;
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

export function IngestionView({ knowledgeBaseName, job, loading, error, onUpload, role }: IngestionProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <Section title="文档摄取" eyebrow={`目标：${knowledgeBaseName}`} description="解析、OCR、父子分块并向量化文档，同时保留完整章节上下文。">
      <button className="upload-zone" disabled={role === "viewer"} onClick={() => inputRef.current?.click()}>
        {loading ? <LoaderCircle className="spin" size={32} /> : <CloudUpload size={32} />}
        <strong>{loading ? "正在处理文档…" : role === "viewer" ? "只读账号不可上传文档" : "上传运行手册、事故复盘或参考文档"}</strong>
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
  const [copyLabel, setCopyLabel] = useState("复制专属网址");
  const canManage = currentRole === "owner" || currentRole === "admin";

  async function copy(value: string, successLabel: string) {
    await navigator.clipboard.writeText(value);
    setCopyLabel(successLabel);
    window.setTimeout(() => setCopyLabel("复制专属网址"), 1800);
  }

  async function submit() {
    if (!email.trim()) return;
    await onInvite(email.trim(), role);
    setEmail("");
  }

  return (
    <Section
      title="团队成员"
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
            <strong>{organizationName} 专属入口</strong>
            <p>企业成员可通过此网址登录并访问本企业授权的知识库。</p>
          </div>
        </div>
        <code>{organizationUrl}</code>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void copy(organizationUrl, "企业网址已复制")}
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

function roleLabel(role: TenantRole) {
  return {
    owner: "企业所有者",
    admin: "管理员",
    editor: "内容编辑者",
    viewer: "只读成员"
  }[role];
}
