import { Building2, CheckCircle2, LockKeyhole, Mail, Users } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { acceptInvitation, login, previewInvitation, register } from "../api";
import type { TenantContext, TenantInvitationPreview } from "../types";

type Props = {
  onAuthenticated: (context: TenantContext) => void;
};

export function AuthView({ onAuthenticated }: Props) {
  const [invitationToken] = useState(() => (
    typeof window === "undefined"
      ? ""
      : new URLSearchParams(window.location.hash.slice(1)).get("invite")
        ?? new URLSearchParams(window.location.search).get("invite")
        ?? ""
  ));
  const [invitation, setInvitation] = useState<TenantInvitationPreview | null>(null);
  const [invitationLoading, setInvitationLoading] = useState(Boolean(invitationToken));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [slug, setSlug] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!invitationToken) return;
    void previewInvitation(invitationToken)
      .then(setInvitation)
      .catch((nextError) => {
        setError(nextError instanceof Error ? nextError.message : "邀请链接无效");
      })
      .finally(() => setInvitationLoading(false));
  }, [invitationToken]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const context = invitationToken
        ? await acceptInvitation(invitationToken, password)
        : mode === "login"
          ? await login(email, password)
          : await register({
              email,
              password,
              organization_name: organizationName,
              slug
            });
      if (invitationToken && typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
      onAuthenticated(context);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "认证失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <div className="auth-brand">
          <span className="brand-mark">R</span>
          <span className="brand-name">Runbook<i>IQ</i></span>
        </div>
        <p className="eyebrow">企业级知识库与可信问答</p>
        <h1>让企业知识真正成为每个人都能使用的生产力。</h1>
        <p className="auth-description">
          上传制度、手册和业务资料，自动完成解析、检索与证据引用。
          每个企业拥有独立空间、专属网址和严格隔离的数据。
        </p>
        <ul className="auth-benefits">
          <li><CheckCircle2 size={20} />回答附带可核验的原文证据</li>
          <li><CheckCircle2 size={20} />企业与知识库双重隔离</li>
          <li><CheckCircle2 size={20} />支持 DOCX、PDF、Markdown 与 OCR</li>
        </ul>
      </section>

      <section className="auth-card" aria-labelledby="auth-title">
        {!invitationToken ? <div className="auth-mode" role="tablist" aria-label="账号入口">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "is-active" : ""}
            onClick={() => {
              setMode("login");
              setError(null);
            }}
          >
            登录
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "is-active" : ""}
            onClick={() => {
              setMode("register");
              setError(null);
            }}
          >
            创建企业空间
          </button>
        </div> : null}

        <div className="auth-card-heading">
          <span className="auth-icon">
            {invitationToken ? <Users size={22} /> : <LockKeyhole size={22} />}
          </span>
          <div>
            <h2 id="auth-title">
              {invitationToken
                ? "加入企业知识空间"
                : mode === "login"
                  ? "欢迎回来"
                  : "开始创建企业知识库"}
            </h2>
            <p>
              {invitationToken
                ? invitationLoading
                  ? "正在验证邀请链接…"
                  : invitation
                    ? `${invitation.organization_name} 邀请你以“${roleLabel(invitation.role)}”身份加入。`
                    : "请检查邀请链接是否完整或联系企业管理员。"
                : mode === "login"
                  ? "登录后继续管理企业知识。"
                  : "注册成功后将自动生成专属企业网址。"}
            </p>
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {invitation ? (
            <div className="invitation-summary">
              <span>受邀邮箱</span>
              <strong>{invitation.email}</strong>
              <small>接受后可进入 {invitation.organization_url}</small>
            </div>
          ) : null}

          {!invitationToken && mode === "register" ? (
            <>
              <label>
                <span>企业名称</span>
                <div className="auth-input">
                  <Building2 size={19} />
                  <input
                    required
                    minLength={2}
                    maxLength={120}
                    value={organizationName}
                    onChange={(event) => setOrganizationName(event.target.value)}
                    placeholder="例如：星港零售有限公司"
                  />
                </div>
              </label>
              <label>
                <span>企业网址标识</span>
                <div className="slug-input">
                  <input
                    required
                    minLength={2}
                    maxLength={32}
                    pattern="[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?"
                    value={slug}
                    onChange={(event) => setSlug(event.target.value.toLowerCase())}
                    placeholder="xinggang"
                  />
                  <span>.rag.墩bang妮.top</span>
                </div>
              </label>
            </>
          ) : null}

          {!invitationToken ? <label>
            <span>邮箱</span>
            <div className="auth-input">
              <Mail size={19} />
              <input
                required
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@company.com"
              />
            </div>
          </label> : null}
          <label>
            <span>密码</span>
            <div className="auth-input">
              <LockKeyhole size={19} />
              <input
                required
                type="password"
                minLength={invitationToken || mode === "register" ? 12 : 1}
                autoComplete={invitationToken || mode === "register" ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={invitationToken || mode === "register" ? "设置至少 12 位密码" : "输入密码"}
              />
            </div>
          </label>

          {error ? <div className="auth-error" role="alert">{error}</div> : null}

          <button
            className="auth-submit"
            type="submit"
            disabled={submitting || invitationLoading || (Boolean(invitationToken) && !invitation)}
          >
            {submitting
              ? "正在处理..."
              : invitationToken
                ? "接受邀请并进入"
                : mode === "login"
                  ? "登录企业空间"
                  : "创建企业空间"}
          </button>
        </form>
      </section>
    </main>
  );
}

function roleLabel(role: TenantInvitationPreview["role"]) {
  return {
    admin: "管理员",
    editor: "内容编辑者",
    viewer: "只读成员"
  }[role];
}
