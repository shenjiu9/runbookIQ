import { BookOpen, Network } from "lucide-react";

export function Topbar({
  healthy,
  knowledgeBaseName
}: {
  healthy: boolean | null;
  knowledgeBaseName: string;
}) {
  const healthLabel = healthy === null
    ? "正在检查服务"
    : healthy
      ? "API 服务可用"
      : "API 连接异常";

  return (
    <header className="topbar">
      <div className="workspace-context">
        <Network size={16} />
        <span>平台工程团队</span>
      </div>
      <div className="topbar-actions">
        <div className="topbar-scope"><BookOpen size={16} />{knowledgeBaseName}</div>
        <div className={`system-health ${healthy === false ? "is-error" : ""}`}>
          <i />
          <span>{healthLabel}</span>
        </div>
        <div className="avatar" aria-label="平台工程团队">PE</div>
      </div>
    </header>
  );
}
