# ADR-020: Knowledge Intelligence — Embeddings, Semantic Retrieval, and Evidence-Grounded RAG

## Status
Accepted

## Context
RoadmapAI previously accumulated rich market intelligence, web research sources, and discrete evidence claims across MVP-3, MVP-4, and MVP-5. However:
1. Research evidence was keyed primarily by exact skill name matches or manual aggregation.
2. Conceptual inquiries ("memory management", "data-oriented design", "multithreading paradigms") could not retrieve semantically related evidence if exact keyword overlap was absent.
3. LLM generation could potentially hallucinate synthetic or ungrounded evidence identifiers when reasoning over research materials.

MVP-6 establishes a robust Knowledge Intelligence layer providing semantic vector indexing, cosine similarity retrieval, evidence-grounded prompt assembly, and deterministic citation validation.

## Invariant: Canonical Evidence as Authoritative Truth
A fundamental principle of RoadmapAI is that **vector similarity is strictly a candidate retrieval heuristic, never a source of truth**.
- Authoritative truth resides exclusively in the canonical `sources` and `evidence` relational tables.
- A vector hit that cannot be joined to a valid, non-deleted canonical `Evidence` row is discarded.
- Synthetic or hallucinated evidence references proposed by LLMs are deterministically caught and rejected.

## Decision

### 1. Layered Knowledge Domain Architecture
We introduced dedicated entities in the domain layer (`roadmap.domain.entities.knowledge`):
- `KnowledgeDocument`: Synchronized snapshot of canonical evidence content, maintaining document indexing status (`PENDING`, `INDEXING`, `READY`, `FAILED`) and a SHA-256 `content_hash`.
- `KnowledgeChunk`: Deterministic, boundary-aware slice of a document with sequence index and content hash.
- `EmbeddingRecord`: Persistent normalized vector embedding associated with a specific chunk.
- `RetrievalQuery`, `RetrievalFilter`, and `RetrievalResult`: Domain value objects for parameterized semantic search.
- `EvidenceContextBlock` and `EvidenceContext`: Prompt-ready structures carrying canonical citation metadata (`evidence_id`, `source_url`, `source_title`, `is_authoritative`).

### 2. Pure Deterministic Chunker (`KnowledgeChunker`)
- Implemented as a domain service (`roadmap.domain.services.knowledge_chunker`) with zero external or LLM dependencies.
- Natural boundary detection: breaks chunks cleanly on paragraph breaks (`\n\n`), newlines (`\n`), or sentence terminators (`. `, `? `, `! `) before falling back to character bounds.
- Sliding window with configurable `chunk_size` (default: 500 chars) and `chunk_overlap` (default: 50 chars).
- Preserves chunk sequence index (`chunk_index`) and generates deterministic SHA-256 hashes for each chunk.

### 3. Embedding Provider Port & Adapters
- **Port**: `EmbeddingProvider` protocol in `roadmap.application.ports.embedding_provider` specifying `embed_text(text: str) -> list[float]`, `embed_batch(texts: list[str]) -> list[list[float]]`, `dimension: int`, `model_name: str`, and `provider_name: str`.
- **Gemini Adapter**: `GeminiEmbeddingProvider` utilizing Google Gemini `gemini-embedding-001` with explicit output dimensionality configuration (`types.EmbedContentConfig(output_dimensionality=768)`) via the `google-genai` SDK. Validates returned dimension at runtime and enforces L2 unit normalization.
- **Fake Adapter**: `FakeEmbeddingProvider` for offline, hermetic testing and development. Generates deterministic unit-normalized pseudo-random vectors seeded from the text's SHA-256 hash.

### 4. Embedding Identity Tuple & Re-indexing Safety
Embeddings are strictly identified by a 5-tuple:
`(content_hash, provider, model, dimension, embedding_version)`
- Reuse is permitted **only** when all five elements match and document status is `READY`.
- If the content, provider, model, dimension, or version changes, the existing document is invalidated and re-indexed.
- Cross-model vector comparisons are strictly forbidden: `SqliteVectorStore` pre-filters candidates by `provider`, `model`, and dimension (`len(query_vector)`), preventing comparisons across different embedding spaces.

### 5. Local-First SQLite Vector Store (`SqliteVectorStore`)
- Relational schema with three new Alembic-managed tables:
  - `knowledge_documents` (foreign key to `evidence.id` with `ON DELETE CASCADE`)
  - `knowledge_chunks` (foreign key to `knowledge_documents.id`)
  - `embedding_records` (foreign key to `knowledge_chunks.id`)
- Vector search runs in-process using pure Python cosine similarity over stored vector lists.
- Deterministic multi-attribute tie-breaking:
  `sort_key = (-similarity, evidence_id, chunk_index)`
- Pre-filtering and post-filtering support:
  - Required `provider` and `model` (matches query embedding model)
  - Allowed `evidence_ids`
  - Required `skill_names`
  - Target `domain`
  - `source_types`
  - Minimum similarity threshold `min_similarity`

### 6. Separation of Retrieval and Generation
- `RAGService` orchestrates `SemanticRetrievalService` and `EvidenceContextBuilder`. It executes vector retrieval, canonical verification, and prompt-ready context formatting **without invoking an LLM**.
- Semantic retrieval and indexing consume **zero LLM generation request budget**.
- `GroundedReasoningService` handles grounded generation and enforces a deterministic validation gate:
  - Injects retrieved context with clear system prompt boundaries (`<user_query>`, `<retrieved_evidence>`).
  - Instructs the model that retrieved text is untrusted data and cannot issue administrative instructions.
  - Inspects `cited_evidence_ids` returned by the LLM.
  - Verifies that every cited ID exists within `context.cited_evidence_ids`.
  - Rejects ungrounded citations into `rejected_citations` and penalizes response confidence accordingly.

### 7. CLI Management
- `roadmap knowledge stats`: Displays canonical sources/evidence counts, indexed documents, chunks, and vector storage statistics.
- `roadmap knowledge index [--force]`: Executes the incremental indexing pipeline with SHA-256 change detection and identity tuple validation.
- `roadmap knowledge search <query> [--top-k N] [--threshold F] [--skill S] [--domain D] [--json]`: Performs semantic retrieval and prints formatted evidence cards with authoritativeness flags.

## Consequences

### Positive
- Full semantic search capability across all collected market research and curricula.
- Local-first architecture requiring no Docker, Redis, or pgvector dependencies.
- 100% offline reproducible testing via `FakeEmbeddingProvider`.
- Real semantic relevance verified empirically via `gemini-embedding-001` (768d).
- Strong provenance invariants prevent hallucinations from polluting recommendations or roadmaps.
- Zero impact on LLM generation rate limits and request quotas during search and indexing.

### Negative / Trade-offs
- In-process cosine similarity over SQLite table rows is optimized for local-first scales (thousands of chunks). For enterprise scale (>100k chunks), an external index (such as sqlite-vss or pgvector with `hnsw`/`ivfflat` indexes) would be required.
- Requires initial indexing step (`roadmap knowledge index`) before semantic search is populated.

### Future PostgreSQL / pgvector Migration Path
When deploying to production with PostgreSQL:
- The `vector_json` column on `embedding_records` maps to `pgvector`'s native `vector(768)` type.
- Cosine similarity computation moves from application in-process Python to SQL `ORDER BY vector <=> query_vector` indexed with an HNSW or IVFFlat index.
- All domain and application logic (`RAGService`, `EvidenceContextBuilder`, `GroundedReasoningService`) remains completely untouched due to the Port/Adapter abstraction.
