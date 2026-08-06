from runbookiq.evaluation.benchmark import (
    CHAT_SUPPORT_SOURCE,
    CHAT_SUPPORT_SUITE_ID,
    CONFIG_SOURCE,
    CRASHLOOP_SOURCE,
    PLATFORM_OPERATIONS_SUITE_ID,
    PROBE_SOURCE,
    list_benchmarks,
    load_benchmark,
)


def test_platform_benchmark_has_sixty_labeled_cases() -> None:
    cases, total = load_benchmark(PLATFORM_OPERATIONS_SUITE_ID)

    assert total == 60
    assert len(cases) == 60
    assert all(case["question"].strip() for case in cases)
    assert all(case["expected_source_ids"] for case in cases)


def test_quick_benchmark_is_stratified_across_all_sources() -> None:
    cases, total = load_benchmark(PLATFORM_OPERATIONS_SUITE_ID, max_cases=6)
    expected = {
        source_id
        for case in cases
        for source_id in case["expected_source_ids"]
    }

    assert total == 60
    assert len(cases) == 6
    assert expected == {CRASHLOOP_SOURCE, CONFIG_SOURCE, PROBE_SOURCE}


def test_gold_source_ids_match_the_shipped_runbook_content() -> None:
    project_root = Path(__file__).resolve().parents[2]
    expected = {
        "crashloopbackoff.md": CRASHLOOP_SOURCE,
        "config-rollout.md": CONFIG_SOURCE,
        "probe-postmortem.md": PROBE_SOURCE,
    }

    for filename, source_id in expected.items():
        content = (project_root / "examples" / "runbooks" / filename).read_bytes()
        assert source_id == f"src-{hashlib.sha256(content).hexdigest()[:16]}"


def test_chat_support_benchmark_has_conversation_and_fact_labels() -> None:
    cases, total = load_benchmark(CHAT_SUPPORT_SUITE_ID)

    assert total == 24
    assert len(cases) == 24
    assert all(case["expected_source_ids"] == [CHAT_SUPPORT_SOURCE] for case in cases)
    assert all(case["expected_section_paths"] for case in cases)
    assert all(case["expected_evidence_terms"] for case in cases)
    assert all(case["expected_answer_terms"] for case in cases)
    assert CHAT_SUPPORT_SUITE_ID in {
        suite.id for suite in list_benchmarks("platform")
    }


def test_chat_support_source_id_matches_the_shipped_json_content() -> None:
    project_root = Path(__file__).resolve().parents[2]
    content = (
        project_root / "examples" / "chat" / "customer-support-synthetic.json"
    ).read_bytes()

    assert CHAT_SUPPORT_SOURCE == f"src-{hashlib.sha256(content).hexdigest()[:16]}"
import hashlib
from pathlib import Path
