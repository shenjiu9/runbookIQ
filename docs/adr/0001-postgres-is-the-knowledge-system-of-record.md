# PostgreSQL is the knowledge system of record

RunbookIQ persists knowledge-base identity, logical document records, stable citation source IDs,
extracted source chunks, full-text indexes, and embeddings in PostgreSQL, with pgvector providing
cosine search. Knowledge-base ID remains the tenant-authorized isolation boundary, while document
ID is the replacement and deletion boundary inside a knowledge base. Deleting a document cascades
to its indexed content.

The original uploaded binary remains outside PostgreSQL behind a document-store interface. The
single-host production adapter uses a durable Docker volume, keeping binary storage and database
backup concerns separable while still supporting download, safe replacement, and cleanup. A
multi-node deployment should replace that adapter with S3 or MinIO.

Every new binary is registered first in PostgreSQL as a delayed-cleanup staging object. Committing
the document transaction activates that key; interrupted or failed writes remain eligible for
retryable garbage collection. Deleting a document or an entire knowledge base queues its current
binary through the same durable mechanism.
