import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { AppProvider } from "./context/AppContext";
import Topbar from "./components/common/Topbar";
import Sidebar from "./components/common/Sidebar";
import DashboardPage from "./pages/DashboardPage";
import CatalogPage from "./pages/CatalogPage";
import ComparePage from "./pages/ComparePage";
import PolicyDetailPage from "./pages/PolicyDetailPage";
import MyPoliciesPage from "./pages/MyPoliciesPage";
import {
  AdminPage,
  ChatPage,
  ClaimChecklistPage,
  HospitalsPage,
} from "./pages/OtherPages";

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <div className="app-shell">
          <Topbar />
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/catalog" element={<CatalogPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/policy/:variantId" element={<PolicyDetailPage />} />
              <Route path="/my-policies" element={<MyPoliciesPage />} />
              <Route path="/hospitals" element={<HospitalsPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/checklist" element={<ClaimChecklistPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </main>
        </div>

        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--c-surface-2)",
              border: "1px solid var(--c-border-strong)",
              color: "var(--c-text-1)",
              borderRadius: "var(--r-lg)",
              fontSize: "0.875rem",
              boxShadow: "var(--shadow-md)",
            },
          }}
        />
      </AppProvider>
    </BrowserRouter>
  );
}
