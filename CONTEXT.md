# RunbookIQ domain context

RunbookIQ is an incident-investigation RAG workbench for SRE and platform teams.

## Domain language

- **Knowledge base**: an isolated searchable corpus, such as Kubernetes docs or internal runbooks.
- **Knowledge base catalog**: the collection of knowledge bases a workspace can create, select, and retire.
- **Source**: an uploaded file, pasted text, or synced URL.
- **Extracted text**: normalized searchable text produced from a source, including OCR output.
- **Parent section**: a heading-aware document section retained for answer context.
- **Child chunk**: a smaller retrieval unit linked to its parent section.
- **Evidence**: a retrieved child chunk plus source metadata, scores, and a stable citation number.
- **Answer**: a grounded response whose factual claims cite evidence.
- **Trace**: observable timing, candidate counts, and scores for each retrieval/generation stage.
- **Evaluation suite**: versioned questions, expected source identifiers, and optional reference answers.
- **Ingestion job**: an asynchronous, retryable source-processing operation.
- **Organization**: an enterprise tenant that owns members, domains, and knowledge bases.
- **Tenant context**: the authenticated user, organization, and role resolved for one request.
- **Tenant domain**: a verified hostname routed to exactly one organization.

## Confirmed public seams

Tests exercise behavior only through:

1. `POST /api/auth/register`
2. `POST /api/auth/login`
3. `GET /api/auth/me`
4. `POST /api/auth/logout`
5. `POST/GET/DELETE /api/knowledge-bases`
6. `POST /api/query`
7. `POST /api/documents`
8. `GET /api/ingestion/jobs/{job_id}`
9. `GET /api/knowledge-bases/{knowledge_base_id}/evaluation-suites`
10. `POST /api/evaluations/run`
11. `GET /api/evaluations/latest?knowledge_base_id={knowledge_base_id}`
12. `GET /api/internal/tls/allow?domain={tenant_domain}`

The database, embedding model, reranker, object store, queue, and chat model are external seams
with production and in-memory adapters.
