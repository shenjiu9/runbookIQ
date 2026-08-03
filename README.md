# RunbookIQ

面向 SRE / 平台工程团队的故障调查 RAG 工作台。它把 Kubernetes 文档、内部 Runbook
和事故复盘统一成可检索的证据库，并输出带段落引用、检索分数和执行链路的回答。

这不是只调用一次向量库的聊天壳。项目刻意保留了企业 RAG 最值得练习和讲解的部分：

- 企业注册登录、专属子域名，以及企业和知识库双重隔离；
- 多知识库目录与严格的来源、分块、向量、查询隔离；
- 标题感知的 Markdown/PDF/DOCX 解析、图片与扫描 PDF OCR、parent-child chunking；
- BM25/全文检索与 pgvector 语义检索并行执行；
- Reciprocal Rank Fusion 去重融合，再由真实 LLM reranker 重排；
- 只基于检索证据生成回答，返回 source、section、excerpt 和各阶段分数；
- 查询改写、检索、融合、重排、生成的逐阶段 latency trace；
- 60 条中英文黄金问题，真实计算 Recall@5、MRR@5、Precision@5 与
  LLM evidence faithfulness；
- 端口与适配器架构：生产默认使用轻量 ONNX FastEmbed，也可将 Chat 与 Embedding
  分别接入任意 OpenAI-compatible 厂商，Ollama 仅作为可选 profile；
- React 调查控制台、FastAPI、Nginx、Caddy 自动 HTTPS、健康检查和 Docker Compose 单机部署。

![RunbookIQ console](docs/design/runbookiq-dashboard-concept.png)

## 解决的真实问题

线上故障发生后，值班人员往往要在官方文档、团队 Runbook、历史事故复盘之间反复切换。
普通语义搜索只给“相似内容”，普通聊天机器人又很难证明答案来自哪里。RunbookIQ 将两件事合并：

1. 用混合检索找出既包含精确术语、又在语义上相关的段落；
2. 把每条建议绑定到可审计的原文证据，并暴露整条检索 trace。

它适合做内部排障助手、交接知识库或事故复盘检索的基础版本。

## 架构

```mermaid
flowchart LR
    U[Browser] --> N[Nginx + React]
    N --> A[FastAPI]
    A --> Q[Query rewrite]
    Q --> H1[PostgreSQL FTS]
    Q --> H2[pgvector]
    H1 --> R[RRF fusion]
    H2 --> R
    R --> X[Reranker]
    X --> G[Grounded answer + citations]
    G --> O[External Chat API]
    A --> I[DOCX/PDF parser + OCR + parent-child chunker]
    I --> E[FastEmbed ONNX or external Embedding API]
    E --> P[(PostgreSQL + pgvector)]
```

核心领域模块与基础设施通过 Protocol 端口隔离。`InvestigationEngine` 不依赖 FastAPI、
PostgreSQL 或具体模型，因此检索融合和引用行为可以在没有外部服务的 CI 中稳定测试。
更完整的设计说明见 [docs/architecture.md](docs/architecture.md) 和
[CONTEXT.md](CONTEXT.md)。

## 5 分钟本地运行

本地模式不需要数据库和大模型，适合开发与演示真实的摄取、混合检索和引用链路。

后端：

```powershell
cd backend
uv sync --dev
$env:RUNBOOKIQ_MODE="local"
uv run uvicorn runbookiq.runtime:app --reload --port 8000
```

前端（新终端）：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，在 Ingestion 页面上传 `examples/runbooks` 中的三个文件，
再回到 Ask 页面提问。也可以把 `RUNBOOKIQ_URL` 设为 `http://localhost:8000` 后运行：

```powershell
.\scripts\seed.ps1
```

API 文档位于 `http://localhost:8000/docs`。

## 部署到 Linux 服务器

全部模型使用外部 API 时，建议至少 2 核 CPU、4 GB 内存、20 GB 磁盘；服务器只运行
Web、API 和 PostgreSQL/pgvector，不需要 GPU。

