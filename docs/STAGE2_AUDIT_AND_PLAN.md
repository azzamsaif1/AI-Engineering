# Stage 2 — Architecture Audit, Refactoring Plan & Implementation Roadmap

## A. Architecture Audit

### Repo Structure Summary

| Directory | State | Purpose |
|-----------|-------|---------|
| `app.py` (1131 lines) | **Monolith** | ALL DB models, ALL routes, ALL component wiring |
| `backend/` | Active | 6 subdirs: nlp, embeddings, vector_db, knowledge_graph, recommendation, topic_modeling |
| `engines/` | Mixed | 3 with content (ghost 461L, prediction 426L, topic 58L); 3 empty placeholders |
| `api/` | **Dead code** | 5 files, ALL 0 lines (auth, competition, ghost, session, translation) |
| `models/` | **Dead code** | 10 files, ALL 0 lines (models live inline in app.py) |
| `feature/` | Specs only | 20 stage-foundation dirs (2.7MB text); no executable code |
| `docs/` | Mostly empty | 3 of 4 files are 0 lines |
| `tests/` | Exists | 3 test files |

**Finding:** Significant dead code. `api/` and `models/` were intended as modular decompositions of `app.py` but never populated. Empty `engines/` files (`ai_engine.py`, `competition_engine.py`, `focus_engine.py`) are placeholders.

---

### Overlap Analysis with Stage 2 Layers

#### 1. Embeddings — 3 separate BGE-M3 instantiations (DUPLICATION)

| Location | Class | Model | Notes |
|----------|-------|-------|-------|
| `backend/embeddings/sentence_encoder.py` | `TechnicalEncoder` | `BAAI/bge-m3` | Used by `/api/smart_analyze`, `/api/semantic_search` |
| `backend/topic_modeling/topic_detector.py` | `SmartTopicDetector` | `BAAI/bge-m3` | Loads its own `SentenceTransformer` (duplicate) |
| `backend/nlp/smart_understanding_layer.py` | `_SharedModels` | `BAAI/bge-m3` | Singleton; used by v2 pipeline |

**Risk:** Each instance loads ~2.3GB into memory. Three copies = ~7GB wasted. `_SharedModels` was designed to consolidate this, but `TechnicalEncoder` and `SmartTopicDetector` still load independently.

#### 2. Vector Storage — DIMENSION MISMATCH BUG

`backend/vector_db/qdrant_client.py` creates collections with `size=768`, but BGE-M3 produces **1024-dim** vectors.

```python
# qdrant_client.py line 11 — WRONG
VectorParams(size=768, distance=Distance.COSINE)
# BGE-M3 actual output — 1024
```

**Impact:** `/api/semantic_search` will crash or silently fail on any real query. Additionally, **nothing ever calls `vector_store.upsert()`** — there is no data ingestion pipeline, so Qdrant is always empty.

#### 3. Semantic Search — BROKEN

`/api/semantic_search` (app.py:1068) calls `get_encoder().encode()` → `get_vector_store().search()`, but:
- Dimension mismatch (1024 vector → 768 collection) causes Qdrant error
- Empty collection means 0 results even if dimensions matched
- No endpoint or pipeline populates the collection

#### 4. Reasoning / Code Understanding — NONE (regex-only)

| Engine | Lines | Approach | AST? | ML? |
|--------|-------|----------|------|-----|
| `ghost_engine.py` | 461 | Regex templates for code prediction | No | No |
| `prediction_engine.py` | 426 | Character/line comparison via patterns | No | No |
| `topic_engine.py` | 58 | Hardcoded keyword-count matching (8 categories) | No | No |

None of these engines parse code structure. Stage 2 Layer 7 (Code Understanding via Tree-sitter) fills this gap entirely.

#### 5. Roadmap Generation — TRIVIAL

`backend/recommendation/roadmap_generator.py` (21 lines of logic): iterates first 10 concepts, assigns "2 hours" to each. No graph traversal, no user-adaptive logic, no dependency ordering.

