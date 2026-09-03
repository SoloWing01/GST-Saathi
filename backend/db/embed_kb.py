"""Phase 3 — Embed GST rules KB and load into Supabase.

Reads all markdown files from backend/kb/gst_rules/, generates embeddings
using sentence-transformers (all-MiniLM-L6-v2, 384 dims), and stores them
in the gst_kb_embeddings table in Supabase.

Run once (after setup_phase3.py):
    cd backend && uv run python -m db.embed_kb
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KB_DIR = Path(__file__).resolve().parent.parent / "kb" / "gst_rules"
MODEL_NAME = "all-MiniLM-L6-v2"


def _run_ddl(sql: str) -> None:
    """Run SQL against Supabase Postgres via psycopg."""
    import psycopg
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def embed_and_load() -> None:
    print("=== Embedding GST Rules KB ===\n")

    # 1. Collect markdown files
    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        print(f"No markdown files found in {KB_DIR}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(md_files)} KB files")

    # 2. Load the embedding model
    print(f"Loading model: {MODEL_NAME}...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model loaded (embedding dim: {model.get_embedding_dimension()})")

    # 3. Generate embeddings
    print("\nGenerating embeddings...")
    records = []
    for f in md_files:
        content = f.read_text(encoding="utf-8")

        # Extract metadata from the markdown
        title = ""
        section = ""
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# ") and not title:
                title = line[2:].strip()
                # Try to extract section code from title
                # e.g. "ASMT-10 — Scrutiny of Returns" -> "ASMT-10"
                parts = title.split("—")
                if parts:
                    section = parts[0].strip()
            if line.startswith("## What it means") and not section:
                # Fallback: use filename as section
                section = f.stem.upper()

        if not section:
            section = f.stem.upper()

        # Use first 512 chars for embedding (captures the most relevant content)
        embed_text = content[:512]

        embedding = model.encode(embed_text, normalize_embeddings=True).tolist()

        records.append({
            "filename": f.name,
            "section": section,
            "title": title or f.stem,
            "content": content,
            "embedding": embedding,
        })
        print(f"  Embedded: {f.name} -> section='{section}', title='{title[:50]}'")

    # 4. Clear existing embeddings (re-embed from scratch)
    print("\nClearing existing embeddings...")
    _run_ddl("DELETE FROM gst_kb_embeddings")

    # 5. Insert into Supabase
    print(f"Inserting {len(records)} embeddings...")
    from db.supabase_client import get_client

    client = get_client()
    if client is None:
        print("ERROR: Supabase client not configured", file=sys.stderr)
        sys.exit(1)

    # Insert in batches
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        client.table("gst_kb_embeddings").insert(batch).execute()

    print(f"Inserted {len(records)} KB embeddings into Supabase")

    # 6. Create IVFFlat index now that data exists
    print("Creating IVFFlat index...")
    try:
        _run_ddl(
            "CREATE INDEX idx_kb_embedding ON gst_kb_embeddings "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 3)"
        )
        print("   Index created (lists=3)")
    except Exception as e:
        # Index might already exist
        if "already exists" in str(e).lower():
            print("   Index already exists — rebuilding...")
            _run_ddl("DROP INDEX IF EXISTS idx_kb_embedding")
            _run_ddl(
                "CREATE INDEX idx_kb_embedding ON gst_kb_embeddings "
                "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 3)"
            )
            print("   Index rebuilt")
        else:
            print(f"   Warning: {e}")

    # 7. Verify
    count = client.table("gst_kb_embeddings").select("id", count="exact").execute()
    print(f"\nTotal embeddings in table: {count.count}")

    # 7. Test a similarity search
    print("\n--- Test Similarity Search ---")
    test_query = "notice for excess ITC claimed"
    query_embedding = model.encode(test_query, normalize_embeddings=True).tolist()

    # Use pgvector cosine similarity via Supabase RPC
    # For now, let's do a raw SQL query via psycopg
    import psycopg
    import json

    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT section, title, filename,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM gst_kb_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT 3
                """,
                (json.dumps(query_embedding), json.dumps(query_embedding)),
            )
            results = cur.fetchall()
            print(f"\nQuery: '{test_query}'")
            print("Top 3 matches:")
            for section, title, filename, sim in results:
                print(f"  [{sim:.4f}] {section}: {title} ({filename})")
    finally:
        conn.close()

    print("\n=== Embedding Complete ===")


if __name__ == "__main__":
    embed_and_load()
