import React, { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  GitCompare,
  MessageSquare,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import ChatPanel from "../components/chat/ChatPanel";
import { useApp } from "../context/AppContext";
import { useVariant } from "../hooks";

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

  if (number >= 1000) {
    return `Rs ${Math.floor(number / 1000)}K`;
  }

  return `Rs ${number}`;
}

function yesNoLabel(value, suffix) {
  if (value === true) {
    return suffix ? `Covered - ${suffix}` : "Covered";
  }

  if (value === false) {
    return "Not covered";
  }

  return null;
}

export default function PolicyDetailPage() {
  const { variantId } = useParams();
  const navigate = useNavigate();
  const { data: variant, error, loading } = useVariant(variantId);
  const { addToCompare, isInCompare, removeFromCompare } = useApp();
  const inCompare = isInCompare(variantId);
  const [showChat, setShowChat] = useState(false);
  const [openSections, setOpenSections] = useState({
    "Core Hospitalisation": true,
    "Waiting Periods": true,
  });

  const toggle = (label) => {
    setOpenSections((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return <ErrorState message={error} onBack={() => navigate(-1)} />;
  }

  if (!variant) {
    return null;
  }

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Policy Detail</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            {variant.policy_name}
          </h1>
          <p className="body-sm">
            Review key policy facts, benefits, waiting periods, exclusions, and claim conditions in one reading flow.
          </p>
        </div>
      </div>

      <section className="hero-panel" style={{ marginBottom: "var(--sp-6)", padding: "var(--sp-8)" }}>
        <div className="hero-grid">
          <div>
            <div style={{ display: "flex", gap: "var(--sp-2)", marginBottom: "var(--sp-3)", flexWrap: "wrap" }}>
              <span className="badge badge-primary">{variant.insurer_name}</span>
              {variant.policy_type ? <span className="badge">{variant.policy_type}</span> : null}
              {variant.irdai_reg ? (
                <span className="badge" style={{ fontFamily: "var(--f-mono)" }}>
                  IRDAI {variant.irdai_reg}
                </span>
              ) : null}
            </div>

            <p style={{ color: "var(--c-text-2)", fontSize: "0.92rem", marginBottom: "var(--sp-2)" }}>
              {variant.variant_name}
            </p>

            {variant.helpline ? (
              <p style={{ color: "var(--c-text-3)", fontSize: "0.84rem", marginBottom: "var(--sp-4)" }}>
                Claim helpline: <span style={{ color: "var(--c-text-1)", fontFamily: "var(--f-mono)" }}>{variant.helpline}</span>
              </p>
            ) : null}

            <div className="page-header-actions">
              <button
                className={`btn ${showChat ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setShowChat((prev) => !prev)}
                type="button"
              >
                <MessageSquare size={15} />
                Ask about this
              </button>
              <button
                className={`btn ${inCompare ? "btn-accent" : "btn-ghost"}`}
                onClick={() => (inCompare ? removeFromCompare(variantId) : addToCompare(variant))}
                type="button"
              >
                <GitCompare size={15} />
                {inCompare ? "In Compare" : "Add to Compare"}
              </button>
            </div>
          </div>

          <div className="summary-grid">
            {[
              [
                "Sum Insured",
                variant.si_min_inr && variant.si_max_inr
                  ? `${formatInr(variant.si_min_inr)} - ${formatInr(variant.si_max_inr)}`
                  : variant.si_options_text || "-",
              ],
              ["PED Waiting", variant.ped_waiting_months ? `${variant.ped_waiting_months} months` : "-"],
              ["Initial Waiting", variant.initial_waiting_days ? `${variant.initial_waiting_days} days` : "-"],
              [
                "Room Rent",
                variant.room_rent_type === "no_limit" ? "No limit" : variant.room_rent_limit_text || "-",
              ],
              ["Pre-Hosp", variant.pre_hosp_days ? `${variant.pre_hosp_days} days` : "-"],
              ["Post-Hosp", variant.post_hosp_days ? `${variant.post_hosp_days} days` : "-"],
            ].map(([label, value]) => (
              <div key={label} className="metric-card">
                <p className="metric-label">{label}</p>
                <p className="metric-value">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {variant.extraction_date ? (
        <div className="status-banner status-banner-warn" style={{ marginBottom: "var(--sp-5)" }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            Data extracted on{" "}
            {new Date(variant.extraction_date).toLocaleDateString("en-IN", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
            . Verify final coverage against the official policy wording before purchase or claim submission.
          </div>
        </div>
      ) : null}

      <div className={`rail-layout ${showChat ? "rail-layout-open" : ""}`}>
        <div className="section-stack">
          {[
            {
              label: "Core Hospitalisation",
              rows: [
                ["Inpatient Cover", variant.inpatient_limit_text],
                ["Day-Care Procedures", yesNoLabel(variant.daycare_covered)],
                [
                  "Domiciliary Treatment",
                  variant.domiciliary_covered
                    ? `Covered${variant.domiciliary_min_days ? ` (min ${variant.domiciliary_min_days} days)` : ""}`
                    : variant.domiciliary_covered === false
                      ? "Not covered"
                      : null,
                ],
                [
                  "AYUSH Treatment",
                  variant.ayush_covered
                    ? `Covered${variant.ayush_limit_text ? ` - ${variant.ayush_limit_text}` : ""}`
                    : variant.ayush_covered === false
                      ? "Not covered"
                      : null,
                ],
                ["Organ Donor Expenses", yesNoLabel(variant.organ_donor_covered)],
              ],
            },
            {
              label: "Room Rent & Limits",
              rows: [
                [
                  "Room Rent",
                  variant.room_rent_type === "no_limit"
                    ? "No sub-limit"
                    : variant.room_rent_type === "fixed_per_day"
                      ? `${formatInr(variant.room_rent_fixed_inr)}/day`
                      : variant.room_rent_type === "percentage_si"
                        ? `${variant.room_rent_pct_si}% of SI/day`
                        : variant.room_rent_category || variant.room_rent_limit_text,
                ],
                ["ICU Coverage", variant.icu_limit_text],
                [
                  "Co-payment",
                  variant.has_copay === true
                    ? `Yes${variant.copay_text ? ` - ${variant.copay_text}` : ""}`
                    : variant.has_copay === false
                      ? "No"
                      : null,
                ],
                [
                  "Deductible",
                  variant.has_deductible === true
                    ? `Yes${variant.deductible_text ? ` - ${variant.deductible_text}` : ""}`
                    : variant.has_deductible === false
                      ? "No"
                      : null,
                ],
              ],
            },
            {
              label: "Waiting Periods",
              rows: [
                ["Initial Waiting Period", variant.initial_waiting_days ? `${variant.initial_waiting_days} days` : null],
                [
                  "Pre-Existing Diseases (PED)",
                  variant.ped_waiting_months
                    ? `${variant.ped_waiting_months} months${variant.ped_reducible ? " (reducible via portability)" : ""}`
                    : null,
                ],
                [
                  "Specific Disease Waiting",
                  variant.specific_disease_waiting_months
                    ? `${variant.specific_disease_waiting_months} months`
                    : null,
                ],
                ["Moratorium Period", variant.moratorium_months ? `${variant.moratorium_months} months` : null],
              ],
            },
            {
              label: "Additional Benefits",
              rows: [
                [
                  "Maternity & Newborn",
                  !variant.maternity_covered
                    ? "Not covered"
                    : [
                        variant.maternity_normal_inr ? `Normal: ${formatInr(variant.maternity_normal_inr)}` : null,
                        variant.maternity_caesar_inr ? `C-section: ${formatInr(variant.maternity_caesar_inr)}` : null,
                        variant.maternity_waiting_months ? `Waiting: ${variant.maternity_waiting_months} months` : null,
                        variant.newborn_covered ? "Newborn covered" : null,
                      ]
                        .filter(Boolean)
                        .join(" | ") || "Covered",
                ],
                ["Critical Illness", yesNoLabel(variant.critical_illness_covered, variant.critical_illness_limit_text)],
                ["Mental Health Cover", yesNoLabel(variant.mental_health_covered)],
                ["OPD Cover", yesNoLabel(variant.opd_covered)],
                [
                  "Restoration Benefit",
                  !variant.restoration_covered
                    ? "Not covered"
                    : [
                        variant.restoration_pct ? `${variant.restoration_pct}% of SI restored` : null,
                        variant.restoration_frequency_text,
                        variant.restoration_same_illness === false ? "Different illness only" : null,
                      ]
                        .filter(Boolean)
                        .join(" | ") || "Covered",
                ],
                [
                  "No-Claim Bonus",
                  !variant.ncb_covered
                    ? "No bonus"
                    : [variant.ncb_rate_text, variant.ncb_max_text ? `Max: ${variant.ncb_max_text}` : null]
                        .filter(Boolean)
                        .join(" | ") || "Available",
                ],
                ["International Cover", yesNoLabel(variant.international_covered)],
                [
                  "Preventive Checkup",
                  yesNoLabel(variant.health_checkup_covered, variant.health_checkup_frequency),
                ],
                ["Wellness Benefits", yesNoLabel(variant.wellness_covered, variant.wellness_details_text)],
              ],
            },
            {
              label: "Claim Process",
              rows: [
                [
                  "Cashless Claims",
                  variant.cashless_available === true
                    ? [
                        "Available",
                        variant.cashless_notice_planned ? `Planned: ${variant.cashless_notice_planned}` : null,
                        variant.cashless_notice_emergency ? `Emergency: ${variant.cashless_notice_emergency}` : null,
                      ]
                        .filter(Boolean)
                        .join(" | ")
                    : variant.cashless_available === false
                      ? "Not available"
                      : null,
                ],
                [
                  "Reimbursement",
                  variant.reimbursement_available === true
                    ? `Available${variant.reimbursement_submit_days ? ` - Submit within ${variant.reimbursement_submit_days} days` : ""}`
                    : variant.reimbursement_available === false
                      ? "Not available"
                      : null,
                ],
                ["Claim Helpline", variant.cashless_helpline],
              ],
            },
            {
              label: "Policy Conditions",
              rows: [
                ["Free Look Period", variant.free_look_days ? `${variant.free_look_days} days` : null],
                ["Grace Period", variant.grace_period_text],
                [
                  "Guaranteed Renewal",
                  variant.renewal_guaranteed === true
                    ? "Yes"
                    : variant.renewal_guaranteed === false
                      ? "No"
                      : null,
                ],
                [
                  "Portability",
                  variant.portability_available === true
                    ? "Yes"
                    : variant.portability_available === false
                      ? "No"
                      : null,
                ],
                ["Geographic Coverage", variant.territorial_limit],
              ],
            },
          ].map((section) => (
            <SectionCard
              key={section.label}
              open={openSections[section.label] !== false}
              section={section}
              toggle={toggle}
            />
          ))}

          {variant.exclusions?.length ? (
            <div className="section-card">
              <div className="section-card-header" onClick={() => toggle("Exclusions")}>
                <h3 className="heading-lg">Exclusions</h3>
                {openSections.Exclusions !== false ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>

              {openSections.Exclusions !== false ? (
                <div className="section-card-body" style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
                  {variant.exclusions.map((exclusion, index) => (
                    <div
                      key={`${exclusion.exclusion_name}-${index}`}
                      className="metric-card"
                      style={{
                        padding: "var(--sp-4)",
                        borderLeft: "3px solid rgba(240, 115, 115, 0.4)",
                        background: "rgba(255,255,255,0.02)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--sp-3)" }}>
                        <p style={{ fontWeight: 700, fontSize: "0.9rem" }}>{exclusion.exclusion_name}</p>
                        {exclusion.exclusion_category ? <span className="badge">{exclusion.exclusion_category}</span> : null}
                      </div>
                      {exclusion.description ? (
                        <p style={{ fontSize: "0.84rem", color: "var(--c-text-2)", marginTop: "var(--sp-2)" }}>
                          {exclusion.description}
                        </p>
                      ) : null}
                      {exclusion.exception_conditions ? (
                        <p style={{ fontSize: "0.8rem", color: "var(--c-success)", marginTop: "var(--sp-2)" }}>
                          Exception: {exclusion.exception_conditions}
                        </p>
                      ) : null}
                      {exclusion.page_number ? (
                        <div style={{ marginTop: "var(--sp-2)" }}>
                          <span className="citation">
                            <BookOpen size={10} />
                            p.{exclusion.page_number}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {showChat ? (
          <div className="rail-pane" style={{ height: "calc(100vh - var(--topbar-h) - var(--sp-8))" }}>
            <ChatPanel
              contextId={variantId}
              contextLabel={`${variant.policy_name} - ${variant.variant_name}`}
              contextType="variant"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SectionCard({ open, section, toggle }) {
  const rows = section.rows.filter(([, value]) => value != null);

  if (!rows.length) {
    return null;
  }

  return (
    <div className="section-card">
      <div className="section-card-header" onClick={() => toggle(section.label)}>
        <h3 className="heading-lg">{section.label}</h3>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>

      {open ? (
        <div className="section-card-body" style={{ display: "flex", flexDirection: "column" }}>
          {rows.map(([label, value], index) => (
            <div
              key={label}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(140px, 220px) 1fr",
                gap: "var(--sp-4)",
                padding: "var(--sp-3) 0",
                borderTop: index === 0 ? "none" : "1px solid rgba(255,255,255,0.05)",
              }}
            >
              <span style={{ fontSize: "0.8rem", color: "var(--c-text-3)", fontWeight: 700 }}>{label}</span>
              <span
                style={{
                  fontSize: "0.88rem",
                  color: String(value).startsWith("Covered") || String(value).startsWith("Yes")
                    ? "var(--c-success)"
                    : String(value).startsWith("Not") || String(value).startsWith("No")
                      ? "var(--c-text-3)"
                      : "var(--c-text-1)",
                }}
              >
                {value || <span style={{ color: "var(--c-text-3)", fontFamily: "var(--f-mono)", fontSize: "0.75rem" }}>-</span>}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="card" style={{ marginBottom: "var(--sp-6)", padding: "var(--sp-8)" }}>
        <div className="skeleton" style={{ height: 20, width: "26%", marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 40, width: "56%", marginBottom: 12 }} />
        <div className="skeleton" style={{ height: 18, width: "24%", marginBottom: 24 }} />
        <div className="summary-grid">
          {[1, 2, 3, 4, 5, 6].map((index) => (
            <div key={index} className="skeleton" style={{ height: 76 }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message, onBack }) {
  return (
    <div className="empty-state">
      <p style={{ color: "var(--c-danger)", marginBottom: "var(--sp-4)" }}>{message}</p>
      <button className="btn btn-ghost" onClick={onBack} type="button">
        Go back
      </button>
    </div>
  );
}