#### 6. Graph Knowledge — REUSABLE

`backend/knowledge_graph/graph_builder.py` (`KnowledgeGraphBuilder`): real Neo4j integration with `add_concept`, `add_relation`, `get_learning_path`. Used by `/api/smart_analyze` and `/api/learning_roadmap`. Stage 2 Layer 9 should **extend** this, not replace it.

#### 7. Topic Detection — THREE OVERLAPPING IMPLEMENTATIONS

| Implementation | Approach | Quality |
|----------------|----------|---------|
| `engines/topic_engine.py` | Hardcoded keyword counting (8 categories) | Low |
| `backend/topic_modeling/topic_detector.py` | Stub: returns `text[:50]` | None |
| `smart_understanding_layer.py` SmartContextDetector | Zero-shot `bart-large-mnli` (12 domains) | **Production** |

**Recommendation:** The smart layer's zero-shot approach subsumes both older implementations.

---

### Critical Issues

1. **BGE-M3 loaded 3× in separate processes** — ~7GB wasted memory
2. **Qdrant dimension mismatch** (768 vs 1024) — semantic_search is broken
3. **No vector ingestion pipeline** — Qdrant always empty
4. **Monolithic `app.py`** — 1131 lines, all models/routes/logic in one file
5. **Dead code scaffolding** — 15+ empty files in `api/`, `models/`, `engines/`, `docs/`
6. **Hardcoded competitors** — competition uses `random.random()` for rival accuracy
7. **No code understanding** — ghost/prediction engines parse code as text, not AST

---

### What Stage 2 Can REUSE

| Existing Code | Stage 2 Layer | How |
|---------------|---------------|-----|
| `KnowledgeGraphBuilder` | L9 Code Knowledge Graph | Extend with code-specific node/edge types |
| `QdrantVectorStore` | L10 Long-term Memory | Fix dimension, add user-scoped collections |
| `_SharedModels` singleton | All | Extend for new model loading |
| `_get_component()` lazy registry | All | Add new components via same pattern |
| `docker-compose.yml` | Infra | Already has Neo4j + Qdrant + Flask |
| `UserFingerprint` model | L10 | Extend for programmer proficiency tracking |
| `CompetitionSession` model | L12 | Extend for adaptive difficulty |
| `SelfAdaptiveUnderstandingLayer` | L7-L9 | Feed code analysis into smart layer |

---

## B. Repository Refactoring Plan

### Phase 0 — Prerequisites (done in Stage 2 PR)

| # | Task | Risk | Effort |
|---|------|------|--------|
| B0.1 | Fix Qdrant `VectorParams(size=768)` → `size=1024` | High (broken endpoint) | 1 line |
| B0.2 | Consolidate BGE-M3 instantiation: make `TechnicalEncoder` and `SmartTopicDetector` share `_SharedModels.encoder` | High (memory waste) | ~20 lines |

### Phase 1 — Cleanup (future PRs, not blocking Stage 2)

| # | Task | Priority |
|---|------|----------|
| B1.1 | Extract DB models from `app.py` into `models/` (populate empty files) | Medium |
| B1.2 | Extract route handlers into `api/` Flask Blueprints | Medium |
| B1.3 | Remove or populate empty engines (`ai_engine.py`, `competition_engine.py`, `focus_engine.py`) | Low |
| B1.4 | Retire `engines/topic_engine.py` keyword matcher (superseded by zero-shot) | Low |
| B1.5 | Retire `backend/topic_modeling/topic_detector.py` stub | Low |

---

## C. Stage 2 Implementation Roadmap

### Module Priority Matrix

