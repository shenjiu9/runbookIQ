# 聊天记录公开数据集调研与测试建议

更新日期：2026-08-06

## 结论

RunbookIQ 的公开测试基线建议采用 **Bitext Customer Support Dataset**，并搭配一套项目自有的中文合成客服黄金集。

- Bitext 与客户支持场景最贴近，数据为合成问答对，实体采用占位符，公开页面标注为 CDLA-Sharing-1.0；适合验证 CSV 转换、批量摄取、英文检索和负载表现。
- Bitext 不是自然形成的多轮工单，且同一意图内有大量近似表达，不应单独用于宣称真实聊天准确率。
- 中文合成黄金集应覆盖多轮追问、纠正、跨分片事实、口语和相似干扰案例，并用会话、证据短语和最终答案三个层级进行评测。

许可证结论仅用于工程选型，不构成法律意见。对外再分发原始数据或衍生数据前，应重新核对数据集当时的许可证全文。

## 候选数据集

### 1. Bitext Customer Support Dataset（首选公开基线）

官方来源：[Bitext 官方 Hugging Face 数据集卡](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset)

- 内容：26,872 个客户支持问答对，27 个意图、10 个类别、30 种实体/槽位；数据集卡说明其为混合合成数据，并由计算语言学人员审核。
- 字段：`flags`、`instruction`、`category`、`intent`、`response`。
- 语言：英语。
- 许可证：数据集卡标注 `CDLA-Sharing-1.0`。该许可证允许使用和修改数据，但在发布数据或增强数据时有同许可证共享义务；官方说明见 [CDLA Sharing 1.0](https://cdla.dev/sharing-1-0/) 和 [CDLA 1.0 版本说明](https://cdla.dev/version-1-0-license-agreements/)。
- 隐私：数据是合成的，订单号、网址、姓名等以 `{{Order Number}}` 等槽位出现，真实个人信息风险低。
- 局限：每行只是一个用户请求和一个助手回复；没有真实时间戳，也没有跨轮状态变化。大量近重复问法会使直接用原问题评测的结果虚高。

建议从 27 个意图各抽取 20 条，共 540 条，转换为两轮会话：

```csv
conversation_id,conversation_title,timestamp,sender,message
bitext-cancel_order-0001,ORDER / cancel_order,1,customer,<instruction>
bitext-cancel_order-0001,ORDER / cancel_order,2,agent,<response>
```

这批数据用于：格式兼容、摄取吞吐、英文混合检索和大批量会话隔离测试。准确率问题必须使用未出现在原数据中的改写问法，并以 `conversation_id` 或章节路径为黄金标注，不能只使用文件级 `source_id`。

### 2. Google Schema-Guided Dialogue（多轮结构备选）

官方来源：[Google Schema-Guided Dialogue 官方仓库](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue)

- 内容：超过 20,000 个多领域、任务型对话，覆盖银行、事件、媒体、日历、旅行和天气等 20 个领域；对话由模拟器辅助并由付费众包人员完成。
- 字段：`dialogue_id`、`services`、`turns`；每轮包含 `speaker`、`utterance`、`frames`，frame 还包含意图、槽位、服务调用和结果。
- 语言：官方仓库提供的原始 SGD 对话为英语。
- 许可证：CC BY-SA 4.0，使用和再分发时需要署名，改编材料需按相同许可共享。
- 隐私：不是企业真实客服日志，隐私风险低于真实工单；仍应保留来源和许可说明。
- 局限：属于“用户—虚拟助手执行 API 任务”，不完全等同于员工或客户支持历史；没有真实客服时间戳。

转换时将 `dialogue_id` 映射为 `conversation_id`，`speaker` 映射为 `sender`，`utterance` 映射为 `message`。`services` 可拼成 `conversation_title`。

### 3. MultiWOZ（人类多轮对话备选）

官方来源：[剑桥对话系统组 MultiWOZ 官方仓库](https://github.com/budzianowski/multiwoz)

- 内容：10,438 个多领域 Wizard-of-Oz 人类书面对话，其中 3,406 个单领域、7,032 个多领域；包含目标、用户/系统话语和 belief state。
- 语言：英语。
- 许可证：官方仓库标注 MIT。
- 隐私：参与者根据任务脚本对话，不是直接公开真实客户工单；风险较低。
- 局限：早期版本存在标注错误，官方仓库建议使用修正版本；旅游、酒店、餐饮和交通领域占比较高，与企业知识库支持仍有距离。

MultiWOZ 适合验证长多轮上下文和领域切换，不建议作为客服准确率的唯一依据。

### 4. OpenAssistant OASST1（多语言压力测试备选）

官方来源：[OpenAssistant 官方数据集卡](https://huggingface.co/datasets/OpenAssistant/oasst1)

- 内容：161,443 条众包消息、35 种语言、超过 10,000 棵对话树；官方 `ready_for_export` 子集有 10,364 棵树和 88,838 条消息。
- 字段：`message_id`、`parent_id`、`message_tree_id`、`created_date`、`text`、`role`、`lang`、质量标签等。
- 语言：官方统计含 4,962 条中文消息，另有英语、西班牙语、俄语等。
- 许可证：Apache-2.0。
- 隐私与内容风险：来自全球志愿者众包，数据字段明确包含 PII、毒性、不适当内容、仇恨言论和色情内容等标签。即使使用 `ready_for_export`，仍应再次执行 PII 和安全内容过滤。
- 局限：它是分支对话树，不是线性工单；导入前必须从根节点到叶节点选择一条路径。内容主题广泛，不以客户支持为主。

只建议将 OASST1 用于多语言、长文本和异常内容压力测试，不建议把它直接放入公开演示知识库。

## 不建议作为当前主基准的数据

- 真实网络聊天或论坛日志：即使公开可下载，也可能包含用户名、邮箱、电话、访问令牌或未预期公开的个人对话；许可和个人信息处理基础通常不够清晰。
- 没有明确许可证的数据集：公开下载不等于可以重新发布或商用。
- 单纯把大语言模型自由生成的问答当成唯一黄金集：生成模型可能同时生成错误事实和参考答案，导致评测自洽但不正确。

## 中文合成补充集设计

建议生成 `chat-support-zh-v1`，数据与答案事实全部由本项目定义，不使用真实个人信息。

### 数据规模

- 8 个场景：订单退款、账号权限、发票付款、物流异常、售后维修、人事制度、IT 故障、门店冷链。
- 每个场景 15 个会话，共 120 个会话。
- 普通会话 4～12 条消息；另设 20 个 30～40 条消息的长会话，强制触发 24 条消息窗口和 4 条重叠策略。
- 120 个可回答问题，外加 30 个知识库中没有答案的问题。

### 可验证事实

每个会话包含：

- 唯一案件编号，例如 `CASE-CN-0047`；
- 一个精确事实，例如“退款在 3 个工作日内原路退回”；
- 一个容易混淆但不同的事实，例如另一案件是“5 个工作日退至余额”；
- 至少一次追问、否定或纠正；
- 一个与原话不同的测试问法。

20 个长会话应把关键事实放在第 21～27 条消息附近，专门验证分片边界和重叠是否丢失证据。

示例：

```json
{
  "conversations": [
    {
      "id": "CASE-CN-0047",
      "title": "退款去向纠正",
      "messages": [
        {"timestamp": "2026-08-01 09:01", "sender": "客户", "content": "订单 ORD-CN-8047 的退款会到余额吗？"},
        {"timestamp": "2026-08-01 09:03", "sender": "客服", "content": "先前说明有误。案件 CASE-CN-0047 已确认在 3 个工作日内原路退回，不退至账户余额。"}
      ]
    }
  ]
}
```

对应黄金用例：

```json
{
  "question": "ORD-CN-8047 最终退到哪里，大约要多久？",
  "expected_section_paths": ["退款去向纠正 / 会话 CASE-CN-0047"],
  "expected_evidence_terms": ["3 个工作日内", "原路退回", "不退至账户余额"],
  "expected_answer_terms": ["3 个工作日", "原路退回"]
}
```

## 测试执行逻辑

### 公开基线

1. 从 Bitext 分层抽样 540 行，每个意图 20 行。
2. 转成 RunbookIQ CSV，每个问答对一个 `conversation_id`。
3. 将评测问题改写为未在源文本中出现的表达，避免原句复制导致关键词检索虚高。
4. 记录导入消息数、生成章节数、摄取耗时、失败数，以及章节级 Recall@5。

### 中文准确率基线

1. 上传 `chat-support-zh-v1.json` 到独立知识库。
2. 运行 120 个可回答问题，统计 `section_recall_at_5`、`evidence_term_recall_at_5`、`answer_term_coverage` 和忠实度。
3. 运行 30 个不可回答问题，统计正确拒答率，不能把“看似合理但无证据”的答案算正确。
4. 单独汇总普通会话、长会话、分片边界、纠正事实、口语/错别字和相似干扰六组结果。
5. 固定聊天模型、Embedding、Reranker 和检索参数后再比较版本，避免把模型变化误认为解析器提升。

建议的首版验收线：

| 指标 | 目标 |
| --- | ---: |
| 导入会话/消息完整率 | 100% |
| 章节 Recall@5 | ≥ 95% |
| 证据短语 Recall@5 | ≥ 95% |
| 答案关键事实覆盖率 | ≥ 90% |
| 不可回答问题正确拒答率 | ≥ 90% |
| 跨会话错误引用率 | ≤ 2% |

## 最终建议

本轮实际测试应使用“**Bitext 公开样本 + 中文自有合成黄金集**”两条线：前者证明系统能处理公开、规模化的客服语料；后者提供可审计的中文、多轮和分片边界准确率。Google SGD 可作为后续多轮英语测试，OASST1 只作为经过安全过滤后的多语言压力测试。
