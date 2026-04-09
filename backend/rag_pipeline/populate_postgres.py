import os
import json
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

SCALAR_TYPES = (str, int, float, bool)


# -----------------------------
# DB
# -----------------------------
def get_conn():
    dsn = os.getenv("HEALIN_RAG_DB_URL") or os.getenv("PG_DSN") or os.getenv("HEALIN_DB_URL") or "postgresql://postgres:postgres@localhost:5432/HealIn"
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)


# -----------------------------
# Utility: chunking + flattening
# -----------------------------
def chunk_long_text(text: str, max_chars: int = 700, overlap: int = 100) -> List[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    step = max(1, max_chars - overlap)
    i = 0
    while i < len(text):
        chunks.append(text[i:i + max_chars])
        i += step
    return chunks


def dict_to_chunk_text(path: str, d: Dict[str, Any]) -> str:
    parts = []
    for k, v in d.items():
        if v is None or k == "page_number":
            continue
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}: {v}")
        elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
            parts.append(f"{k}: {', '.join(map(str, v))}")
    if not parts:
        return ""
    return f"{path}\n" + "\n".join(parts)


def extract_facts_and_chunks(
    obj: Any,
    path: str = "",
    section: Optional[str] = None,
    inherited_page: Optional[int] = None,
    facts: Optional[List[Dict[str, Any]]] = None,
    chunks: Optional[List[Dict[str, Any]]] = None,
):
    if facts is None:
        facts = []
    if chunks is None:
        chunks = []

    if isinstance(obj, dict):
        page = obj.get("page_number", inherited_page)
        if not isinstance(page, int):
            page = inherited_page

        # Dict summary chunk
        ctext = dict_to_chunk_text(path or "root", obj)
        for c in chunk_long_text(ctext):
            chunks.append({
                "source_section": section or (path.split(".")[0] if path else "root"),
                "json_path": path or "root",
                "chunk_text": c,
                "page_number": page,
                "metadata": {"kind": "dict_summary"}
            })

        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else k
            child_section = section or (path.split(".")[0] if path else k)

            if isinstance(v, SCALAR_TYPES):
                rec = {
                    "source_section": child_section,
                    "fact_path": child_path,
                    "fact_key": k,
                    "value_type": type(v).__name__,
                    "value_text": None,
                    "value_num": None,
                    "value_bool": None,
                    "page_number": page
                }

                if isinstance(v, bool):
                    rec["value_bool"] = v
                    rec["value_text"] = str(v)
                elif isinstance(v, (int, float)):
                    rec["value_num"] = float(v)
                    rec["value_text"] = str(v)
                else:
                    rec["value_text"] = str(v)
                    # scalar text chunk
                    for t in chunk_long_text(f"{child_path}: {v}", max_chars=500, overlap=50):
                        chunks.append({
                            "source_section": child_section,
                            "json_path": child_path,
                            "chunk_text": t,
                            "page_number": page,
                            "metadata": {"kind": "scalar_text"}
                        })

                facts.append(rec)
            else:
                extract_facts_and_chunks(
                    v,
                    path=child_path,
                    section=child_section,
                    inherited_page=page,
                    facts=facts,
                    chunks=chunks,
                )

    elif isinstance(obj, list):
        if all(isinstance(x, SCALAR_TYPES) for x in obj):
            for idx, item in enumerate(obj):
                item_path = f"{path}[{idx}]"
                rec = {
                    "source_section": section or (path.split(".")[0] if path else "root"),
                    "fact_path": item_path,
                    "fact_key": path.split(".")[-1] if path else "root",
                    "value_type": type(item).__name__,
                    "value_text": None,
                    "value_num": None,
                    "value_bool": None,
                    "page_number": inherited_page
                }

                if isinstance(item, bool):
                    rec["value_bool"] = item
                    rec["value_text"] = str(item)
                elif isinstance(item, (int, float)):
                    rec["value_num"] = float(item)
                    rec["value_text"] = str(item)
                else:
                    rec["value_text"] = str(item)

                facts.append(rec)

            joined = "\n".join(f"- {x}" for x in obj)
            for c in chunk_long_text(f"{path}:\n{joined}"):
                chunks.append({
                    "source_section": section or (path.split(".")[0] if path else "root"),
                    "json_path": path,
                    "chunk_text": c,
                    "page_number": inherited_page,
                    "metadata": {"kind": "list_simple"}
                })
        else:
            for idx, item in enumerate(obj):
                extract_facts_and_chunks(
                    item,
                    path=f"{path}[{idx}]",
                    section=section,
                    inherited_page=inherited_page,
                    facts=facts,
                    chunks=chunks,
                )

    return facts, chunks


