import { useEffect, useState } from "react";
import {
  askRunbook,
  createKnowledgeBase,
  deleteKnowledgeBase,
  fetchLatestEvaluation,
  listKnowledgeBases,
  runEvaluation,
  uploadDocument
} from "./api";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { initialResponse } from "./demoData";
import { AskView } from "./pages/AskView";
import { EvaluationView, IngestionView, KnowledgeView, SettingsView } from "./pages/SecondaryViews";
import type {
  EvaluationReport,
  IngestionJob,
  KnowledgeBase,
  NavKey,
  QueryResponse
} from "./types";

const defaultQuestion = "配置发布后 Deployment 进入 CrashLoopBackOff，应该优先检查什么？";

export default function App() {
  const [active, setActive] = useState<NavKey>("ask");
  const [question, setQuestion] = useState(defaultQuestion);
  const [response, setResponse] = useState<QueryResponse>(initialResponse);
  const [selectedCitation, setSelectedCitation] = useState(0);
  const [inspectorTab, setInspectorTab] = useState<"evidence" | "trace">("evidence");
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null);
  const [ingestionLoading, setIngestionLoading] = useState(false);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("platform");
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.allSettled([listKnowledgeBases(), fetchLatestEvaluation()]).then(
      ([catalogResult, evaluationResult]) => {
        if (catalogResult.status === "fulfilled") {
          setKnowledgeBases(catalogResult.value);
          if (!catalogResult.value.some((item) => item.id === "platform")) {
            setSelectedKnowledgeBaseId(catalogResult.value[0]?.id ?? "");
          }
        } else {
          setCatalogError("知识库目录加载失败");
        }
        if (evaluationResult.status === "fulfilled") {
          setEvaluationReport(evaluationResult.value);
        }
        setCatalogLoading(false);
      }
    );
  }, []);

  async function investigate() {
    if (!selectedKnowledgeBaseId) return;
    setQueryLoading(true);
    setQueryError(null);
    try {
      const next = await askRunbook(selectedKnowledgeBaseId, question);
      setResponse(next);
      setSelectedCitation(0);
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "故障调查失败");
    } finally {
      setQueryLoading(false);
    }
  }

  async function ingest(file: File) {
    if (!selectedKnowledgeBaseId) return;
    setIngestionLoading(true);
    setIngestionError(null);
    try {
      setIngestionJob(await uploadDocument(selectedKnowledgeBaseId, file));
    } catch (error) {
      setIngestionError(error instanceof Error ? error.message : "文档上传失败");
    } finally {
      setIngestionLoading(false);
    }
  }

  async function evaluate() {
    if (!selectedKnowledgeBaseId) return;
    setEvaluationLoading(true);
    setEvaluationError(null);
    try {
      setEvaluationReport(await runEvaluation(selectedKnowledgeBaseId));
    } catch (error) {
      setEvaluationError(error instanceof Error ? error.message : "质量评测失败");
    } finally {
      setEvaluationLoading(false);
    }
  }

  function selectKnowledgeBase(knowledgeBaseId: string) {
    setSelectedKnowledgeBaseId(knowledgeBaseId);
    setResponse({
      answer: "请在当前知识库中提交问题，系统将只使用该库的证据回答。",
      confidence: 0,
      citations: [],
      trace: { query_id: "pending", stages: [] }
    });
    setSelectedCitation(0);
    setQueryError(null);
  }

  async function addKnowledgeBase(name: string, description: string) {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const created = await createKnowledgeBase(name, description);
      setKnowledgeBases((current) => [...current, created]);
      selectKnowledgeBase(created.id);
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "知识库创建失败");
    } finally {
      setCatalogLoading(false);
    }
  }

  async function removeKnowledgeBase(knowledgeBaseId: string) {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      await deleteKnowledgeBase(knowledgeBaseId);
      setKnowledgeBases((current) => current.filter((item) => item.id !== knowledgeBaseId));
      if (selectedKnowledgeBaseId === knowledgeBaseId) selectKnowledgeBase("platform");
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "知识库删除失败");
    } finally {
      setCatalogLoading(false);
    }
  }

  const selectedKnowledgeBase = knowledgeBases.find(
    (item) => item.id === selectedKnowledgeBaseId
  );

  return (
    <div className="app-shell">
      <Sidebar active={active} onChange={setActive} />
      <div className="app-main">
        <Topbar />
        <main>
          {active === "ask" ? (
            <AskView
              question={question}
              onQuestionChange={setQuestion}
              response={response}
              loading={queryLoading}
              error={queryError}
              selected={selectedCitation}
              onSelectedChange={setSelectedCitation}
              inspectorTab={inspectorTab}
              onInspectorTabChange={setInspectorTab}
              onSubmit={investigate}
              evaluationReport={evaluationReport}
              evaluationLoading={evaluationLoading}
              onEvaluate={evaluate}
              knowledgeBases={knowledgeBases}
              selectedKnowledgeBaseId={selectedKnowledgeBaseId}
              onKnowledgeBaseChange={selectKnowledgeBase}
            />
          ) : null}
          {active === "knowledge" ? (
            <KnowledgeView
              knowledgeBases={knowledgeBases}
              selectedKnowledgeBaseId={selectedKnowledgeBaseId}
              loading={catalogLoading}
              error={catalogError}
              onSelect={selectKnowledgeBase}
              onCreate={addKnowledgeBase}
              onDelete={removeKnowledgeBase}
            />
          ) : null}
          {active === "ingestion" ? <IngestionView knowledgeBaseName={selectedKnowledgeBase?.name ?? "未选择知识库"} job={ingestionJob} loading={ingestionLoading} error={ingestionError} onUpload={ingest} /> : null}
          {active === "evaluation" ? <EvaluationView report={evaluationReport} loading={evaluationLoading} error={evaluationError} onRun={evaluate} /> : null}
          {active === "settings" ? <SettingsView /> : null}
        </main>
      </div>
    </div>
  );
}
