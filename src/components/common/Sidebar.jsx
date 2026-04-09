import React from "react";
import {
  Building2,
  ClipboardList,
  FileText,
  GitCompare,
  LayoutDashboard,
  MessageSquare,
  Rows3,
  Settings,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useApp } from "../../context/AppContext";

const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { to: "/", icon: LayoutDashboard, label: "Dashboard" },
      { to: "/catalog", icon: Rows3, label: "Catalog" },
      { to: "/compare", icon: GitCompare, label: "Compare", badge: "compare" },
    ],
  },
  {
    label: "Advisory Tools",
    items: [
      { to: "/my-policies", icon: FileText, label: "My Policies", badge: "docs" },
      { to: "/hospitals", icon: Building2, label: "Hospitals" },
      { to: "/chat", icon: MessageSquare, label: "Assistant" },
      { to: "/checklist", icon: ClipboardList, label: "Checklist" },
    ],
  },
  {
    label: "Operations",
    items: [{ to: "/admin", icon: Settings, label: "Admin" }],
  },
];

export default function Sidebar() {
  const { compareCart, myDocuments } = useApp();

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {NAV_GROUPS.map((group) => (
          <React.Fragment key={group.label}>
            <p className="sidebar-group-label">{group.label}</p>
            {group.items.map(({ badge, icon: Icon, label, to }) => {
              const badgeValue =
                badge === "compare"
                  ? compareCart.length || null
                  : badge === "docs"
                    ? myDocuments.length || null
                    : null;

              return (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    isActive ? "nav-link nav-link-active" : "nav-link"
                  }
                >
                  <span className="nav-link-left">
                    <Icon size={16} />
                    <span>{label}</span>
                  </span>
                  {badgeValue ? <span className="nav-badge">{badgeValue}</span> : null}
                </NavLink>
              );
            })}
          </React.Fragment>
        ))}
      </nav>
    </aside>
  );
}
