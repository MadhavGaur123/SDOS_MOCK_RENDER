import React, { useState } from "react";
import { GitCompare, MessageSquare, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import ChatPanel from "../components/chat/ChatPanel";
import ComparisonTable from "../components/comparison/ComparisonTable";
import { useApp } from "../context/AppContext";
import { useComparison } from "../hooks";

export default function ComparePage() {
  const navigate = useNavigate();
  const { clearCompare, compareCart, removeFromCompare } = useApp();
  const [showChat, setShowChat] = useState(false);

  const idA = compareCart[0]?.variant_id;
  const idB = compareCart[1]?.variant_id;
  const { data, error, loading } = useComparison(idA, idB);
  const canCompare = compareCart.length === 2;

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Comparison Workspace</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Compare plans side by side with less visual noise
          </h1>
          <p className="body-sm">
            Keep two shortlisted policies in view and review differences field by field before moving to a decision.
          </p>
        </div>

        {canCompare ? (
          <div className="page-header-actions">
            <button
              className={`btn ${showChat ? "btn-primary" : "btn-ghost"} btn-sm`}
              onClick={() => setShowChat((prev) => !prev)}
              type="button"
            >
              <MessageSquare size={14} />
              Chat about this
            </button>
            <button className="btn btn-ghost btn-sm" onClick={clearCompare} type="button">
              <X size={14} />
              Clear
            </button>
          </div>
        ) : null}
      </div>

      <div className="summary-grid" style={{ marginBottom: "var(--sp-6)" }}>
        {[0, 1].map((index) => {
          const item = compareCart[index];

          return item ? (
            <div
              key={index}
              className="card"
              style={{
                padding: "var(--sp-5)",
                background: index === 0 ? "linear-gradient(180deg, rgba(111,182,255,0.12), rgba(111,182,255,0.03)), var(--c-surface)" : "linear-gradient(180deg, rgba(217,177,90,0.1), rgba(217,177,90,0.02)), var(--c-surface)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--sp-3)", alignItems: "flex-start" }}>
                <div>
                  <p className="metric-label">{item.insurer_name}</p>
                  <p className="metric-value" style={{ fontSize: "1rem" }}>{item.policy_name}</p>
                  <p style={{ color: "var(--c-text-2)", fontSize: "0.82rem", marginTop: 4 }}>{item.variant_name}</p>
                </div>

                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => removeFromCompare(item.variant_id)}
                  style={{ padding: "6px 10px" }}
                  type="button"
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          ) : (
            <button
              key={index}
              className="card-ghost"
              onClick={() => navigate("/catalog")}
              style={{
                padding: "var(--sp-6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 112,
                cursor: "pointer",
                color: "var(--c-text-3)",
                borderRadius: "var(--r-lg)",
              }}
              type="button"
            >
              + Add policy from catalog
            </button>
          );
        })}
      </div>

      {!canCompare ? (
        <div className="empty-state">
          <GitCompare size={44} style={{ margin: "0 auto var(--sp-4)", color: "var(--c-text-4)" }} />
          <p style={{ fontWeight: 700, fontSize: "1rem", color: "var(--c-text-1)" }}>Add two policies to compare</p>
          <p style={{ fontSize: "0.85rem", marginTop: "var(--sp-2)", marginBottom: "var(--sp-6)" }}>
            Browse the catalog and use Compare on any policy card to build your shortlist.
          </p>
          <button className="btn btn-primary" onClick={() => navigate("/catalog")} type="button">
            Browse Catalog
          </button>
        </div>
      ) : null}

      {canCompare && loading ? (
        <div className="card" style={{ padding: "var(--sp-8)", textAlign: "center", color: "var(--c-text-3)" }}>
          <div
            style={{
              width: 34,
              height: 34,
              border: "3px solid rgba(255,255,255,0.08)",
              borderTopColor: "var(--c-primary)",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
              margin: "0 auto var(--sp-4)",
            }}
          />
          <p>Loading comparison...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : null}

      {canCompare && error ? (
        <div className="status-banner status-banner-danger">
          <div>{error}</div>
        </div>
      ) : null}

      {canCompare && data ? (
        <div className={`rail-layout ${showChat ? "rail-layout-open" : ""}`}>
          <div className="section-stack">
            {data.diff_fields?.length ? (
              <div className="status-banner status-banner-warn">
                <div>
                  <span className="diff-marker">DIFF</span>{" "}
                  <strong>
                    {data.diff_fields.length} field{data.diff_fields.length !== 1 ? "s" : ""} differ
                  </strong>{" "}
                  between these plans.
                </div>
              </div>
            ) : null}

            <ComparisonTable variantA={data.variant_a} variantB={data.variant_b} />

            {data.exclusions_a?.length || data.exclusions_b?.length ? (
              <ExclusionsComparison
                exclusionsA={data.exclusions_a || []}
                exclusionsB={data.exclusions_b || []}
                labelA={`${data.variant_a?.policy_name} (${data.variant_a?.variant_name})`}
                labelB={`${data.variant_b?.policy_name} (${data.variant_b?.variant_name})`}
              />
            ) : null}
          </div>

          {showChat ? (
            <div className="rail-pane" style={{ height: "calc(100vh - var(--topbar-h) - 120px)" }}>
              <ChatPanel
                contextId={`${idA}__${idB}`}
                contextLabel={`${compareCart[0]?.policy_name} vs ${compareCart[1]?.policy_name}`}
                contextType="comparison"
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ExclusionsComparison({ exclusionsA, exclusionsB, labelA, labelB }) {
  const allNames = [
    ...new Set([
      ...exclusionsA.map((item) => item.exclusion_name),
      ...exclusionsB.map((item) => item.exclusion_name),
    ]),
  ].sort();
  const mapA = Object.fromEntries(exclusionsA.map((item) => [item.exclusion_name, item]));
  const mapB = Object.fromEntries(exclusionsB.map((item) => [item.exclusion_name, item]));

  return (
    <div className="table-card">
      <div style={{ padding: "var(--sp-5)", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <h3 className="heading-lg">Exclusions Comparison</h3>
      </div>
      <div className="table-scroll">
        <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0 }}>
          <thead>
            <tr>
              {["Exclusion", labelA, labelB].map((heading) => (
                <th
                  key={heading}
                  style={{
                    padding: "var(--sp-3) var(--sp-4)",
                    background: "rgba(255,255,255,0.025)",
                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                    textAlign: "left",
                    fontSize: "0.74rem",
                    fontWeight: 700,
                    color: "var(--c-text-3)",
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                  }}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {allNames.map((name) => {
              const exclusionA = mapA[name];
              const exclusionB = mapB[name];
              const onlyInOne = !exclusionA || !exclusionB;

              return (
                <tr key={name} style={{ background: onlyInOne ? "rgba(217, 177, 90, 0.035)" : "transparent" }}>
                  <td
                    style={{
                      padding: "var(--sp-3) var(--sp-4)",
                      borderBottom: "1px solid rgba(255,255,255,0.05)",
                      fontSize: "0.84rem",
                      fontWeight: 700,
                      color: "var(--c-text-2)",
                    }}
                  >
                    {onlyInOne ? <span className="diff-marker" style={{ marginRight: 6 }}>DIFF</span> : null}
                    {name}
                  </td>
                  {[exclusionA, exclusionB].map((exclusion, index) => (
                    <td
                      key={`${name}-${index}`}
                      style={{
                        padding: "var(--sp-3) var(--sp-4)",
                        borderBottom: "1px solid rgba(255,255,255,0.05)",
                        fontSize: "0.82rem",
                        color: "var(--c-text-2)",
                      }}
                    >
                      {exclusion ? (
                        <div>
                          <span className="badge badge-danger">Present</span>
                          {exclusion.exception_conditions ? (
                            <p style={{ fontSize: "0.76rem", color: "var(--c-success)", marginTop: 6 }}>
                              Exception: {exclusion.exception_conditions}
                            </p>
                          ) : null}
                        </div>
                      ) : (
                        <span style={{ color: "var(--c-text-3)", fontFamily: "var(--f-mono)", fontSize: "0.75rem" }}>
                          Not listed
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
