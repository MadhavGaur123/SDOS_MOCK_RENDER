import React, { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Info } from "lucide-react";

const TAXONOMY_SECTIONS = [
  {
    label: "Policy Identity",
    fields: [
      { key: "insurer_name", label: "Insurer" },
      { key: "policy_name", label: "Policy Name" },
      { key: "variant_name", label: "Variant / Plan" },
      { key: "policy_type", label: "Policy Type" },
      { key: "_si_range", label: "Sum Insured Range", formatter: "si_range" },
      { key: "si_options_text", label: "Sum Insured Options" },
    ],
  },
  {
    label: "Core Hospitalisation",
    fields: [
      { key: "inpatient_limit_text", label: "Inpatient Cover" },
      { key: "pre_hosp_days", label: "Pre-Hospitalisation", formatter: "days" },
      { key: "post_hosp_days", label: "Post-Hospitalisation", formatter: "days" },
      { key: "daycare_covered", label: "Day-Care Procedures", formatter: "yn" },
      { key: "domiciliary_covered", label: "Domiciliary Treatment", formatter: "yn" },
      { key: "ayush_covered", label: "AYUSH Treatment", formatter: "yn" },
      { key: "organ_donor_covered", label: "Organ Donor Expenses", formatter: "yn" },
    ],
  },
  {
    label: "Room Rent & Limits",
    fields: [
      { key: "_room_rent", label: "Room Rent", formatter: "room_rent" },
      { key: "icu_limit_text", label: "ICU Coverage" },
      { key: "_deductible", label: "Deductible", formatter: "deductible" },
      { key: "_copay", label: "Co-payment", formatter: "copay" },
    ],
  },
  {
    label: "Ambulance",
    fields: [
      { key: "_ambulance", label: "Road Ambulance", formatter: "ambulance" },
      { key: "_air_ambulance", label: "Air Ambulance", formatter: "air_ambulance" },
    ],
  },
  {
    label: "Waiting Periods",
    fields: [
      { key: "initial_waiting_days", label: "Initial Waiting", formatter: "days" },
      { key: "ped_waiting_months", label: "PED Waiting", formatter: "months" },
      {
        key: "specific_disease_waiting_months",
        label: "Specific Disease",
        formatter: "months",
      },
      { key: "moratorium_months", label: "Moratorium Period", formatter: "months" },
    ],
  },
  {
    label: "Additional Benefits",
    fields: [
      { key: "_maternity", label: "Maternity & Newborn", formatter: "maternity" },
      { key: "critical_illness_covered", label: "Critical Illness", formatter: "yn" },
      { key: "mental_health_covered", label: "Mental Health", formatter: "yn" },
      { key: "opd_covered", label: "OPD Cover", formatter: "yn" },
      { key: "_restoration", label: "Restoration Benefit", formatter: "restoration" },
      { key: "_ncb", label: "No-Claim Bonus", formatter: "ncb" },
      { key: "health_checkup_covered", label: "Preventive Checkup", formatter: "yn" },
      { key: "wellness_covered", label: "Wellness Benefits", formatter: "yn" },
      { key: "international_covered", label: "International Cover", formatter: "yn" },
    ],
  },
  {
    label: "Claim Process",
    fields: [
      { key: "_cashless", label: "Cashless Claims", formatter: "cashless" },
      { key: "reimbursement_available", label: "Reimbursement", formatter: "yn" },
      { key: "cashless_helpline", label: "Claim Helpline" },
    ],
  },
  {
    label: "Policy Conditions",
    fields: [
      { key: "free_look_days", label: "Free Look Period", formatter: "days" },
      { key: "grace_period_text", label: "Grace Period" },
      { key: "renewal_guaranteed", label: "Guaranteed Renewal", formatter: "yn" },
      { key: "portability_available", label: "Portability", formatter: "yn" },
      { key: "territorial_limit", label: "Geographic Coverage" },
    ],
  },
  {
    label: "Premium & Discounts",
    fields: [
      { key: "premium_modes_text", label: "Payment Modes" },
      { key: "family_discount_text", label: "Family Discount" },
      { key: "long_term_discount_text", label: "Long-Term Discount" },
      { key: "other_discounts_text", label: "Other Discounts" },
    ],
  },
];

