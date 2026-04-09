import os
import argparse
from typing import List, Dict, Any, Optional
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

def get_conn():
    dsn = os.getenv("HEALIN_RAG_DB_URL") or os.getenv("PG_DSN") or os.getenv("HEALIN_DB_URL") or "postgresql://postgres:postgres@localhost:5432/HealIn"
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)


def get_vector_collection(collection_name: str = "policy_clause_chunks"):
    # Lazy import so DB-only scripts don't fail if Chroma isn't installed
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except Exception as e:
        raise ImportError(
            f"Failed to import chromadb/sentence-transformers: {e}\n"
            f"Install with: pip install chromadb sentence-transformers"
        )

    vector_dir = os.getenv("VECTOR_DB_DIR", str(Path(__file__).resolve().with_name("vectordb")))
    emb_model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=vector_dir)
    ef = SentenceTransformerEmbeddingFunction(model_name=emb_model)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef
    )
    return client, collection


def fetch_chunks(conn, policy_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Reads chunks from Postgres. If policy_filter is provided, it can match:
    - policy_id
    - policy_name
    - policy_code
    """
    with conn.cursor() as cur:
        if policy_filter:
            cur.execute(
                """
                SELECT
                    c.chunk_uid,
                    c.policy_id::text AS policy_id,
                    c.source_section,
                    c.json_path,
                    c.chunk_text,
                    c.page_number,
                    c.metadata,
                    p.policy_name,
                    p.policy_code
                FROM policy_chunks c
                JOIN policies p ON p.policy_id = c.policy_id
                WHERE p.policy_id::text = %s
                   OR lower(p.policy_name) = lower(%s)
                   OR lower(p.policy_code) = lower(%s)
                ORDER BY c.chunk_uid
                """,
                (policy_filter, policy_filter, policy_filter),
            )
        else:
            cur.execute(
                """
                SELECT
                    c.chunk_uid,
                    c.policy_id::text AS policy_id,
                    c.source_section,
                    c.json_path,
                    c.chunk_text,
                    c.page_number,
                    c.metadata,
                    p.policy_name,
                    p.policy_code
                FROM policy_chunks c
                JOIN policies p ON p.policy_id = c.policy_id
                ORDER BY c.chunk_uid
                """
            )
        return cur.fetchall()


def delete_existing_for_policies(collection, policy_ids: List[str]):
    """
    Optional cleanup: remove existing vectors for these policy_ids before re-indexing.
    """
    for pid in sorted(set(policy_ids)):
        try:
            collection.delete(where={"policy_id": pid})
        except Exception:
            # Some Chroma versions behave differently if none exist; safe to ignore
            pass


def build_vectors(conn, collection, policy_filter: Optional[str] = None, batch_size: int = 128, reset_policy: bool = True):
    rows = fetch_chunks(conn, policy_filter=policy_filter)
    if not rows:
        print("No chunks found in Postgres (policy_chunks table).")
        return

    policy_ids = [r["policy_id"] for r in rows]

    if reset_policy:
        print("[DEBUG] Removing old vectors for selected policy/policies...", flush=True)
        delete_existing_for_policies(collection, policy_ids)

    total = len(rows)
    print(f"[DEBUG] Found {total} chunks to index.", flush=True)

    for start in range(0, total, batch_size):
        batch = rows[start:start + batch_size]

        ids = []
        docs = []
        metas = []

        for r in batch:
            ids.append(r["chunk_uid"])
            docs.append(r["chunk_text"] or "")

            # Chroma metadata values should be simple scalars
            metas.append({
                "policy_id": r["policy_id"],
                "policy_name": r.get("policy_name") or "",
                "policy_code": r.get("policy_code") or "",
                "source_section": r.get("source_section") or "",
                "json_path": r.get("json_path") or "",
                "page_number": int(r["page_number"]) if isinstance(r.get("page_number"), int) else -1,
            })

        collection.add(ids=ids, documents=docs, metadatas=metas)
        print(f"[DEBUG] Indexed batch {start + 1}-{min(start + batch_size, total)} / {total}", flush=True)

    print("✅ Vector DB build complete.", flush=True)


def show_collection_stats(collection):
    try:
        count = collection.count()
        print(f"[DEBUG] Collection count: {count}", flush=True)
    except Exception as e:
        print(f"[DEBUG] Could not get collection count: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Build local Chroma vector DB from Postgres policy_chunks")
    parser.add_argument("--policy", help="Optional policy filter (policy_id / policy_name / policy_code)")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size for Chroma add()")
    parser.add_argument("--no-reset", action="store_true", help="Do not delete existing vectors for selected policies before indexing")
    parser.add_argument("--collection", default="policy_clause_chunks", help="Chroma collection name")
    args = parser.parse_args()

    conn = None
    try:
        print("[DEBUG] Connecting to Postgres...", flush=True)
        conn = get_conn()
        print("[DEBUG] Postgres connected.", flush=True)

        print("[DEBUG] Initializing Chroma collection (first run may download embedding model)...", flush=True)
        client, collection = get_vector_collection(collection_name=args.collection)
        print("[DEBUG] Chroma ready.", flush=True)

        build_vectors(
            conn=conn,
            collection=collection,
            policy_filter=args.policy,
            batch_size=max(1, args.batch_size),
            reset_policy=(not args.no_reset),
        )

        show_collection_stats(collection)

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}", flush=True)
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
