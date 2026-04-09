"""
HealIN v2 – JSON → PostgreSQL Populator
========================================
Reads extracted policy JSON files and populates the v2 schema.

Usage:
    python populate_v2.py <file1.json> [file2.json ...]

    Or populate all JSONs in a directory:
    python populate_v2.py policies/

Environment variables for DB connection (same as before):
    DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT

The script is idempotent: re-running it with the same JSON will update
existing rows rather than error or duplicate them.
"""

import json
import os
import sys
import re
import glob
import psycopg2
import psycopg2.extras
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# DB connection
# ─────────────────────────────────────────────────────────────────────────────

def get_conn():
    dsn = os.getenv("HEALIN_DB_URL") or os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host    = os.getenv("DB_HOST",     "localhost"),
        dbname  = os.getenv("DB_NAME",     "HealIN_DB2"),
        user    = os.getenv("DB_USER",     "postgres"),
        password= os.getenv("DB_PASSWORD", "postgres"),
        port    = int(os.getenv("DB_PORT", "5432")),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def _int(v) -> Optional[int]:
    """Safely coerce to int, return None on failure."""
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _bool(v) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "yes", "1")
    return None


def _si_options_text(options: list) -> str:
    """Convert [100000, 150000 …] to 'Rs.1L, Rs.1.5L …'"""
    def fmt(n):
        if n >= 10_00_000:
            return f"Rs.{n // 10_00_000}Cr" if n % 10_00_000 == 0 else f"Rs.{n/10_00_000:.1f}Cr"
        if n >= 1_00_000:
            return f"Rs.{n // 1_00_000}L" if n % 1_00_000 == 0 else f"Rs.{n/1_00_000:.1f}L"
        return f"Rs.{n//1000}K"
    return ", ".join(fmt(o) for o in options) if options else ""


def _si_range(options: list):
    """Return (min_inr, max_inr) from a list of SI options."""
    if not options:
        return None, None
    return min(options), max(options)


# ─────────────────────────────────────────────────────────────────────────────
# Upsert helpers
# ─────────────────────────────────────────────────────────────────────────────

def upsert_insurer(cur, data: dict) -> int:
    bi = data.get("basic_info", {})
    cur.execute("""
        INSERT INTO insurers (insurer_name, irdai_reg, cin, helpline, website)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (insurer_name) DO UPDATE
            SET irdai_reg = EXCLUDED.irdai_reg,
                cin       = EXCLUDED.cin
        RETURNING insurer_id
    """, (
        bi.get("insurer_name"),
        bi.get("irdai_registration"),
        bi.get("cin"),
        None,   # helpline enriched from claim_procedures below
        None,
    ))
    return cur.fetchone()[0]


def upsert_policy(cur, insurer_id: int, data: dict) -> str:
    bi = data.get("basic_info", {})
    eff = bi.get("effective_date")
    if eff and len(eff) == 10:
        eff_date = eff
    else:
        eff_date = None

    cur.execute("""
        INSERT INTO policies
            (insurer_id, policy_name, policy_code, version, effective_date,
             policy_type, document_type, source_file, extraction_date, page_count)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (insurer_id, policy_name, policy_code, version) DO UPDATE
            SET effective_date  = EXCLUDED.effective_date,
                policy_type     = EXCLUDED.policy_type,
                source_file     = EXCLUDED.source_file,
                extraction_date = EXCLUDED.extraction_date,
                page_count      = EXCLUDED.page_count
        RETURNING policy_id
    """, (
        insurer_id,
        bi.get("policy_name"),
        bi.get("policy_code", ""),
        bi.get("version", ""),
        eff_date,
        bi.get("policy_type"),
        bi.get("document_type"),
        data.get("source_file"),
        data.get("extraction_date", "")[:10] if data.get("extraction_date") else None,
        _int(data.get("page_count")),
    ))
    return cur.fetchone()[0]


