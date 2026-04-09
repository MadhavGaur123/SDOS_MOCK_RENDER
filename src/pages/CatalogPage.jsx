import React, { useEffect, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import PolicyCard from "../components/policy/PolicyCard";
import { useVariants } from "../hooks";

const POLICY_TYPES = ["", "Individual", "Family Floater", "Individual+Family"];
const SI_OPTIONS = [
  { label: "Any", value: "" },
  { label: "Rs 3L+", value: "300000" },
  { label: "Rs 5L+", value: "500000" },
  { label: "Rs 10L+", value: "1000000" },
  { label: "Rs 25L+", value: "2500000" },
];

export default function CatalogPage() {
  const [filters, setFilters] = useState({
    insurer: "",
    policy_type: "",
    q: "",
    si_min: "",
  });
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedFilters(filters), 400);
    return () => clearTimeout(timeout);
  }, [filters]);

  const { data, error, loading } = useVariants(debouncedFilters);
  const variants = data?.items || data || [];
  const activeFilters = [
    filters.policy_type ? `Type: ${filters.policy_type}` : null,
    filters.si_min
      ? `Min SI: ${SI_OPTIONS.find((option) => option.value === filters.si_min)?.label || filters.si_min}`
      : null,
    filters.insurer ? `Insurer: ${filters.insurer}` : null,
  ].filter(Boolean);

  const setFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({ insurer: "", policy_type: "", q: "", si_min: "" });
  };

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Policy Catalog</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Browse plans with less noise and clearer policy signals
          </h1>
          <p className="body-sm">
            Search by insurer or plan name, apply the existing filters, and move quickly from shortlist to detailed review.
          </p>
        </div>
      </div>

      <div className="command-bar">
        <div className="command-bar-main">
          <div style={{ position: "relative", flex: 1, minWidth: 260 }}>
            <Search
              size={15}
              style={{
                position: "absolute",
                left: 14,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--c-text-4)",
                pointerEvents: "none",
              }}
            />
            <input
              className="input-field"
              onChange={(event) => setFilter("q", event.target.value)}
              placeholder="Search by insurer, plan, or variant..."
              style={{ paddingLeft: 40 }}
              type="text"
              value={filters.q}
            />
          </div>

          <button
            className={`btn ${showFilters ? "btn-primary" : "btn-ghost"} btn-sm`}
            onClick={() => setShowFilters((prev) => !prev)}
            type="button"
          >
            <SlidersHorizontal size={14} />
            Filters
          </button>

          {activeFilters.length ? (
            <button className="btn btn-ghost btn-sm" onClick={clearFilters} type="button">
              <X size={14} />
              Clear
            </button>
          ) : null}
        </div>

        {showFilters ? (
          <div
            style={{
              marginTop: "var(--sp-4)",
              paddingTop: "var(--sp-4)",
              borderTop: "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <div className="field-grid">
              <Field label="Policy Type">
                <select
                  className="input-field"
                  onChange={(event) => setFilter("policy_type", event.target.value)}
                  value={filters.policy_type}
                >
                  {POLICY_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type || "All types"}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Min Sum Insured">
                <select
                  className="input-field"
                  onChange={(event) => setFilter("si_min", event.target.value)}
                  value={filters.si_min}
                >
                  {SI_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Insurer">
                <input
                  className="input-field"
                  onChange={(event) => setFilter("insurer", event.target.value)}
                  placeholder="e.g. Star Health"
                  type="text"
                  value={filters.insurer}
                />
              </Field>
            </div>
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="card-grid">
          {[1, 2, 3, 4, 5, 6].map((index) => (
            <div key={index} className="card">
              <div className="skeleton" style={{ height: 18, width: "42%", marginBottom: 12 }} />
              <div className="skeleton" style={{ height: 30, width: "78%", marginBottom: 8 }} />
              <div className="skeleton" style={{ height: 14, width: "32%", marginBottom: 18 }} />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10, marginBottom: 18 }}>
                {[1, 2, 3].map((cell) => (
                  <div key={cell} className="skeleton" style={{ height: 70 }} />
                ))}
              </div>
              <div className="skeleton" style={{ height: 36, width: "100%" }} />
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="status-banner status-banner-danger" style={{ marginBottom: "var(--sp-5)" }}>
          <div>
            <strong>Could not load policies.</strong> {error}
          </div>
        </div>
      ) : null}

      {!loading && !error ? (
        <>
          <div className="results-strip">
            <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)", flexWrap: "wrap" }}>
              <span className="heading-sm">Results</span>
              <span className="badge">{variants.length} variant{variants.length !== 1 ? "s" : ""}</span>
            </div>
            {activeFilters.length ? (
              <div style={{ display: "flex", gap: "var(--sp-2)", flexWrap: "wrap" }}>
                {activeFilters.map((label) => (
                  <span key={label} className="chip">
                    {label}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="card-grid stagger">
            {variants.map((variant) => (
              <PolicyCard key={variant.variant_id} variant={variant} />
            ))}
          </div>

          {!variants.length ? (
            <div className="empty-state" style={{ marginTop: "var(--sp-4)" }}>
              <Search size={34} style={{ margin: "0 auto var(--sp-3)", color: "var(--c-text-4)" }} />
              <p style={{ fontWeight: 700, color: "var(--c-text-1)" }}>No policies found</p>
              <p style={{ fontSize: "0.85rem", marginTop: "var(--sp-2)" }}>
                Try broadening the insurer name, policy type, or minimum sum insured.
              </p>
            </div>
          ) : null}
        </>
      ) : null}
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
