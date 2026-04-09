from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import (
    ALLOW_ORIGINS,
    DATABASE_URL,
    DOCUMENTS_PATH,
    HOSPITALS_PATH,
    READ_SOURCE,
    REFRESH_LOGS_PATH,
    UPLOAD_DIR,
)
from .db import get_conn, serialize_row
from .json_catalog import get_variant as get_json_variant
from .json_catalog import load_variants as load_json_variants
from .json_catalog import page_variants as page_json_variants
from .store import ensure_json_file, read_json, write_json


app = FastAPI(title="HealIN API", version="1.0.0")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://69d7bd30ba9af1d169894112--magenta-nougat-e21cb8.netlify.app/"],  # ← your Netlify URL
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_VARIANT_SELECT = """
SELECT
    v.*,
    p.policy_name,
    p.policy_code,
    p.version,
    p.effective_date,
    p.policy_type,
    p.document_type,
    p.source_file,
    p.extraction_date,
    p.page_count,
    i.insurer_id,
    i.insurer_name,
    i.irdai_reg,
    i.cin,
    i.helpline,
    i.website,
    i.grievance_email
FROM policy_variants v
JOIN policies p ON p.policy_id = v.policy_id
JOIN insurers i ON i.insurer_id = p.insurer_id
"""

COMPARE_FIELDS = [
    "policy_type",
    "si_min_inr",
    "si_max_inr",
    "si_options_text",
    "inpatient_limit_text",
    "pre_hosp_days",
    "post_hosp_days",
    "daycare_covered",
    "domiciliary_covered",
    "domiciliary_min_days",
    "organ_donor_covered",
    "ayush_covered",
    "ayush_limit_text",
    "room_rent_limit_text",
    "room_rent_type",
    "room_rent_pct_si",
    "room_rent_fixed_inr",
    "room_rent_category",
    "icu_limit_text",
    "ambulance_covered",
    "ambulance_limit_inr",
    "ambulance_annual_limit_inr",
    "air_ambulance_covered",
    "air_ambulance_limit_text",
    "initial_waiting_days",
    "ped_waiting_months",
    "specific_disease_waiting_months",
    "ped_reducible",
    "has_deductible",
    "deductible_text",
    "has_copay",
    "copay_text",
    "maternity_covered",
    "maternity_normal_inr",
    "maternity_caesar_inr",
    "maternity_waiting_months",
    "newborn_covered",
    "critical_illness_covered",
    "critical_illness_limit_text",
    "mental_health_covered",
    "opd_covered",
    "restoration_covered",
    "restoration_pct",
    "restoration_frequency_text",
    "restoration_same_illness",
    "ncb_covered",
    "ncb_rate_text",
    "ncb_max_text",
    "health_checkup_covered",
    "wellness_covered",
    "international_covered",
    "moratorium_months",
    "cashless_available",
    "cashless_notice_planned",
    "cashless_notice_emergency",
    "cashless_helpline",
    "reimbursement_available",
    "reimbursement_submit_days",
    "free_look_days",
    "grace_period_text",
    "renewal_guaranteed",
    "portability_available",
    "territorial_limit",
    "premium_modes_text",
    "family_discount_text",
    "long_term_discount_text",
    "other_discounts_text",
]

VARIANT_MUTABLE_FIELDS = [
    field for field in COMPARE_FIELDS if field not in {"policy_type"}
] + [
    "policy_id",
    "variant_name",
    "icu_covered",
    "maternity_max_deliveries",
    "newborn_limit_inr",
    "critical_illness_waiting_days",
    "opd_limit_text",
    "restoration_limit_text",
    "ncb_on_claim",
    "health_checkup_limit_text",
    "health_checkup_frequency",
    "wellness_details_text",
    "international_details_text",
    "cancellation_by_holder_text",
    "claim_settlement_days",
]


def startup_storage():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ensure_json_file(DOCUMENTS_PATH, [])
    ensure_json_file(HOSPITALS_PATH, [])
    ensure_json_file(REFRESH_LOGS_PATH, [])


@app.on_event("startup")
def _startup():
    startup_storage()


def http_not_found(message):
    raise HTTPException(status_code=404, detail=message)


def normalize_compare_value(value):
    if value in ("", None):
        return None
    if isinstance(value, float):
        return round(value, 4)
    return value


def normalize_policy_type(value):
    return " ".join(
        str(value or "")
        .lower()
        .replace("/", " ")
        .replace("+", " ")
        .replace("-", " ")
        .split()
    )


def read_source_prefers_json():
    return READ_SOURCE in {"auto", "json", "json_first", "json-only", "json_only"}


def read_source_requires_json():
    return READ_SOURCE in {"json", "json-only", "json_only"}


