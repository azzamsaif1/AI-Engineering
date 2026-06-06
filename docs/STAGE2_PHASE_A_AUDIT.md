# Stage 2 — Phase A: Full Repository Audit

Scope: Python, HTML, CSS, JS, API routes, Vector DB, Knowledge Graph. Goal: confirm
the system is free of hardcoded **terms / domains / concepts / learning paths**, surface
duplication and scalability risks, and define the consistency fixes that precede Phase C.

---

## 1. Hardcoded content found

| # | Location | What is hardcoded | Severity | Action |
|---|----------|-------------------|----------|--------|
| H1 | `engines/topic_engine.py` (`DynamicTopicAnalyzer`) | **8 fixed domains** (`Algorithms`, `Databases`, `Networks`, `Web`, `Programming`, `Security`, `AI`, `Cloud`) each with a hardcoded keyword list; topic = max substring-count | High | Recommend unifying on the semantic layer (see §4); **needs product decision** because it is on the real-time audio path |
| H2 | `backend/recommendation/roadmap_generator.py` | Every step gets a constant `'estimated_time': '2 hours'`; takes first 10 concepts; no ordering | Medium | De-hardcoded in this phase (derive time from level/length; preserve order) |
| H3 | `backend/nlp/smart_understanding_layer.py` `ADVANCED_INDICATORS` | 14-word keyword list drives `level` heuristic | Low | Acceptable heuristic; documented, left as-is (no behavior risk) |
| H4 | `backend/nlp/smart_understanding_layer.py` `DOMAINS` | 12-label taxonomy for **zero-shot** classification | Low (soft) | Not pure hardcoding — labels are matched *semantically* by `bart-large-mnli`, not by keyword. Kept; can be made configurable later |

> H3/H4 are bounded, semantic, or heuristic — not the keyword-matching anti-pattern the
> directive targets. H1 is the real offender (pure substring counting over a fixed taxonomy).

No hardcoded **terms** remain in extraction: both `TechnicalTermExtractor` and
`DynamicEntityExtractor` use spaCy NER + noun-chunking + generic regex patterns (CamelCase,
acronyms, snake/kebab-case), not term lists. No hardcoded **learning paths** in the graph:
`KnowledgeGraphBuilder.get_learning_path` is a Cypher `shortestPath` over `:REQUIRES` edges.

## 2. Duplication & scalability risks

- **R1 — BGE-M3 loaded up to 3×** (~2.3 GB each ⇒ ~7 GB): `_SharedModels.encoder`
  (smart layer), `TechnicalEncoder` (`get_encoder`), and `SmartTopicDetector.__init__`
  (which loads the model but **never uses it** — pure waste). *Fixed in this phase:*
  `TechnicalEncoder` now delegates to the `_SharedModels` singleton; the dead load in
  `SmartTopicDetector` is removed.
- **R2 — Empty Qdrant**: nothing ever upserts vectors, so `/api/semantic_search` always
  returns `[]`. Dimension was fixed (768→1024) in #3; an **ingestion pipeline** is the
  Layer 9 (Vector Memory) deliverable.
- **R3 — `SmartTopicDetector` is a stub**: returns `name = text[:50]`, `confidence = 0.7`
  regardless of input. Used by the legacy `/api/smart_analyze` (v1).

## 3. Dead scaffolding (unreferenced, 0 lines)

Verified no Python import or template reference targets any of these:
`api/` (6 files), `models/` (10 files), `engines/{ai_engine,competition_engine,focus_engine}.py`,
`components/` (4 JS files), `static/js/competition.js`. Real DB models and routes live inline
in `app.py`; real engines are `ghost_engine`, `prediction_engine`, `topic_engine`.
*Removed in this phase* to eliminate misleading structure. (`tests/` empty files are left in
place pending a real test suite.)

## 4. Frontend integration gap (the "important point")

Frontend (`templates/index.html`, `static/js/*`) calls only legacy endpoints. The new
capabilities are **not surfaced anywhere in the UI**:

| Capability | Backend endpoint | Consumed by UI? |
|------------|------------------|-----------------|
| Self-Adaptive Understanding | `POST /api/smart_analyze_v2` | ❌ no |
| Code Understanding (AST) | `POST /api/code/analyze` | ❌ no |
| Topic detection | `POST /api/topic/detect` (hardcoded H1) | ✅ yes |

This is the dedicated **Frontend phase**: expose & visualize discovered concepts, semantic
clusters, detected relations, code structure, complexity metrics, and confidence scores.

**Open decision (H1):** `/api/topic/detect` runs on the live audio loop where the hardcoded
matcher is instant. Routing it through the semantic layer (`SmartContextDetector`) removes
the hardcoding but adds a `bart-large-mnli` zero-shot call (~seconds on CPU) per request.
Options: (a) replace + throttle/cache, (b) keep fast matcher for live + add a semantic
"confirm" pass, (c) replace outright. Recommend (a). Flagged for confirmation before
touching the real-time path.

## 5. Phase A changes applied (this PR)

1. **De-hardcode roadmap** (H2): `estimated_time` derived per concept; order preserved.
2. **Consolidate BGE-M3** (R1): single shared encoder; removed dead model load in stub.
3. **Remove dead scaffolding** (§3).
4. Audit documented (this file).

Deferred (with justification): H1 unification (needs product decision, §4), Qdrant
ingestion (Layer 9), frontend visualizations (Frontend phase).
