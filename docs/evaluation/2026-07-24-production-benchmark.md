# RunbookIQ production benchmark — 2026-07-24

## Run

- Environment: Tokyo production server
- Suite: `platform-operations-v1`
- Run ID: `eval-176dda3d9c87`
- Cases: 60 / 60
- Judge: `llm_evidence_judge`
- Duration: 614.1 seconds

## Metrics

| Metric | Result |
| --- | ---: |
| Recall@5 | 1.0000 |
| MRR@5 | 0.9611 |
| Precision@5 | 0.4694 |
| Evidence faithfulness | 0.8212 |

Every case retrieved its annotated source in the top five. The first relevant source
rank distribution was:

- rank 1: 56 cases
- rank 2: 2 cases
- rank 3: 2 cases
- missed: 0 cases

## Regression fixed before this run

The initial production run incorrectly reported zero retrieval metrics. Source identity
was derived from raw upload bytes, so the Windows CRLF release fixtures produced
different SHA-256 source IDs from the LF fixtures used by the golden suite.

The fix normalizes newline sequences for text documents before computing source
identity, while retaining the original bytes for parsing and leaving binary document
identity unchanged. A public-API regression test now uploads LF and CRLF variants of
the same Markdown runbook and requires both citations to use the same annotated source
ID. The repository also pins the shipped Markdown fixtures to LF through
`.gitattributes`.

Before replacing the three affected production sources, the database was backed up to:

```text
~/runbookiq/shared/pre-source-id-normalization-20260724.sql
```

The full backend verification after the code change was:

```text
ruff: all checks passed
pytest: 23 passed, 1 skipped
```
