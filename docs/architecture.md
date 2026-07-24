# Architecture

## Design goals

- Deploy on one Linux host with Docker Compose.
- Keep the RAG implementation observable and replaceable.
- Prefer deterministic rules for identifiers, metadata, citations, and authorization.
- Keep chat generation and embedding behind independent provider ports.
- Make retrieval quality measurable without requiring a live model in CI.

## Deep modules

### Ingestion module

Small interface: submit a source, observe its job.

Implementation hides parsing, heading-aware parent/child chunking, hashing, deduplication,
embedding batches, persistence, retries, and job progress.

### Investigation module

Small interface: ask a question in a knowledge base.

Implementation hides query rewriting, lexical and vector retrieval, reciprocal-rank fusion,
reranking, parent expansion, citation numbering, grounded generation, and trace assembly.

### Evaluation module

Small interface: run an evaluation suite.

Implementation hides per-case execution, retrieval metrics, citation validation,
faithfulness checks, aggregation, and regression comparison.

## Runtime topology

```text
Browser -> Nginx -> React
                  -> FastAPI
FastAPI -> PostgreSQL + pgvector
        -> external OpenAI-compatible chat endpoint
        -> external OpenAI-compatible embedding endpoint
        -> ingestion module -> PostgreSQL
```

The repository also ships in-memory adapters and a deterministic demo model. Tests and the
local UI can therefore run without downloading a language model. Ollama remains available
behind the optional `local-models` Compose profile, but the default production topology does
not run a model container.

The current single-host edition performs ingestion inline and records job state in the API
process. That keeps the deployment small and is honest about the failure boundary. A durable
queue and worker are the next scaling step when documents become large or ingestion must
survive API restarts.
