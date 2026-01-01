# AI Log Analyzer – System Architecture

## 1. Overview
AI Log Analyzer is a backend service designed to automatically analyze CI/CD failure logs.
Instead of manually reading large log files, the system preprocesses logs, extracts relevant error
segments, performs semantic search using embeddings, and generates human-readable explanations
and fix suggestions using a Large Language Model (LLM).

The system is designed to be modular, scalable, and hardware-agnostic.

---

## 2. High-Level Architecture

The system consists of the following core components:

- **FastAPI Backend**
  - Handles API requests
  - Coordinates preprocessing, storage, embeddings, retrieval, and LLM calls

- **MinIO (Object Storage)**
  - Stores raw CI/CD logs
  - Acts as S3-compatible persistent storage

- **Qdrant (Vector Database)**
  - Stores embeddings of preprocessed log chunks
  - Enables semantic retrieval (RAG)

- **Remote LLM Server**
  - Runs on a separate machine due to local hardware constraints
  - Accessed securely over a private VPN (Tailscale)
  - Performs reasoning and fix generation

---

## 3. Data Flow

1. CI/CD log is submitted via `/analyze` API
2. Backend preprocesses the log to extract error-relevant lines
3. Reduced log text is chunked and embedded
4. Embeddings are stored in Qdrant
5. Relevant chunks are retrieved using semantic similarity
6. Retrieved chunks are sent to a remote LLM for analysis
7. Backend returns structured analysis and suggested fixes

---

## 4. Key Design Decisions

### Backend-First Architecture
The system is designed as a backend service that can integrate with any CI/CD pipeline
(GitHub Actions, Jenkins, GitLab CI).

### Preprocessing Before Embedding
Only error-relevant lines are embedded to reduce vector storage cost and improve retrieval quality.

### Remote LLM Inference
Due to limited local hardware, LLM inference is hosted on a remote machine.
This keeps the backend lightweight and allows independent scaling of the LLM.

### Secure Communication
The remote LLM is accessed via a private VPN (Tailscale), avoiding public exposure of inference APIs.

---

## 5. Scalability and Safety

- Raw logs and embeddings are stored separately
- LLM inference is isolated from core backend logic
- No automatic code changes are applied without human review
- System supports rollback via version control and CI/CD safeguards

---

## 6. Future Extensions

- CI webhook integration for automatic failure detection
- Frontend dashboard for incident review
- LLM streaming responses
- PR generation with human-in-the-loop approval
