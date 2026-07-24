import {
  BarChart3,
  BookOpen,
  Database,
  MessageSquareText,
  Settings,
  type LucideIcon
} from "lucide-react";
import type { NavKey } from "../types";

type Props = {
  active: NavKey;
  onChange: (key: NavKey) => void;
};

const items: Array<{ key: NavKey; label: string; icon: LucideIcon }> = [
  { key: "ask", label: "故障调查", icon: MessageSquareText },
  { key: "knowledge", label: "知识库", icon: BookOpen },
  { key: "ingestion", label: "文档摄取", icon: Database },
  { key: "evaluation", label: "质量评测", icon: BarChart3 },
  { key: "settings", label: "系统设置", icon: Settings }
];

export function Sidebar({ active, onChange }: Props) {
  return (
    <aside className="sidebar">
      <button className="brand" onClick={() => onChange("ask")} aria-label="RunbookIQ 首页">
        Runbook<span>IQ</span>
      </button>
      <nav className="primary-nav" aria-label="主导航">
        {items.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={active === key ? "nav-item is-active" : "nav-item"}
            onClick={() => onChange(key)}
          >
            <Icon size={17} strokeWidth={1.7} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-meta">
        <span className="meta-label">工作空间</span>
        <strong>平台工程团队</strong>
        <span className="meta-label environment-label">运行环境</span>
        <div className="environment"><i />生产环境</div>
      </div>
    </aside>
  );
}