def upsert_variant(cur, policy_id: str, variant_name: str, fields: dict) -> str:
    """
    Insert or update a policy_variants row.
    `fields` is a dict matching column names exactly.
    Returns variant_id (UUID).
    """
    fields["policy_id"]    = policy_id
    fields["variant_name"] = variant_name

    cols   = list(fields.keys())
    vals   = [fields[c] for c in cols]
    placeholders = ", ".join(["%s"] * len(cols))
    col_str      = ", ".join(cols)
    update_str   = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("policy_id", "variant_name"))

    cur.execute(f"""
        INSERT INTO policy_variants ({col_str})
        VALUES ({placeholders})
        ON CONFLICT (policy_id, variant_name) DO UPDATE SET {update_str}
        RETURNING variant_id
    """, vals)
    return cur.fetchone()[0]


def insert_features(cur, variant_id: str, features: list):
    cur.execute("DELETE FROM variant_features WHERE variant_id = %s", (variant_id,))
    for f in features:
        cur.execute("""
            INSERT INTO variant_features
                (variant_id, feature_type, feature_name, is_covered, limit_text, details, notes, page_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            variant_id,
            f.get("feature_type"),
            f.get("feature_name"),
            _bool(f.get("is_covered", True)),
            f.get("coverage_limit"),
            f.get("coverage_details"),
            f.get("notes"),
            _int(f.get("page_number")),
        ))


def insert_sublimits(cur, variant_id: str, sublimits: list):
    cur.execute("DELETE FROM variant_sublimits WHERE variant_id = %s", (variant_id,))
    for s in sublimits:
        lv = s.get("limit_value")
        cur.execute("""
            INSERT INTO variant_sublimits
                (variant_id, limit_category, item_name, limit_type, limit_inr, limit_pct,
                 applies_to, description, page_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            variant_id,
            s.get("limit_category"),
            s.get("item_name"),
            s.get("limit_type"),
            _int(lv) if s.get("limit_type") == "fixed_amount" else None,
            float(lv) if s.get("limit_type") in ("percentage",) and lv is not None else None,
            s.get("applies_to"),
            s.get("description"),
            _int(s.get("page_number")),
        ))


def insert_waiting_periods(cur, variant_id: str, wps: list):
    cur.execute("DELETE FROM variant_waiting_periods WHERE variant_id = %s", (variant_id,))
    for w in wps:
        cur.execute("""
            INSERT INTO variant_waiting_periods
                (variant_id, period_type, disease_or_procedure, duration_days,
                 can_be_reduced, reduction_conditions, page_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            variant_id,
            w.get("period_type"),
            w.get("disease_or_procedure"),
            _int(w.get("duration_days")),
            _bool(w.get("can_be_reduced")),
            w.get("reduction_conditions"),
            _int(w.get("page_number")),
        ))


def insert_exclusions(cur, variant_id: str, excls: list):
    cur.execute("DELETE FROM variant_exclusions WHERE variant_id = %s", (variant_id,))
    for e in excls:
        cur.execute("""
            INSERT INTO variant_exclusions
                (variant_id, exclusion_category, exclusion_name, description,
                 exception_conditions, page_number)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            variant_id,
            e.get("exclusion_category"),
            e.get("exclusion_name"),
            e.get("description"),
            e.get("exception_conditions"),
            _int(e.get("page_number")),
        ))


