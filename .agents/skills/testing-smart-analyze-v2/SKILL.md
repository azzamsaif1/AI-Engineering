---
name: testing-smart-analyze-v2
description: Test the Self-Adaptive Understanding Layer (POST /api/smart_analyze_v2) and the TechLingua Flask app end-to-end against the Docker Compose stack (Neo4j + Qdrant + Flask). Use when verifying smart_analyze_v2, term extraction, or Docker Compose startup.
---

# Testing the Self-Adaptive Understanding Layer (`/api/smart_analyze_v2`)

## What it is
`POST /api/smart_analyze_v2` (defined in `app.py`, backed by `backend/nlp/smart_understanding_layer.py`) runs a fully automatic NLP pipeline on raw `text`: auto language/domain/level detection, dynamic entity extraction (no hardcoded lists), BGE-M3 embeddings, KMeans clustering, and pattern-based relation detection. It is **authenticated** (`@login_required`) and **has no UI** — test it programmatically.

## Bring up the stack
```bash
cd docker
docker compose build flask      # first build is slow: ~1GB deps + spaCy models
docker compose up -d            # neo4j(healthy) + qdrant + flask on :5001
docker compose ps              # confirm all 3 up
```
- First `/api/smart_analyze_v2` call lazily downloads ~4GB of models (BGE-M3 `BAAI/bge-m3` + `facebook/bart-large-mnli`) **inside the Flask container**, cached in the `models_cache` volume. Use a long client timeout (>= 600s). Subsequent calls are fast.

### GOTCHA: Qdrant healthcheck
The `qdrant/qdrant` image is **distroless** (no shell, no `wget`/`curl`). A `wget`/`curl`-based Docker healthcheck will always fail, marking Qdrant `unhealthy` and (if Flask uses `depends_on: condition: service_healthy`) aborting the whole stack with `dependency failed to start: container techlingua-qdrant is unhealthy`. Qdrant itself is fine — `curl http://localhost:6333/readyz` returns 200 from the host. Fix: don't put a shell-based healthcheck on the qdrant service; gate Flask on qdrant `service_started` instead (Flask init is lazy/resilient and tolerates Qdrant not being ready yet).

## Auth path (intended programmatic client)
The app uses flask-login session cookies via JSON endpoints. Use a `requests.Session`:
```python
import requests, time
s = requests.Session(); u = f"tester_{int(time.time())}"
s.post("http://localhost:5001/register", json={"username": u, "password": "pw123456"})
s.post("http://localhost:5001/login",    json={"username": u, "password": "pw123456"})
r = s.post("http://localhost:5001/api/smart_analyze_v2", json={"text": "...", "session_id": 42}, timeout=1200)
```
`requests` may not be in the base venv — `pip install requests` first.

## Expected response shape & sanity values
For networking text like `"The TCP protocol uses a three-way handshake... The NIC card uses DMA... kernel manages interrupts and memory-mapped IO."`:
- `context.language == "en"`; German text → `"de"`.
- `context.domain == "computer networking and protocols"` at ~80-90% `domain_confidence` (zero-shot).
- `context.level` in {intermediate, advanced}.
- `entities.count` >= 5; dynamic acronyms `TCP`/`NIC`/`DMA` appear (regex + spaCy NER, no hardcoded list).
- `clusters.num_clusters` >= 2 (KMeans).
- `relations`: list, e.g. USES `card→DMA`, IMPLEMENTS `Python→garbage`.
- `semantic.dimension == 1024`, `summary.has_semantic_data == true` (BGE-M3).
- Echoes `session_id` and ISO `timestamp`.

## Edge / regression
- Short text (<20 chars), e.g. `{"text": "hi"}` → HTTP **400** `"Text too short for analysis (minimum 20 characters)"`.
- Regression: legacy `POST /api/smart_analyze` (v1) still returns 200 with `terms`/`topic`/`roadmap` keys (the rewritten `term_extractor.py` kept the `extract_terms(text, language) -> {terms, count}` signature).

## Notes
- Compose uses `neo4j:5-community` (the enterprise image needs a license-acceptance env var that blocks startup).
- Testing here is shell/HTTP-driven (no UI) — collect JSON responses as evidence; a screen recording isn't useful. Browser screenshots of `http://localhost:5001/` and the Qdrant dashboard `http://localhost:6333/dashboard` are good supporting proof the stack is live.

## Devin Secrets Needed
None. The stack runs fully locally with default in-compose credentials (`neo4j/password`). No external API keys required.
