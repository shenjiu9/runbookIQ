import type { QueryResponse } from "./types";

export const initialResponse: QueryResponse = {
  answer:
    "配置发布后出现 CrashLoopBackOff，通常与启动参数、挂载配置或探针变化有关。首先检查上一轮容器日志，确认进程退出前的最后一条错误信息。[1] 然后对比当前与上一版本 ReplicaSet 挂载的 ConfigMap、Secret，并核验所有引用键。[2] 最后检查资源限制，以及存活、就绪或启动探针是否在新版本启动完成前过早触发。[1][3]",
  confidence: 0.92,
  citations: [
    {
      number: 1,
      source_id: "k8s-pod-lifecycle",
      title: "Kubernetes 文档：排查 CrashLoopBackOff",
      section_path: "工作负载 / Pod / 容器状态",
      excerpt:
        "处于 CrashLoopBackOff 状态的容器正在反复崩溃。请检查当前及上一轮容器日志，然后核验资源限制与探针配置。",
      source_url: "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/",
      scores: { bm25: 0.81, vector: 0.89, rrf: 0.0325, rerank: 0.92 }
    },
    {
      number: 2,
      source_id: "runbook-config-rollout",
      title: "运行手册：配置发布故障排查",
      section_path: "平台工程 / 发布 / 配置漂移",
      excerpt:
        "将当前挂载的 ConfigMap、Secret 与上一版本 ReplicaSet 对比，并检查校验和注解以及 envFrom 引用的键。",
      source_url: "runbook://platform/config-rollout",
      scores: { bm25: 0.76, vector: 0.88, rrf: 0.0318, rerank: 0.88 }
    },
    {
      number: 3,
      source_id: "postmortem-july-rollout",
      title: "事故复盘：配置发布导致服务崩溃",
      section_path: "事故复盘 / 根因",
      excerpt:
        "新的存活探针在迁移完成前启动，形成了重启循环。增加启动探针并延长初始等待时间后问题得到解决。",
      source_url: "postmortem://2026-07-15-config-rollout",
      scores: { bm25: 0.61, vector: 0.81, rrf: 0.0309, rerank: 0.84 }
    }
  ],
  trace: {
    query_id: "q_01HY7FQ2VBJ5S2D6M7A1Z9T",
    stages: [
      { name: "query_rewrite", duration_ms: 142, candidate_count: 3 },
      { name: "hybrid_search", duration_ms: 812, candidate_count: 2408 },
      { name: "rrf_fusion", duration_ms: 98, candidate_count: 100 },
      { name: "rerank", duration_ms: 421, candidate_count: 10 },
      { name: "grounded_answer", duration_ms: 1320, candidate_count: 3 }
    ]
  }
};
