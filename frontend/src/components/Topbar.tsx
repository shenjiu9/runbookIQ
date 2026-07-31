import { BookOpen, LogOut } from "lucide-react";
import type { NavKey } from "../types";

const pageLabels: Record<NavKey, string> = {
  ask: "知识问答",
  knowledge: "知识库",
  ingestion: "文档管理",
  evaluation: "质量评测",
  team: "成员与权限",
  settings: "企业设置"
};

export function Topbar({
  healthy,
  knowledgeBaseName,
  organizationName,
  userEmail,
  page,
  onLogout
}: {
  healthy: boolean | null;
  knowledgeBaseName: string;
  organizationName: string;
  userEmail: string;
  page: NavKey;
  onLogout: () => void;
}) {
  const healthLabel = healthy === null
    ? "检查服务中"
    : healthy
      ? "服务正常"
      : "连接异常";

  return (
    <header className="topbar">
      <div className="topbar-title">
        <span>{organizationName}</span>
        <i>/</i>
        <strong>{pageLabels[page]}</strong>
      </div>
      <div className="topbar-actions">
        <div className="topbar-scope" title="当前问答和文档操作范围">
          <BookOpen size={16} />
          <span>{knowledgeBaseName}</span>
        </div>
        <div className={`system-health ${healthy === false ? "is-error" : ""}`}>
          <i />
          <span>{healthLabel}</span>
        </div>
        <button className="account-menu" type="button" title={userEmail}>
          {userEmail.slice(0, 1).toUpperCase()}
        </button>
        <button className="logout-button" type="button" onClick={onLogout}>
          <LogOut size={17} />
          <span>退出</span>
        </button>
      </div>
    </header>
  );
}
