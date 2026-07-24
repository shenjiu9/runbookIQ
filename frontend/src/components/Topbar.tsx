import { Bell, ChevronDown, CircleHelp, Network } from "lucide-react";

export function Topbar() {
  return (
    <header className="topbar">
      <button className="workspace-select">
        <Network size={16} />
        <span>平台工程团队</span>
        <ChevronDown size={15} />
      </button>
      <div className="topbar-actions">
        <div className="system-health"><i />系统状态</div>
        <span className="operational">全部服务运行正常</span>
        <button className="icon-button" aria-label="帮助"><CircleHelp size={17} /></button>
        <button className="icon-button" aria-label="通知"><Bell size={17} /></button>
        <button className="avatar">PE</button>
      </div>
    </header>
  );
}
