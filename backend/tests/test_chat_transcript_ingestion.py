import json
from pathlib import Path

import httpx
import pytest

from runbookiq.app import create_local_app
from runbookiq.evaluation.benchmark import CHAT_SUPPORT_SUITE_ID


@pytest.mark.asyncio
async def test_json_chat_export_is_searchable_by_conversation_with_message_context() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    transcript = {
        "conversations": [
            {
                "id": "conv-payments",
                "title": "支付系统上线复盘",
                "messages": [
                    {
                        "timestamp": "2026-07-20 09:00",
                        "sender": "林薇",
                        "content": "昨晚支付延迟来自旧连接池配置。",
                    },
                    {
                        "timestamp": "2026-07-20 09:03",
                        "sender": "周启",
                        "content": "最终决定编号 ORBIT-7421：连接池上限改为 180。",
                    },
                ],
            },
            {
                "id": "conv-warehouse",
                "title": "仓储例会",
                "messages": [
                    {
                        "timestamp": "2026-07-20 10:00",
                        "sender": "陈冬",
                        "content": "本周盘点没有发现账实差异。",
                    }
                ],
            },
        ]
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={
                "file": (
                    "team-chat.json",
                    json.dumps(transcript, ensure_ascii=False).encode(),
                    "application/json",
                )
            },
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "ORBIT-7421 最终决定把连接池上限改为多少？",
            },
        )

    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "completed"
    assert answered.status_code == 200
    citation = answered.json()["citations"][0]
    assert citation["title"] == "支付系统上线复盘"
    assert "会话 conv-payments" in citation["section_path"]
    assert "2026-07-20 09:03" in citation["excerpt"]
    assert "周启" in citation["excerpt"]
    assert "连接池上限改为 180" in citation["excerpt"]


@pytest.mark.asyncio
async def test_csv_chat_export_groups_messages_by_conversation() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    transcript = """conversation_id,conversation_title,timestamp,sender,message
support-88,退款争议处理,2026-07-22 14:10,客户,订单一直没有退款到账
support-88,退款争议处理,2026-07-22 14:12,客服小韩,工单代码 REFUND-983，承诺 2 个工作日内原路退回
delivery-12,配送异常,2026-07-22 15:00,调度员,配送车辆临时故障
""".encode()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={"file": ("support-chat.csv", transcript, "text/csv")},
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "REFUND-983 承诺多久完成退款？",
            },
        )

    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "completed"
    citation = answered.json()["citations"][0]
    assert citation["title"] == "退款争议处理"
    assert "会话 support-88" in citation["section_path"]
    assert "客服小韩" in citation["excerpt"]
    assert "2 个工作日内原路退回" in citation["excerpt"]


@pytest.mark.asyncio
async def test_long_chat_uses_overlapping_message_windows() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    messages = [
        {
            "timestamp": f"2026-07-23 09:{index:02d}",
            "sender": "项目群成员",
            "content": f"这是第 {index} 条例会消息。",
        }
        for index in range(1, 36)
    ]
    messages[23]["content"] = "上一轮结论是先核对灰度环境。"
    messages[24]["content"] = "边界决策 WINDOW-2525：正式切流时间为周五 21:30。"
    transcript = {
        "conversations": [
            {"id": "release-room", "title": "发布协调群", "messages": messages}
        ]
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={
                "file": (
                    "release-chat.json",
                    json.dumps(transcript, ensure_ascii=False).encode(),
                    "application/json",
                )
            },
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "WINDOW-2525 决定何时正式切流？",
            },
        )

    assert uploaded.json()["status"] == "completed"
    assert uploaded.json()["chunks_created"] == 2
    citation = answered.json()["citations"][0]
    assert "消息 21-35" in citation["section_path"]
    assert "上一轮结论是先核对灰度环境" in citation["excerpt"]
    assert "正式切流时间为周五 21:30" in citation["excerpt"]


