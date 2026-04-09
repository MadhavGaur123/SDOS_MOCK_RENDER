import React, { useState } from "react";
import { Clock3, MapPin, Phone, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { admin } from "../api";
import ChatPanel from "../components/chat/ChatPanel";
import { useApp } from "../context/AppContext";
import { useClaimChecklist, useFetch, useHospitals, useVariants } from "../hooks";

export function HospitalsPage() {
  const [query, setQuery] = useState({ city: "", insurer: "", pincode: "" });
  const [submitted, setSubmitted] = useState(null);
  const { data, error, loading } = useHospitals(submitted || {});
  const hospitals = data?.items || data || [];

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Hospital Lookup</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Find cashless hospitals by location and insurer
          </h1>
          <p className="body-sm">
            Search the current network data and verify final hospital eligibility with the insurer before admission.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-6)" }}>
        <div className="field-grid">
          <Field label="City">
            <input
              className="input-field"
              onChange={(event) => setQuery((prev) => ({ ...prev, city: event.target.value }))}
              placeholder="e.g. Mumbai"
              type="text"
              value={query.city}
            />
          </Field>
          <Field label="Pincode">
            <input
              className="input-field"
              onChange={(event) => setQuery((prev) => ({ ...prev, pincode: event.target.value }))}
              placeholder="e.g. 400001"
              type="text"
              value={query.pincode}
            />
          </Field>
          <Field label="Insurer">
            <input
              className="input-field"
              onChange={(event) => setQuery((prev) => ({ ...prev, insurer: event.target.value }))}
              placeholder="e.g. Star Health"
              type="text"
              value={query.insurer}
            />
          </Field>
        </div>

        <button className="btn btn-primary" onClick={() => setSubmitted({ ...query })} style={{ marginTop: "var(--sp-4)" }} type="button">
          <Search size={15} />
          Search Hospitals
        </button>
      </div>

      {loading ? <LoadingRows /> : null}
      {error ? <p style={{ color: "var(--c-danger)" }}>{error}</p> : null}

      {!loading && hospitals.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
          <div className="results-strip">
            <p className="heading-sm">Hospital Results</p>
            <span className="badge">{hospitals.length} found</span>
          </div>
          {hospitals.map((hospital, index) => (
            <div
              key={`${hospital.hospital_name}-${index}`}
              className="card"
              style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "var(--sp-4)" }}
            >
              <div>
                <p style={{ fontWeight: 700, fontSize: "0.98rem" }}>{hospital.hospital_name}</p>
                <p style={{ fontSize: "0.82rem", color: "var(--c-text-2)", marginTop: 4, display: "flex", gap: 6, alignItems: "center" }}>
                  <MapPin size={12} /> {hospital.address}, {hospital.city}
                  {hospital.pincode ? ` - ${hospital.pincode}` : ""}
                </p>
                {hospital.phone ? (
                  <p style={{ fontSize: "0.8rem", color: "var(--c-text-3)", marginTop: 4, display: "flex", gap: 6, alignItems: "center" }}>
                    <Phone size={12} /> {hospital.phone}
                  </p>
                ) : null}
              </div>

              <div style={{ textAlign: "right" }}>
                {hospital.network_type ? <span className="badge badge-success">{hospital.network_type}</span> : null}
                {hospital.last_updated ? (
                  <p style={{ fontSize: "0.72rem", color: "var(--c-text-3)", marginTop: 8, display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                    <Clock3 size={10} /> {new Date(hospital.last_updated).toLocaleDateString("en-IN")}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {!loading && submitted && !hospitals.length ? (
        <div className="empty-state">
          <MapPin size={32} style={{ margin: "0 auto var(--sp-3)", color: "var(--c-text-4)" }} />
          <p style={{ fontWeight: 700, color: "var(--c-text-1)" }}>No hospitals found for this search</p>
          <p style={{ fontSize: "0.82rem", marginTop: "var(--sp-2)", color: "var(--c-text-3)" }}>
            Network data may be incomplete. Verify the final list with the insurer&apos;s official portal.
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function ChatPage() {
  const { chatContext, setChatContext } = useApp();
  const [policyQuery, setPolicyQuery] = useState("");
  const { data, error, loading } = useVariants({ page_size: 100, q: policyQuery });
  const variants = data?.items || data || [];
  const hasScopedContext = Boolean(chatContext?.id && chatContext?.type && chatContext.type !== "general");

  const selectPolicy = (variant) => {
    setChatContext({
      type: "variant",
      id: variant.variant_id,
      label: `${variant.policy_name} - ${variant.variant_name}`,
    });
  };

  const contextDescription =
    chatContext?.type === "document"
      ? "Document-scoped chat. Full uploaded-document RAG still depends on OCR and clause indexing."
      : chatContext?.type === "comparison"
        ? "Comparison-scoped chat across two selected variants."
        : "Policy-scoped chat across the selected variant's extracted clauses.";

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Policy Assistant</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Ask grounded questions with the right context
          </h1>
          <p className="body-sm">
            Choose a policy, use a comparison, or continue from <Link to="/my-policies">My Policies</Link> for document-scoped Q&amp;A.
          </p>
        </div>
      </div>

      {!hasScopedContext ? (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
          <div>
            <h3 className="heading-lg">Choose a policy first</h3>
            <p className="body-sm mt-2">
              The assistant is strongest when it is scoped to one policy variant. Choose a plan below, then ask about coverage, exclusions, waiting periods, room rent, or claims.
            </p>
          </div>

          <div style={{ position: "relative", maxWidth: 520 }}>
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
              onChange={(event) => setPolicyQuery(event.target.value)}
              placeholder="Search by policy, insurer, or variant..."
              style={{ paddingLeft: 40 }}
              type="text"
              value={policyQuery}
            />
          </div>

          {loading ? <LoadingRows /> : null}
          {error ? <p style={{ color: "var(--c-danger)" }}>{error}</p> : null}

          {!loading && !error ? (
            <div className="card-grid">
              {variants.map((variant) => (
                <button
                  key={variant.variant_id}
                  onClick={() => selectPolicy(variant)}
                  className="card"
                  style={{ textAlign: "left", cursor: "pointer" }}
                  type="button"
                >
                  <div style={{ display: "flex", gap: "var(--sp-2)", flexWrap: "wrap", marginBottom: "var(--sp-3)" }}>
                    <span className="badge badge-primary">{variant.insurer_name}</span>
                    {variant.policy_type ? <span className="badge">{variant.policy_type}</span> : null}
                  </div>
                  <p style={{ fontWeight: 700, fontSize: "0.98rem" }}>{variant.policy_name}</p>
                  <p style={{ color: "var(--c-text-2)", fontSize: "0.82rem", marginTop: 4 }}>{variant.variant_name}</p>
                  <p style={{ color: "var(--c-text-3)", fontSize: "0.78rem", marginTop: "var(--sp-3)" }}>
                    {variant.si_options_text || "Sum insured options not stated"}
                  </p>
                </button>
              ))}
            </div>
          ) : null}

          {!loading && !error && !variants.length ? (
            <div className="empty-state">
              <p style={{ fontWeight: 700, color: "var(--c-text-1)" }}>No policies matched your search</p>
              <p style={{ fontSize: "0.84rem", marginTop: "var(--sp-2)" }}>
                Try a broader insurer or policy name to continue.
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <div
            className="card"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "var(--sp-4)",
              marginBottom: "var(--sp-4)",
              flexWrap: "wrap",
            }}
          >
            <div>
              <p className="metric-label">Current Context</p>
              <h3 className="metric-value" style={{ fontSize: "1.02rem" }}>
                {chatContext.label}
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--c-text-3)", marginTop: 4 }}>
                {contextDescription}
              </p>
            </div>

            <button className="btn btn-ghost btn-sm" onClick={() => setChatContext(null)} type="button">
              Change Context
            </button>
          </div>

          <div style={{ height: "calc(100vh - var(--topbar-h) - 220px)" }}>
            <ChatPanel
              contextId={chatContext?.id || null}
              contextLabel={chatContext?.label || null}
              contextType={chatContext?.type || "general"}
            />
          </div>
        </>
      )}
    </div>
  );
}

export function ClaimChecklistPage() {
  const [form, setForm] = useState({ claim_type: "cashless", procedure: "", variant_id: "" });
  const { checklist, generate, loading } = useClaimChecklist();

  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Claim Checklist</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Generate a claim-readiness checklist
          </h1>
          <p className="body-sm">
            Build a simple cashless or reimbursement checklist using the selected variant and procedure context.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-6)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
          <Field label="Variant ID">
            <input
              className="input-field"
              onChange={(event) => setForm((prev) => ({ ...prev, variant_id: event.target.value }))}
              placeholder="From catalog or My Policies"
              type="text"
              value={form.variant_id}
            />
          </Field>
          <Field label="Claim Type">
            <select
              className="input-field"
              onChange={(event) => setForm((prev) => ({ ...prev, claim_type: event.target.value }))}
              value={form.claim_type}
            >
              <option value="cashless">Cashless (Pre-auth)</option>
              <option value="reimbursement">Reimbursement</option>
            </select>
          </Field>
          <Field label="Procedure / Diagnosis (optional)">
            <input
              className="input-field"
              onChange={(event) => setForm((prev) => ({ ...prev, procedure: event.target.value }))}
              placeholder="e.g. Knee replacement, Appendectomy"
              type="text"
              value={form.procedure}
            />
          </Field>
          <button
            className="btn btn-primary"
            disabled={!form.variant_id || loading}
            onClick={() => generate(form)}
            style={{ alignSelf: "flex-start" }}
            type="button"
          >
            {loading ? "Generating..." : "Generate Checklist"}
          </button>
        </div>
      </div>

      {checklist ? <ChecklistDisplay checklist={checklist} /> : null}
    </div>
  );
}

export function AdminPage() {
  const { data, error, loading } = useFetch(() => admin.getVariants(), []);
  const variants = data?.items || data || [];

  return (
    <div style={{ maxWidth: "var(--content-max)", margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Operations</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Admin workspace
          </h1>
          <p className="body-sm">
            Review policy variants and data operations without changing the existing admin behavior.
          </p>
        </div>
      </div>

      <div className="table-card">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "var(--sp-3)",
            padding: "var(--sp-5)",
            borderBottom: "1px solid rgba(255,255,255,0.05)",
          }}
        >
          <h3 className="heading-lg">Policy Variants</h3>
          <button className="btn btn-primary btn-sm" type="button">
            + Add Variant
          </button>
        </div>

        {loading ? <div style={{ padding: "var(--sp-5)" }}><LoadingRows /></div> : null}
        {error ? <p style={{ color: "var(--c-danger)", padding: "var(--sp-5)" }}>{error}</p> : null}

        {!loading ? (
          <div className="table-scroll">
            <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, fontSize: "0.875rem" }}>
              <thead>
                <tr>
                  {["Insurer", "Policy", "Variant", "Type", "SI Range", "Extracted", "Actions"].map((heading) => (
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
                        whiteSpace: "nowrap",
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
                {variants.map((variant) => (
                  <tr key={variant.variant_id}>
                    {[
                      variant.insurer_name,
                      variant.policy_name,
                      variant.variant_name,
                      variant.policy_type || "-",
                      variant.si_options_text || "-",
                      variant.extraction_date ? new Date(variant.extraction_date).toLocaleDateString("en-IN") : "-",
                    ].map((value, index) => (
                      <td
                        key={`${variant.variant_id}-${index}`}
                        style={{ padding: "var(--sp-3) var(--sp-4)", borderBottom: "1px solid rgba(255,255,255,0.05)", color: "var(--c-text-2)" }}
                      >
                        {value}
                      </td>
                    ))}
                    <td style={{ padding: "var(--sp-3) var(--sp-4)", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                      <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                        <button className="btn btn-ghost btn-sm" type="button">
                          Edit
                        </button>
                        <button className="btn btn-danger btn-sm" type="button">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ChecklistDisplay({ checklist }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
      {checklist.sections?.map((section, sectionIndex) => (
        <div key={`${section.title}-${sectionIndex}`} className="card">
          <h3 className="heading-lg" style={{ marginBottom: "var(--sp-4)" }}>
            {section.title}
          </h3>
          {section.timeline ? (
            <p style={{ fontSize: "0.8rem", color: "var(--c-warn)", marginBottom: "var(--sp-3)", display: "flex", gap: 6, alignItems: "center" }}>
              <Clock3 size={13} /> {section.timeline}
            </p>
          ) : null}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
            {section.items?.map((item, itemIndex) => (
              <label
                key={`${item.label}-${itemIndex}`}
                style={{
                  display: "flex",
                  gap: "var(--sp-3)",
                  cursor: "pointer",
                  alignItems: "flex-start",
                  padding: "var(--sp-3)",
                  borderRadius: "var(--r-md)",
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <input style={{ marginTop: 3 }} type="checkbox" />
                <div>
                  <p style={{ fontSize: "0.875rem", fontWeight: 600 }}>{item.label}</p>
                  {item.note ? <p style={{ fontSize: "0.78rem", color: "var(--c-text-3)", marginTop: 2 }}>{item.note}</p> : null}
                </div>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function LoadingRows() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
      {[1, 2, 3].map((index) => (
        <div key={index} className="skeleton" style={{ height: 72, borderRadius: "var(--r-md)" }} />
      ))}
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