```bash
git clone <your-repository-url> runbook-iq
cd runbook-iq
cp .env.example .env
# 修改 .env 中的数据库密码和模型配置
# 配置已解析到服务器的根域名和主站域名；中文域名使用 xn-- 开头的 Punycode
docker compose up -d --build
docker compose ps
./scripts/seed.sh
```

确保域名的 A 记录已指向服务器，并在防火墙开放 TCP 80/443。Caddy 会自动申请和续期
TLS 证书、将 HTTP 重定向到 HTTPS，并把根域名重定向到主站域名。公网通过
`https://RUNBOOKIQ_PUBLIC_DOMAIN` 访问；`8080` 只绑定服务器回环地址，用于本机健康检查。

默认 Embedding 使用内置 FastEmbed ONNX 运行时，首次
启动会下载约 130 MB 的 `nomic-embed-text-v1.5-Q` 模型并缓存到 Docker volume；
Chat 与 reranker 使用你配置的外部 Chat API。当前版本提供企业所有者注册、登录、
服务端会话、企业域名和知识库归属校验。正式大规模商用前还应补充成员邀请、SSO、
细粒度角色权限、对象存储、备份和日志采集。

### 企业空间和专属域名

企业负责人在主站注册时填写企业名称与网址标识。例如标识为 `xinggang`，系统会登记：

```text
https://xinggang.rag.xn--bang-fe6gk6c.top
```

在域名控制台增加一条主机记录为 `*.rag`、记录值为服务器 IP 的 A 记录。Caddy 使用
On-Demand TLS 为已经登记在数据库中的企业域名自动签发证书；签发前会调用内部授权接口，
未知域名返回 403，不会消耗证书额度。企业用户也可以先在主站登录和使用，专属域名解析
生效后再从专属网址登录。

认证使用 HttpOnly、Secure、SameSite=Lax 的主机级 Cookie，数据库仅保存会话令牌和
CSRF 令牌的 SHA-256 摘要，密码使用 Argon2。所有知识库列表、上传、查询、删除和评测
接口都会在服务端校验 CSRF 与企业归属；无权访问的知识库统一返回 404，避免泄露资源
是否存在。

### GitHub 自动发布到服务器

生产更新链路使用不可变发布包：

```text
本地 main → GitHub → CI 测试 → 打包 commit → SSH 上传 → Docker 构建
→ 健康检查 → current 版本指针切换
```

服务器首次准备：

```bash
sudo bash scripts/server-bootstrap.sh shenjiu
```

生产 `.env` 只保存在服务器的 `~/runbookiq/shared/.env`，不会进入 GitHub。GitHub
仓库的 `production` Environment 需要配置以下 Actions secrets：

- `TOKYO_DEPLOY_HOST`：服务器 IP 或域名；
- `TOKYO_DEPLOY_USER`：非 root 部署用户；
- `TOKYO_DEPLOY_SSH_KEY`：专用于 GitHub Actions 的 SSH 私钥；
- `TOKYO_KNOWN_HOSTS`：预先核验的服务器 SSH host key。

推送 `main` 后，[CI 与东京发布工作流](.github/workflows/ci-deploy.yml)会先运行后端和
前端测试，全部成功才调用服务器的
[`deploy-release.sh`](scripts/deploy-release.sh)。部署脚本通过 `flock` 防止并发发布，
失败时恢复上一版本容器；`postgres_data` 和 `model_cache` 是命名 volume，因此发布
代码不会删除知识库或模型缓存。工作流只允许 `main` 分支进入生产发布，发布完成后还会
核对服务器 `current` 指针并通过公网 HTTPS 健康接口复验。不要把 API Key 写入 Actions
workflow 或仓库文件。

建议为 `main` 开启分支保护，并把 `test-backend`、`test-frontend` 设为必需检查。日常
更新通过功能分支和 Pull Request 合并；合并后的 `main` 推送会自动部署。手动运行
workflow 时也必须选择 `main`，其他分支只运行 CI，不会进入生产发布。

### 使用其他模型厂商

Chat 与 Embedding 已完全解耦，可以来自同一家或两家不同厂商。查询改写和回答复用
Chat 模型；文档摄取与查询向量使用 Embedding 模型。默认 reranker 也复用 Chat API，
根据语义相关性、故障标识符和操作价值重排候选；若外部模型不可用，会安全回退到原始
候选顺序。测试环境仍使用确定性的本地替身以保证结果可复现。

