import {
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Users
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  acceptInvitation,
  fetchSecurityConfig,
  login,
  previewInvitation,
  register
} from "../api";
import { TurnstileWidget } from "../components/TurnstileWidget";
import type { SecurityConfig, TenantContext, TenantInvitationPreview } from "../types";

type Props = {
  onAuthenticated: (context: TenantContext) => void;
};

const fallbackSecurityConfig: SecurityConfig = {
  turnstile_enabled: false,
  turnstile_required: false,
  turnstile_site_key: null,
  max_batch_files: 10,
  max_document_mib: 20
};

const REGISTRATION_MIN_PASSWORD_LENGTH = 12;
const INVITATION_MIN_PASSWORD_LENGTH = 8;

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
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [organizationName, setOrganizationName] = useState("");
  const [securityConfig, setSecurityConfig] = useState<SecurityConfig | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileAttempt, setTurnstileAttempt] = useState(0);
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

  useEffect(() => {
    void fetchSecurityConfig()
      .then(setSecurityConfig)
      .catch(() => setSecurityConfig(fallbackSecurityConfig));
  }, []);

  const isNewPassword = Boolean(invitationToken) || mode === "register";
  const newPasswordMinLength = invitationToken
    ? INVITATION_MIN_PASSWORD_LENGTH
    : REGISTRATION_MIN_PASSWORD_LENGTH;
  const passwordsMatch = !isNewPassword || password === confirmPassword;
  const strength = passwordStrength(password, newPasswordMinLength);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isNewPassword && !passwordsMatch) {
      setError("两次输入的密码不一致");
      return;
    }
    if (
      !invitationToken
      && mode === "register"
      && securityConfig?.turnstile_required
      && !turnstileToken
    ) {
      setError("请先完成人机验证");
      return;
    }
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
              turnstile_token: turnstileToken
            });
      if (invitationToken && typeof window !== "undefined") {
        window.history.replaceState({}, "", window.location.pathname);
      }
      onAuthenticated(context);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "认证失败，请稍后重试");
      if (!invitationToken && mode === "register" && securityConfig?.turnstile_enabled) {
        setTurnstileToken(null);
        setTurnstileAttempt((current) => current + 1);
      }
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
        <p className="eyebrow">一个入口 · 独立企业空间</p>
        <h1>把散落的企业资料，变成可核验的知识生产力。</h1>
        <p className="auth-description">
          上传制度、手册和业务资料，自动完成解析、检索与证据引用。
          所有成员从同一入口登录，系统会安全地进入所属企业空间。
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
              setConfirmPassword("");
              setTurnstileToken(null);
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
              setConfirmPassword("");
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
                  : "无需配置域名，注册完成即可开始上传企业资料。"}
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
            <div className="auth-input password-input">
              <LockKeyhole size={19} />
              <input
                required
                type={showPassword ? "text" : "password"}
                minLength={isNewPassword ? newPasswordMinLength : 1}
                maxLength={200}
                autoComplete={isNewPassword ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={
                  isNewPassword
                    ? `设置至少 ${newPasswordMinLength} 位密码`
                    : "输入密码"
                }
              />
              <button
                className="password-visibility"
                type="button"
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((current) => !current)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>

          {isNewPassword ? (
            <>
              <div className={`password-strength strength-${strength.level}`} aria-live="polite">
                <span><i /><i /><i /></span>
                <small>{strength.label} · 建议使用较长且不重复的密码短语</small>
              </div>
              <label>
                <span>确认密码</span>
                <div className="auth-input password-input">
                  <ShieldCheck size={19} />
                  <input
                    required
                    type={showConfirmPassword ? "text" : "password"}
                    minLength={newPasswordMinLength}
                    maxLength={200}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="再次输入密码"
                    aria-invalid={Boolean(confirmPassword) && !passwordsMatch}
                  />
                  <button
                    className="password-visibility"
                    type="button"
                    aria-label={showConfirmPassword ? "隐藏确认密码" : "显示确认密码"}
                    aria-pressed={showConfirmPassword}
                    onClick={() => setShowConfirmPassword((current) => !current)}
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {confirmPassword && !passwordsMatch
                  ? <small className="field-error">两次输入的密码不一致</small>
                  : null}
              </label>
            </>
          ) : null}

          {!invitationToken && mode === "register" && securityConfig?.turnstile_enabled && securityConfig.turnstile_site_key ? (
            <TurnstileWidget
              key={`${securityConfig.turnstile_site_key}-${turnstileAttempt}`}
              siteKey={securityConfig.turnstile_site_key}
              action="register"
              required={securityConfig.turnstile_required}
              onTokenChange={setTurnstileToken}
            />
          ) : null}

          {!invitationToken && mode === "register" && securityConfig?.turnstile_required && !securityConfig.turnstile_enabled ? (
            <div className="auth-error" role="alert">注册保护尚未完成配置，请联系管理员。</div>
          ) : null}

          {error ? <div className="auth-error" role="alert">{error}</div> : null}

          <button
            className="auth-submit"
            type="submit"
            disabled={
              submitting
              || invitationLoading
              || (!invitationToken && mode === "register" && !securityConfig)
              || (Boolean(invitationToken) && !invitation)
              || (
                isNewPassword
                && (!passwordsMatch || password.length < newPasswordMinLength)
              )
              || (
                !invitationToken
                && mode === "register"
                && securityConfig?.turnstile_required
                && !turnstileToken
              )
            }
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

function passwordStrength(password: string, minLength: number) {
  if (!password) return { level: 0, label: `至少 ${minLength} 位` };
  if (password.length < minLength) {
    return { level: 0, label: "长度不足" };
  }
  let score = 1;
  if (password.length >= minLength + 4) score += 1;
  if (/[a-zA-Z]/.test(password) && /\d/.test(password) && /[^a-zA-Z\d]/.test(password)) {
    score += 1;
  }
  const level = Math.min(3, score);
  return {
    level,
    label: ["长度不足", "可用", "较强", "很强"][level]
  };
}

function roleLabel(role: TenantInvitationPreview["role"]) {
  return {
    admin: "管理员",
    editor: "内容编辑者",
    viewer: "只读成员"
  }[role];
}
