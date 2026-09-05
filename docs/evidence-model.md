# Evidence & Citation Model

In RoadmapAI, every recommended skill, milestone, and resource can be audited through **verifiable evidence citations**.

## Domain Entities

### `Source`
Represents an external document, webpage, job posting, or repository.
- `id`: Unique identifier (UUIDv4).
- `url`: Canonical URL of the source.
- `title`: Extracted title or publication title.
- `source_type`: `SourceType` enum (`job_posting`, `official_documentation`, `university_curriculum`, `course`, `book`, etc.).
- `publisher`: Publisher or organization name.
- `domain`: Hostname / domain name (e.g. `docs.python.org`).
- `reliability_score`: Float between 0.0 and 1.0 assessed by `SourceScorer`.
- `content_hash`: SHA-256 hash of the extracted text content.
- `retrieved_at` & `published_at`: UTC timestamps.

### `Evidence`
Represents a discrete factual claim or requirement extracted from a `Source`.
- `id`: Unique identifier.
- `source_id`: Foreign key referencing `Source.id`.
- `extracted_claim`: Concrete factual statement or skill requirement extracted from the source.
- `confidence`: Assessed confidence of the claim extraction (0.0 - 1.0).
- `relevance`: Relevance to the targeted career path (0.0 - 1.0).
- `associated_skill_names`: List of skills directly supported by this evidence snippet.

### `ResearchRun`
Records metadata for an execution of the research pipeline.
- `id`: Unique run identifier.
- `profile_id`: Associated user profile.
- `topic`: Career role or technical subject.
- `target_market`: Market context (e.g. "US Tech Companies").
- `status`: `started`, `completed`, `partial`, or `failed`.
- `queries`: Array of search queries executed.
- `source_count` & `evidence_count`: Summary counts.
- `started_at` & `completed_at`: UTC execution timestamps.