在 `.env` 中设置：

```dotenv
RUNBOOKIQ_CHAT_PROVIDER=openai_compatible
RUNBOOKIQ_CHAT_BASE_URL=https://vendor.example/v1
RUNBOOKIQ_CHAT_API_KEY=replace-with-vendor-key
RUNBOOKIQ_CHAT_MODEL=vendor-model-name
RUNBOOKIQ_CHAT_THINKING_ENABLED=false
RUNBOOKIQ_RERANK_PROVIDER=chat

RUNBOOKIQ_EMBEDDING_PROVIDER=openai_compatible
RUNBOOKIQ_EMBEDDING_BASE_URL=https://embedding-vendor.example/v1
RUNBOOKIQ_EMBEDDING_API_KEY=replace-with-embedding-vendor-key
RUNBOOKIQ_EMBEDDING_MODEL=vendor-embedding-model
RUNBOOKIQ_EMBEDDING_DIMENSIONS=1024
```

如不希望为 Embedding 另购 API，可保留默认本地 ONNX 配置：

```dotenv
RUNBOOKIQ_EMBEDDING_PROVIDER=fastembed
RUNBOOKIQ_EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5-Q
RUNBOOKIQ_EMBEDDING_DIMENSIONS=768
```

`RUNBOOKIQ_EMBEDDING_DIMENSIONS` 必须与厂商模型实际输出维度一致，并应在数据库首次
初始化前确定。更换到不同维度的模型时，需要新建向量表/数据卷并重新摄取文档，不能混用
旧向量。当前 `vector` HNSW 索引配置支持 1–2000 维。

然后启动：

```bash
docker compose up -d --build
docker compose logs -f api
```

例如，阿里云百炼北京地域可使用 `https://dashscope.aliyuncs.com/compatible-mode/v1`；
DeepSeek 可使用 `https://api.deepseek.com`。模型名称和 API Key 必须使用对应厂商控制台
提供的值。Embedding 可以使用另一家提供 OpenAI-compatible `/embeddings` 的厂商。
密钥只放在服务器 `.env`，不要提交到 Git，也不会发送给浏览器。

如果希望所有模型都在本地运行，把两个 provider 都改为 `ollama`，模型名改为对应
Ollama 模型，再启用可选 profile：

```bash
docker compose --profile local-models up -d --build
```

常用运维命令：

```bash
docker compose logs -f api
docker compose pull
docker compose up -d --build
```

## API 示例

创建独立知识库：

```bash
curl -X POST http://localhost:8080/api/knowledge-bases \
  -H "Content-Type: application/json" \
  -d '{"name":"支付系统","description":"支付服务运行手册与事故复盘"}'
```

响应中的 `id` 是后续上传、查询和评测必须携带的隔离键。删除知识库会级联删除其分块和
向量；内置 `platform` 知识库不能删除。

上传文档：

```bash
curl -F "knowledge_base_id=platform" \
  -F "file=@examples/runbooks/crashloopbackoff.md;type=text/markdown" \
  http://localhost:8080/api/documents
```

查询：

```bash
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"knowledge_base_id":"platform","question":"CrashLoopBackOff 应该先看什么？"}'
```

运行随仓库提交的 golden set：

```bash
curl -X POST http://localhost:8080/api/evaluations/run \
  -H "Content-Type: application/json" \
  -d '{"knowledge_base_id":"platform","suite_id":"platform-operations-v1","max_cases":6}'
```

省略 `max_cases` 会运行完整 60 条套件，在线模型模式下会产生更多 API 调用和费用。
`GET /api/evaluations/latest` 返回当前进程最近一次真实报告及逐题结果。

## 关键目录

```text
backend/runbookiq/
  ingestion/       解析、结构化切块、embedding 与写入
  investigation/   查询改写、并行检索、RRF、rerank、引用
  evaluation/      检索与回答质量评测
  adapters/        内存、PostgreSQL/pgvector、外部模型与可选 Ollama 适配器
  api/             FastAPI transport
frontend/src/      React 运维调查控制台
infra/postgres/    pgvector 表与索引
examples/          可摄取 Runbook 与 golden evaluation set
```

