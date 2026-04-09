import React from "react";
import { ArrowRight, GitCompare, Shield, Stethoscope, WalletCards } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../../context/AppContext";

function formatInr(value) {
  if (!value) {
    return "-";
  }

  const number = Number(value);

  if (number >= 1000000) {
    return `Rs ${Number(number / 100000).toFixed(0)}L`;
  }

  if (number >= 100000) {
    return `Rs ${Number(number / 100000).toFixed(1).replace(".0", "")}L`;
  }

  return `Rs ${number}`;
}

function getSiRange(variant) {
  if (variant.si_min_inr && variant.si_max_inr) {
    return `${formatInr(variant.si_min_inr)} - ${formatInr(variant.si_max_inr)}`;
  }

  return variant.si_options_text || "-";
}

function getRoomRentLabel(variant) {
  if (variant.room_rent_type === "no_limit") {
    return "No limit";
  }

  if (variant.room_rent_limit_text) {
    return variant.room_rent_limit_text;
  }

  return "-";
}

export default function PolicyCard({ variant }) {
  const { addToCompare, isInCompare, removeFromCompare } = useApp();
  const inCompare = isInCompare(variant.variant_id);

  const evidenceTags = [
    variant.cashless_available ? "Cashless" : null,
    variant.maternity_covered ? "Maternity" : null,
    variant.restoration_covered ? "Restoration" : null,
    variant.mental_health_covered ? "Mental Health" : null,
    variant.opd_covered ? "OPD" : null,
  ].filter(Boolean);
  const visibleEvidenceTags = evidenceTags.slice(0, 3);
  const remainingEvidenceCount = Math.max(evidenceTags.length - visibleEvidenceTags.length, 0);
  const metrics = [
    { icon: WalletCards, label: "Sum Insured", value: getSiRange(variant) },
    {
      icon: Shield,
      label: "PED Waiting",
      value: variant.ped_waiting_months ? `${variant.ped_waiting_months} months` : "-",
    },
    { icon: Stethoscope, label: "Room Rent", value: getRoomRentLabel(variant), wide: true },
  ];

  return (
    <article className="card policy-card fade-in-up" style={{ gap: "var(--sp-4)" }}>
      <div className="policy-card-meta" style={{ gap: "var(--sp-3)" }}>
        <div style={{ minWidth: 0 }}>
          <p className="policy-card-insurer line-clamp-2">{variant.insurer_name}</p>
          <div style={{ display: "flex", gap: "var(--sp-2)", flexWrap: "wrap", marginTop: "var(--sp-2)", marginBottom: "var(--sp-3)" }}>
            {variant.policy_type ? <span className="badge">{variant.policy_type}</span> : null}
          </div>
          <h3 style={{ fontSize: "1.08rem", lineHeight: 1.3, fontWeight: 800 }}>{variant.policy_name}</h3>
          <p style={{ color: "var(--c-text-2)", fontSize: "0.84rem", marginTop: 4 }}>
            {variant.variant_name || "Base plan"}
          </p>
        </div>

        {variant.extraction_date ? (
          <span className="stale-tag">{new Date(variant.extraction_date).toLocaleDateString("en-IN")}</span>
        ) : null}
      </div>

      <div className="policy-card-metrics">
        {metrics.map(({ icon: Icon, label, value, wide }) => (
          <div
            key={label}
            className={`metric-card ${wide ? "policy-card-metric-wide" : ""}`.trim()}
            style={{
              padding: "var(--sp-3)",
              minHeight: wide ? 0 : 92,
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--c-text-4)", marginBottom: 8 }}>
              <Icon size={13} />
              <span style={{ fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>
                {label}
              </span>
            </div>
            <p className={wide ? "line-clamp-4" : undefined} style={{ fontSize: "0.84rem", fontWeight: 700, lineHeight: 1.4 }}>
              {value}
            </p>
          </div>
        ))}
      </div>

      <div
        style={{
          padding: "var(--sp-3) var(--sp-4)",
          borderRadius: "var(--r-md)",
          border: "1px solid rgba(255,255,255,0.05)",
          background: "rgba(255,255,255,0.02)",
        }}
      >
        <p className="heading-sm" style={{ marginBottom: "var(--sp-2)" }}>
          Evidence Highlights
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)" }}>
          {visibleEvidenceTags.length ? (
            <>
              {visibleEvidenceTags.map((tag) => <span key={tag} className="badge">{tag}</span>)}
              {remainingEvidenceCount ? <span className="badge">+{remainingEvidenceCount} more</span> : null}
            </>
          ) : (
            <span className="badge">Core hospitalization cover</span>
          )}
        </div>
      </div>

      <div className="policy-card-actions">
        <Link className="btn btn-primary btn-sm" to={`/policy/${variant.variant_id}`}>
          View Details
          <ArrowRight size={14} />
        </Link>

        <button
          className={`btn ${inCompare ? "btn-accent" : "btn-ghost"} btn-sm`}
          onClick={() => (inCompare ? removeFromCompare(variant.variant_id) : addToCompare(variant))}
          type="button"
        >
          <GitCompare size={14} />
          {inCompare ? "In Compare" : "Compare"}
        </button>
      </div>
    </article>
  );
}
