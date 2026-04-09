"""
HealIN v2 – Policy Display & Comparison
========================================
Works with the v2 normalized schema where every comparable field
is a typed column in policy_variants — no JSONB drilling needed.

Usage:
    python policy_display_v2.py list   [--policy <name_fragment>]
    python policy_display_v2.py show   <variant_id> [--out file.txt]
    python policy_display_v2.py compare <variant_id_a> <variant_id_b> [--out file.txt]

The unit of display/comparison is a VARIANT (e.g. "Easy Health – Exclusive"),
not the parent policy document.
"""

import os, sys, textwrap
import psycopg2, psycopg2.extras
from tabulate import tabulate

# ── DB ────────────────────────────────────────────────────────────────────────
def get_conn():
    dsn = os.getenv("HEALIN_DB_URL") or os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("DB_HOST","localhost"), dbname=os.getenv("DB_NAME","HealIN_DB2"),
        user=os.getenv("DB_USER","postgres"),  password=os.getenv("DB_PASSWORD","postgres"),
        port=int(os.getenv("DB_PORT","5432")),
    )

# ── Fetchers ──────────────────────────────────────────────────────────────────
def fetch_variant(vid, cur):
    cur.execute("""
        SELECT v.*, p.policy_name, p.policy_code, p.version, p.effective_date,
               p.policy_type, p.source_file, p.extraction_date, p.page_count,
               i.insurer_name, i.irdai_reg, i.helpline
        FROM policy_variants v
        JOIN policies  p USING (policy_id)
        JOIN insurers  i USING (insurer_id)
        WHERE v.variant_id = %s
    """, (vid,))
    r = cur.fetchone()
    return dict(r) if r else None

def fetch_exclusions(vid, cur):
    cur.execute("""SELECT exclusion_name, description, exception_conditions, exclusion_category
                   FROM variant_exclusions WHERE variant_id=%s
                   ORDER BY exclusion_category, exclusion_name""", (vid,))
    return cur.fetchall()

def fetch_waiting_periods(vid, cur):
    cur.execute("""SELECT period_type, disease_or_procedure, duration_days,
                          can_be_reduced, reduction_conditions
                   FROM variant_waiting_periods WHERE variant_id=%s ORDER BY period_type""", (vid,))
    return cur.fetchall()

def fetch_sublimits(vid, cur):
    cur.execute("""SELECT limit_category, item_name, description, limit_inr, limit_pct, applies_to
                   FROM variant_sublimits WHERE variant_id=%s
                   ORDER BY limit_category, item_name""", (vid,))
    return cur.fetchall()

def list_variants(cur, fragment=None):
    if fragment:
        cur.execute("""SELECT v.variant_id, i.insurer_name, p.policy_name, v.variant_name,
                              v.si_options_text, p.policy_type
                       FROM policy_variants v
                       JOIN policies p USING(policy_id) JOIN insurers i USING(insurer_id)
                       WHERE lower(p.policy_name) LIKE %s
                       ORDER BY i.insurer_name, p.policy_name, v.variant_name""",
                    (f"%{fragment.lower()}%",))
    else:
        cur.execute("""SELECT v.variant_id, i.insurer_name, p.policy_name, v.variant_name,
                              v.si_options_text, p.policy_type
                       FROM policy_variants v
                       JOIN policies p USING(policy_id) JOIN insurers i USING(insurer_id)
                       ORDER BY i.insurer_name, p.policy_name, v.variant_name""")
    return cur.fetchall()

# ── Formatters ────────────────────────────────────────────────────────────────
W_SINGLE, W_COL = 85, 38

def _w(text, width=W_SINGLE):
    if not text or str(text).strip() in ("","None"): return "—"
    return "\n".join(textwrap.wrap(str(text), width))

def _yn(val):
    if val is True:  return "Yes"
    if val is False: return "No"
    return "—"

def _inr(val):
    if val is None: return "—"
    v = int(val)
    if v >= 10_00_000: return f"Rs.{v/10_00_000:.1f}L".replace(".0L","L")
    if v >= 1_00_000:  return f"Rs.{v/1_00_000:.1f}L".replace(".0L","L")
    if v >= 1_000:     return f"Rs.{v//1000}K"
    return f"Rs.{v}"

def _months(m):
    if m is None: return "—"
    m = int(m)
    if m % 12 == 0: return f"{m//12} year{'s' if m//12>1 else ''}"
    return f"{m} months"

def _days(d):
    return f"{d} days" if d else "—"