def build_variant_filters(q=None, policy_type=None, insurer=None, si_min=None, si_max=None):
    clauses = []
    params = []

    if q:
        like = f"%{q.lower()}%"
        clauses.append(
            "(lower(p.policy_name) LIKE %s OR lower(v.variant_name) LIKE %s OR lower(i.insurer_name) LIKE %s)"
        )
        params.extend([like, like, like])

    if policy_type:
        clauses.append(
            "replace(replace(replace(lower(p.policy_type), '/', ' '), '+', ' '), '-', ' ') LIKE %s"
        )
        params.append(f"%{normalize_policy_type(policy_type)}%")

    if insurer:
        clauses.append("lower(i.insurer_name) LIKE %s")
        params.append(f"%{insurer.lower()}%")

    if si_min is not None:
        clauses.append("(v.si_max_inr IS NULL OR v.si_max_inr >= %s)")
        params.append(si_min)

    if si_max is not None:
        clauses.append("(v.si_min_inr IS NULL OR v.si_min_inr <= %s)")
        params.append(si_max)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_clause, params


def fetch_variant_children(cur, variant_id):
    cur.execute(
        """
        SELECT feature_type, feature_name, is_covered, limit_text, details, notes, page_number
        FROM variant_features
        WHERE variant_id = %s
        ORDER BY feature_type, feature_name
        """,
        (variant_id,),
    )
    features = [serialize_row(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT exclusion_name, exclusion_category, description, exception_conditions, page_number
        FROM variant_exclusions
        WHERE variant_id = %s
        ORDER BY exclusion_category, exclusion_name
        """,
        (variant_id,),
    )
    exclusions = [serialize_row(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT period_type, disease_or_procedure, duration_days, can_be_reduced, reduction_conditions, page_number
        FROM variant_waiting_periods
        WHERE variant_id = %s
        ORDER BY period_type, disease_or_procedure NULLS FIRST
        """,
        (variant_id,),
    )
    waiting_periods = [serialize_row(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT limit_category, item_name, limit_type, limit_inr, limit_pct, applies_to, description, page_number
        FROM variant_sublimits
        WHERE variant_id = %s
        ORDER BY limit_category, item_name
        """,
        (variant_id,),
    )
    sublimits = [serialize_row(row) for row in cur.fetchall()]

    return features, exclusions, waiting_periods, sublimits


def fetch_variant_detail(variant_id, include_children=True):
    if read_source_prefers_json():
        variant = get_json_variant(variant_id)
        if variant or read_source_requires_json():
            return variant

    db_error = None

    try:
        with get_conn(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"{BASE_VARIANT_SELECT} WHERE v.variant_id = %s", (variant_id,))
                row = cur.fetchone()
                if row:
                    variant = serialize_row(row)
                    if include_children:
                        features, exclusions, waiting_periods, sublimits = fetch_variant_children(cur, variant_id)
                        variant["features"] = features
                        variant["exclusions"] = exclusions
                        variant["waiting_periods"] = waiting_periods
                        variant["sublimits"] = sublimits
                    return variant
    except Exception as exc:
        db_error = exc

    variant = get_json_variant(variant_id)
    if variant:
        return variant

    if db_error:
        raise db_error

    return None


def fetch_variants_page(q=None, policy_type=None, insurer=None, si_min=None, si_max=None, page=1, page_size=20):
    if read_source_prefers_json():
        json_result = page_json_variants(q, policy_type, insurer, si_min, si_max, page, page_size)
        if json_result["total"] or read_source_requires_json():
            return json_result

    where_clause, params = build_variant_filters(q, policy_type, insurer, si_min, si_max)
    offset = max(page - 1, 0) * page_size

    db_error = None

    try:
        with get_conn(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM policy_variants v
                    JOIN policies p ON p.policy_id = v.policy_id
                    JOIN insurers i ON i.insurer_id = p.insurer_id
                    {where_clause}
                    """,
                    params,
                )
                total = int(cur.fetchone()["total"])

                cur.execute(
                    f"""
                    {BASE_VARIANT_SELECT}
                    {where_clause}
                    ORDER BY i.insurer_name, p.policy_name, v.variant_name
                    LIMIT %s OFFSET %s
                    """,
                    (*params, page_size, offset),
                )
                items = [serialize_row(row) for row in cur.fetchall()]

        if items or total == 0:
            json_result = page_json_variants(q, policy_type, insurer, si_min, si_max, page, page_size)
            return json_result if json_result["total"] and not items else {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
    except Exception as exc:
        db_error = exc

    json_result = page_json_variants(q, policy_type, insurer, si_min, si_max, page, page_size)
    if json_result["total"] or db_error is None:
        return json_result

    raise db_error


def fetch_all_variants():
    if read_source_prefers_json():
        rows = load_json_variants()
        if rows or read_source_requires_json():
            return rows

    db_error = None

    try:
        with get_conn(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    {BASE_VARIANT_SELECT}
                    ORDER BY i.insurer_name, p.policy_name, v.variant_name
                    """
                )
                rows = [serialize_row(row) for row in cur.fetchall()]
        if rows:
            return rows
    except Exception as exc:
        db_error = exc

    rows = load_json_variants()
    if rows or db_error is None:
        return rows

    raise db_error


def compute_diff_fields(variant_a, variant_b):
    return [
        field
        for field in COMPARE_FIELDS
        if normalize_compare_value(variant_a.get(field))
        != normalize_compare_value(variant_b.get(field))
    ]


def format_inr(value):
    if value in (None, ""):
        return None
    number = int(value)
    if number >= 1_000_000:
        return f"Rs {number // 100000}L"
    if number >= 100_000:
        whole = number / 100000
        text = f"{whole:.1f}".replace(".0", "")
        return f"Rs {text}L"
    if number >= 1000:
        return f"Rs {number // 1000}K"
    return f"Rs {number}"


def format_room_rent(variant):
    if variant.get("room_rent_type") == "no_limit":
        return "No room-rent sub-limit"
    if variant.get("room_rent_type") == "fixed_per_day" and variant.get("room_rent_fixed_inr"):
        return f"{format_inr(variant['room_rent_fixed_inr'])}/day"
    if variant.get("room_rent_type") == "percentage_si" and variant.get("room_rent_pct_si") is not None:
        return f"{variant['room_rent_pct_si']}% of SI/day"
    if variant.get("room_rent_type") == "room_category" and variant.get("room_rent_category"):
        return variant["room_rent_category"]
    return variant.get("room_rent_limit_text") or "Not stated"


def score_variant(variant, preferences):
    score = 30
    reasons = []
    needs = {need.lower() for need in preferences.get("key_needs", [])}

    si_required = preferences.get("si_required")
    if si_required:
        try:
            si_required = int(si_required)
        except (TypeError, ValueError):
            si_required = None

    if si_required and variant.get("si_max_inr") and variant["si_max_inr"] >= si_required:
        score += 18
        reasons.append(f"supports sum insured up to {format_inr(variant['si_max_inr'])}")

    if preferences.get("family_size", 1) > 1 and "family" in (variant.get("policy_type") or "").lower():
        score += 10
        reasons.append("suited to family coverage")

    if variant.get("ped_waiting_months") is not None:
        ped_wait = int(variant["ped_waiting_months"])
        if ped_wait <= 24:
            score += 10
        elif ped_wait <= 36:
            score += 6

    if "maternity" in needs and variant.get("maternity_covered"):
        score += 15
        reasons.append("covers maternity")
    if "critical illness" in needs and variant.get("critical_illness_covered"):
        score += 10
        reasons.append("includes critical illness support")
    if "mental health" in needs and variant.get("mental_health_covered"):
        score += 8
        reasons.append("covers mental health")
    if "opd" in needs and variant.get("opd_covered"):
        score += 8
        reasons.append("includes OPD cover")
    if "no co-pay" in needs and not variant.get("has_copay"):
        score += 12
        reasons.append("does not have co-pay")
    if "no sub-limits" in needs and variant.get("room_rent_type") == "no_limit":
        score += 12
        reasons.append("does not impose room-rent sub-limits")
    if "cashless only" in needs and variant.get("cashless_available"):
        score += 8
        reasons.append("supports cashless claims")
    if "family floater" in needs and "family" in (variant.get("policy_type") or "").lower():
        score += 8
        reasons.append("is available as a family floater")
    if "senior citizen" in needs and variant.get("renewal_guaranteed"):
        score += 6
        reasons.append("offers guaranteed renewal")

    if variant.get("restoration_covered"):
        score += 4
    if variant.get("cashless_available"):
        score += 4

    score = max(0, min(score, 100))
    if not reasons:
        reasons.append("matches core hospitalization cover requirements")

    rationale = (
        f"{variant['policy_name']} {variant['variant_name']} scores {score}/100 because it "
        + ", ".join(reasons[:4])
        + "."
    )
    return {
        "variant_id": variant["variant_id"],
        "score": score,
        "rationale": rationale,
        "variant": variant,
    }


def tokenise(text):
    words = text.split()
    if not words:
        return []
    return [words[0], *[f" {word}" for word in words[1:]]]


CHAT_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "benefit",
    "between",
    "claim",
    "claims",
    "cover",
    "coverage",
    "covered",
    "does",
    "from",
    "have",
    "into",
    "more",
    "plan",
    "policy",
    "tell",
    "than",
    "that",
    "this",
    "what",
    "which",
    "with",
    "wish",
    "would",
    "your",
}


def compact_text(value):
    return " ".join(str(value or "").split()).strip()


def query_terms(text):
    return [
        term
        for term in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(term) >= 3 and term not in CHAT_STOPWORDS
    ]


def extend_citations(citations, items, limit=5):
    merged = list(citations)
    seen = {
        (item.get("section"), item.get("page"), item.get("text"))
        for item in merged
    }

    for item in items:
        key = (item.get("section"), item.get("page"), item.get("text"))
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        if len(merged) >= limit:
            break

    return merged[:limit]


def variant_evidence_chunks(variant):
    chunks = []

    def add_chunk(section, text, page=None):
        body = compact_text(text)
        if not body:
            return
        chunks.append(
            {
                "section": compact_text(section) or "Policy clause",
                "text": body,
                "page": page,
            }
        )

    waits = []
    if variant.get("initial_waiting_days"):
        waits.append(f"Initial waiting period is {variant['initial_waiting_days']} days.")
    if variant.get("ped_waiting_months"):
        waits.append(f"Pre-existing disease waiting period is {variant['ped_waiting_months']} months.")
    if variant.get("specific_disease_waiting_months"):
        waits.append(
            f"Specific disease waiting period is {variant['specific_disease_waiting_months']} months."
        )
    if waits:
        page = next(
            (
                item.get("page_number")
                for item in variant.get("waiting_periods", [])
                if item.get("page_number")
            ),
            None,
        )
        add_chunk("Waiting periods", " ".join(waits), page)

    add_chunk("Room rent", format_room_rent(variant))

    if variant.get("maternity_covered") or variant.get("newborn_covered"):
        maternity = []
        if variant.get("maternity_covered"):
            maternity.append("Maternity is covered.")
        if variant.get("maternity_normal_inr"):
            maternity.append(f"Normal delivery limit is {format_inr(variant['maternity_normal_inr'])}.")
        if variant.get("maternity_caesar_inr"):
            maternity.append(f"C-section limit is {format_inr(variant['maternity_caesar_inr'])}.")
        if variant.get("maternity_waiting_months"):
            maternity.append(f"Maternity waiting period is {variant['maternity_waiting_months']} months.")
        if variant.get("newborn_covered"):
            maternity.append("Newborn cover is included.")
        add_chunk("Maternity", " ".join(maternity))

    claims = []
    if variant.get("cashless_available") is not None:
        claims.append(
            "Cashless claims are available."
            if variant.get("cashless_available")
            else "Cashless claims are not listed."
        )
    if variant.get("cashless_notice_planned"):
        claims.append(f"Planned admission notice is {variant['cashless_notice_planned']}.")
    if variant.get("cashless_notice_emergency"):
        claims.append(f"Emergency notice is {variant['cashless_notice_emergency']}.")
    if variant.get("reimbursement_submit_days"):
        claims.append(
            f"Reimbursement documents are usually submitted within {variant['reimbursement_submit_days']} days."
        )
    if claims:
        add_chunk("Claims", " ".join(claims))

    benefits = []
    if variant.get("restoration_covered"):
        benefits.append("Restoration benefit is available.")
    if variant.get("critical_illness_covered"):
        benefits.append("Critical illness cover is included.")
    if variant.get("mental_health_covered"):
        benefits.append("Mental health cover is included.")
    if variant.get("opd_covered"):
        benefits.append("OPD cover is included.")
    if variant.get("wellness_covered"):
        benefits.append("Wellness benefits are available.")
    if variant.get("ncb_covered"):
        benefits.append("No-claim bonus is available.")
    if benefits:
        add_chunk("Benefits", " ".join(benefits))

    for item in variant.get("features", []):
        add_chunk(
            item.get("feature_name") or item.get("feature_type") or "Feature",
            " ".join(
                part
                for part in [
                    "Covered." if item.get("is_covered") else "Not covered.",
                    compact_text(item.get("limit_text") or item.get("coverage_limit")),
                    compact_text(item.get("details") or item.get("coverage_details")),
                    compact_text(item.get("notes")),
                ]
                if part
            ),
            item.get("page_number"),
        )

    for item in variant.get("waiting_periods", []):
        add_chunk(
            item.get("period_type") or "Waiting period",
            " ".join(
                part
                for part in [
                    compact_text(item.get("disease_or_procedure")),
                    (
                        f"Duration is {item['duration_days']} days."
                        if item.get("duration_days") is not None
                        else ""
                    ),
                    compact_text(item.get("reduction_conditions")),
                ]
                if part
            ),
            item.get("page_number"),
        )

    for item in variant.get("sublimits", []):
        limit_bits = [
            compact_text(item.get("description")),
            compact_text(item.get("limit_type")),
            compact_text(item.get("applies_to")),
        ]
        if item.get("limit_inr"):
            limit_bits.append(f"Limit is {format_inr(item['limit_inr'])}.")
        if item.get("limit_pct") is not None:
            limit_bits.append(f"Limit is {item['limit_pct']}%.")
        add_chunk(
            item.get("item_name") or item.get("limit_category") or "Sub-limit",
            " ".join(part for part in limit_bits if part),
            item.get("page_number"),
        )

    for item in variant.get("exclusions", []):
        add_chunk(
            item.get("exclusion_name") or "Exclusion",
            " ".join(
                part
                for part in [
                    compact_text(item.get("description")),
                    compact_text(item.get("exception_conditions")),
                ]
                if part
            ),
            item.get("page_number"),
        )

    return chunks


def retrieve_variant_evidence(variant, message, limit=3):
    chunks = variant_evidence_chunks(variant)
    terms = query_terms(message)
    if not chunks:
        return []
    if not terms:
        return chunks[:limit]

    ranked = []
    for index, chunk in enumerate(chunks):
        section = chunk["section"].lower()
        haystack = f"{section} {chunk['text'].lower()}"
        score = 0
        for term in terms:
            if term in section:
                score += 4
            elif term in haystack:
                score += 2
        if score:
            ranked.append((score, index, chunk))

    if not ranked:
        return []

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _, _, chunk in ranked[:limit]]


def chunk_to_citation(chunk):
    return {
        "section": chunk.get("section"),
        "page": chunk.get("page"),
        "text": chunk.get("text"),
    }


def evidence_answer(evidence):
    snippets = []
    for item in evidence[:3]:
        text = item["text"]
        if len(text) > 180:
            text = text[:177].rstrip() + "..."
        snippets.append(f"{item['section']}: {text}")
    return "Relevant clauses I found: " + "; ".join(snippets) + "."


def build_variant_chat_answer(message, variant):
    lower = message.lower()
    answer_parts = []
    citations = []
    evidence = retrieve_variant_evidence(variant, message, limit=4)

    if any(term in lower for term in ["wait", "ped", "pre-existing", "pre existing"]):
        waits = []
        if variant.get("initial_waiting_days"):
            waits.append(f"initial waiting is {variant['initial_waiting_days']} days")
        if variant.get("ped_waiting_months"):
            waits.append(f"PED waiting is {variant['ped_waiting_months']} months")
        if variant.get("specific_disease_waiting_months"):
            waits.append(
                f"specific disease waiting is {variant['specific_disease_waiting_months']} months"
            )
        if waits:
            answer_parts.append("Waiting periods: " + "; ".join(waits) + ".")

        citations = extend_citations(
            citations,
            [
                {
                    "section": item.get("period_type", "Waiting period"),
                    "page": item.get("page_number"),
                    "text": item.get("disease_or_procedure") or item.get("reduction_conditions") or "",
                }
                for item in variant.get("waiting_periods", [])[:3]
            ],
        )

    if any(term in lower for term in ["room", "rent", "icu"]):
        answer_parts.append(f"Room rent: {format_room_rent(variant)}.")

    if any(term in lower for term in ["maternity", "newborn", "pregnan"]):
        if variant.get("maternity_covered"):
            maternity_parts = []
            if variant.get("maternity_normal_inr"):
                maternity_parts.append(f"normal delivery up to {format_inr(variant['maternity_normal_inr'])}")
            if variant.get("maternity_caesar_inr"):
                maternity_parts.append(f"C-section up to {format_inr(variant['maternity_caesar_inr'])}")
            if variant.get("maternity_waiting_months"):
                maternity_parts.append(
                    f"waiting period {variant['maternity_waiting_months']} months"
                )
            if variant.get("newborn_covered"):
                maternity_parts.append("newborn cover is included")
            answer_parts.append("Maternity benefit: " + ", ".join(maternity_parts) + ".")
        else:
            answer_parts.append("Maternity is not covered in this variant.")

    if any(term in lower for term in ["co-pay", "copay", "co pay", "deductible"]):
        copay = "has co-pay" if variant.get("has_copay") else "does not have co-pay"
        deductible = (
            f"has deductible ({variant['deductible_text']})"
            if variant.get("has_deductible") and variant.get("deductible_text")
            else "does not have a deductible"
            if not variant.get("has_deductible")
            else "has a deductible"
        )
        answer_parts.append(f"Cost sharing: this plan {copay} and {deductible}.")

    if any(term in lower for term in ["cashless", "claim", "reimburse", "reimbursement"]):
        answer_parts.append(
            "Claims: "
            + (
                "cashless is available"
                if variant.get("cashless_available")
                else "cashless is not listed"
            )
            + (
                f"; planned admission notice is {variant['cashless_notice_planned']}"
                if variant.get("cashless_notice_planned")
                else ""
            )
            + (
                f"; emergency notice is {variant['cashless_notice_emergency']}"
                if variant.get("cashless_notice_emergency")
                else ""
            )
            + (
                f"; reimbursement documents are usually submitted within {variant['reimbursement_submit_days']} days"
                if variant.get("reimbursement_submit_days")
                else ""
            )
            + "."
        )

    if any(term in lower for term in ["exclude", "exclusion", "not cover", "not covered"]):
        matched = []
        query_terms = [part for part in lower.replace("-", " ").split() if len(part) >= 4]
        for item in variant.get("exclusions", []):
            haystack = " ".join(
                str(item.get(key, "")).lower()
                for key in ("exclusion_name", "description", "exception_conditions")
            )
            if not query_terms or any(term in haystack for term in query_terms):
                matched.append(item)
        if not matched:
            matched = variant.get("exclusions", [])[:3]

        if matched:
            names = ", ".join(item["exclusion_name"] for item in matched[:3])
            answer_parts.append(f"Relevant exclusions listed in the document include: {names}.")
            citations = extend_citations(
                citations,
                [
                    {
                        "section": item.get("exclusion_name"),
                        "page": item.get("page_number"),
                        "text": item.get("description") or "",
                    }
                    for item in matched[:3]
                ],
            )

    if any(term in lower for term in ["sublimit", "sub-limit", "limit", "cap"]):
        matched = variant.get("sublimits", [])[:3]
        if matched:
            summary = ", ".join(
                f"{item['item_name']} ({item.get('description') or item.get('limit_category')})"
                for item in matched
            )
            answer_parts.append(f"Notable sub-limits: {summary}.")
            citations = extend_citations(
                citations,
                [
                    {
                        "section": item.get("item_name"),
                        "page": item.get("page_number"),
                        "text": item.get("description") or "",
                    }
                    for item in matched
                ],
            )

    if not answer_parts and evidence:
        answer_parts.append(evidence_answer(evidence))

    if not answer_parts:
        answer_parts.append(
            f"{variant['policy_name']} {variant['variant_name']} by {variant['insurer_name']} "
            f"offers sum insured from {format_inr(variant.get('si_min_inr')) or 'not stated'} to "
            f"{format_inr(variant.get('si_max_inr')) or 'not stated'}, PED waiting of "
            f"{variant.get('ped_waiting_months') or 'not stated'} months, room rent of {format_room_rent(variant)}, "
            f"and {'cashless claims' if variant.get('cashless_available') else 'no listed cashless benefit'}."
        )

    citations = extend_citations(citations, [chunk_to_citation(item) for item in evidence])

    return {
        "answer": " ".join(answer_parts).strip(),
        "citations": citations[:5],
        "caveat": "Coverage is subject to the full policy wording, eligibility, and claim conditions.",
    }


def build_comparison_chat_answer(message, variant_a, variant_b):
    lower = message.lower()
    diff_fields = compute_diff_fields(variant_a, variant_b)
    lines = [
        f"I compared {variant_a['policy_name']} ({variant_a['variant_name']}) with {variant_b['policy_name']} ({variant_b['variant_name']})."
    ]

    if any(term in lower for term in ["wait", "ped", "pre-existing", "pre existing"]):
        lines.append(
            f"PED waiting is {variant_a.get('ped_waiting_months') or 'not stated'} months vs {variant_b.get('ped_waiting_months') or 'not stated'} months."
        )

    if any(term in lower for term in ["room", "rent", "icu"]):
        lines.append(
            f"Room rent is {format_room_rent(variant_a)} vs {format_room_rent(variant_b)}."
        )

    if any(term in lower for term in ["maternity", "newborn"]):
        lines.append(
            f"Maternity is {'covered' if variant_a.get('maternity_covered') else 'not covered'} in the first plan and "
            f"{'covered' if variant_b.get('maternity_covered') else 'not covered'} in the second."
        )

    if any(term in lower for term in ["copay", "co-pay", "co pay"]):
        lines.append(
            f"Co-pay is {'present' if variant_a.get('has_copay') else 'absent'} vs "
            f"{'present' if variant_b.get('has_copay') else 'absent'}."
        )

    if len(lines) == 1:
        lines.append(
            f"There are {len(diff_fields)} differing comparison fields. Major differences include PED waiting, room rent, maternity, co-pay, restoration, and claim process where applicable."
        )

    return {
        "answer": " ".join(lines),
        "citations": [],
        "caveat": "Compare the exact clauses in the policy wording before purchase or claim submission.",
    }


def build_document_chat_answer(document):
    return {
        "answer": (
            f"{document['filename']} is stored successfully, but the upload-to-extraction pipeline in this repo "
            "is not wired to OCR and clause indexing yet. The frontend integration is ready; the remaining step is "
            "connecting your document parser to save extracted facts and chunks for uploaded files."
        ),
        "citations": [],
        "caveat": "Uploaded document chat is currently storage-only unless you connect the extraction pipeline.",
    }


def build_general_chat_answer():
    suggestions = []
    for item in load_json_variants()[:4]:
        suggestions.append(f"{item['policy_name']} ({item['variant_name']})")

    suggestion_text = (
        " Available policies in the sample data include "
        + ", ".join(suggestions)
        + "."
        if suggestions
        else ""
    )

    return {
        "answer": (
            "Choose a specific policy first for grounded answers." + suggestion_text + " "
            "The live assistant is strongest when it is scoped to one policy or one comparison, especially for waiting periods, room rent, maternity, exclusions, co-pay, and claim timelines."
        ),
        "citations": [],
        "caveat": "General chat is not full RAG yet. Policy-scoped chat is more reliable because it can retrieve clause evidence from the selected policy data.",
    }


def build_chat_payload(message, context_type, context_id):
    if context_type == "variant" and context_id:
        variant = fetch_variant_detail(context_id, include_children=True)
        if not variant:
            http_not_found("Variant not found")
        return build_variant_chat_answer(message, variant)

    if context_type == "comparison" and context_id:
        try:
            variant_id_a, variant_id_b = context_id.split("__", 1)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid comparison context") from exc

        variant_a = fetch_variant_detail(variant_id_a, include_children=True)
        variant_b = fetch_variant_detail(variant_id_b, include_children=True)
        if not variant_a or not variant_b:
            http_not_found("Comparison variants not found")
        return build_comparison_chat_answer(message, variant_a, variant_b)

    if context_type == "document" and context_id:
        documents = read_json(DOCUMENTS_PATH, [])
        document = next((item for item in documents if item["doc_id"] == context_id), None)
        if not document:
            http_not_found("Document not found")
        return build_document_chat_answer(document)

    return build_general_chat_answer()


def paginated(items, page, page_size):
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return items[start:end]


def log_refresh(source_id, status="queued"):
    logs = read_json(REFRESH_LOGS_PATH, [])
    entry = {
        "id": str(uuid4()),
        "source_id": source_id,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "Refresh requested. Execute the pipeline scripts manually to populate data.",
    }
    logs.insert(0, entry)
    write_json(REFRESH_LOGS_PATH, logs)
    return entry


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/variants")
def get_variants(
    q: Optional[str] = None,
    policy_type: Optional[str] = None,
    insurer: Optional[str] = None,
    si_min: Optional[int] = None,
    si_max: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return fetch_variants_page(q, policy_type, insurer, si_min, si_max, page, page_size)


@app.get("/api/variants/{variant_id}")
def get_variant(variant_id: str):
    variant = fetch_variant_detail(variant_id, include_children=True)
    if not variant:
        http_not_found("Variant not found")
    return variant


@app.get("/api/variants/{variant_id}/exclusions")
def get_variant_exclusions(variant_id: str):
    variant = fetch_variant_detail(variant_id, include_children=True)
    if not variant:
        http_not_found("Variant not found")
    return variant["exclusions"]


@app.get("/api/variants/{variant_id}/waiting-periods")
def get_variant_waiting_periods(variant_id: str):
    variant = fetch_variant_detail(variant_id, include_children=True)
    if not variant:
        http_not_found("Variant not found")
    return variant["waiting_periods"]


@app.get("/api/variants/{variant_id}/sublimits")
def get_variant_sublimits(variant_id: str):
    variant = fetch_variant_detail(variant_id, include_children=True)
    if not variant:
        http_not_found("Variant not found")
    return variant["sublimits"]


@app.post("/api/compare")
def compare_variants(payload: dict):
    variant_id_a = payload.get("variant_id_a")
    variant_id_b = payload.get("variant_id_b")
    if not variant_id_a or not variant_id_b:
        raise HTTPException(status_code=400, detail="Both variant IDs are required")

    variant_a = fetch_variant_detail(variant_id_a, include_children=True)
    variant_b = fetch_variant_detail(variant_id_b, include_children=True)
    if not variant_a or not variant_b:
        http_not_found("One or both variants were not found")

    return {
        "variant_a": variant_a,
        "variant_b": variant_b,
        "diff_fields": compute_diff_fields(variant_a, variant_b),
        "exclusions_a": variant_a.get("exclusions", []),
        "exclusions_b": variant_b.get("exclusions", []),
    }


@app.post("/api/match")
def match_variants(payload: dict):
    variants = fetch_all_variants()
    results = [score_variant(variant, payload or {}) for variant in variants]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:20]


@app.get("/api/hospitals")
def get_hospitals(
    city: Optional[str] = None,
    pincode: Optional[str] = None,
    insurer: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    items = read_json(HOSPITALS_PATH, [])

    def _matches(item):
        if city and city.lower() not in str(item.get("city", "")).lower():
            return False
        if pincode and pincode != str(item.get("pincode", "")):
            return False
        if insurer and insurer.lower() not in str(item.get("insurer", "")).lower():
            return False
        return True

    filtered = [item for item in items if _matches(item)]
    return {"items": paginated(filtered, page, page_size)}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    startup_storage()

    filename = Path(file.filename or "upload.bin").name
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    doc_id = str(uuid4())
    stored_name = f"{doc_id}-{filename}"
    target = UPLOAD_DIR / stored_name
    target.write_bytes(await file.read())

    document = {
        "doc_id": doc_id,
        "filename": filename,
        "stored_name": stored_name,
        "status": "ready",
        "page_count": None,
        "extraction_confidence": 50,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    documents = read_json(DOCUMENTS_PATH, [])
    documents.insert(0, document)
    write_json(DOCUMENTS_PATH, documents)
    return document


@app.get("/api/documents")
def list_documents():
    return read_json(DOCUMENTS_PATH, [])


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    documents = read_json(DOCUMENTS_PATH, [])
    document = next((item for item in documents if item["doc_id"] == doc_id), None)
    if not document:
        http_not_found("Document not found")

    filtered = [item for item in documents if item["doc_id"] != doc_id]
    write_json(DOCUMENTS_PATH, filtered)
    stored_name = document.get("stored_name")
    if stored_name:
        target = UPLOAD_DIR / stored_name
        if target.exists():
            target.unlink()
    return {"deleted": True, "doc_id": doc_id}


@app.post("/api/chat")
def chat(payload: dict):
    message = (payload or {}).get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    return build_chat_payload(
        message,
        payload.get("context_type"),
        payload.get("context_id"),
    )


@app.post("/api/chat/stream")
def stream_chat(payload: dict):
    message = (payload or {}).get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    response_payload = build_chat_payload(
        message,
        payload.get("context_type"),
        payload.get("context_id"),
    )

    def event_stream():
        for token in tokenise(response_payload["answer"]):
            yield "data: " + json.dumps({"token": token}) + "\n\n"
        if response_payload["citations"]:
            yield "data: " + json.dumps({"citations": response_payload["citations"]}) + "\n\n"
        if response_payload["caveat"]:
            yield "data: " + json.dumps({"caveat": response_payload["caveat"]}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/claim-checklist")
def claim_checklist(payload: dict):
    variant_id = payload.get("variant_id")
    claim_type = payload.get("claim_type", "cashless")
    procedure = payload.get("procedure")
    if not variant_id:
        raise HTTPException(status_code=400, detail="Variant ID is required")

    variant = fetch_variant_detail(variant_id, include_children=False)
    if not variant:
        http_not_found("Variant not found")

    sections = []
    if claim_type == "cashless":
        sections.append(
            {
                "title": "Before Admission",
                "timeline": variant.get("cashless_notice_planned") or "48 hours before planned admission",
                "items": [
                    {
                        "label": f"Call cashless helpline: {variant.get('cashless_helpline') or 'use insurer helpline'}",
                        "note": "Keep policy number and ID proof ready",
                    },
                    {
                        "label": "Submit the pre-auth form at the hospital TPA desk",
                        "note": procedure if procedure else None,
                    },
                ],
            }
        )
        sections.append(
            {
                "title": "During Hospitalisation",
                "timeline": variant.get("cashless_notice_emergency") or "Within 24 hours for emergency admission",
                "items": [
                    {
                        "label": "Confirm approval status with the hospital insurance desk",
                        "note": "Follow up if the insurer asks for additional reports",
                    },
                    {
                        "label": "Keep doctor advice, admission note, and prescriptions available",
                        "note": None,
                    },
                ],
            }
        )
    else:
        sections.append(
            {
                "title": "During Treatment",
                "timeline": "Collect documents at discharge",
                "items": [
                    {
                        "label": "Keep original bills, prescriptions, discharge summary, and reports",
                        "note": procedure if procedure else None,
                    },
                    {
                        "label": "Retain payment proof and bank details for reimbursement",
                        "note": None,
                    },
                ],
            }
        )
        sections.append(
            {
                "title": "After Discharge",
                "timeline": (
                    f"Submit within {variant['reimbursement_submit_days']} days"
                    if variant.get("reimbursement_submit_days")
                    else "Submit as early as possible after discharge"
                ),
                "items": [
                    {
                        "label": "Send the reimbursement claim with all supporting documents",
                        "note": "Include the completed claim form and ID proof",
                    },
                    {
                        "label": "Track claim status with the insurer helpline",
                        "note": variant.get("cashless_helpline"),
                    },
                ],
            }
        )

    sections.append(
        {
            "title": "Final Verification",
            "timeline": "Before submission",
            "items": [
                {
                    "label": "Check waiting periods, exclusions, and sub-limits relevant to the treatment",
                    "note": "Use the policy detail or comparison page to confirm clause-level limits",
                }
            ],
        }
    )

    return {"sections": sections}


@app.get("/api/admin/variants")
def admin_get_variants(
    q: Optional[str] = None,
    policy_type: Optional[str] = None,
    insurer: Optional[str] = None,
    si_min: Optional[int] = None,
    si_max: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return fetch_variants_page(q, policy_type, insurer, si_min, si_max, page, page_size)


@app.post("/api/admin/variants")
def admin_create_variant(payload: dict):
    policy_id = payload.get("policy_id")
    variant_name = payload.get("variant_name")
    if not policy_id or not variant_name:
        raise HTTPException(status_code=400, detail="policy_id and variant_name are required")

    fields = {key: value for key, value in payload.items() if key in VARIANT_MUTABLE_FIELDS}
    if "policy_id" not in fields:
        fields["policy_id"] = policy_id
    if "variant_name" not in fields:
        fields["variant_name"] = variant_name

    columns = list(fields.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in columns
        if column not in {"policy_id", "variant_name"}
    )
    conflict_clause = (
        f"ON CONFLICT (policy_id, variant_name) DO UPDATE SET {updates}"
        if updates
        else "ON CONFLICT (policy_id, variant_name) DO NOTHING"
    )

    with get_conn(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO policy_variants ({", ".join(columns)})
                VALUES ({placeholders})
                {conflict_clause}
                RETURNING variant_id
                """,
                [fields[column] for column in columns],
            )
            row = cur.fetchone()
            if row:
                variant_id = serialize_row(row)["variant_id"]
            else:
                cur.execute(
                    """
                    SELECT variant_id
                    FROM policy_variants
                    WHERE policy_id = %s AND variant_name = %s
                    """,
                    (policy_id, variant_name),
                )
                variant_id = serialize_row(cur.fetchone())["variant_id"]
        conn.commit()

    return fetch_variant_detail(variant_id, include_children=False)


@app.put("/api/admin/variants/{variant_id}")
def admin_update_variant(variant_id: str, payload: dict):
    updates = {key: value for key, value in payload.items() if key in VARIANT_MUTABLE_FIELDS and key != "policy_id"}
    if not updates:
        raise HTTPException(status_code=400, detail="No mutable fields supplied")

    assignments = ", ".join(f"{column} = %s" for column in updates)
    params = [updates[column] for column in updates] + [variant_id]

    with get_conn(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE policy_variants
                SET {assignments}
                WHERE variant_id = %s
                RETURNING variant_id
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                http_not_found("Variant not found")
        conn.commit()

    return fetch_variant_detail(variant_id, include_children=False)


@app.delete("/api/admin/variants/{variant_id}")
def admin_delete_variant(variant_id: str):
    with get_conn(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM policy_variants WHERE variant_id = %s RETURNING variant_id",
                (variant_id,),
            )
            row = cur.fetchone()
            if not row:
                http_not_found("Variant not found")
        conn.commit()

    return {"deleted": True, "variant_id": variant_id}


@app.get("/api/admin/refresh-logs")
def admin_refresh_logs():
    return read_json(REFRESH_LOGS_PATH, [])


@app.post("/api/admin/refresh/{source_id}")
def admin_trigger_refresh(source_id: str):
    return log_refresh(source_id)
