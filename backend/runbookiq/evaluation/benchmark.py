from dataclasses import dataclass

from runbookiq.domain.models import EvaluationSuite

PLATFORM_OPERATIONS_SUITE_ID = "platform-operations-v1"

CRASHLOOP_SOURCE = "src-d0ddef69082afff0"
CONFIG_SOURCE = "src-fc5c92d441c484ab"
PROBE_SOURCE = "src-ecc35d05aefe91f2"


@dataclass(frozen=True)
class GoldenCase:
    question: str
    expected_source_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "expected_source_ids": list(self.expected_source_ids),
        }


def _cases(questions: tuple[str, ...], *source_ids: str) -> list[GoldenCase]:
    return [
        GoldenCase(question=question, expected_source_ids=source_ids)
        for question in questions
    ]


PLATFORM_OPERATIONS_CASES = [
    *_cases(
        (
            "How do I inspect the logs from the previous crashed container?",
            "Which kubectl command preserves the message written before the last container exit?",
            "A Pod keeps restarting; how can I identify which container is failing?",
            "What should I inspect in kubectl describe pod Events for CrashLoopBackOff?",
            "How do I distinguish an application crash from an image pull or mount failure?",
            "What does an OOMKilled termination reason mean?",
            "How can CPU throttling cause Kubernetes health checks to fail?",
            "When should a startup probe be added to a workload?",
            "How should probe timing be compared with measured application startup time?",
            "What is the safe mitigation when CrashLoopBackOff starts after a deployment?",
            "Pod 持续重启时，如何查看上一次容器崩溃前的日志？",
            "多容器 Pod 中应该怎样确认究竟是哪一个容器在重启？",
            "CrashLoopBackOff 时 kubectl describe pod 需要重点检查哪些事件？",
            "如何判断容器是不是因为超过内存限制而被终止？",
            "CPU 节流为什么可能导致健康检查超时？",
            "应用启动较慢时，存活探针应该怎样配置？",
            "什么时候应该为 Kubernetes 工作负载增加 startupProbe？",
            "发布后立即发生 CrashLoopBackOff，安全的止损步骤是什么？",
            "怎样记录容器的退出码、终止原因和最后几行日志？",
            "当前容器日志只有启动信息时，还能从哪里找到上次退出错误？",
        ),
        CRASHLOOP_SOURCE,
    ),
    *_cases(
        (
            "What configuration should be compared with the previous ReplicaSet after a rollout?",
            "How do I verify the ConfigMap that is actually mounted in a live Pod?",
            "Which ConfigMap and Secret fields should be checked for configuration drift?",
            "Why can a renamed Secret key become an empty environment variable?",
            "How should immutable ConfigMaps be rolled out safely?",
            "Why should checksum annotations be verified for mutable configuration objects?",
            "What is included when diffing effective rather than repository configuration?",
            "How do admission controller mutations affect configuration comparisons?",
            "What should be preserved before rolling back a failed ReplicaSet?",
            "How do I validate JSON, YAML, and connection-string configuration before restart?",
            "配置发布失败后，需要与上一版 ReplicaSet 对比哪些字段？",
            "如何确认 Pod 实际挂载的 ConfigMap 内容，而不是只看引用名称？",
            "ConfigMap 或 Secret 改名后为什么可能产生空环境变量？",
            "不可变 ConfigMap 更新时 Deployment 应该引用什么对象？",
            "可变配置对象为什么需要 checksum 注解触发 Pod 重建？",
            "所谓有效配置对比为什么还要包含 Helm 默认值和环境覆盖层？",
            "准入控制器对 Pod 的修改应该如何纳入配置漂移检查？",
            "回滚配置前应当保留哪些 ReplicaSet 和事件信息？",
            "重启应用之前怎样验证 JSON、YAML 和连接字符串格式？",
            "envFrom 引用的键不存在时应该优先检查什么？",
        ),
        CONFIG_SOURCE,
    ),
    *_cases(
        (
            "Why did the checkout service restart continuously during a database migration?",
            "How long did startup take after the migration change?",
            "Why did the liveness probe prevent the migration from completing?",
            "What failure budget was configured for the new startup probe?",
            "When should liveness and readiness probes begin after the remediation?",
            "How should a deployment pipeline measure startup duration?",
            "What alert should detect a developing restart loop?",
            "Under which cache condition should probe timing be tested?",
            "Which services should be required to define a startup probe?",
            "How can remote dependency checks interact with probe timing?",
            "数据库迁移后 checkout 服务为什么连续重启？",
            "这次事故中应用启动时间从多少秒增加到多少秒？",
            "存活探针为何让数据库迁移始终无法完成？",
            "修复后 startupProbe 设置了多长的失败预算？",
            "修复后 livenessProbe 和 readinessProbe 应该何时开始？",
            "发布流水线应该在哪个阶段测量应用启动耗时？",
            "应该针对哪项指标配置告警来提前发现重启循环？",
            "为什么需要在冷缓存条件下测试探针时序？",
            "哪些执行迁移或远程依赖检查的服务必须配置启动探针？",
            "这次探针事故采取了哪些预防措施？",
        ),
        PROBE_SOURCE,
    ),
]


PLATFORM_OPERATIONS_SUITE = EvaluationSuite(
    id=PLATFORM_OPERATIONS_SUITE_ID,
    knowledge_base_id="platform",
    name="平台故障调查基准 v1",
    description="Kubernetes、配置发布与探针事故的中英文黄金问题",
    case_count=len(PLATFORM_OPERATIONS_CASES),
)

SUITES = {
    PLATFORM_OPERATIONS_SUITE_ID: (
        PLATFORM_OPERATIONS_SUITE,
        PLATFORM_OPERATIONS_CASES,
    )
}


def list_benchmarks(knowledge_base_id: str) -> list[EvaluationSuite]:
    return [
        suite
        for suite, _cases_for_suite in SUITES.values()
        if suite.knowledge_base_id == knowledge_base_id
    ]


def get_benchmark(suite_id: str) -> EvaluationSuite:
    try:
        suite, _cases_for_suite = SUITES[suite_id]
    except KeyError as exc:
        raise KeyError(suite_id) from exc
    return suite


def load_benchmark(
    suite_id: str,
    *,
    max_cases: int | None = None,
) -> tuple[list[dict], int]:
    try:
        _suite, suite_cases = SUITES[suite_id]
    except KeyError as exc:
        raise KeyError(suite_id) from exc
    if max_cases and max_cases < len(suite_cases):
        groups = [
            suite_cases[0:20],
            suite_cases[20:40],
            suite_cases[40:60],
        ]
        selected = [
            group[index]
            for index in range(20)
            for group in groups
            if index < len(group)
        ][:max_cases]
    else:
        selected = suite_cases
    return [case.as_dict() for case in selected], len(suite_cases)
