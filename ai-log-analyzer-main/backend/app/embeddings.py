"""
embeddings.py

This module handles:
- Chunking text into segments
- Creating embeddings using SentenceTransformer
- Storing vectors in Qdrant
- Retrieving top-k relevant chunks (for RAG in LLM analysis)
"""

import os
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
import requests
from dotenv import load_dotenv

load_dotenv("backend/.env")
# --------------------------
# Configuration
# --------------------------
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# Initialize global clients
embedder = SentenceTransformer(MODEL_NAME)
qdrant = QdrantClient(QDRANT_URL)


# --------------------------
# Chunking Function
# --------------------------
def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """
    Splits long text into overlapping chunks for embedding.
    """
    if not text:
        return []

    chunks = []
    i = 0
    n = len(text)

    while i < n:
        end = i + chunk_size
        chunks.append(text[i:end])
        i = end - overlap

        if i < 0:
            i = 0

    return chunks


# --------------------------
# Indexing Function
# --------------------------
def index_chunks(text: str, collection: str = "logs") -> Dict[str, Any]:
    """
    Embeds text chunks and stores them in Qdrant.
    """
    chunks = chunk_text(text)
    if not chunks:
        return {"count": 0, "collection": collection}

    vectors = embedder.encode(chunks, show_progress_bar=False)
    dim = len(vectors[0])

    # Create vector collection
    qdrant.recreate_collection(
        collection_name=collection,
        vectors_config=rest.VectorParams(
            size=dim,
            distance=rest.Distance.COSINE
        )
    )

    # Upload chunks
    payloads = []
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        payloads.append(
            rest.PointStruct(
                id=idx,
                vector=vec.tolist(),
                payload={"chunk": chunk}
            )
        )

    qdrant.upsert(collection_name=collection, points=payloads)

    return {"count": len(chunks), "collection": collection}


# --------------------------
# Retrieval Function
# --------------------------
def retrieve_top_k(query: str, collection: str = "logs", k: int = 5) -> List[Dict[str, Any]]:
    """
    Robust retrieval: try qdrant client's search() if present; otherwise fall back to Qdrant REST search.
    Returns list of {"id", "score", "chunk"}.
    """
    # compute query vector
    qvec = embedder.encode([query])[0].tolist()

    # 1) Try qdrant client's search method if available
    try:
        search_fn = getattr(qdrant, "search", None)
        if callable(search_fn):
            results = qdrant.search(collection_name=collection, query_vector=qvec, limit=k)
            return [
                {"id": getattr(r, "id", None), "score": getattr(r, "score", None), "chunk": (getattr(r, "payload", {}) or {}).get("chunk")}
                for r in results
            ]
    except Exception:
        # if calling client search fails, fall back to REST below
        pass

    # 2) Fallback: Qdrant REST API
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
    endpoint = f"{qdrant_url}/collections/{collection}/points/search"

    payload = {
        "vector": qvec,
        "limit": k,
        "with_payload": True,
        "with_vector": False
    }

    try:
        resp = requests.post(endpoint, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # different server versions return the hits under different keys
        hits = data.get("result") or data.get("hits") or data.get("points") or []
        out = []
        for h in hits:
            # some responses have {'point': {id, payload}}; others are flat dicts
            if isinstance(h, dict) and "point" in h:
                pt = h["point"]
                pid = pt.get("id")
                payload = pt.get("payload", {}) or {}
                score = h.get("score")
                chunk = payload.get("chunk")
            else:
                pid = h.get("id")
                score = h.get("score")
                payload = h.get("payload", {}) or {}
                chunk = payload.get("chunk")
            out.append({"id": pid, "score": score, "chunk": chunk})
        return out
    except Exception as e:
        raise RuntimeError(f"Qdrant retrieval failed (client+REST): {e}")