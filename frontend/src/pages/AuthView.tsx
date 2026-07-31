import { Building2, CheckCircle2, LockKeyhole, Mail } from "lucide-react";
import { FormEvent, useState } from "react";

import { login, register } from "../api";
import type { TenantContext } from "../types";

type Props = {
  onAuthenticated: (context: TenantContext) => void;
};

export function AuthView({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [slug, setSlug] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const context = mode === "login"
        ? await login(email, password)
        : await register({
            email,
            password,
            organization_name: organizationName,
            slug
          });
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
        <div className="auth-mode" role="tablist" aria-label="账号入口">
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
        </div>

        <div className="auth-card-heading">
          <span className="auth-icon"><LockKeyhole size={22} /></span>
          <div>
            <h2 id="auth-title">{mode === "login" ? "欢迎回来" : "开始创建企业知识库"}</h2>
            <p>{mode === "login" ? "登录后继续管理企业知识。" : "注册成功后将自动生成专属企业网址。"}</p>
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" ? (
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

          <label>
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
          </label>
          <label>
            <span>密码</span>
            <div className="auth-input">
              <LockKeyhole size={19} />
              <input
                required
                type="password"
                minLength={mode === "register" ? 12 : 1}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === "register" ? "至少 12 位" : "输入密码"}
              />
            </div>
          </label>

          {error ? <div className="auth-error" role="alert">{error}</div> : null}

          <button className="auth-submit" type="submit" disabled={submitting}>
            {submitting
              ? "正在处理..."
              : mode === "login"
                ? "登录企业空间"
                : "创建企业空间"}
          </button>
        </form>
      </section>
    </main>
  );
}
