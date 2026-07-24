# Configuration Rollout Failure Runbook

Source: Platform Engineering deployment runbook

## Detect configuration drift

Compare the new Deployment Pod template with the previous ReplicaSet. Check ConfigMap and Secret names, checksum annotations, `env`, `envFrom`, command-line arguments and mounted volume paths.

Do not assume a referenced ConfigMap is the value actually mounted in the container. Inspect the live Pod specification and, when permitted, read the mounted file or environment variable from a running replica.

## Validate keys and formats

Confirm every referenced ConfigMap or Secret key exists. Validate JSON, YAML and connection-string formatting before restart. A renamed key can become an empty environment variable when application validation is weak.

For immutable ConfigMaps and Secrets, verify the Deployment references the newly created object name. For mutable objects, verify the rollout mechanism updates a checksum annotation so Pods are recreated.

## Compare with the last known-good release

Diff the effective configuration, not only the source repository. The comparison must include admission-controller mutations, Helm defaults and environment-specific overlays.

## Recovery

Restore the last known-good configuration or roll back the Deployment. Keep the failed ReplicaSet and relevant Events until the incident timeline and root cause are captured.

