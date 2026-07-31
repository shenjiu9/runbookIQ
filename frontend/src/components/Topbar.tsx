import { BookOpen, LogOut, Network } from "lucide-react";

export function Topbar({
  healthy,
  knowledgeBaseName,
  organizationName,
  userEmail,
  onLogout
}: {
  healthy: boolean | null;
  knowledgeBaseName: string;
  organizationName: string;
  userEmail: string;
  onLogout: () => void;
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
        <span>{organizationName}</span>
      </div>
      <div className="topbar-actions">
        <div className="topbar-scope"><BookOpen size={16} />{knowledgeBaseName}</div>
        <div className={`system-health ${healthy === false ? "is-error" : ""}`}>
          <i />
          <span>{healthLabel}</span>
        </div>
        <div className="avatar" aria-label={userEmail}>
          {organizationName.slice(0, 2).toUpperCase()}
        </div>
        <button className="logout-button" type="button" onClick={onLogout}>
          <LogOut size={17} />
          <span>退出</span>
        </button>
      </div>
    </header>
  );
}
