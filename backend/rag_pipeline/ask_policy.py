# import re
# import argparse
# from typing import Any, Dict, List, Optional

# import psycopg
# from psycopg.rows import dict_row

# # Optional OpenAI (only used if OPENAI_API_KEY is set)
# try:
#     import os
#     from openai import OpenAI
# except Exception:
#     OpenAI = None
#     os = None


# # -----------------------------
# # HARDcoded local config
# # -----------------------------
# PG_DSN = "postgresql://postgres:madhav@localhost:5432/HealIn"
# VECTOR_DB_DIR = r"C:\Users\gaurm\Downloads\HealIn\vectordb"   # <-- your vector DB folder
# EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# COLLECTION_NAME = "policy_clause_chunks"


# STRUCTURED_QUERY_HINTS = {
#     "waiting", "period", "copay", "co-pay", "limit", "sub-limit", "sublimit",
#     "premium", "sum", "insured", "grace", "renewal", "cancellation", "maternity",
#     "claim", "cashless", "reimbursement", "discount", "room", "ambulance", "bonus",
#     "exclusion", "territorial", "portability", "migration", "icu", "rent"
# }


# # -----------------------------
# # DB / Chroma setup
# # -----------------------------
# def get_conn():
#     return psycopg.connect(PG_DSN, row_factory=dict_row, connect_timeout=5)


# def get_vector_collection(collection_name: str = COLLECTION_NAME):
#     try:
#         import chromadb
#         from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
#     except Exception as e:
#         raise ImportError(
#             f"Failed to import chromadb/sentence-transformers: {e}\n"
#             f"Install with: pip install chromadb sentence-transformers"
#         )

#     client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
#     ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)

#     collection = client.get_or_create_collection(
#         name=collection_name,
#         embedding_function=ef
#     )
#     return collection


# # -----------------------------
# # Policy resolution / listing
# # -----------------------------
# def list_policies(conn):
#     with conn.cursor() as cur:
#         cur.execute(
#             """
#             SELECT p.policy_id::text AS policy_id, p.policy_name, p.policy_code, p.version, i.insurer_name
#             FROM policies p
#             JOIN insurers i ON i.insurer_id = p.insurer_id
#             ORDER BY i.insurer_name, p.policy_name
#             """
#         )
#         return cur.fetchall()


# def resolve_policy_id(conn, identifier: str) -> Optional[str]:
#     with conn.cursor() as cur:
#         cur.execute(
#             """
#             SELECT policy_id::text
#             FROM policies
#             WHERE lower(policy_name) = lower(%s)
#                OR lower(coalesce(policy_code, '')) = lower(%s)
#                OR policy_id::text = %s
#             LIMIT 1
#             """,
#             (identifier, identifier, identifier),
#         )
#         row = cur.fetchone()
#         return row["policy_id"] if row else None


# # -----------------------------
# # Structured search
# # -----------------------------
# def tokenize_query(q: str) -> List[str]:
#     return [t for t in re.findall(r"[A-Za-z0-9_]+", (q or "").lower()) if len(t) >= 3]


# def should_route_structured(query: str) -> bool:
#     q = (query or "").lower()
#     return any(k in q for k in STRUCTURED_QUERY_HINTS)


# def structured_search(conn, policy_id: str, query: str, limit: int = 8):
#     terms = tokenize_query(query)[:8]
#     if not terms:
#         terms = [query.lower()]

#     likes = [f"%{t}%" for t in terms]

#     path_ors = " OR ".join(["lower(fact_path) LIKE %s"] * len(likes))
#     val_ors = " OR ".join(["lower(coalesce(value_text,'')) LIKE %s"] * len(likes))

#     sql = f"""
#     SELECT fact_path, value_text, value_num, value_bool, page_number, source_section,
#            (
#              CASE WHEN ({path_ors}) THEN 1 ELSE 0 END +
#              CASE WHEN ({val_ors}) THEN 1 ELSE 0 END
#            ) AS score
#     FROM policy_facts
#     WHERE policy_id=%s
#       AND (({path_ors}) OR ({val_ors}))
#     ORDER BY score DESC, fact_path
#     LIMIT %s
#     """

#     params = []
#     params.extend(likes)   # score path
#     params.extend(likes)   # score val
#     params.append(policy_id)
#     params.extend(likes)   # where path
#     params.extend(likes)   # where val
#     params.append(limit)

#     with conn.cursor() as cur:
#         cur.execute(sql, params)
#         return cur.fetchall()


# # -----------------------------
# # Semantic search (Chroma)
# # -----------------------------
# def semantic_search(collection, policy_id: str, query: str, top_k: int = 5):
#     res = collection.query(
#         query_texts=[query],
#         n_results=top_k,
#         where={"policy_id": policy_id},
#         include=["documents", "metadatas", "distances"],
#     )

