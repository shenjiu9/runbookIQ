#!/usr/bin/env sh
set -eu

BASE_URL="${RUNBOOKIQ_URL:-http://localhost:8080}"
for document in examples/runbooks/*.md; do
  echo "Ingesting ${document}"
  curl --fail --silent --show-error \
    -F "knowledge_base_id=platform" \
    -F "file=@${document};type=text/markdown" \
    "${BASE_URL}/api/documents"
  echo
done

echo "RunbookIQ sample knowledge is ready."

