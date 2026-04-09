import json
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.comparison_pipeline.populate_v2 import (
    _claim_proc_fields,
    _discounts_fields,
    _get_builder,
    _policy_conditions_fields,
    _premium_fields,
)

from .config import DATA_DIR


def _generic_builder(data):
    return [
        (
            "Base",
            {
                **_claim_proc_fields(data.get("claim_procedures", {})),
                **_policy_conditions_fields(data.get("policy_conditions", {})),
                **_premium_fields(data.get("premium_payment", {})),
                **_discounts_fields(data.get("discounts_and_loadings", {})),
            },
            data.get("coverage", {}).get("coverage_features", []),
            data.get("sub_limits", {}).get("sub_limits", []),
            data.get("exclusions", {}).get("waiting_periods", []),
            data.get("exclusions", {}).get("exclusions", []),
        )
    ]


def _policy_id(data):
    basic = data.get("basic_info", {})
    seed = "|".join(
        [
            basic.get("policy_code") or "",
            basic.get("policy_name") or "",
            data.get("source_file") or "",
        ]
    )
    return str(uuid5(NAMESPACE_URL, f"policy:{seed}"))


def _variant_id(policy_id, variant_name):
    return str(uuid5(NAMESPACE_URL, f"variant:{policy_id}:{variant_name}"))


def _load_json(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _normalize_policy_type(value):
    return " ".join(
        str(value or "")
        .lower()
        .replace("/", " ")
        .replace("+", " ")
        .replace("-", " ")
        .split()
    )


def _build_variant_record(data, variant_name, fields, features, sublimits, waiting_periods, exclusions):
    basic = data.get("basic_info", {})
    policy_id = _policy_id(data)
    variant_id = _variant_id(policy_id, variant_name)
    return {
        "variant_id": variant_id,
        "policy_id": policy_id,
        "variant_name": variant_name,
        "policy_name": basic.get("policy_name"),
        "policy_code": basic.get("policy_code"),
        "version": basic.get("version"),
        "effective_date": basic.get("effective_date"),
        "policy_type": basic.get("policy_type"),
        "document_type": basic.get("document_type"),
        "source_file": data.get("source_file"),
        "extraction_date": data.get("extraction_date"),
        "page_count": data.get("page_count"),
        "insurer_name": basic.get("insurer_name"),
        "irdai_reg": basic.get("irdai_registration"),
        "cin": basic.get("cin"),
        "helpline": fields.get("cashless_helpline"),
        "website": basic.get("website"),
        "grievance_email": basic.get("grievance_email"),
        "features": features or [],
        "sublimits": sublimits or [],
        "waiting_periods": waiting_periods or [],
        "exclusions": exclusions or [],
        **fields,
    }


@lru_cache(maxsize=1)
def load_variants():
    variants = []

    for path in sorted(DATA_DIR.glob("*.json")):
        data = _load_json(path)
        policy_name = data.get("basic_info", {}).get("policy_name", "")
        builder = _get_builder(policy_name) or _generic_builder

        for variant_name, fields, features, sublimits, waiting_periods, exclusions in builder(data):
            variants.append(
                _build_variant_record(
                    data,
                    variant_name,
                    fields,
                    features,
                    sublimits,
                    waiting_periods,
                    exclusions,
                )
            )

    variants.sort(
        key=lambda item: (
            item.get("insurer_name") or "",
            item.get("policy_name") or "",
            item.get("variant_name") or "",
        )
    )
    return variants


def get_variant(variant_id):
    return next((item for item in load_variants() if item["variant_id"] == variant_id), None)


def filter_variants(q=None, policy_type=None, insurer=None, si_min=None, si_max=None):
    items = load_variants()

    def _matches(item):
        if q:
            haystack = " ".join(
                [
                    item.get("policy_name") or "",
                    item.get("variant_name") or "",
                    item.get("insurer_name") or "",
                ]
            ).lower()
            if q.lower() not in haystack:
                return False

        if policy_type and _normalize_policy_type(policy_type) not in _normalize_policy_type(item.get("policy_type")):
            return False

        if insurer and insurer.lower() not in (item.get("insurer_name") or "").lower():
            return False

        if si_min is not None and item.get("si_max_inr") is not None and item["si_max_inr"] < si_min:
            return False

        if si_max is not None and item.get("si_min_inr") is not None and item["si_min_inr"] > si_max:
            return False

        return True

    return [item for item in items if _matches(item)]


def page_variants(q=None, policy_type=None, insurer=None, si_min=None, si_max=None, page=1, page_size=20):
    items = filter_variants(q, policy_type, insurer, si_min, si_max)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": len(items),
    }