#     docs = res.get("documents", [[]])[0] if res.get("documents") else []
#     metas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
#     dists = res.get("distances", [[]])[0] if res.get("distances") else []

#     out = []
#     for d, m, dist in zip(docs, metas, dists):
#         out.append({"text": d, "meta": m, "distance": dist})
#     return out


# # -----------------------------
# # Optional LLM synthesis
# # -----------------------------
# def call_llm_with_rag(question: str, contexts: List[Dict[str, Any]]) -> str:
#     if not contexts:
#         return "No relevant chunks found in semantic retrieval."

#     # If OPENAI_API_KEY not set, just return evidence
#     if os is None or not os.getenv("OPENAI_API_KEY") or OpenAI is None:
#         lines = ["[LLM disabled] Retrieved evidence only:"]
#         for i, c in enumerate(contexts, 1):
#             page = c["meta"].get("page_number", -1)
#             lines.append(f"{i}. (page {page}) {c['text'][:400]}")
#         return "\n".join(lines)

#     client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#     model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

#     evidence = "\n\n".join(
#         f"[{i}] page={c['meta'].get('page_number', -1)} path={c['meta'].get('json_path')}\n{c['text']}"
#         for i, c in enumerate(contexts, 1)
#     )

#     prompt = f"""Use ONLY the evidence to answer the insurance policy question.
# If the answer is not clearly present, say so.
# Always cite evidence as [1], [2], etc.

# Question:
# {question}

# Evidence:
# {evidence}
# """

#     resp = client.chat.completions.create(
#         model=model,
#         messages=[
#             {"role": "system", "content": "You answer policy queries using only retrieved policy evidence."},
#             {"role": "user", "content": prompt},
#         ],
#         temperature=0,
#     )
#     return resp.choices[0].message.content


# # -----------------------------
# # End-to-end ask
# # -----------------------------
# def ask_policy(conn, collection, policy_identifier: str, query: str, top_k: int = 5) -> str:
#     policy_id = resolve_policy_id(conn, policy_identifier)
#     if not policy_id:
#         rows = list_policies(conn)
#         known = [f"{r['policy_name']} | code={r['policy_code']} | id={r['policy_id']}" for r in rows]
#         raise ValueError("Policy not found.\nAvailable policies:\n- " + "\n- ".join(known))

#     lines = [f"Policy ID: {policy_id}"]

#     # Structured exact-ish lookup first
#     if should_route_structured(query):
#         facts = structured_search(conn, policy_id, query, limit=8)
#         if facts:
#             lines.append("\nStructured matches:")
#             for f in facts:
#                 val = f["value_text"]
#                 if val is None and f["value_num"] is not None:
#                     val = str(f["value_num"])
#                 if val is None and f["value_bool"] is not None:
#                     val = str(f["value_bool"])
#                 lines.append(f"- {f['fact_path']} = {val} (page {f['page_number']})")
#         else:
#             lines.append("\nStructured matches: none")

#     # Semantic retrieval
#     contexts = semantic_search(collection, policy_id, query, top_k=top_k)

#     lines.append("\nRAG answer:")
#     lines.append(call_llm_with_rag(query, contexts))

#     lines.append("\nRetrieved chunks:")
#     if not contexts:
#         lines.append("- none")
#     else:
#         for i, c in enumerate(contexts, 1):
#             m = c["meta"]
#             preview = (c["text"] or "")[:220].replace("\n", " ")
#             dist = c.get("distance", 0.0)
#             lines.append(
#                 f"- [{i}] dist={dist:.4f} | page {m.get('page_number')} | {m.get('json_path')} | {preview}..."
#             )

#     return "\n".join(lines)


# # -----------------------------
# # CLI
# # -----------------------------
# def main():
#     parser = argparse.ArgumentParser(description="Ask policy questions using Postgres + Chroma")
#     sub = parser.add_subparsers(dest="cmd", required=True)

#     sub.add_parser("list-policies")

#     p_ask = sub.add_parser("ask")
#     p_ask.add_argument("--policy", required=True, help="Policy name / policy_code / policy_id")
#     p_ask.add_argument("--top-k", type=int, default=5, help="Top semantic chunks to retrieve")
#     p_ask.add_argument("query", help="Question to ask")

#     args = parser.parse_args()

#     conn = None
#     try:
#         print("[DEBUG] Connecting to Postgres...", flush=True)
#         conn = get_conn()
#         print("[DEBUG] Postgres connected.", flush=True)