# -----------------------------
# Postgres upserts / inserts
# -----------------------------
def get_or_create_insurer(cur, basic_info: Dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO insurers (insurer_name, irdai_registration, cin)
        VALUES (%s, %s, %s)
        ON CONFLICT (insurer_name) DO UPDATE
        SET irdai_registration = COALESCE(EXCLUDED.irdai_registration, insurers.irdai_registration),
            cin = COALESCE(EXCLUDED.cin, insurers.cin)
        RETURNING insurer_id
        """,
        (
            basic_info.get("insurer_name", "Unknown"),
            basic_info.get("irdai_registration"),
            basic_info.get("cin"),
        ),
    )
    return cur.fetchone()["insurer_id"]


def upsert_policy(cur, insurer_id: int, data: Dict[str, Any]) -> str:
    b = data.get("basic_info", {})
    policy_name = b.get("policy_name", "Unknown Policy")
    policy_code = (b.get("policy_code") or "")
    version = (b.get("version") or "")

    cur.execute(
        """
        INSERT INTO policies (
            insurer_id, policy_name, policy_code, version, effective_date, policy_type, document_type,
            source_file, extraction_date, page_count,
            raw_json, coverage_json, exclusions_json, sub_limits_json, additional_benefits_json,
            claim_procedures_json, policy_conditions_json, premium_payment_json, discounts_json,
            geography_json, non_disclosure_json, grievance_json, non_payable_json, key_features_json
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
            %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
            %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
            %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb
        )
        ON CONFLICT ON CONSTRAINT uq_policy_identity DO NOTHING
        RETURNING policy_id
        """,
        (
            insurer_id,
            policy_name,
            policy_code,
            version,
            b.get("effective_date"),
            b.get("policy_type"),
            b.get("document_type"),
            data.get("source_file"),
            data.get("extraction_date"),
            data.get("page_count"),
            json.dumps(data),
            json.dumps(data.get("coverage")),
            json.dumps(data.get("exclusions")),
            json.dumps(data.get("sub_limits")),
            json.dumps(data.get("additional_benefits")),
            json.dumps(data.get("claim_procedures")),
            json.dumps(data.get("policy_conditions")),
            json.dumps(data.get("premium_payment")),
            json.dumps(data.get("discounts_and_loadings")),
            json.dumps(data.get("geography")),
            json.dumps(data.get("non_disclosure_misrepresentation")),
            json.dumps(data.get("grievance_redressal")),
            json.dumps(data.get("non_payable_items")),
            json.dumps(data.get("key_features")),
        ),
    )

    row = cur.fetchone()
    if row:
        return str(row["policy_id"])

    # Existing row -> fetch and update JSONs
    cur.execute(
        """
        SELECT policy_id::text
        FROM policies
        WHERE insurer_id=%s
          AND policy_name=%s
          AND policy_code=%s
          AND version=%s
        LIMIT 1
        """,
        (insurer_id, policy_name, policy_code, version),
    )
    policy_id = cur.fetchone()["policy_id"]

    cur.execute(
        """
        UPDATE policies
        SET source_file=%s,
            extraction_date=%s,
            page_count=%s,
            raw_json=%s::jsonb,
            coverage_json=%s::jsonb,
            exclusions_json=%s::jsonb,
            sub_limits_json=%s::jsonb,
            additional_benefits_json=%s::jsonb,
            claim_procedures_json=%s::jsonb,
            policy_conditions_json=%s::jsonb,
            premium_payment_json=%s::jsonb,
            discounts_json=%s::jsonb,
            geography_json=%s::jsonb,
            non_disclosure_json=%s::jsonb,
            grievance_json=%s::jsonb,
            non_payable_json=%s::jsonb,
            key_features_json=%s::jsonb
        WHERE policy_id=%s
        """,
        (
            data.get("source_file"),
            data.get("extraction_date"),
            data.get("page_count"),
            json.dumps(data),
            json.dumps(data.get("coverage")),
            json.dumps(data.get("exclusions")),
            json.dumps(data.get("sub_limits")),
            json.dumps(data.get("additional_benefits")),
            json.dumps(data.get("claim_procedures")),
            json.dumps(data.get("policy_conditions")),
            json.dumps(data.get("premium_payment")),
            json.dumps(data.get("discounts_and_loadings")),
            json.dumps(data.get("geography")),
            json.dumps(data.get("non_disclosure_misrepresentation")),
            json.dumps(data.get("grievance_redressal")),
            json.dumps(data.get("non_payable_items")),
            json.dumps(data.get("key_features")),
            policy_id,
        ),
    )
    return policy_id


def rebuild_plan_variants(cur, policy_id: str, data: Dict[str, Any]):
    b = data.get("basic_info", {})
    variants = []
    for k in ["plan_variants", "plan_types"]:
        v = b.get(k)
        if isinstance(v, list):
            variants.extend([str(x) for x in v if x is not None])

    # dedupe preserving order
    seen = set()
    final_variants = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            final_variants.append(v)

    cur.execute("DELETE FROM policy_plan_variants WHERE policy_id=%s", (policy_id,))
    for v in final_variants:
        cur.execute(
            """
            INSERT INTO policy_plan_variants (policy_id, variant_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (policy_id, v),
        )


def rebuild_facts(cur, policy_id: str, facts: List[Dict[str, Any]]):
    cur.execute("DELETE FROM policy_facts WHERE policy_id=%s", (policy_id,))
    if not facts:
        return

    rows = [
        (
            policy_id,
            f["source_section"],
            f["fact_path"],
            f["fact_key"],
            f["value_type"],
            f.get("value_text"),
            f.get("value_num"),
            f.get("value_bool"),
            f.get("page_number"),
        )
        for f in facts
    ]

    cur.executemany(
        """
        INSERT INTO policy_facts (
            policy_id, source_section, fact_path, fact_key, value_type,
            value_text, value_num, value_bool, page_number
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        rows,
    )


def rebuild_chunks_pg(cur, policy_id: str, chunks: List[Dict[str, Any]]):
    cur.execute("DELETE FROM policy_chunks WHERE policy_id=%s", (policy_id,))
    if not chunks:
        return

    rows = []
    for i, c in enumerate(chunks):
        cid = f"{policy_id}:{i}"
        rows.append(
            (
                cid,
                policy_id,
                c.get("source_section"),
                c.get("json_path"),
                c.get("chunk_text", ""),
                c.get("page_number"),
                json.dumps(c.get("metadata", {})),
            )
        )

    cur.executemany(
        """
        INSERT INTO policy_chunks (
            chunk_uid, policy_id, source_section, json_path, chunk_text, page_number, metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        rows,
    )


# -----------------------------
# Ingest one file
# -----------------------------
def ingest_file(conn, json_path: str) -> str:
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with p.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    facts, chunks = extract_facts_and_chunks(data)

    with conn.cursor() as cur:
        insurer_id = get_or_create_insurer(cur, data.get("basic_info", {}))
        policy_id = upsert_policy(cur, insurer_id, data)
        rebuild_plan_variants(cur, policy_id, data)
        rebuild_facts(cur, policy_id, facts)
        rebuild_chunks_pg(cur, policy_id, chunks)

    conn.commit()
    return policy_id


def main():
    data_dir = Path(__file__).resolve().parents[1] / "data"
    json_files = [str(path) for path in sorted(data_dir.glob("*.json"))]

    conn = None
    try:
        print("[DEBUG] Connecting to Postgres...", flush=True)
        conn = get_conn()
        print("[DEBUG] Connected.", flush=True)

        for fp in json_files:
            print(f"[DEBUG] Ingesting: {fp}", flush=True)
            pid = ingest_file(conn, fp)
            print(f"✅ Ingested {fp} -> policy_id={pid}", flush=True)

        print("✅ Done.", flush=True)

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}", flush=True)
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