| Priority | Module | Layer | Feasibility | GPU? | Reuse | Approach |
|----------|--------|-------|-------------|------|-------|----------|
| **1 (THIS PR)** | **Code Understanding (Tree-sitter)** | 7 | ✅ Production | No | New | AST parsing for Python/Java/JS/C++ |
| 2 | Performance Analysis | 8 | ✅ Feasible | No | Builds on L7 | Complexity + bottleneck detection from AST |
| 3 | Code Knowledge Graph | 9 | ✅ Feasible | No | Extend `graph_builder` | Code-specific concepts → Neo4j |
| 4 | Long-term Memory | 10 | ✅ Feasible | No | Fix + extend `vector_store` | User error/evolution tracking |
| 5 | Multi-Agent Orchestrator | 11 | 🟡 Partial | No | New (lightweight) | Python orchestration, no LangGraph needed |
| 6 | Adaptive Competition | 12 | 🟡 Partial | No | Extend competition | Difficulty scaling + personalized challenges |

### EXCLUDED with justification

| Tool | Layer | Why excluded |
|------|-------|-------------|
| **DeepSeek-Coder** (6.7B) | L7 | Requires GPU + 13GB+ VRAM. Not feasible to run end-to-end without GPU hardware. Can be added later behind an optional API/config key. |
| **Joern** | L7 | Requires Java runtime + significant setup. Tree-sitter covers the core AST needs; Joern adds data-flow analysis that can be layered on later. |
| **LLVM** | L8 | Requires LLVM toolchain + C/C++ compilation chain. Out of scope for a Python/Flask app. |
| **LangGraph / CrewAI** | L11 | Heavyweight frameworks unnecessary for initial multi-agent coordination. Simple Python orchestration (function composition + routing) suffices and avoids dependency bloat. |
| **Ray RLlib / Stable Baselines3** | L12 | Requires training data + RL infrastructure. Premature — rule-based adaptive difficulty (ELO-like) is production-ready without ML. |

### Dependency Chain

```
Layer 7 (Code Understanding)      ← IMPLEMENT FIRST (no deps)
    ↓
Layer 8 (Performance Analysis)    ← needs L7 AST output
    ↓
Layer 9 (Code Knowledge Graph)    ← needs L7 entities + existing Neo4j
    ↓
Layer 10 (Long-term Memory)       ← needs L9 + fixed Qdrant
    ↓
Layer 11 (Multi-Agent)            ← orchestrates L7-L10
    ↓
Layer 12 (Adaptive Competition)   ← needs L10 user profile + L11 agents
```

---

## D. First Module: Code Understanding (Tree-sitter AST Analyzer)

### What it does
Parses code in Python, Java, JavaScript, and C++ into an Abstract Syntax Tree using Tree-sitter, then extracts structured information:

- **Functions**: name, parameters, line range, nesting depth, cyclomatic complexity estimate
- **Classes**: name, methods, line range
- **Imports**: module names, aliased imports
- **Call graph**: which functions call which
- **Control flow**: loops, conditionals, nesting depth
- **Complexity metrics**: cyclomatic complexity, max nesting, lines per function

### Why this is the right first module
1. **No GPU required** — Tree-sitter is deterministic, fast, and lightweight
2. **Fills the biggest gap** — the repo has zero code understanding capability
3. **Foundation for Layers 8-12** — performance analysis, code graphs, all depend on AST
4. **Production-ready** — not a stub; real parsing with real metrics
5. **Incrementally useful** — works standalone via API even before later layers exist

### API Endpoint
`POST /api/code/analyze`

Request:
```json
{"code": "def foo():\n    pass", "language": "python"}
```

Response:
```json
{
  "language": "python",
  "structure": {
    "functions": [...],
    "classes": [...],
    "imports": [...]
  },
  "metrics": {
    "total_functions": 1,
    "total_classes": 0,
    "max_complexity": 1,
    "max_nesting": 0,
    "avg_function_length": 1
  },
  "call_graph": [...],
  "summary": "1 function, 0 classes, complexity 1"
}
```

### Files
- `backend/code_understanding/__init__.py`
- `backend/code_understanding/ast_analyzer.py` — main module
- `app.py` — new endpoint + lazy component wiring
- `requirements.txt` — tree-sitter dependencies
- `docker/Dockerfile` — install tree-sitter at build time
