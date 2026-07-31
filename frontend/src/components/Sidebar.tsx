import {
  BarChart3,
  BookOpen,
  Files,
  MessageSquareText,
  Settings,
  Users,
  type LucideIcon
} from "lucide-react";
import type {
  NavKey,
  OrganizationBranding,
  TenantRole
} from "../types";

type Props = {
  active: NavKey;
  onChange: (key: NavKey) => void;
  branding: OrganizationBranding;
  userEmail: string;
  role: TenantRole;
};

const items: Array<{
  key: NavKey;
  label: string;
  icon: LucideIcon;
  group: "work" | "manage";
}> = [
  { key: "ask", label: "知识问答", icon: MessageSquareText, group: "work" },
  { key: "knowledge", label: "知识库", icon: BookOpen, group: "work" },
  { key: "ingestion", label: "文档管理", icon: Files, group: "work" },
  { key: "evaluation", label: "质量评测", icon: BarChart3, group: "work" },
  { key: "team", label: "成员与权限", icon: Users, group: "manage" },
  { key: "settings", label: "企业设置", icon: Settings, group: "manage" }
];

export function Sidebar({
  active,
  onChange,
  branding,
  userEmail,
  role
}: Props) {
  const initial = branding.display_name.trim().slice(0, 1).toUpperCase() || "R";
  return (
    <aside className="sidebar">
      <div className="tenant-brand">
        <button
          className="tenant-brand-button"
          onClick={() => onChange("ask")}
          aria-label={`${branding.display_name} 首页`}
        >
          <span className="tenant-logo">
            {branding.logo_url
              ? <img src={branding.logo_url} alt="" />
              : initial}
          </span>
          <span>
            <strong>{branding.display_name}</strong>
            <small>企业知识工作台</small>
          </span>
        </button>
      </div>

      <nav className="primary-nav" aria-label="主导航">
        <span className="nav-group-label">知识工作</span>
        {items.filter((item) => item.group === "work").map(({ key, label, icon: Icon }) => (
          <NavItem
            key={key}
            active={active === key}
            label={label}
            icon={Icon}
            onClick={() => onChange(key)}
          />
        ))}
        <span className="nav-group-label nav-group-gap">组织管理</span>
        {items.filter((item) => item.group === "manage").map(({ key, label, icon: Icon }) => (
          <NavItem
            key={key}
            active={active === key}
            label={label}
            icon={Icon}
            onClick={() => onChange(key)}
          />
        ))}
      </nav>

      <div className="sidebar-account">
        <span className="account-avatar">{userEmail.slice(0, 1).toUpperCase()}</span>
        <span>
          <strong>{userEmail}</strong>
          <small>{roleLabel(role)}</small>
        </span>
      </div>
      <div className="powered-by">由 <strong>RunbookIQ</strong> 提供支持</div>
    </aside>
  );
}

function NavItem({
  active,
  label,
  icon: Icon,
  onClick
}: {
  active: boolean;
  label: string;
  icon: LucideIcon;
  onClick: () => void;
}) {
  return (
    <button
      className={active ? "nav-item is-active" : "nav-item"}
      onClick={onClick}
    >
      <Icon size={19} strokeWidth={1.8} />
      <span>{label}</span>
    </button>
  );
}

function roleLabel(role: TenantRole) {
  return {
    owner: "企业所有者",
    admin: "管理员",
    editor: "内容编辑者",
    viewer: "只读成员"
  }[role];
}