def insert_non_payable(cur, policy_id: str, np_data: dict):
    cur.execute("DELETE FROM policy_non_payable WHERE policy_id = %s", (policy_id,))
    mapping = {
        "list_1_items_not_covered":   "list_1",
        "subsumed_in_room_charges":   "subsumed_room",
        "subsumed_in_procedure_charges": "subsumed_procedure",
        "subsumed_in_treatment_costs":   "subsumed_treatment",
    }
    for key, cat in mapping.items():
        for item in np_data.get(key, []):
            cur.execute(
                "INSERT INTO policy_non_payable (policy_id, category, item_name) VALUES (%s,%s,%s)",
                (policy_id, cat, item),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Policy-specific variant builders
# Each function returns a list of (variant_name, fields_dict) tuples.
# ─────────────────────────────────────────────────────────────────────────────

def _claim_proc_fields(cp: dict) -> dict:
    cashless = cp.get("cashless", {})
    reimb    = cp.get("reimbursement", {})
    return {
        "cashless_available":         _bool(cashless.get("available", True)),
        "cashless_notice_planned":    cashless.get("planned_treatment_notice") or cashless.get("preauthorization_required") and "Required",
        "cashless_notice_emergency":  cashless.get("emergency_notice") or cashless.get("emergency_intimation_time"),
        "cashless_helpline":          cashless.get("helpline"),
        "reimbursement_available":    _bool(reimb.get("available", True)),
        "reimbursement_submit_days":  _int(
            (reimb.get("claim_submission_time") or {}).get("hospitalization", "").replace("Within ", "").replace(" days from date of discharge","")
            if isinstance(reimb.get("claim_submission_time"), dict)
            else str(reimb.get("document_submission_time","")).replace("Within ","").replace(" days","")
        ),
    }


def _policy_conditions_fields(pc: dict) -> dict:
    grace  = pc.get("grace_period", {})
    fl     = pc.get("free_look_period", {})
    renew  = pc.get("renewal", {})
    port   = pc.get("portability", {})
    cancel = pc.get("cancellation", {})

    grace_parts = []
    if grace.get("monthly_premium"):
        grace_parts.append(f"Monthly: {grace['monthly_premium']}")
    for k in ("other_modes", "quarterly_half_yearly"):
        if grace.get(k):
            grace_parts.append(f"Others: {grace[k]}")

    return {
        "free_look_days":              _int(fl.get("duration_days")),
        "grace_period_text":           "; ".join(grace_parts) or None,
        "renewal_guaranteed":          _bool(renew.get("guaranteed")),
        "portability_available":       _bool(port.get("available")),
        "cancellation_by_holder_text": cancel.get("by_policyholder"),
        "territorial_limit":           pc.get("territorial_limit"),
    }


def _premium_fields(pp: dict) -> dict:
    modes = pp.get("modes", [])
    return {
        "premium_modes_text": ", ".join(modes) if modes else None,
    }


def _discounts_fields(dl: dict) -> dict:
    if not dl:
        return {}
    parts = []
    if dl.get("family_discount"):
        fd = dl["family_discount"]
        if isinstance(fd, dict):
            parts_fd = [f"{k.replace('_',' ')}: {v}" for k,v in fd.items()]
            family_txt = "; ".join(parts_fd)
        else:
            family_txt = str(fd)
    else:
        family_txt = None

    ltd = dl.get("multi_year_discount", {})
    lt_txt = ltd.get("two_year_policy") if isinstance(ltd, dict) else str(ltd) if ltd else None

    other = []
    if dl.get("stay_active_discount"):
        other.append(f"Stay Active: up to {dl['stay_active_discount'].get('maximum_discount','')}")
    if dl.get("floater_discount"):
        fd2 = dl["floater_discount"]
        if isinstance(fd2, dict):
            other.append(f"Floater: {list(fd2.values())[0]}")

    return {
        "family_discount_text":    family_txt,
        "long_term_discount_text": lt_txt,
        "other_discounts_text":    "; ".join(other) if other else None,
    }


# ── Easy Health ───────────────────────────────────────────────────────────────

def build_easy_health_variants(data: dict) -> list:
    """Returns [(variant_name, fields), …]"""
    cov      = data.get("coverage", {})
    excl     = data.get("exclusions", {})
    ab       = data.get("additional_benefits", {})
    cp       = data.get("claim_procedures", {})
    pc       = data.get("policy_conditions", {})
    pp       = data.get("premium_payment", {})
    dl       = data.get("discounts_and_loadings", {})
    sl_list  = data.get("sub_limits", {}).get("sub_limits", [])
    wp_list  = excl.get("waiting_periods", [])
    excl_list= excl.get("exclusions", [])

    ind  = cov.get("individual_plan", {})
    mat  = cov.get("maternity_coverage", {})
    ci   = cov.get("critical_illness_optional", {})

    common_fields = {
        **_claim_proc_fields(cp),
        **_policy_conditions_fields(pc),
        **_premium_fields(pp),
        **_discounts_fields(dl),
        "inpatient_covered":     True,
        "inpatient_limit_text":  "Up to sum insured",
        "daycare_covered":       True,
        "domiciliary_covered":   True,
        "domiciliary_min_days":  3,
        "organ_donor_covered":   True,
        "ayush_covered":         True,
        "ayush_limit_text":      "Up to sum insured",
        "icu_covered":           True,
        "icu_limit_text":        "ICU bed, nursing, monitoring, intensivist charges",
        "room_rent_limit_text":  "Reasonable and customary charges (no sub-limit)",
        "room_rent_type":        "no_limit",
        "ambulance_covered":     True,
        "air_ambulance_covered": False,
        "initial_waiting_days":  30,
        "ped_waiting_months":    excl.get("pre_existing_waiting_period_months", 36),
        "specific_disease_waiting_months": excl.get("specific_disease_waiting_months", 24),
        "ped_reducible":         True,
        "has_deductible":        False,
        "has_copay":             False,
        "mental_health_covered": None,
        "opd_covered":           False,
        "moratorium_months":     _int(ab.get("moratorium_period", {}).get("duration_months")),
        "ncb_covered":           True,
        "ncb_rate_text":         ab.get("cumulative_bonus", {}).get("accrual_rate"),
        "ncb_max_text":          ab.get("cumulative_bonus", {}).get("maximum_bonus"),
        "ncb_on_claim":          "Does not reduce on claim",
        "restoration_covered":   False,
        "critical_illness_covered":    _bool(ci.get("available")),
        "critical_illness_limit_text": ci.get("sum_insured"),
        "critical_illness_waiting_days": _int(ci.get("waiting_period", "").split()[0]) if ci.get("waiting_period") else 90,
        "wellness_covered":      True,
        "wellness_details_text": "Stay Active Discount (up to 8% via step count), Preventive Health Checkup",
        "international_covered": False,
    }

    variants = []

    # Standard variant
    std = ind.get("standard_variant", {})
    si_opts = std.get("sum_insured_options", [])
    si_min, si_max = _si_range(si_opts)
    std_fields = {
        **common_fields,
        "si_min_inr":           si_min,
        "si_max_inr":           si_max,
        "si_options_text":      _si_options_text(si_opts),
        "pre_hosp_days":        _int(std.get("pre_hospitalization_days", 60)),
        "post_hosp_days":       _int(std.get("post_hospitalization_days", 90)),
        "ambulance_limit_inr":  2000,
        "maternity_covered":    False,
        "newborn_covered":      False,
        "air_ambulance_covered": False,
        "health_checkup_covered":   True,
        "health_checkup_limit_text": "1% of SI, max Rs.5,000 per person",
        "health_checkup_frequency":  "Every 4 claim-free years",
    }
    variants.append(("Standard", std_fields, std.get("coverage_features", []), sl_list, wp_list, excl_list))

    # Exclusive variant
    excl_var = ind.get("exclusive_variant", {})
    si_opts_ex = excl_var.get("sum_insured_options", [])
    si_min_ex, si_max_ex = _si_range(si_opts_ex)

    mat_ex = mat.get("exclusive_variant", {})
    mat_s35 = mat_ex.get("si_300000_to_500000", {})

    excl_fields = {
        **common_fields,
        "si_min_inr":           si_min_ex,
        "si_max_inr":           si_max_ex,
        "si_options_text":      _si_options_text(si_opts_ex),
        "pre_hosp_days":        60,
        "post_hosp_days":       90,
        "ambulance_limit_inr":  2000,
        "air_ambulance_covered": True,
        "air_ambulance_limit_text": "Rs.2.5L per hospitalisation (SI Rs.3L+)",
        "maternity_covered":    True,
        "maternity_normal_inr": _int(mat_s35.get("normal_delivery")),
        "maternity_caesar_inr": _int(mat_s35.get("caesarean_delivery")),
        "maternity_waiting_months": 72,   # 6 years (worst case)
        "maternity_max_deliveries": 2,
        "newborn_covered":      True,
        "newborn_limit_inr":    _int(mat_s35.get("newborn_limit")),
        "health_checkup_covered":   True,
        "health_checkup_limit_text": "1% of SI, max Rs.5,000 per person",
        "health_checkup_frequency":  "Every 3 years",
    }
    all_feats = excl_var.get("coverage_features", []) + std.get("coverage_features", [])
    variants.append(("Exclusive", excl_fields, all_feats, sl_list, wp_list, excl_list))

    return variants


# ── Medi Classic ──────────────────────────────────────────────────────────────

def build_medi_classic_variants(data: dict) -> list:
    cov     = data.get("coverage", {})
    excl    = data.get("exclusions", {})
    ab      = data.get("additional_benefits", {})
    cp      = data.get("claim_procedures", {})
    pc      = data.get("policy_conditions", {})
    sl_list = data.get("sub_limits", {}).get("sub_limits", [])
    wp_list = excl.get("waiting_periods", [])
    excl_list = excl.get("exclusions", [])

    si_opts = cov.get("sum_insured_options", [])
    si_min, si_max = _si_range(si_opts)

    auto_rest = ab.get("automatic_restoration", {})
    super_rest = ab.get("super_restoration", {})

    base_fields = {
        **_claim_proc_fields(cp),
        **_policy_conditions_fields(pc),
        "premium_modes_text":    None,
        "family_discount_text":  None,
        "long_term_discount_text": None,
        "other_discounts_text":  None,
        "si_min_inr":            si_min,
        "si_max_inr":            si_max,
        "si_options_text":       _si_options_text(si_opts),
        "inpatient_covered":     True,
        "inpatient_limit_text":  "Up to sum insured",
        "pre_hosp_days":         _int(cov.get("pre_hospitalization_days")),
        "post_hosp_days":        _int(cov.get("post_hospitalization_days")),
        "daycare_covered":       True,
        "domiciliary_covered":   False,
        "organ_donor_covered":   None,
        "ayush_covered":         None,
        "icu_covered":           True,
        "icu_limit_text":        cov.get("icu_coverage"),
        "room_rent_limit_text":  cov.get("room_rent_limit"),
        "room_rent_type":        "percentage_si",
        "room_rent_pct_si":      2.0,
        "room_rent_fixed_inr":   5000,
        "ambulance_covered":     True,
        "ambulance_limit_inr":   750,
        "ambulance_annual_limit_inr": 1500,
        "air_ambulance_covered": False,
        "initial_waiting_days":  30,
        "ped_waiting_months":    excl.get("pre_existing_waiting_period_months", 36),
        "specific_disease_waiting_months": excl.get("specific_disease_waiting_months", 24),
        "ped_reducible":         True,
        "has_deductible":        False,
        "has_copay":             False,
        "maternity_covered":     False,
        "newborn_covered":       False,
        "critical_illness_covered": False,
        "mental_health_covered": None,
        "opd_covered":           False,
        "moratorium_months":     _int(ab.get("moratorium_period", {}).get("duration_months")),
        "international_covered": False,
        "wellness_covered":      False,
        "health_checkup_covered": True,
        "health_checkup_limit_text": "1% of avg SI, max Rs.5,000",
        "health_checkup_frequency":  "After 4 claim-free years (SI ≥ Rs.2L)",
    }

    # Base Plan
    ncb_base = ab.get("cumulative_bonus", {}).get("base_plan", {})
    base_plan_fields = {
        **base_fields,
        "ncb_covered":       True,
        "ncb_rate_text":     ncb_base.get("accrual_rate"),
        "ncb_max_text":      ncb_base.get("maximum_bonus"),
        "ncb_on_claim":      ncb_base.get("notes"),
        "restoration_covered": _bool(auto_rest.get("available")),
        "restoration_pct":    _int(auto_rest.get("restoration_percentage")),
        "restoration_frequency_text": auto_rest.get("frequency"),
        "restoration_same_illness": False,
        "restoration_limit_text": "200% of SI, once per policy period, unrelated illness only",
    }

    # Gold Plan
    ncb_gold = ab.get("cumulative_bonus", {}).get("gold_plan", {})
    gold_plan_fields = {
        **base_fields,
        "ncb_covered":       True,
        "ncb_rate_text":     ncb_gold.get("accrual_rate"),
        "ncb_max_text":      ncb_gold.get("maximum_bonus"),
        "ncb_on_claim":      ncb_gold.get("notes"),
        "restoration_covered": _bool(super_rest.get("available")),
        "restoration_pct":    _int(super_rest.get("restoration_percentage")),
        "restoration_frequency_text": super_rest.get("frequency"),
        "restoration_same_illness": True,
        "restoration_limit_text": "100% of SI, once per policy period, same or different illness",
    }

    feats = cov.get("coverage_features", [])
    return [
        ("Base Plan",  base_plan_fields,  feats, sl_list, wp_list, excl_list),
        ("Gold Plan",  gold_plan_fields,  feats, sl_list, wp_list, excl_list),
    ]


# ── Super Surplus ─────────────────────────────────────────────────────────────

def build_super_surplus_variants(data: dict) -> list:
    cov     = data.get("coverage", {})
    excl    = data.get("exclusions", {})
    ab      = data.get("additional_benefits", {})
    cp      = data.get("claim_procedures", {})
    pc      = data.get("policy_conditions", {})
    sl_list = data.get("sub_limits", {}).get("sub_limits", [])
    wp_list = excl.get("waiting_periods", [])
    excl_list = excl.get("exclusions", [])
    diff    = data.get("key_differences_between_plans", {})

    def _plan_cov(plan_key):
        return cov.get(plan_key, {})

    silver = _plan_cov("silver_plan")
    gold   = _plan_cov("gold_plan")

    common = {
        **_claim_proc_fields(cp),
        **_policy_conditions_fields(pc),
        "premium_modes_text":    None,
        "family_discount_text":  None,
        "long_term_discount_text": None,
        "other_discounts_text":  None,
        "inpatient_covered":     True,
        "inpatient_limit_text":  "Up to sum insured (above deductible/defined limit)",
        "daycare_covered":       True,
        "organ_donor_covered":   False,
        "ayush_covered":         None,
        "icu_covered":           True,
        "mental_health_covered": None,
        "opd_covered":           False,
        "international_covered": False,
        "moratorium_months":     _int(ab.get("moratorium_period", {}).get("duration_months")),
        "critical_illness_covered": False,
        "wellness_covered":      False,
        "health_checkup_covered": False,
        "ncb_covered":           False,
    }

    # Silver
    si_silver = silver.get("sum_insured_options", [])
    si_min_s, si_max_s = _si_range(si_silver)
    silver_fields = {
        **common,
        "si_min_inr":            si_min_s,
        "si_max_inr":            si_max_s,
        "si_options_text":       _si_options_text(si_silver),
        "pre_hosp_days":         _int(silver.get("pre_hospitalization_days", 30)),
        "post_hosp_days":        _int(silver.get("post_hospitalization_days", 60)),
        "domiciliary_covered":   False,
        "room_rent_limit_text":  silver.get("room_rent_limit", "Max Rs.4,000/day"),
        "room_rent_type":        "fixed_per_day",
        "room_rent_fixed_inr":   4000,
        "ambulance_covered":     False,
        "air_ambulance_covered": False,
        "has_deductible":        True,
        "deductible_text":       "Per hospitalisation as per schedule",
        "has_copay":             False,
        "maternity_covered":     False,
        "newborn_covered":       False,
        "initial_waiting_days":  30,
        "ped_waiting_months":    36,
        "specific_disease_waiting_months": 24,
        "ped_reducible":         True,
        "restoration_covered":   False,
    }

    # Gold
    si_gold = gold.get("sum_insured_options", [])
    si_min_g, si_max_g = _si_range(si_gold)
    recharge = ab.get("recharge_benefit", {})
    wellness = ab.get("wellness_services", {})

    gold_fields = {
        **common,
        "si_min_inr":            si_min_g,
        "si_max_inr":            si_max_g,
        "si_options_text":       _si_options_text(si_gold),
        "pre_hosp_days":         _int(gold.get("pre_hospitalization_days", 60)),
        "post_hosp_days":        _int(gold.get("post_hospitalization_days", 90)),
        "domiciliary_covered":   True,
        "room_rent_limit_text":  "Single Private A/C Room",
        "room_rent_type":        "room_category",
        "room_rent_category":    "Single Private A/C Room",
        "ambulance_covered":     True,
        "ambulance_annual_limit_inr": 3000,
        "air_ambulance_covered": True,
        "air_ambulance_limit_text": "10% of SI (for SI Rs.7L+)",
        "has_deductible":        False,
        "deductible_text":       "Has 'Defined Limit' (threshold before coverage begins)",
        "has_copay":             False,
        "maternity_covered":     True,
        "maternity_normal_inr":  None,
        "maternity_caesar_inr":  None,
        "maternity_waiting_months": None,
        "maternity_max_deliveries": 2,
        "maternity_normal_inr":  50000,   # per sub_limits: Rs.50,000 per policy period
        "newborn_covered":       False,
        "initial_waiting_days":  30,
        "ped_waiting_months":    12,
        "specific_disease_waiting_months": 12,
        "ped_reducible":         True,
        "restoration_covered":   _bool(recharge.get("available")),
        "restoration_frequency_text": recharge.get("conditions", "").split(".")[0] if recharge else None,
        "restoration_same_illness": True,
        "restoration_limit_text": "Rs.50K–Rs.2.5L based on defined limit tier",
        "wellness_covered":      _bool(wellness.get("available")),
        "wellness_details_text": "Online doctor chat, medical concierge, health vault, post-op care, network discounts",
    }

    silver_feats = silver.get("coverage_features", [])
    gold_feats   = gold.get("coverage_features", [])

    return [
        ("Silver Plan", silver_fields, silver_feats, sl_list, wp_list, excl_list),
        ("Gold Plan",   gold_fields,   gold_feats,   sl_list, wp_list, excl_list),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Router — picks the right builder based on policy name
# ─────────────────────────────────────────────────────────────────────────────

BUILDERS = {
    "easy health":              build_easy_health_variants,
    "medi classic":             build_medi_classic_variants,
    "super surplus":            build_super_surplus_variants,
}

def _get_builder(policy_name: str):
    name_lower = policy_name.lower()
    for key, fn in BUILDERS.items():
        if key in name_lower:
            return fn
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main populate function
# ─────────────────────────────────────────────────────────────────────────────

def populate_from_json(filepath: str, conn):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    policy_name = data.get("basic_info", {}).get("policy_name", "Unknown")
    print(f"\n[HealIN] Processing: {policy_name}  ({filepath})")

    builder = _get_builder(policy_name)
    if builder is None:
        # Generic fallback: single variant named "Base"
        print(f"  ⚠  No specific builder found for '{policy_name}'. Using generic single-variant builder.")
        builder = lambda d: [("Base", {
            **_claim_proc_fields(d.get("claim_procedures", {})),
            **_policy_conditions_fields(d.get("policy_conditions", {})),
            **_premium_fields(d.get("premium_payment", {})),
            **_discounts_fields(d.get("discounts_and_loadings", {})),
        }, d.get("coverage", {}).get("coverage_features", []),
           d.get("sub_limits", {}).get("sub_limits", []),
           d.get("exclusions", {}).get("waiting_periods", []),
           d.get("exclusions", {}).get("exclusions", []))]

    variants = builder(data)

    with conn:
        cur = conn.cursor()
        insurer_id = upsert_insurer(cur, data)
        policy_id  = upsert_policy(cur, insurer_id, data)

        # Non-payable items (policy-level)
        np_data = data.get("non_payable_items", {})
        if np_data:
            insert_non_payable(cur, policy_id, np_data)

        for entry in variants:
            variant_name, fields, feats, sl, wps, excls = entry
            print(f"  → Variant: {variant_name}")
            variant_id = upsert_variant(cur, policy_id, variant_name, fields)
            insert_features(cur, variant_id, feats)
            insert_sublimits(cur, variant_id, sl)
            insert_waiting_periods(cur, variant_id, wps)
            insert_exclusions(cur, variant_id, excls)

    print(f"  ✔  Done: {policy_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python populate_v2.py <file.json> [file2.json …] OR <directory/>")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            paths.extend(p.glob("*.json"))
        elif p.exists():
            paths.append(p)
        else:
            print(f"[WARN] Not found: {arg}")

    if not paths:
        print("No JSON files found.")
        sys.exit(1)

    conn = get_conn()
    try:
        for fp in paths:
            try:
                populate_from_json(str(fp), conn)
            except Exception as e:
                print(f"  ✗  Error processing {fp}: {e}")
                import traceback; traceback.print_exc()
    finally:
        conn.close()

    print("\n[HealIN] Population complete.")
