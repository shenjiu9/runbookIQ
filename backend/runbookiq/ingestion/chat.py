import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptSection:
    title: str
    section_path: str
    text: str


class ChatTranscriptParser:
    """Convert structured chat exports into searchable conversation sections."""

    def __init__(
        self,
        *,
        max_messages_per_section: int = 24,
        overlap_messages: int = 4,
        max_section_characters: int = 6000,
    ) -> None:
        if max_messages_per_section <= overlap_messages:
            raise ValueError("聊天窗口必须大于重叠消息数")
        self._max_messages = max_messages_per_section
        self._overlap_messages = overlap_messages
        self._max_characters = max_section_characters

    def parse_json(self, *, filename: str, content: bytes) -> list[TranscriptSection]:
        try:
            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("聊天记录 JSON 格式无效") from exc

        raw_conversations = (
            payload.get("conversations", []) if isinstance(payload, dict) else payload
        )
        if not isinstance(raw_conversations, list):
            raise TypeError("聊天记录 JSON 必须包含 conversations 数组")
        if raw_conversations and all(
            isinstance(record, dict) and "messages" not in record
            for record in raw_conversations
        ):
            return self._flat_record_sections(
                filename=filename,
                records=raw_conversations,
            )

        fallback_title = self._fallback_title(filename)
        sections: list[TranscriptSection] = []
        for index, conversation in enumerate(raw_conversations, start=1):
            if not isinstance(conversation, dict):
                continue
            messages = conversation.get("messages")
            if not isinstance(messages, list):
                continue
            conversation_id = str(conversation.get("id") or index).strip()
            title = str(conversation.get("title") or fallback_title or "聊天记录").strip()
            sections.extend(
                self._conversation_sections(
                    title=title,
                    conversation_id=conversation_id,
                    messages=messages,
                )
            )
        if not sections:
            raise ValueError("聊天记录中没有可索引的消息")
        return sections

    def parse_csv(self, *, filename: str, content: bytes) -> list[TranscriptSection]:
        text = self._decode_text(content)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("聊天记录 CSV 缺少表头")

        return self._flat_record_sections(filename=filename, records=list(reader))

    def parse_json_lines(
        self,
        *,
        filename: str,
        content: bytes,
    ) -> list[TranscriptSection]:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(self._decode_text(content).splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"聊天记录 JSONL 第 {line_number} 行格式无效") from exc
            if isinstance(record, dict):
                records.append(record)

        return self._flat_record_sections(filename=filename, records=records)

    def _flat_record_sections(
        self,
        *,
        filename: str,
        records: list[dict[str, Any]],
    ) -> list[TranscriptSection]:
        fallback_title = self._fallback_title(filename)
        conversations: dict[str, dict[str, Any]] = {}
        for row_number, record in enumerate(records, start=1):
            conversation_id = self._pick(
                record,
                "conversation_id",
                "conversation",
                "session_id",
                "chat_id",
                "会话ID",
                "会话编号",
            ) or "default"
            conversation = conversations.setdefault(
                conversation_id,
                {
                    "id": conversation_id,
                    "title": self._pick(
                        record,
                        "conversation_title",
                        "title",
                        "chat_title",
                        "会话标题",
                    )
                    or fallback_title
                    or "聊天记录",
                    "messages": [],
                },
            )
            conversation["messages"].append(
                {
                    "timestamp": self._pick(
                        record,
                        "timestamp",
                        "time",
                        "created_at",
                        "时间",
                        "发送时间",
                    )
                    or f"第 {row_number} 条",
                    "sender": self._pick(
                        record,
                        "sender",
                        "speaker",
                        "name",
                        "role",
                        "发言人",
                        "发送者",
                    ),
                    "content": self._pick(
                        record,
                        "message",
                        "content",
                        "text",
                        "消息",
                        "内容",
                    ),
                }
            )

        sections: list[TranscriptSection] = []
        for conversation in conversations.values():
            sections.extend(
                self._conversation_sections(
                    title=str(conversation["title"]),
                    conversation_id=str(conversation["id"]),
                    messages=conversation["messages"],
                )
            )
        if not sections:
            raise ValueError("聊天记录中没有可索引的消息")
        return sections

    @staticmethod
    def _fallback_title(filename: str) -> str:
        return Path(filename).stem.replace("_", " ").replace("-", " ").strip()

    @staticmethod
    def _decode_text(content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content.decode("gb18030")

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _conversation_sections(
        self,
        *,
        title: str,
        conversation_id: str,
        messages: list[Any],
    ) -> list[TranscriptSection]:
        lines = [self._message_line(message) for message in messages]
        lines = [line for line in lines if line]
        sections: list[TranscriptSection] = []
        start = 0
        while start < len(lines):
            end = start
            character_count = 0
            while end < len(lines) and end - start < self._max_messages:
                added = len(lines[end]) + (1 if end > start else 0)
                if end > start and character_count + added > self._max_characters:
                    break
                character_count += added
                end += 1
            if end == start:
                end += 1
            body = "\n".join(lines[start:end])
            sections.append(
                TranscriptSection(
                    title=title,
                    section_path=(
                        f"{title} / 会话 {conversation_id} / 消息 {start + 1}-{end}"
                    ),
                    text=body,
                )
            )
            if end >= len(lines):
                break
            start = max(start + 1, end - self._overlap_messages)
        return sections

    @staticmethod
    def _message_line(message: Any) -> str:
        if not isinstance(message, dict):
            return ""
        timestamp = str(
            message.get("timestamp")
            or message.get("time")
            or message.get("created_at")
            or "未知时间"
        ).strip()
        sender = str(
            message.get("sender")
            or message.get("speaker")
            or message.get("name")
            or message.get("role")
            or "未知发言人"
        ).strip()
        value = message.get("content", message.get("text", message.get("message", "")))
        if isinstance(value, list):
            value = " ".join(str(item) for item in value)
        elif isinstance(value, dict):
            value = value.get("text", json.dumps(value, ensure_ascii=False))
        text = " ".join(str(value).split())
        return f"[{timestamp}] {sender}: {text}" if text else ""