#         if args.cmd == "list-policies":
#             rows = list_policies(conn)
#             if not rows:
#                 print("No policies found.", flush=True)
#                 return
#             print("Policies:", flush=True)
#             for r in rows:
#                 print(
#                     f"- {r['policy_name']} | code={r['policy_code']} | version={r['version']} | insurer={r['insurer_name']} | id={r['policy_id']}",
#                     flush=True
#                 )
#             return

#         print("[DEBUG] Initializing Chroma collection...", flush=True)
#         collection = get_vector_collection()
#         print(f"[DEBUG] Chroma ready. Count={collection.count()}", flush=True)

#         answer = ask_policy(conn, collection, args.policy, args.query, top_k=args.top_k)
#         print(answer, flush=True)

#     except Exception as e:
#         print(f"❌ ERROR: {type(e).__name__}: {e}", flush=True)
#         raise
#     finally:
#         if conn is not None:
#             try:
#                 conn.close()
#             except Exception:
#                 pass


# if __name__ == "__main__":
#     main()

import re
import argparse
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

# Optional OpenAI client (used with Groq's OpenAI-compatible API)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -----------------------------
# Local/env config
# -----------------------------
PG_DSN = os.getenv("HEALIN_RAG_DB_URL") or os.getenv("PG_DSN") or os.getenv("HEALIN_DB_URL") or "postgresql://postgres:postgres@localhost:5432/HealIn"
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR") or str(Path(__file__).resolve().with_name("vectordb"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
COLLECTION_NAME = "policy_clause_chunks"


STRUCTURED_QUERY_HINTS = {
    "waiting", "period", "copay", "co-pay", "limit", "sub-limit", "sublimit",
    "premium", "sum", "insured", "grace", "renewal", "cancellation", "maternity",
    "claim", "cashless", "reimbursement", "discount", "room", "ambulance", "bonus",
    "exclusion", "territorial", "portability", "migration", "icu", "rent"
}


# -----------------------------
# DB / Chroma setup
# -----------------------------
def get_conn():
    return psycopg.connect(PG_DSN, row_factory=dict_row, connect_timeout=5)


def get_vector_collection(collection_name: str = COLLECTION_NAME):
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except Exception as e:
        raise ImportError(
            f"Failed to import chromadb/sentence-transformers: {e}\n"
            f"Install with: pip install chromadb sentence-transformers"
        )

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef
    )
    return collection


# -----------------------------
# Policy resolution / listing
# -----------------------------
def list_policies(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.policy_id::text AS policy_id, p.policy_name, p.policy_code, p.version, i.insurer_name
            FROM policies p
            JOIN insurers i ON i.insurer_id = p.insurer_id
            ORDER BY i.insurer_name, p.policy_name
            """
        )
        return cur.fetchall()


def resolve_policy_id(conn, identifier: str) -> Optional[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT policy_id::text
            FROM policies
            WHERE lower(policy_name) = lower(%s)
               OR lower(coalesce(policy_code, '')) = lower(%s)
               OR policy_id::text = %s
            LIMIT 1
            """,
            (identifier, identifier, identifier),
        )
        row = cur.fetchone()
        return row["policy_id"] if row else None


# -----------------------------
# Structured search
# -----------------------------
def tokenize_query(q: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z0-9_]+", (q or "").lower()) if len(t) >= 3]


def should_route_structured(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in STRUCTURED_QUERY_HINTS)


def structured_search(conn, policy_id: str, query: str, limit: int = 8):
    terms = tokenize_query(query)[:8]
    if not terms:
        terms = [query.lower()]

    likes = [f"%{t}%" for t in terms]

    path_ors = " OR ".join(["lower(fact_path) LIKE %s"] * len(likes))
    val_ors = " OR ".join(["lower(coalesce(value_text,'')) LIKE %s"] * len(likes))

    sql = f"""
    SELECT fact_path, value_text, value_num, value_bool, page_number, source_section,
           (
             CASE WHEN ({path_ors}) THEN 1 ELSE 0 END +
             CASE WHEN ({val_ors}) THEN 1 ELSE 0 END
           ) AS score
    FROM policy_facts
    WHERE policy_id=%s
      AND (({path_ors}) OR ({val_ors}))
    ORDER BY score DESC, fact_path
    LIMIT %s
    """

    params = []
    params.extend(likes)   # score path
    params.extend(likes)   # score val
    params.append(policy_id)
    params.extend(likes)   # where path
    params.extend(likes)   # where val
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# -----------------------------
# Semantic search (Chroma)
# -----------------------------
def semantic_search(collection, policy_id: str, query: str, top_k: int = 5):
    res = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={"policy_id": policy_id},
        include=["documents", "metadatas", "distances"],
    )

    docs = res.get("documents", [[]])[0] if res.get("documents") else []
    metas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
    dists = res.get("distances", [[]])[0] if res.get("distances") else []

    out = []
    for d, m, dist in zip(docs, metas, dists):
        out.append({"text": d, "meta": m, "distance": dist})
    return out


