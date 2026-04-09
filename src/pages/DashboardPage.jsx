import React, { useState } from "react";
import {
  ArrowRight,
  Building2,
  Clock3,
  FileText,
  GitCompare,
  MessageSquare,
  Search,
  Shield,
  TrendingUp,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useMatchScores } from "../hooks";

const QUICK_NEEDS = [
  "Maternity",
  "Critical Illness",
  "Mental Health",
  "OPD",
  "No Co-pay",
  "No Sub-limits",
  "Cashless Only",
  "Senior Citizen",
  "Family Floater",
];

const WORKSPACE_FEATURES = [
  {
    icon: GitCompare,
    color: "var(--c-primary)",
    desc: "Compare two plans field by field with calmer difference highlighting and clear plan summaries.",
    label: "Side-by-Side Compare",
    to: "/compare",
  },
  {
    icon: MessageSquare,
    color: "var(--c-info)",
    desc: "Ask grounded policy questions with citations and context-aware answers.",
    label: "Policy Assistant",
    to: "/chat",
  },
  {
    icon: Building2,
    color: "var(--c-success)",
    desc: "Check cashless hospital availability by city, insurer, or pincode.",
    label: "Hospital Lookup",
    to: "/hospitals",
  },
  {
    icon: Shield,
    color: "var(--c-accent)",
    desc: "Review benefits, exclusions, and waiting periods in a cleaner advisory format.",
    label: "Coverage Clarity",
    to: "/catalog",
  },
  {
    icon: Clock3,
    color: "var(--c-warn)",
    desc: "Understand claim timelines, PED waiting periods, and key process deadlines.",
    label: "Claims Readiness",
    to: "/checklist",
  },
  {
    icon: FileText,
    color: "var(--c-primary)",
    desc: "Upload personal policy documents and keep them ready for document-scoped questions.",
    label: "My Documents",
    to: "/my-policies",
  },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const { results, loading, compute } = useMatchScores();

  const [prefs, setPrefs] = useState({
    age: "",
    city: "",
    family_size: 1,
    key_needs: [],
    si_required: "",
  });

  const toggleNeed = (need) => {
    setPrefs((prev) => ({
      ...prev,
      key_needs: prev.key_needs.includes(need)
        ? prev.key_needs.filter((item) => item !== need)
        : [...prev.key_needs, need],
    }));
  };

  const handleMatch = () => {
    compute({
      ...prefs,
      age: prefs.age ? Number(prefs.age) : undefined,
      family_size: Number(prefs.family_size),
      si_required: prefs.si_required ? String(Number(prefs.si_required) * 100000) : "",
    });
  };

  return (
    <div
      className="fade-in-up"
      style={{
        maxWidth: "var(--content-max)",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "var(--sp-12)",
      }}
    >
      <section className="hero-panel" style={{ padding: "var(--sp-10)" }}>
        <div className="hero-grid">
          <div>
            <p className="page-header-kicker">Insurance Advisor Workspace</p>
            <h1 className="display-lg" style={{ maxWidth: 640, marginBottom: "var(--sp-4)" }}>
              Understand health insurance with less clutter and better evidence.
            </h1>
            <p className="body-sm" style={{ fontSize: "1rem", maxWidth: 600, marginBottom: "var(--sp-6)" }}>
              Browse plans, compare benefits side by side, ask clause-linked questions, and prepare for claims from one calm workspace.
            </p>

            <div className="page-header-actions" style={{ marginBottom: "var(--sp-8)" }}>
              <button className="btn btn-primary btn-lg" onClick={() => navigate("/catalog")} type="button">
                <Search size={17} />
                Browse Policies
              </button>
              <button className="btn btn-ghost btn-lg" onClick={() => navigate("/my-policies")} type="button">
                <FileText size={17} />
                Upload My Policy
              </button>
            </div>

            <div className="trust-strip">
              {[
                ["Coverage Review", "Policy details, exclusions, and waiting periods presented in one reading flow."],
                ["Assistant Context", "Chat is scoped to a plan, comparison, or uploaded document for more grounded answers."],
                ["Claims Support", "Checklist and hospital lookup tools stay available without leaving the workspace."],
              ].map(([label, value]) => (
                <div key={label} className="trust-item">
                  <p className="metric-label">{label}</p>
                  <p className="metric-value" style={{ fontSize: "0.86rem", color: "var(--c-text-2)", fontWeight: 600 }}>
                    {value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ background: "var(--c-surface-2)" }}>
            <p className="heading-sm" style={{ marginBottom: "var(--sp-3)" }}>
              Workspace Snapshot
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
              {[
                ["Catalog Review", "Search, filter, and compare policy variants without jumping across tabs."],
                ["Clause Evidence", "Policy chat and detail pages keep the important evidence near the question."],
                ["Operational Readiness", "My Policies, hospital lookup, checklist, and admin remain in the same shell."],
              ].map(([title, desc]) => (
                <div
                  key={title}
                  style={{
                    padding: "var(--sp-4)",
                    borderRadius: "var(--r-md)",
                    border: "1px solid rgba(255,255,255,0.05)",
                    background: "rgba(255,255,255,0.02)",
                  }}
                >
                  <p style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: 4 }}>{title}</p>
                  <p style={{ color: "var(--c-text-2)", fontSize: "0.82rem", lineHeight: 1.6 }}>{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="page-header">
          <div className="page-header-copy">
            <p className="page-header-kicker">Match Intake</p>
            <h2 className="display-md" style={{ fontSize: "2rem", marginBottom: "var(--sp-2)" }}>
              Find plans that match your needs
            </h2>
            <p className="body-sm">
              The form stays simple: basic profile, sum insured, and the features you care about most.
            </p>
          </div>
        </div>

        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--sp-5)" }}>
          <div className="field-grid">
            <Field label="Age">
              <input
                className="input-field"
                max={99}
                min={1}
                onChange={(event) => setPrefs((prev) => ({ ...prev, age: event.target.value }))}
                placeholder="e.g. 32"
                type="number"
                value={prefs.age}
              />
            </Field>

            <Field label="Family Members">
              <select
                className="input-field"
                onChange={(event) =>
                  setPrefs((prev) => ({ ...prev, family_size: Number(event.target.value) }))
                }
                value={prefs.family_size}
              >
                {[1, 2, 3, 4, 5, 6].map((value) => (
                  <option key={value} value={value}>
                    {value === 6 ? "6+" : value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Sum Insured (Lakh)">
              <input
                className="input-field"
                onChange={(event) => setPrefs((prev) => ({ ...prev, si_required: event.target.value }))}
                placeholder="e.g. 10"
                type="number"
                value={prefs.si_required}
              />
            </Field>

            <Field label="City">
              <input
                className="input-field"
                onChange={(event) => setPrefs((prev) => ({ ...prev, city: event.target.value }))}
                placeholder="e.g. Mumbai"
                type="text"
                value={prefs.city}
              />
            </Field>
          </div>

          <div>
            <label className="heading-sm" style={{ display: "block", marginBottom: "var(--sp-3)" }}>
              Key Needs
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)" }}>
              {QUICK_NEEDS.map((need) => {
                const active = prefs.key_needs.includes(need);

                return (
                  <button
                    key={need}
                    onClick={() => toggleNeed(need)}
                    style={{
                      padding: "8px 14px",
                      borderRadius: "var(--r-full)",
                      border: `1px solid ${active ? "rgba(111, 182, 255, 0.28)" : "rgba(255,255,255,0.06)"}`,
                      background: active ? "var(--c-primary-soft)" : "rgba(255,255,255,0.025)",
                      color: active ? "var(--c-primary-strong)" : "var(--c-text-2)",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                      fontWeight: 700,
                      transition: "all var(--t-fast)",
                    }}
                    type="button"
                  >
                    {need}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="page-header-actions">
            <button
              className="btn btn-primary"
              disabled={loading}
              onClick={handleMatch}
              type="button"
            >
              <TrendingUp size={16} />
              {loading ? "Computing..." : "Compute Match Scores"}
            </button>
          </div>
        </div>

        {results.length ? (
          <div style={{ marginTop: "var(--sp-6)" }}>
            <div className="results-strip">
              <p className="heading-sm">Top matches</p>
              <span className="badge">{results.length} plans scored</span>
            </div>
            <div className="card-grid stagger">
              {results.slice(0, 6).map((result) => (
                <MatchCard key={result.variant_id} result={result} />
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section>
        <div className="page-header">
          <div className="page-header-copy">
            <p className="page-header-kicker">What You Can Do</p>
            <h2 className="display-md" style={{ fontSize: "2rem", marginBottom: "var(--sp-2)" }}>
              Core insurance tasks in one calm workspace
            </h2>
            <p className="body-sm">
              Every tool stays focused on policy clarity, evidence, and operational readiness.
            </p>
          </div>
        </div>

        <div className="card-grid stagger">
          {WORKSPACE_FEATURES.map(({ color, desc, icon: Icon, label, to }) => (
            <button
              key={label}
              className="card fade-in-up"
              onClick={() => navigate(to)}
              style={{ cursor: "pointer", textAlign: "left", minHeight: 220 }}
              type="button"
            >
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: "var(--r-md)",
                  background: `${color}18`,
                  border: `1px solid ${color}20`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "var(--sp-4)",
                }}
              >
                <Icon color={color} size={20} />
              </div>
              <p style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "var(--sp-2)" }}>{label}</p>
              <p style={{ fontSize: "0.84rem", color: "var(--c-text-2)", lineHeight: 1.65 }}>{desc}</p>
              <div
                style={{
                  marginTop: "var(--sp-5)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  color,
                  fontSize: "0.8rem",
                  fontWeight: 700,
                }}
              >
                Open tool <ArrowRight size={12} />
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Field({ children, label }) {
  return (
    <div>
      <label className="heading-sm" style={{ display: "block", marginBottom: "var(--sp-2)" }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function MatchCard({ result }) {
  const navigate = useNavigate();
  const scoreColor =
    result.score >= 80 ? "var(--c-success)" : result.score >= 60 ? "var(--c-warn)" : "var(--c-danger)";

  return (
    <button
      className="card fade-in-up"
      onClick={() => navigate(`/policy/${result.variant_id}`)}
      style={{ cursor: "pointer", textAlign: "left" }}
      type="button"
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--sp-4)", alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: "0.75rem", color: "var(--c-text-4)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {result.variant?.insurer_name}
          </p>
          <p style={{ fontWeight: 700, fontSize: "1rem", marginTop: 4 }}>{result.variant?.policy_name}</p>
          <p style={{ fontSize: "0.82rem", color: "var(--c-text-2)", marginTop: 2 }}>{result.variant?.variant_name}</p>
        </div>
        <div
          style={{
            minWidth: 64,
            padding: "10px 12px",
            borderRadius: "var(--r-md)",
            background: `${scoreColor}14`,
            border: `1px solid ${scoreColor}22`,
            color: scoreColor,
            fontFamily: "var(--f-mono)",
            fontSize: "1.3rem",
            fontWeight: 700,
            textAlign: "center",
          }}
        >
          {result.score}
        </div>
      </div>

      {result.rationale ? (
        <p
          style={{
            marginTop: "var(--sp-4)",
            paddingTop: "var(--sp-4)",
            borderTop: "1px solid rgba(255,255,255,0.05)",
            fontSize: "0.82rem",
            color: "var(--c-text-2)",
            lineHeight: 1.65,
          }}
        >
          {result.rationale}
        </p>
      ) : null}
    </button>
  );
}
