import { useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      action: string;
      theme: "light";
      language: string;
      size: "flexible";
      retry: "auto";
      "retry-interval": number;
      "refresh-expired": "auto";
      "refresh-timeout": "auto";
      "response-field": false;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": (errorCode: string) => void;
      "timeout-callback": () => void;
      "unsupported-callback": () => void;
    }
  ) => string;
  remove: (widgetId: string) => void;
  reset: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_ID = "cloudflare-turnstile-script";
const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let scriptPromise: Promise<TurnstileApi> | null = null;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<TurnstileApi>((resolve, reject) => {
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    const loaded = () => {
      if (window.turnstile) resolve(window.turnstile);
      else reject(new Error("Turnstile 未能初始化"));
    };
    script.addEventListener("load", loaded, { once: true });
    script.addEventListener("error", () => reject(new Error("Turnstile 加载失败")), {
      once: true
    });
    if (!existing) {
      script.id = SCRIPT_ID;
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }).catch((error) => {
    scriptPromise = null;
    const failedScript = document.getElementById(SCRIPT_ID);
    if (!window.turnstile) failedScript?.remove();
    throw error;
  });
  return scriptPromise;
}

export function TurnstileWidget({
  siteKey,
  action,
  required = true,
  onTokenChange
}: {
  siteKey: string;
  action: string;
  required?: boolean;
  onTokenChange: (token: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const callbackRef = useRef(onTokenChange);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  callbackRef.current = onTokenChange;

  useEffect(() => {
    let cancelled = false;
    setError(null);
    callbackRef.current(null);
    void loadTurnstile()
      .then((api) => {
        if (cancelled || !containerRef.current) return;
        widgetIdRef.current = api.render(containerRef.current, {
          sitekey: siteKey,
          action,
          theme: "light",
          language: "zh-CN",
          size: "flexible",
          retry: "auto",
          "retry-interval": 5000,
          "refresh-expired": "auto",
          "refresh-timeout": "auto",
          "response-field": false,
          callback: (token) => {
            setError(null);
            callbackRef.current(token);
          },
          "expired-callback": () => callbackRef.current(null),
          "timeout-callback": () => {
            callbackRef.current(null);
            setError("验证等待超时，请重新验证");
          },
          "unsupported-callback": () => {
            callbackRef.current(null);
            setError("当前内置浏览器不支持人机验证，请使用 Safari 或 Chrome 打开");
          },
          "error-callback": (errorCode) => {
            callbackRef.current(null);
            setError(`人机验证暂时不可用（错误码 ${errorCode}）`);
          }
        });
      })
      .catch(() => {
        if (!cancelled) setError("人机验证加载失败，请检查网络后重试");
      });
    return () => {
      cancelled = true;
      callbackRef.current(null);
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
      }
      widgetIdRef.current = null;
    };
  }, [action, attempt, siteKey]);

  function retryVerification() {
    setError(null);
    callbackRef.current(null);
    if (widgetIdRef.current && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
      return;
    }
    setAttempt((current) => current + 1);
  }

  return (
    <div className="turnstile-field">
      <div ref={containerRef} />
      {error ? (
        <div className="turnstile-recovery" role="alert">
          <p>
            {error}
            {!required ? "；你仍可继续注册，系统会启用频率限制" : ""}
          </p>
          <button type="button" onClick={retryVerification}>重新验证</button>
        </div>
      ) : <small>由 Cloudflare Turnstile 完成人机验证</small>}
    </div>
  );
}
