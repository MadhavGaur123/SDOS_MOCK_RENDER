import React from "react";
import { Activity } from "lucide-react";
import { useLocation } from "react-router-dom";

const TITLES = {
  "/": "Dashboard",
  "/admin": "Admin",
  "/catalog": "Policy Catalog",
  "/chat": "Policy Assistant",
  "/checklist": "Claim Checklist",
  "/compare": "Compare Policies",
  "/hospitals": "Cashless Hospitals",
  "/my-policies": "My Policies",
};

export default function Topbar() {
  const location = useLocation();
  const title = location.pathname.startsWith("/policy/")
    ? "Policy Detail"
    : TITLES[location.pathname] || "HealIN";

  return (
    <header className="topbar">
      <div className="topbar-content">
        <div>
          <div className="topbar-brand">
            <Activity size={18} />
            <span>HealIN</span>
          </div>
          <p className="topbar-title">{title}</p>
        </div>
      </div>
    </header>
  );
}