function formatInr(value) {
  if (!value) {
    return null;
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

function formatMonths(value) {
  if (!value) {
    return null;
  }

  const months = Number(value);

  if (months % 12 === 0) {
    const years = months / 12;
    return `${years} year${years > 1 ? "s" : ""}`;
  }

  return `${months} months`;
}

function formatDays(value) {
  return value ? `${value} days` : null;
}

function formatYesNo(value) {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  return null;
}

function resolveValue(row, field) {
  if (!row) {
    return null;
  }

  const get = (key) => {
    const value = row[key];
    return value === null || value === undefined || value === "" ? null : value;
  };

  switch (field.formatter) {
    case "yn":
      return formatYesNo(get(field.key));
    case "days":
      return formatDays(get(field.key));
    case "months":
      return formatMonths(get(field.key));
    case "si_range":
      return row.si_min_inr && row.si_max_inr
        ? `${formatInr(row.si_min_inr)} - ${formatInr(row.si_max_inr)}`
        : null;
    case "room_rent":
      if (row.room_rent_type === "no_limit") {
        return "No sub-limit";
      }
      if (row.room_rent_type === "fixed_per_day") {
        return `${formatInr(row.room_rent_fixed_inr)}/day`;
      }
      if (row.room_rent_type === "percentage_si") {
        return `${row.room_rent_pct_si}% of SI/day`;
      }
      if (row.room_rent_type === "room_category") {
        return row.room_rent_category;
      }
      return row.room_rent_limit_text || null;
    case "deductible":
      if (!row.has_deductible) {
        return "No";
      }
      return row.deductible_text ? `Yes - ${row.deductible_text}` : "Yes";
    case "copay":
      if (!row.has_copay) {
        return "No";
      }
      return row.copay_text ? `Yes - ${row.copay_text}` : "Yes";
    case "ambulance":
      if (!row.ambulance_covered) {
        return "Not covered";
      }
      return [
        "Covered",
        row.ambulance_limit_inr ? `${formatInr(row.ambulance_limit_inr)}/hosp` : null,
        row.ambulance_annual_limit_inr ? `${formatInr(row.ambulance_annual_limit_inr)}/yr` : null,
      ]
        .filter(Boolean)
        .join(", ");
    case "air_ambulance":
      if (!row.air_ambulance_covered) {
        return "Not covered";
      }
      return row.air_ambulance_limit_text
        ? `Covered - ${row.air_ambulance_limit_text}`
        : "Covered";
    case "maternity":
      if (!row.maternity_covered) {
        return "Not covered";
      }
      return [
        row.maternity_normal_inr ? `Normal: ${formatInr(row.maternity_normal_inr)}` : null,
        row.maternity_caesar_inr ? `C-section: ${formatInr(row.maternity_caesar_inr)}` : null,
        row.maternity_waiting_months
          ? `Waiting: ${formatMonths(row.maternity_waiting_months)}`
          : null,
        row.newborn_covered ? "Newborn covered" : null,
      ]
        .filter(Boolean)
        .join(" | ");
    case "restoration":
      if (!row.restoration_covered) {
        return "Not covered";
      }
      return [
        row.restoration_pct ? `${row.restoration_pct}% restored` : null,
        row.restoration_frequency_text || null,
        row.restoration_same_illness === false ? "Different illness only" : null,
        row.restoration_same_illness === true ? "Same illness too" : null,
      ]
        .filter(Boolean)
        .join(" | ");
    case "ncb":
      if (!row.ncb_covered) {
        return "No bonus";
      }
      return [row.ncb_rate_text, row.ncb_max_text ? `Max: ${row.ncb_max_text}` : null]
        .filter(Boolean)
        .join(" | ");
    case "cashless":
      if (!row.cashless_available) {
        return "Not available";
      }
      return [
        "Available",
        row.cashless_notice_planned ? `Planned: ${row.cashless_notice_planned}` : null,
        row.cashless_notice_emergency ? `Emergency: ${row.cashless_notice_emergency}` : null,
      ]
        .filter(Boolean)
        .join(" | ");
    default:
      return get(field.key) != null ? String(get(field.key)) : null;
  }
}

export default function ComparisonTable({ variantA, variantB }) {
  const [collapsed, setCollapsed] = useState({});

  const toggle = (label) => {
    setCollapsed((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const colA = `${variantA?.policy_name || "Policy A"} (${variantA?.variant_name || "-"})`;
  const colB = `${variantB?.policy_name || "Policy B"} (${variantB?.variant_name || "-"})`;

  return (
    <div className="table-card">
      {variantA?.extraction_date || variantB?.extraction_date ? (
        <div className="status-banner status-banner-warn" style={{ margin: "var(--sp-4)" }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>Data freshness warning: verify final coverage with the official policy document before purchase.</div>
        </div>
      ) : null}

      <div className="table-scroll">
        <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "28%" }} />
            <col style={{ width: "36%" }} />
            <col style={{ width: "36%" }} />
          </colgroup>
          <thead>
            <tr>
              <th style={thStyle()}>Feature</th>
              <th style={thStyle("rgba(111,182,255,0.08)")}>{colA}</th>
              <th style={thStyle("rgba(217,177,90,0.07)")}>{colB}</th>
            </tr>
          </thead>
          <tbody>
            {TAXONOMY_SECTIONS.map((section) => {
              const isCollapsed = collapsed[section.label];

              return (
                <React.Fragment key={section.label}>
                  <tr onClick={() => toggle(section.label)} style={{ cursor: "pointer" }}>
                    <td
                      colSpan={3}
                      style={{
                        background: "rgba(255,255,255,0.025)",
                        padding: "var(--sp-3) var(--sp-4)",
                        fontSize: "0.74rem",
                        fontWeight: 700,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: "var(--c-text-4)",
                        borderTop: "1px solid rgba(255,255,255,0.05)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        {section.label}
                        {isCollapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
                      </div>
                    </td>
                  </tr>

                  {!isCollapsed
                    ? section.fields.map((field) => {
                        const valueA = resolveValue(variantA, field);
                        const valueB = resolveValue(variantB, field);
                        const differs = valueA !== valueB && !(valueA == null && valueB == null);

                        return (
                          <tr key={field.key} className={differs ? "row-differs" : ""}>
                            <td style={tdStyle("label")}>
                              <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-1)" }}>
                                {differs ? <span className="diff-marker">DIFF</span> : null}
                                {field.label}
                              </div>
                            </td>
                            <td style={tdStyle("value")}>
                              <CellValue value={valueA} />
                            </td>
                            <td style={tdStyle("value", true)}>
                              <CellValue value={valueB} />
                            </td>
                          </tr>
                        );
                      })
                    : null}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <div
        style={{
          padding: "var(--sp-4) var(--sp-5)",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          fontSize: "0.8rem",
          color: "var(--c-text-2)",
          display: "flex",
          gap: "var(--sp-5)",
          flexWrap: "wrap",
        }}
      >
        <span>
          <span className="diff-marker">DIFF</span> values differ between policies
        </span>
        <span style={{ color: "var(--c-text-3)" }}>- indicates the field is absent in the current policy data</span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Info size={12} style={{ color: "var(--c-primary)" }} />
          Review the official wording before purchase.
        </span>
      </div>
    </div>
  );
}

function CellValue({ value }) {
  if (value === null || value === undefined || value === "") {
    return (
      <span style={{ color: "var(--c-text-3)", fontFamily: "var(--f-mono)", fontSize: "0.75rem" }}>
        -
      </span>
    );
  }

  const isPositive = String(value).startsWith("Yes") || String(value).startsWith("Covered");
  const isNegative = String(value).startsWith("No") || String(value).startsWith("Not");

  return (
    <span
      style={{
        color: isPositive
          ? "var(--c-success)"
          : isNegative
            ? "var(--c-text-3)"
            : "var(--c-text-1)",
        fontSize: "0.875rem",
        lineHeight: 1.6,
      }}
    >
      {value}
    </span>
  );
}

function thStyle(background) {
  return {
    background: background || "rgba(255,255,255,0.025)",
    padding: "var(--sp-4)",
    textAlign: "left",
    fontSize: "0.74rem",
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    color: "var(--c-text-3)",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    verticalAlign: "bottom",
    whiteSpace: "normal",
    lineHeight: 1.45,
  };
}

function tdStyle(type, altBackground) {
  const base = {
    padding: "var(--sp-3) var(--sp-4)",
    borderBottom: "1px solid rgba(255,255,255,0.05)",
    verticalAlign: "top",
    wordBreak: "break-word",
  };

  if (type === "label") {
    return {
      ...base,
      fontSize: "0.82rem",
      color: "var(--c-text-2)",
      fontWeight: 700,
      background: "rgba(255,255,255,0.01)",
    };
  }

  return {
    ...base,
    background: altBackground ? "rgba(255, 255, 255, 0.012)" : "transparent",
  };
}
