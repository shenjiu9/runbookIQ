# Kubernetes CrashLoopBackOff Investigation

Source: Kubernetes workload operations runbook

## Confirm the failing container

List the Pod state and inspect the restart count. A high and increasing restart count confirms an active crash loop. If the Pod has multiple containers, identify the specific container that is restarting before collecting logs.

## Inspect the previous container logs

Use `kubectl logs <pod> -c <container> --previous` first. The current container log may only contain startup output, while `--previous` preserves the message written immediately before the last exit. Record the exit code, termination reason, and last log lines.

Run `kubectl describe pod <pod>` and review Events. Image pull errors, failed mounts, admission errors and probe failures often appear there even when the application log is empty.

## Check probes and resources

Compare liveness, readiness and startup probe timing with the application's measured startup time. A liveness probe that starts before migrations or cache warm-up complete can create a permanent restart loop. Add a startup probe when slow startup is expected.

Inspect `resources.requests` and `resources.limits`. A termination reason of `OOMKilled` means the memory limit was exceeded. CPU throttling can make health checks time out even when the process is correct.

## Safe mitigation

If the failure started after a deployment, pause the rollout and compare the Pod template with the previous ReplicaSet. Roll back when customer impact is ongoing, then reproduce the issue in a non-production namespace.

