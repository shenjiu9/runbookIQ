# Postmortem: Premature Liveness Probe Restarted Checkout

## Impact

The checkout service restarted continuously for eleven minutes after a database migration increased startup time from 18 seconds to 74 seconds.

## Root cause

The liveness probe began after 30 seconds and failed three times while migration work was still running. Kubernetes restarted the container before it could finish, so every attempt repeated the migration check and failed again.

## Resolution

The team added a startup probe with a 120-second failure budget. Liveness and readiness probes now begin only after startup succeeds. The deployment pipeline also measures startup duration in the canary stage.

## Preventive actions

Alert on restart-count growth, test probe timing under cold-cache conditions, and require a startup probe for services that perform migrations or remote dependency checks during boot.