def _room_rent(v):
    t = v.get("room_rent_type")
    if t == "no_limit":      return "No sub-limit (reasonable & customary)"
    if t == "fixed_per_day": return _inr(v.get("room_rent_fixed_inr")) + "/day"
    if t == "percentage_si": return f"{v.get('room_rent_pct_si')}% of SI/day (max {_inr(v.get('room_rent_fixed_inr'))})"
    if t == "room_category": return v.get("room_rent_category","—")
    return _w(v.get("room_rent_limit_text","—"))

def _maternity(v):
    if not v.get("maternity_covered"): return "Not covered"
    parts = []
    if v.get("maternity_normal_inr"):     parts.append(f"Normal: {_inr(v['maternity_normal_inr'])}")
    if v.get("maternity_caesar_inr"):     parts.append(f"C-section: {_inr(v['maternity_caesar_inr'])}")
    if v.get("maternity_waiting_months"): parts.append(f"Waiting: {_months(v['maternity_waiting_months'])}")
    if v.get("maternity_max_deliveries"): parts.append(f"Max {v['maternity_max_deliveries']} deliveries")
    if v.get("newborn_covered"):          parts.append(f"Newborn: {_inr(v.get('newborn_limit_inr')) or 'Covered'}")
    return "\n".join(parts) if parts else "Covered"

def _restoration(v):
    if not v.get("restoration_covered"): return "Not covered"
    parts = []
    if v.get("restoration_pct"):             parts.append(f"{v['restoration_pct']}% of SI restored")
    if v.get("restoration_frequency_text"):  parts.append(v["restoration_frequency_text"])
    same = v.get("restoration_same_illness")
    if same is True:  parts.append("Usable for same illness")
    if same is False: parts.append("Only for different illness")
    if v.get("restoration_limit_text"):      parts.append(v["restoration_limit_text"])
    return "\n".join(parts) if parts else "Covered"

def _ncb(v):
    if not v.get("ncb_covered"): return "No bonus"
    parts = []
    if v.get("ncb_rate_text"): parts.append(v["ncb_rate_text"])
    if v.get("ncb_max_text"):  parts.append(f"Max: {v['ncb_max_text']}")
    if v.get("ncb_on_claim"):  parts.append(v["ncb_on_claim"])
    return "\n".join(parts) if parts else "Yes"

def _resolve(row, field, fmt):
    if fmt:
        try:    return fmt(row) or "—"
        except: return "—"
    if field is None: return ""
    raw = row.get(field)
    return "—" if raw is None or str(raw).strip() == "" else str(raw)

# ── Canonical taxonomy ────────────────────────────────────────────────────────
# (label, field_name_or_None, formatter_or_None)
# field=None + fmt=None => section header row

