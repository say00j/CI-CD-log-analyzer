AI Log Analyzer — Backend (Phase 1 Complete)

An intelligent backend service that accepts CI/CD logs, preprocesses them, embeds them, stores vectors in Qdrant, and retrieves relevant log chunks for LLM-based analysis.

✔ Completed Features (Phase 1)

FastAPI backend

CI log preprocessing (traceback detection, error extraction)

MinIO object storage integration

SentenceTransformer embeddings

Qdrant vector indexing + fallback retrieval

/analyze endpoint returning:

Preprocessed text

Metadata (error count, traceback flag)

Indexed vector chunks

Retrieved top-k similar chunks

✔ Technology Stack

Python 3.12

FastAPI

MinIO (S3-compatible storage)

Qdrant (Vector DB)

SentenceTransformers (MiniLM)

Docker + docker-compose

✔ How to Run (Development)
docker compose -f infra/docker-compose.yml up -d
uvicorn backend.app.main:app --reload --port 8000

✔ Test the API
curl.exe --% -X POST http://localhost:8000/analyze `-H "Content-Type: application/json" `-d "{\"log_text\":\"Traceback...\"}"

✔ Next Milestones

Phase 2: LLM analysis module

Phase 3: CI webhook integration (GitHub Actions/Jenkins)

Phase 4: Frontend dashboard