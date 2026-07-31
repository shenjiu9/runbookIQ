import { useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      action: string;
      theme: "light";
      language: string;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    }
  ) => string;
  remove: (widgetId: string) => void;
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
      script.referrerPolicy = "no-referrer";
      document.head.appendChild(script);
    }
  }).catch((error) => {
    scriptPromise = null;
    throw error;
  });
  return scriptPromise;
}

export function TurnstileWidget({
  siteKey,
  action,
  onTokenChange
}: {
  siteKey: string;
  action: string;
  onTokenChange: (token: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onTokenChange);
  const [error, setError] = useState<string | null>(null);
  callbackRef.current = onTokenChange;

  useEffect(() => {
    let cancelled = false;
    let widgetId: string | null = null;
    callbackRef.current(null);
    void loadTurnstile()
      .then((api) => {
        if (cancelled || !containerRef.current) return;
        widgetId = api.render(containerRef.current, {
          sitekey: siteKey,
          action,
          theme: "light",
          language: "zh-CN",
          callback: (token) => {
            setError(null);
            callbackRef.current(token);
          },
          "expired-callback": () => callbackRef.current(null),
          "error-callback": () => {
            callbackRef.current(null);
            setError("人机验证暂时不可用，请刷新页面重试");
          }
        });
      })
      .catch(() => {
        if (!cancelled) setError("人机验证加载失败，请检查网络后重试");
      });
    return () => {
      cancelled = true;
      callbackRef.current(null);
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [action, siteKey]);

  return (
    <div className="turnstile-field">
      <div ref={containerRef} />
      {error ? <p role="alert">{error}</p> : <small>由 Cloudflare Turnstile 完成人机验证</small>}
    </div>
  );
}