TAXONOMY = [
    ("POLICY IDENTITY",                    None, None),
    ("Insurer",                             "insurer_name",            None),
    ("Policy Name",                         "policy_name",             None),
    ("Variant / Plan",                      "variant_name",            None),
    ("Policy Type",                         "policy_type",             None),
    ("Sum Insured Range",                   None, lambda v: f"{_inr(v.get('si_min_inr'))} – {_inr(v.get('si_max_inr'))}"),
    ("Sum Insured Options",                 "si_options_text",         None),

    ("CORE HOSPITALISATION",               None, None),
    ("Inpatient Cover",                     "inpatient_limit_text",    None),
    ("Pre-Hospitalisation",                 "pre_hosp_days",           lambda v: _days(v.get("pre_hosp_days"))),
    ("Post-Hospitalisation",                "post_hosp_days",          lambda v: _days(v.get("post_hosp_days"))),
    ("Day-Care Procedures",                 "daycare_covered",         lambda v: _yn(v.get("daycare_covered"))),
    ("Domiciliary Treatment",               "domiciliary_covered",     lambda v: (_yn(v.get("domiciliary_covered")) + (f"  (min {v['domiciliary_min_days']} days)" if v.get("domiciliary_min_days") else ""))),
    ("AYUSH Treatment",                     "ayush_covered",           lambda v: (_yn(v.get("ayush_covered")) + (f"\n{v['ayush_limit_text']}" if v.get("ayush_limit_text") else ""))),
    ("Organ Donor Expenses",                "organ_donor_covered",     lambda v: _yn(v.get("organ_donor_covered"))),

    ("ROOM RENT & LIMITS",                 None, None),
    ("Room Rent",                           None, _room_rent),
    ("ICU Coverage",                        "icu_limit_text",          None),
    ("Deductible",                          "has_deductible",          lambda v: (_yn(v.get("has_deductible")) + (f"  {v['deductible_text']}" if v.get("deductible_text") else ""))),
    ("Co-payment",                          "has_copay",               lambda v: (_yn(v.get("has_copay")) + (f"  {v['copay_text']}" if v.get("copay_text") else ""))),

    ("AMBULANCE",                          None, None),
    ("Road Ambulance",                      "ambulance_covered",       lambda v: (_yn(v.get("ambulance_covered")) + (f"  {_inr(v.get('ambulance_limit_inr'))}/hosp" if v.get("ambulance_limit_inr") else "") + (f", {_inr(v.get('ambulance_annual_limit_inr'))}/yr" if v.get("ambulance_annual_limit_inr") else ""))),
    ("Air Ambulance",                       "air_ambulance_covered",   lambda v: (_yn(v.get("air_ambulance_covered")) + (f"\n{v['air_ambulance_limit_text']}" if v.get("air_ambulance_limit_text") else ""))),

    ("WAITING PERIODS",                    None, None),
    ("Initial Waiting Period",              "initial_waiting_days",    lambda v: _days(v.get("initial_waiting_days"))),
    ("Pre-Existing Diseases (PED)",         "ped_waiting_months",      lambda v: (_months(v.get("ped_waiting_months")) + ("  (reducible via portability)" if v.get("ped_reducible") else ""))),
    ("Specific Disease Waiting",            "specific_disease_waiting_months", lambda v: _months(v.get("specific_disease_waiting_months"))),

    ("ADDITIONAL BENEFITS",                None, None),
    ("Maternity & Newborn",                 None, _maternity),
    ("Critical Illness",                    "critical_illness_covered",lambda v: (_yn(v.get("critical_illness_covered")) + (f"\n{v['critical_illness_limit_text']}" if v.get("critical_illness_limit_text") else "") + (f"\nWaiting: {_days(v.get('critical_illness_waiting_days'))}" if v.get("critical_illness_waiting_days") else ""))),
    ("Mental Health Cover",                 "mental_health_covered",   lambda v: _yn(v.get("mental_health_covered"))),
    ("OPD Cover",                           "opd_covered",             lambda v: _yn(v.get("opd_covered"))),
    ("Restoration / Recharge Benefit",      None, _restoration),
    ("No-Claim / Cumulative Bonus",         None, _ncb),
    ("Preventive Health Checkup",           "health_checkup_covered",  lambda v: (_yn(v.get("health_checkup_covered")) + (f"\n{v['health_checkup_limit_text']}" if v.get("health_checkup_limit_text") else "") + (f"  {v['health_checkup_frequency']}" if v.get("health_checkup_frequency") else ""))),
    ("Wellness Benefits",                   "wellness_covered",        lambda v: (_yn(v.get("wellness_covered")) + (f"\n{v['wellness_details_text']}" if v.get("wellness_details_text") else ""))),
    ("International Cover",                 "international_covered",   lambda v: _yn(v.get("international_covered"))),
    ("Moratorium Period",                   "moratorium_months",       lambda v: _months(v.get("moratorium_months"))),

    ("CLAIM PROCESS",                      None, None),
    ("Cashless Claims",                     "cashless_available",      lambda v: (_yn(v.get("cashless_available")) + (f"\nPlanned: {v['cashless_notice_planned']}" if v.get("cashless_notice_planned") else "") + (f"\nEmergency: {v['cashless_notice_emergency']}" if v.get("cashless_notice_emergency") else ""))),
    ("Reimbursement",                       "reimbursement_available", lambda v: (_yn(v.get("reimbursement_available")) + (f"  Submit within {v['reimbursement_submit_days']} days of discharge" if v.get("reimbursement_submit_days") else ""))),
    ("Claim Helpline",                      "cashless_helpline",       None),

    ("POLICY CONDITIONS",                  None, None),
    ("Free Look Period",                    "free_look_days",          lambda v: _days(v.get("free_look_days"))),
    ("Grace Period",                        "grace_period_text",       None),
    ("Guaranteed Renewal",                  "renewal_guaranteed",      lambda v: _yn(v.get("renewal_guaranteed"))),
    ("Portability",                         "portability_available",   lambda v: _yn(v.get("portability_available"))),
    ("Geographic Coverage",                 "territorial_limit",       None),

    ("PREMIUM & DISCOUNTS",                None, None),
    ("Premium Payment Modes",               "premium_modes_text",      None),
    ("Family Discount",                     "family_discount_text",    None),
    ("Long-Term / Multi-year Discount",     "long_term_discount_text", None),
    ("Other Discounts",                     "other_discounts_text",    None),
]

