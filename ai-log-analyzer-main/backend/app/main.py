# backend/app/main.py
import os
import uuid
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .llm import run_llm
from .preprocess import extract_relevant_lines, summarize_metadata
from .storage import store_log_bytes, get_log_bytes, ensure_bucket
from .embeddings import index_chunks, retrieve_top_k
from dotenv import load_dotenv

load_dotenv("backend/.env")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Log Analyzer Backend (wired POC)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)

# config (can be overridden via env)
LOGS_BUCKET = os.getenv("LOGS_BUCKET", "logs")
DEFAULT_COLLECTION_PREFIX = os.getenv("COLLECTION_PREFIX", "logs")

# ensure storage bucket exists on startup
try:
    ensure_bucket(LOGS_BUCKET)
except Exception as e:
    logging.warning("Could not ensure logs bucket: %s", e)


@app.get("/")
def root():
    return {"message": "AI Log Analyzer Backend Running"}


@app.post("/webhook/ci")
async def ci_webhook(request: Request):
    """
    Receive CI webhook. If payload contains `log_text` or `log_url` (or artifact URL),
    optionally store the raw log in MinIO and return an incident id and stored key.
    For POC, this endpoint echoes back metadata and stores if log_text provided.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    incident_id = str(uuid.uuid4())
    resp = {"incident_id": incident_id, "received": True, "payload_summary": {}}

    # If log_text provided, store it
    if "log_text" in payload and payload["log_text"]:
        raw_bytes = payload["log_text"].encode("utf-8", errors="replace")
        key = f"{incident_id}.log"
        try:
            store_log_bytes(raw_bytes, key, bucket=LOGS_BUCKET)
            resp["stored_log_key"] = key
        except Exception as e:
            logging.exception("failed to store provided log_text")
            resp["store_error"] = str(e)

    # If there is a log_url, we don't download here in POC (you can later implement download)
    if "log_url" in payload:
        resp["note"] = "log_url received but not auto-downloaded in POC"

    return JSONResponse(resp)


from .llm import run_llm

@app.post("/analyze")
async def analyze(request: Request):
    """
    Analyze endpoint:
    - preprocess logs
    - embed + index into Qdrant
    - retrieve top-k chunks
    - call remote LLM for explanation + fixes
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    raw_text = None
    stored_key = None
    incident_id = payload.get("incident_id") or str(uuid.uuid4())
    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"

    # -----------------------------
    # INPUT HANDLING
    # -----------------------------
    if "log_text" in payload and payload["log_text"]:
        raw_text = payload["log_text"]

        if payload.get("store", False):
            try:
                key = f"{incident_id}.log"
                store_log_bytes(
                    raw_text.encode("utf-8", errors="replace"),
                    key,
                    bucket=LOGS_BUCKET
                )
                stored_key = key
            except Exception:
                logging.exception("failed to store log_text")

    elif "log_key" in payload and payload["log_key"]:
        try:
            raw_bytes = get_log_bytes(payload["log_key"], bucket=LOGS_BUCKET)
            raw_text = raw_bytes.decode("utf-8", errors="replace")
            stored_key = payload["log_key"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="provide log_text or log_key")

    # -----------------------------
    # PREPROCESSING
    # -----------------------------
    reduced = extract_relevant_lines(raw_text)
    metadata = summarize_metadata(raw_text)

    # -----------------------------
    # EMBEDDINGS + INDEXING
    # -----------------------------
    try:
        index_result = index_chunks(reduced, collection=collection_name)
        indexed_count = index_result.get("count", 0)
        index_error = None
    except Exception as e:
        logging.exception("indexing failed")
        indexed_count = 0
        index_error = str(e)

    # -----------------------------
    # RETRIEVAL (RAG)
    # -----------------------------
    try:
        retrieved = retrieve_top_k(
            "Summarize the failure and suggest fixes",
            collection=collection_name,
            k=5
        )
        retrieval_error = None
    except Exception as e:
        logging.exception("retrieval failed")
        retrieved = []
        retrieval_error = str(e)

    # -----------------------------
    # LLM ANALYSIS (REMOTE)
    # -----------------------------
    llm_analysis = None

    if retrieved:
        context_blocks = []
        for idx, item in enumerate(retrieved, start=1):
            if item.get("chunk"):
                context_blocks.append(
                    f"[CHUNK {idx}]\n{item['chunk']}"
                )

#         llm_prompt = f"""
# You are an expert CI/CD debugging assistant.

# Below are extracted log snippets from a failed CI/CD pipeline.

# LOG CONTEXT:
# {chr(10).join(context_blocks)}

# TASK:
# 1. Explain the root cause clearly.
# 2. List 2–3 likely causes.
# 3. Suggest concrete fixes (commands, config, or code).
# 4. Mention assumptions if any.
# """
        
        llm_prompt = f"""
You are a senior CI/CD reliability engineer performing STRICT forensic analysis
of a FAILED CI/CD pipeline.

Your output will be reviewed for technical accuracy and auditability.

LOG CONTEXT:
{chr(10).join(context_blocks)}

NON-NEGOTIABLE RULES:
- Use ONLY facts explicitly present in the logs.
- If a fact is not explicitly present, it MUST NOT appear.
- Do NOT speculate, generalize, or suggest "possible" causes without evidence.
- If multiple failures appear, you MUST:
  • list earlier failures
  • identify the FINAL BLOCKING failure
- A failure is FINAL BLOCKING ONLY if:
  • subsequent stages did not execute OR
  • the pipeline summary confirms it
- EVERY cause MUST reference at least one exact log line.
- If a cause has no supporting log line, DO NOT include it.
- Fixes MUST be reproducible and configuration-based.
- Do NOT suggest fixes that could worsen compatibility.

TASKS:

1. Root Cause
   - Identify the FINAL BLOCKING failure.
   - Quote the exact log lines proving it.

2. Likely Causes (MAX 2)
   - Include ONLY causes with direct log evidence.
   - Rank by likelihood (High / Medium).
   - Explicitly reference supporting log lines.

3. Concrete Fixes
   - Provide fixes ONLY for the listed causes.
   - Prefer Dockerfile or requirements.txt changes.
   - Include exact snippets.

4. Assumptions
   - List ONLY unavoidable assumptions.
   - If none are required, state:
     "None required based on available logs."

STRICT OUTPUT FORMAT:
Root Cause:
Likely Causes:
Concrete Fixes:
Assumptions:
"""


        llm_analysis = run_llm(llm_prompt)

    # -----------------------------
    # FINAL RESPONSE
    # -----------------------------
    resp = {
        "incident_id": incident_id,
        "stored_key": stored_key,
        "collection": collection_name,
        "reduced_preview": reduced[:2000],
        "reduced_length": len(reduced),
        "metadata": metadata,
        "indexed_count": indexed_count,
        "index_error": index_error,
        "retrieved_top_k": retrieved,
        "retrieval_error": retrieval_error,
        "llm_analysis": llm_analysis
    }

    return JSONResponse(resp)
