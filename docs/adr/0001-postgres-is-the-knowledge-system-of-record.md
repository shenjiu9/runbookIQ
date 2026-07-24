# PostgreSQL is the knowledge system of record

RunbookIQ persists knowledge-base identity, extracted source chunks, full-text indexes, and embeddings in PostgreSQL, with pgvector providing cosine search. A knowledge base is the isolation and deletion boundary, so chunk identity is scoped by knowledge-base ID and deletion cascades to its indexed content; the original uploaded binary remains outside PostgreSQL to keep storage and reprocessing concerns separable.