# ── Display single variant ────────────────────────────────────────────────────
def display_variant(variant_id, conn, print_output=True):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    row = fetch_variant(variant_id, cur)
    if not row:
        return f"[HealIN] Variant not found: {variant_id}"

    W = W_SINGLE * 2 + 5
    lines = []
    lines.append("\n" + "═"*W)
    lines.append("  POLICY DETAILS  –  HealIN")
    lines.append("═"*W)

    current_sec, sec_rows = "", []

    def _flush():
        if sec_rows:
            lines.append(f"\n{'━'*W}\n  {current_sec}\n{'━'*W}")
            lines.append(tabulate(sec_rows, headers=["Feature","Details"], tablefmt="rounded_outline"))

    for label, field, fmt in TAXONOMY:
        if field is None and fmt is None:
            _flush(); sec_rows = []; current_sec = label; continue
        val = _resolve(row, field, fmt)
        sec_rows.append([label, _w(val, W_SINGLE)])
    _flush()

    wps = fetch_waiting_periods(variant_id, cur)
    if wps:
        lines.append(f"\n{'━'*W}\n  DETAILED WAITING PERIODS\n{'━'*W}")
        lines.append(tabulate(
            [[wp["period_type"].replace("_"," ").title(),
              _w(wp["disease_or_procedure"], W_SINGLE),
              _days(wp["duration_days"]),
              _w(("Yes — " + wp["reduction_conditions"]) if wp["can_be_reduced"] and wp["reduction_conditions"] else ("Yes" if wp["can_be_reduced"] else "No"), W_SINGLE//2)]
             for wp in wps],
            headers=["Type","Condition","Duration","Reducible?"], tablefmt="rounded_outline"))

    excls = fetch_exclusions(variant_id, cur)
    if excls:
        lines.append(f"\n{'━'*W}\n  EXCLUSIONS\n{'━'*W}")
        lines.append("  Conditions NOT covered (standard IRDAI + policy-specific). Exceptions noted where applicable.\n")
        lines.append(tabulate(
            [[e["exclusion_category"] or "—", _w(e["exclusion_name"],35),
              _w(e["description"], W_SINGLE),
              _w(e["exception_conditions"], W_SINGLE//2) if e["exception_conditions"] else "—"]
             for e in excls],
            headers=["Category","Name","Description","Exception / When covered"], tablefmt="rounded_outline"))

    subs = fetch_sublimits(variant_id, cur)
    if subs:
        lines.append(f"\n{'━'*W}\n  SUB-LIMITS & CAPS\n{'━'*W}")
        lines.append(tabulate(
            [[s["limit_category"].replace("_"," ").title(), _w(s["item_name"],40),
              _inr(s["limit_inr"]) if s["limit_inr"] else (f"{s['limit_pct']}%" if s["limit_pct"] else "—"),
              s["applies_to"] or "—", _w(s["description"], W_SINGLE//2)]
             for s in subs],
            headers=["Category","Item","Limit","Applies To","Notes"], tablefmt="rounded_outline"))

    lines.append("\n"+"═"*W)
    lines.append("  DISCLAIMER: Informational only. Always verify with the official policy document.")
    lines.append("═"*W+"\n")
    output = "\n".join(lines)
    if print_output: print(output)
    return output

# ── Compare two variants ──────────────────────────────────────────────────────
def compare_variants(vid_a, vid_b, conn, print_output=True):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    row_a = fetch_variant(vid_a, cur)
    row_b = fetch_variant(vid_b, cur)
    missing = []
    if not row_a: missing.append(f"A ({vid_a})")
    if not row_b: missing.append(f"B ({vid_b})")
    if missing: return f"[HealIN] Not found: {', '.join(missing)}"

    row_a, row_b = dict(row_a), dict(row_b)
    col_a = f"{row_a['policy_name']} ({row_a['variant_name']})"
    col_b = f"{row_b['policy_name']} ({row_b['variant_name']})"
    W = W_COL * 2 + 30
    lines, diff_count = [], 0
    lines.append("\n"+"═"*W)
    lines.append("  POLICY COMPARISON  –  HealIN")
    lines.append("═"*W)
    lines.append("  Legend:  ◆ = values differ   |   — = not stated in document\n")

    current_sec, sec_rows = "", []

    def _flush():
        if not sec_rows: return
        lines.append(f"\n{'─'*W}\n  {current_sec}\n{'─'*W}")
        lines.append(tabulate(sec_rows,
                               headers=["Feature", _w(col_a,W_COL), _w(col_b,W_COL)],
                               tablefmt="rounded_outline"))

    for label, field, fmt in TAXONOMY:
        if field is None and fmt is None:
            _flush(); sec_rows = []; current_sec = label; continue
        va = _w(_resolve(row_a, field, fmt), W_COL)
        vb = _w(_resolve(row_b, field, fmt), W_COL)
        differs = va.strip() != vb.strip() and not (va=="—" and vb=="—")
        if differs: diff_count += 1
        sec_rows.append([label+(" ◆" if differs else ""), va, vb])
    _flush()

    # Exclusions side-by-side
    ea_map = {e["exclusion_name"]: e for e in fetch_exclusions(vid_a, cur)}
    eb_map = {e["exclusion_name"]: e for e in fetch_exclusions(vid_b, cur)}
    all_names = sorted(set(ea_map)|set(eb_map))
    if all_names:
        lines.append(f"\n{'─'*W}\n  EXCLUSIONS COMPARISON\n{'─'*W}")
        ex_rows = []
        for name in all_names:
            ea = ea_map.get(name)
            eb = eb_map.get(name)
            va = ("Excluded" + (f"\n  Exception: {_w(ea['exception_conditions'],W_COL-12)}" if ea and ea["exception_conditions"] else "")) if ea else "— Not listed"
            vb = ("Excluded" + (f"\n  Exception: {_w(eb['exception_conditions'],W_COL-12)}" if eb and eb["exception_conditions"] else "")) if eb else "— Not listed"
            ex_rows.append([_w(name,30), va, vb])
        lines.append(tabulate(ex_rows, headers=["Exclusion", _w(col_a,W_COL), _w(col_b,W_COL)], tablefmt="rounded_outline"))

    lines.append(f"\n{'━'*W}")
    lines.append(f"  SUMMARY:  {diff_count} feature(s) differ  (◆ markers above)")
    lines.append(f"{'━'*W}")
    lines.append(tabulate([
        ["— in a cell",  "Field absent in that policy's document."],
        ["Stale data",   "Check extraction dates; data >90 days may be outdated."],
        ["Variant note", "Values reflect the selected variant/plan only."],
        ["Not advice",   "Informational only. Consult a certified advisor before buying."],
    ], headers=["Note","Detail"], tablefmt="rounded_outline"))
    lines.append("═"*W+"\n")
    output = "\n".join(lines)
    if print_output: print(output)
    return output

# ── List variants ─────────────────────────────────────────────────────────────
def list_all_variants(conn, fragment=None, print_output=True):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    rows = list_variants(cur, fragment)
    if not rows: return "[HealIN] No variants found."
    tbl = tabulate(
        [[r["variant_id"], r["insurer_name"], r["policy_name"], r["variant_name"],
          r["si_options_text"] or "—", r["policy_type"] or "—"]
         for r in rows],
        headers=["Variant ID (use for show/compare)","Insurer","Policy","Variant","Sum Insured","Type"],
        tablefmt="rounded_outline")
    if print_output:
        print("\n[HealIN] Available variants:\n")
        print(tbl)
    return tbl

# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HealIN v2 – Policy Display & Comparison")
    sub = parser.add_subparsers(dest="cmd")

    lp = sub.add_parser("list", help="List all variants in DB")
    lp.add_argument("--policy", default=None, help="Filter by policy name fragment")

    sp = sub.add_parser("show", help="Show a single variant")
    sp.add_argument("variant_id")
    sp.add_argument("--out", metavar="FILE", default=None)

    cp = sub.add_parser("compare", help="Compare two variants")
    cp.add_argument("variant_id_a")
    cp.add_argument("variant_id_b")
    cp.add_argument("--out", metavar="FILE", default=None)

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help(); sys.exit(0)

    conn = get_conn()

    def _save(text, path):
        with open(path,"w",encoding="utf-8") as f: f.write(text)
        print(f"[HealIN] Saved to: {os.path.abspath(path)}")

    try:
        out = getattr(args,"out",None)
        to_term = out is None
        if args.cmd == "list":
            list_all_variants(conn, getattr(args,"policy",None))
        elif args.cmd == "show":
            r = display_variant(args.variant_id, conn, print_output=to_term)
            if out: _save(r, out)
        elif args.cmd == "compare":
            r = compare_variants(args.variant_id_a, args.variant_id_b, conn, print_output=to_term)
            if out: _save(r, out)
    finally:
        conn.close()
