# 聊天记录导入与评测

RunbookIQ 将聊天记录作为结构化知识源导入。解析后保留会话标题、会话编号、
时间、发言人和消息正文；长会话按 24 条消息形成一个父段落，相邻父段落重叠
4 条消息，并且每个父段落最多约 6,000 个字符。

## 支持的格式

### JSON

```json
{
  "conversations": [
    {
      "id": "support-88",
      "title": "退款争议处理",
      "messages": [
        {
          "timestamp": "2026-07-22 14:12",
          "sender": "客服小韩",
          "content": "工单代码 REFUND-983，承诺 2 个工作日内原路退回"
        }
      ]
    }
  ]
}
```

JSON 顶层也可以直接使用消息数组，字段规则与 JSONL 相同。

### JSONL / NDJSON

每行一条 JSON 消息：

```json
{"conversation_id":"support-88","conversation_title":"退款争议处理","timestamp":"2026-07-22 14:12","sender":"客服小韩","message":"工单代码 REFUND-983，承诺 2 个工作日内原路退回"}
```

### CSV

```csv
conversation_id,conversation_title,timestamp,sender,message
support-88,退款争议处理,2026-07-22 14:12,客服小韩,工单代码 REFUND-983，承诺 2 个工作日内原路退回
```

CSV 同时支持中文表头：`会话ID`、`会话标题`、`时间`、`发言人`、`内容`。
编码优先使用 UTF-8；解析失败时会尝试 GB18030。

## 字段别名

| 语义 | 可用字段 |
| --- | --- |
| 会话编号 | `conversation_id`、`conversation`、`session_id`、`chat_id`、`会话ID`、`会话编号` |
| 会话标题 | `conversation_title`、`title`、`chat_title`、`会话标题` |
| 时间 | `timestamp`、`time`、`created_at`、`时间`、`发送时间` |
| 发言人 | `sender`、`speaker`、`name`、`role`、`发言人`、`发送者` |
| 消息 | `message`、`content`、`text`、`消息`、`内容` |

## 聊天记录黄金集

自定义评测用例除 `expected_source_ids` 外，还可以提供：

```json
{
  "question": "REFUND-983 承诺多久完成退款？",
  "expected_source_ids": ["src-..."],
  "expected_section_paths": ["会话 support-88"],
  "expected_evidence_terms": ["2 个工作日内原路退回"],
  "expected_answer_terms": ["2 个工作日内原路退回"]
}
```

报告会增加三项指标：

- `section_recall_at_5`：前五条证据是否召回正确会话或章节；
- `evidence_term_recall_at_5`：前五条证据是否覆盖黄金事实短语；
- `answer_term_coverage`：最终答案是否精确覆盖黄金事实短语。

精确短语覆盖适合编号、日期、金额和专有名词。对于允许自由改写的答案，还应结合
LLM 忠实度评测人工抽检，不能只依赖该指标。

## 当前边界

- 暂不直接读取微信、企业微信等客户端的加密数据库；需要先导出为上述格式。
- 附件、语音和表情不会作为独立消息解析；附件应作为普通文档另外上传。
- 聊天中可能含个人信息和商业秘密，上传前应完成授权、脱敏和保留期限确认。
