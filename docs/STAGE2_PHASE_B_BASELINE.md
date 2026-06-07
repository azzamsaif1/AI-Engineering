# Stage 2 — Phase B Final Cleanup Baseline

**Goal:** remove all remaining hardcoded classification logic and route every
entry point through a single semantic source of truth — `UnifiedIntentEngine`
(a wrapper over `SelfAdaptiveUnderstandingLayer`). After this cleanup there is
**zero keyword-based topic/domain classification anywhere** (Python, JS, HTML).

## What was removed

| Location | Hardcoded thing removed | Replaced by |
|---|---|---|
| `engines/topic_engine.py` | `DynamicTopicAnalyzer` — 8 fixed categories + keyword lists (**file deleted**) | `UnifiedIntentEngine.detect_topic()` |
| `app.py` | `TOPIC_CATEGORIES` dict (8 categories: keywords/subtopics/icons/colors) | semantic domain inference |
| `app.py` | `detect_topic_from_text()` (substring keyword matching) | `UnifiedIntentEngine.detect_topic()` |
| `app.py` | `generate_title()` (per-category hardcoded titles) | semantic `display_name` |
| `backend/topic_modeling/topic_detector.py` | `SmartTopicDetector` (now-orphaned) (**file deleted**) | — |
| `static/js/ghost.js` | `getTopicIcon()` keyword→emoji map (frontend keyword classification) | backend-provided `icon`/`color` |
| `static/js/ghost.js` | `testShowTopicCard()` + 3s timer injecting a fake hardcoded topic | removed |
| `static/js/script.js` | 2s timer injecting a fake hardcoded "Algorithms" topic card | removed |

## Single source of truth

`backend/nlp/unified_intent_engine.py` → `UnifiedIntentEngine`

- `analyze(text)` → full self-adaptive payload (delegates to `SelfAdaptiveUnderstandingLayer`).
- `detect_topic(text)` → compact, frontend-ready descriptor
  `{category, title, name, display_name, icon, color, confidence, keywords, subtopics, language, level, topic_id}`.
- Process-wide singleton (`UnifiedIntentEngine.instance()`) so **all** entry
  points share one engine, one model load, and one cache.
- **Realtime safety:** `detect_topic` is debounced/cached (default 8s TTL): an
  unchanged transcript buffer returns the cached descriptor instead of re-running
  the heavy pipeline. The only lookups in the engine are *presentation* helpers
  (emoji + colour per semantic domain label); they never affect classification.

## Post-cleanup architecture (Stage 2 baseline)

```
                         INPUT (text / code / voice transcript)
                                        │
        ┌───────────────────────────────┼─────────────────────────────────┐
        │ ENTRY POINTS (all semantic; zero keyword classification)         │
        │                                                                  │
        │  REST: /api/smart_analyze_v2 ─────────────┐                      │
        │  REST: /api/smart_analyze (v1) ──┐         │                      │
        │  REST: /api/topic/detect ────────┤         │                      │
        │  Realtime: /api/save_transcript ─┤  topic  │ full analysis        │
        │            → socket topic_detected         │                      │
        │  Audio CLI: audio_listener.py ───┤         │                      │
        │  Frontend: ghost.js (poll 8s),   │         │                      │
        │            focus.js (socket) ────┘         │                      │
        └──────────────────┬─────────────────────────┬─────────────────────┘
                           ▼                          ▼
                 UnifiedIntentEngine          SelfAdaptiveUnderstandingLayer
                 .detect_topic() ───────────► .analyze()  (also called directly
                 (debounce + cache +                       by smart_analyze_v2 &
                  presentation theming)                    Code/Performance paths)
                           │
                           ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │           SelfAdaptiveUnderstandingLayer  (semantic pipeline)      │
        │  • language detection      langdetect                              │
        │  • domain inference        zero-shot (facebook/bart-large-mnli)    │
        │  • entity extraction       spaCy NER + noun-chunks + regex         │
        │  • semantic embeddings     BGE-M3 (BAAI/bge-m3, 1024-dim) singleton│
        │  • semantic clustering     KMeans over embeddings                  │
        │  • relation detection      dependency/pattern based               │
        │  • confidence scoring      zero-shot score                         │
        └──────────────────────────────────────────────────────────────────┘

   Code paths (unchanged, semantic/AST — no keywords):
     /api/code/analyze      → ASTAnalyzer (Tree-sitter)        [Layer 7]
     /api/code/performance  → PerformanceAnalyzer (on AST)     [Layer 8]

   Stores: Qdrant (1024-dim vectors) · Neo4j (knowledge graph)
```

## Verification (live Docker stack: Neo4j + Qdrant + Flask :5001)

Regression — **all PASS**:

| Check | Result |
|---|---|
| Smart Analysis `/api/smart_analyze_v2` | 200 · en · "computer networking and protocols" @89% · 13 entities · 4 clusters · dim 1024 |
| Topic detect `/api/topic/detect` (unified) | 200 · semantic domain @89% · icon/color from backend · dynamic keywords TCP/NIC/DMA · subtopics from clusters |
| Topic detect (German) | 200 · semantic language detection |
| v1 `/api/smart_analyze` regression | 200 · topic now from UnifiedIntentEngine |
| Code Analysis `/api/code/analyze` | 200 · 3 functions · 1 class |
| Performance `/api/code/performance` | 200 · score 90 · O(n²) · 1 bottleneck |
| Edge: short text | 400 |
| Audio path (`audio_listener.py`) | imports clean · shares singleton · cache hit ~0s after 7.2s cold |

**Zero-keyword grep proof:** no references to `TOPIC_CATEGORIES`,
`detect_topic_from_text`, `generate_title`, `DynamicTopicAnalyzer`,
`SmartTopicDetector`, or `getTopicIcon` remain in code (only doc comments).

## Known tradeoff (flagged, not hidden)

A fresh semantic classification costs ~7s on CPU (zero-shot BART-large-mnli);
sub-second on GPU. The realtime audio path is therefore **debounced** (runs at
most once per ~8s window, served from cache otherwise) so live transcription
stays responsive. If sub-second fresh classification on CPU becomes a hard
requirement, swap the zero-shot domain step for a smaller distilled classifier.
