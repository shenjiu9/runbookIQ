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
  organizationName: string;
};

const items: Array<{ key: NavKey; label: string; icon: LucideIcon }> = [
  { key: "ask", label: "故障调查", icon: MessageSquareText },
  { key: "knowledge", label: "知识库", icon: BookOpen },
  { key: "ingestion", label: "文档摄取", icon: Database },
  { key: "evaluation", label: "质量评测", icon: BarChart3 },
  { key: "settings", label: "系统设置", icon: Settings }
];

export function Sidebar({ active, onChange, organizationName }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand-wrap">
        <button className="brand" onClick={() => onChange("ask")} aria-label="RunbookIQ 首页">
          <span className="brand-mark">R</span>
          <span className="brand-name">Runbook<i>IQ</i></span>
        </button>
        <span className="product-tag">智能运维知识台</span>
      </div>
      <nav className="primary-nav" aria-label="主导航">
        {items.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={active === key ? "nav-item is-active" : "nav-item"}
            onClick={() => onChange(key)}
          >
            <Icon size={19} strokeWidth={1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-meta">
        <span className="meta-label">当前工作空间</span>
        <strong>{organizationName}</strong>
        <div className="environment"><i />生产环境</div>
      </div>
    </aside>
  );
}