@pytest.mark.asyncio
async def test_jsonl_chat_export_is_supported() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    records = [
        {
            "conversation_id": "sales-31",
            "conversation_title": "重点客户交接",
            "timestamp": "2026-07-24 16:00",
            "sender": "销售顾问",
            "message": "客户要求发票抬头保持不变。",
        },
        {
            "conversation_id": "sales-31",
            "conversation_title": "重点客户交接",
            "timestamp": "2026-07-24 16:02",
            "sender": "销售主管",
            "message": "交接编号 HANDOFF-310：下次回访日期为 8 月 6 日。",
        },
    ]
    transcript = "\n".join(
        json.dumps(record, ensure_ascii=False) for record in records
    ).encode()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={"file": ("sales-chat.jsonl", transcript, "application/x-ndjson")},
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "HANDOFF-310 的下次回访日期是什么时候？",
            },
        )

    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "completed"
    citation = answered.json()["citations"][0]
    assert citation["title"] == "重点客户交接"
    assert "8 月 6 日" in citation["excerpt"]


@pytest.mark.asyncio
async def test_chat_benchmark_reports_conversation_and_fact_accuracy() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    conversations = []
    for index in range(12):
        conversations.append(
            {
                "id": f"approval-{index:02d}",
                "title": f"客户 {index:02d} 审批群",
                "messages": [
                    {
                        "timestamp": "2026-07-25 10:00",
                        "sender": "客户经理",
                        "content": "请确认本次申请的最终审批条件。",
                    },
                    {
                        "timestamp": "2026-07-25 10:02",
                        "sender": "审批主管",
                        "content": (
                            f"决策编号 CHAT-{index:04d}：审批额度为 {1200 + index * 37} 元，"
                            f"复核日期为 8 月 {index + 1} 日。"
                        ),
                    },
                    {
                        "timestamp": "2026-07-25 10:03",
                        "sender": "客户经理",
                        "content": "收到，后续将按该结论执行。",
                    },
                ],
            }
        )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={
                "file": (
                    "approval-chats.json",
                    json.dumps(
                        {"conversations": conversations},
                        ensure_ascii=False,
                    ).encode(),
                    "application/json",
                )
            },
        )
        documents = await client.get("/api/knowledge-bases/platform/documents")
        source_id = documents.json()[0]["source_id"]
        cases = [
            {
                "question": f"CHAT-{index:04d} 的审批额度是多少？",
                "expected_source_ids": [source_id],
                "expected_section_paths": [f"会话 approval-{index:02d}"],
                "expected_evidence_terms": [f"审批额度为 {1200 + index * 37} 元"],
                "expected_answer_terms": [f"审批额度为 {1200 + index * 37} 元"],
            }
            for index in range(12)
        ]
        evaluated = await client.post(
            "/api/evaluations/run",
            json={"knowledge_base_id": "platform", "cases": cases},
        )

    assert uploaded.json()["status"] == "completed"
    assert evaluated.status_code == 200
    assert evaluated.json()["case_count"] == 12
    assert evaluated.json()["metrics"]["section_recall_at_5"] == 1.0
    assert evaluated.json()["metrics"]["evidence_term_recall_at_5"] == 1.0
    assert evaluated.json()["metrics"]["answer_term_coverage"] == 1.0


@pytest.mark.asyncio
async def test_shipped_chat_suite_runs_end_to_end_against_shipped_transcript() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    project_root = Path(__file__).resolve().parents[2]
    transcript = (
        project_root / "examples" / "chat" / "customer-support-synthetic.json"
    ).read_bytes()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={"file": ("customer-support-synthetic.json", transcript, "application/json")},
        )
        evaluated = await client.post(
            "/api/evaluations/run",
            json={
                "knowledge_base_id": "platform",
                "suite_id": CHAT_SUPPORT_SUITE_ID,
            },
        )

    assert uploaded.json()["status"] == "completed"
    assert evaluated.status_code == 200
    metrics = evaluated.json()["metrics"]
    # The zero-config hashing adapter is deliberately lexical and is not the
    # production semantic baseline. It must still retrieve all 12 exact-ID
    # cases; the production embedding/reranker run is expected to improve the
    # 12 paraphrased cases.
    assert metrics["section_recall_at_5"] >= 0.5
    assert metrics["evidence_term_recall_at_5"] >= 0.5
    assert metrics["answer_term_coverage"] >= 0.5