# -----------------------------
# LLM synthesis via Groq (OpenAI-compatible)
# -----------------------------
def call_llm_with_rag(question: str, contexts: List[Dict[str, Any]]) -> str:
    if not contexts:
        return "No relevant chunks found in semantic retrieval."

    # If GROQ_API_KEY not set, just return evidence
    if os is None or not os.getenv("GROQ_API_KEY") or OpenAI is None:
        lines = ["[LLM disabled] Retrieved evidence only:"]
        for i, c in enumerate(contexts, 1):
            page = c["meta"].get("page_number", -1)
            lines.append(f"{i}. (page {page}) {c['text'][:400]}")
        return "\n".join(lines)

    # Groq uses OpenAI-compatible API with a different base_url
    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

    # Set a Groq model (change if you want a different one)
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    evidence = "\n\n".join(
        f"[{i}] page={c['meta'].get('page_number', -1)} path={c['meta'].get('json_path')}\n{c['text']}"
        for i, c in enumerate(contexts, 1)
    )

    prompt = f"""Use ONLY the evidence to answer the insurance policy question.
If the answer is not clearly present, say so.
Always cite evidence as [1], [2], etc.

Question:
{question}

Evidence:
{evidence}
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You answer policy queries using only retrieved policy evidence."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        # Graceful fallback
        lines = [f"[LLM call failed: {type(e).__name__}: {e}] Retrieved evidence only:"]
        for i, c in enumerate(contexts, 1):
            page = c["meta"].get("page_number", -1)
            lines.append(f"{i}. (page {page}) {c['text'][:400]}")
        return "\n".join(lines)


# -----------------------------
# End-to-end ask
# -----------------------------
def ask_policy(conn, collection, policy_identifier: str, query: str, top_k: int = 5) -> str:
    policy_id = resolve_policy_id(conn, policy_identifier)
    if not policy_id:
        rows = list_policies(conn)
        known = [f"{r['policy_name']} | code={r['policy_code']} | id={r['policy_id']}" for r in rows]
        raise ValueError("Policy not found.\nAvailable policies:\n- " + "\n- ".join(known))

    lines = [f"Policy ID: {policy_id}"]

    # Structured exact-ish lookup first
    if should_route_structured(query):
        facts = structured_search(conn, policy_id, query, limit=8)
        if facts:
            lines.append("\nStructured matches:")
            for f in facts:
                val = f["value_text"]
                if val is None and f["value_num"] is not None:
                    val = str(f["value_num"])
                if val is None and f["value_bool"] is not None:
                    val = str(f["value_bool"])
                lines.append(f"- {f['fact_path']} = {val} (page {f['page_number']})")
        else:
            lines.append("\nStructured matches: none")

    # Semantic retrieval
    contexts = semantic_search(collection, policy_id, query, top_k=top_k)

    lines.append("\nRAG answer:")
    lines.append(call_llm_with_rag(query, contexts))

    lines.append("\nRetrieved chunks:")
    if not contexts:
        lines.append("- none")
    else:
        for i, c in enumerate(contexts, 1):
            m = c["meta"]
            preview = (c["text"] or "")[:220].replace("\n", " ")
            dist = c.get("distance", 0.0)
            lines.append(
                f"- [{i}] dist={dist:.4f} | page {m.get('page_number')} | {m.get('json_path')} | {preview}..."
            )

    return "\n".join(lines)


# -----------------------------
# CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Ask policy questions using Postgres + Chroma + Groq")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-policies")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("--policy", required=True, help="Policy name / policy_code / policy_id")
    p_ask.add_argument("--top-k", type=int, default=5, help="Top semantic chunks to retrieve")
    p_ask.add_argument("query", help="Question to ask")

    args = parser.parse_args()

    conn = None
    try:
        print("[DEBUG] Connecting to Postgres...", flush=True)
        conn = get_conn()
        print("[DEBUG] Postgres connected.", flush=True)

        if args.cmd == "list-policies":
            rows = list_policies(conn)
            if not rows:
                print("No policies found.", flush=True)
                return
            print("Policies:", flush=True)
            for r in rows:
                print(
                    f"- {r['policy_name']} | code={r['policy_code']} | version={r['version']} | insurer={r['insurer_name']} | id={r['policy_id']}",
                    flush=True
                )
            return

        print("[DEBUG] Initializing Chroma collection...", flush=True)
        collection = get_vector_collection()
        print(f"[DEBUG] Chroma ready. Count={collection.count()}", flush=True)

        answer = ask_policy(conn, collection, args.policy, args.query, top_k=args.top_k)
        print(answer, flush=True)

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