## 测试

```powershell
cd backend
uv run ruff check .
uv run pytest -q

# Docker 中的 PostgreSQL 已启动后，显式运行持久化集成测试
$env:RUNBOOKIQ_TEST_DATABASE_URL="postgresql+asyncpg://runbookiq:runbookiq@127.0.0.1:55432/runbookiq"
uv run pytest -q tests/test_postgres_persistence.py

cd ..\frontend
npm run test
npm run lint
npm run build
```

后端测试覆盖知识库隔离、API contract、RRF 调查链路、DOCX/OCR 解析、真实模型
adapter contract、持久化重启和评测指标。常规 CI 不调用在线模型，因此结果可复现、
不会因网络或模型漂移产生随机失败；PostgreSQL 测试由上面的环境变量显式开启。

## 简历写法

2026-07-24 在东京生产环境运行完整 60 条套件，实测 Recall@5 `1.0000`、
MRR@5 `0.9611`、Precision@5 `0.4694`、LLM 证据忠实度 `0.8212`；60 条问题
全部在前 5 条证据中命中黄金来源，其中 56 条首位命中。详细记录见
[完整评测报告](docs/evaluation/2026-07-24-production-benchmark.md)。

> 独立设计并实现面向 SRE 故障调查的企业级 RAG 工作台 RunbookIQ；构建
> 多知识库严格隔离及 Markdown/PDF/DOCX/OCR parent-child 摄取管线，基于 PostgreSQL
> FTS + pgvector 的双路检索、RRF 融合与 LLM rerank，并实现段落级引用和全链路
> latency trace；建立 60 条中英文 golden set，生产环境实测 Recall@5 1.00、
> MRR@5 0.96、证据忠实度 0.82，通过 Docker Compose 部署 React/FastAPI/
> PostgreSQL/Caddy 与可配置外部模型 API 完整服务。

面试时只使用完整 60 条套件的实际运行结果，不要把快速样本或未实测的提升比例写进简历。

## 文档生命周期

- `GET /api/knowledge-bases/{knowledge_base_id}/documents` 返回当前知识库的持久文档目录。
- 每个文档拥有独立的文档 ID、稳定来源 ID、SHA-256、当前版本、分块数和更新时间。
- 相同内容（包括某文档已经替换掉的旧内容）再次上传会复用原有逻辑文档，不会回滚当前版本，也不会重复消耗 Embedding。
- 替换文件时先完成解析和 Embedding，再在一个数据库事务中切换文档元数据与检索分块；失败时旧版本继续可用。
- 删除文档或整个知识库会级联删除全文索引和向量，并通过可重试清理队列移除持久化原件；知识库和企业租户权限同时参与校验。
- 原件保存在 Docker `document_data` 持久卷中，PostgreSQL 保存文档元数据和检索数据；迁移前已有来源会显示“无原件”，首次替换后恢复完整管理能力。

已有部署在执行 `docker compose up` 时会自动运行
`infra/postgres/006-document-lifecycle.sql`。升级前仍应先备份 PostgreSQL 数据卷。

## 已知边界与下一步

- 当前摄取在 API 进程内执行，适合单机与中等文档；大规模生产版应拆为持久化队列和 worker。
- 当前单 API 进程通过内容锁避免并发重复 Embedding；扩为多 worker 或多节点前，需要把该锁升级为 PostgreSQL 任务认领或分布式锁。
- 当前原件存储采用单服务器持久卷；扩展为多节点部署前，应通过现有对象存储接口迁移至 S3/MinIO。
- 当前保留当前可检索版本及递增版本号，尚未开放历史版本恢复；需要合规留档的企业应继续增加不可变版本记录和保留策略。
- OCR 质量受扫描分辨率、版面和语言包影响；生产版应补充页数上限、版面分析和人工校验通道。
- HTML 抓取尚未做站点级 robots、限速和增量同步，当前推荐上传公开资料的导出文件。

这些边界是有意写清楚的工程事实，也给后续迭代留下了明确方向。
