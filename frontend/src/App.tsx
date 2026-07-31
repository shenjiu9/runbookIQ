import { useEffect, useState } from "react";
import {
  askRunbook,
  createOrganizationInvitation,
  createKnowledgeBase,
  deleteKnowledgeBase,
  fetchCurrentUser,
  fetchHealth,
  fetchLatestEvaluation,
  fetchRuntimeConfig,
  listEvaluationSuites,
  listKnowledgeBases,
  listOrganizationInvitations,
  listOrganizationMembers,
  logout,
  revokeOrganizationInvitation,
  runEvaluation,
  uploadDocument
} from "./api";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { AskView } from "./pages/AskView";
import { AuthView } from "./pages/AuthView";
import {
  EvaluationView,
  IngestionView,
  KnowledgeView,
  SettingsView,
  TeamView
} from "./pages/SecondaryViews";
import type {
  CreatedTenantInvitation,
  EvaluationReport,
  EvaluationSuite,
  IngestionJob,
  KnowledgeBase,
  NavKey,
  OrganizationMember,
  QueryResponse,
  RuntimeConfig,
  TenantInvitation,
  TenantRole,
  TenantContext
} from "./types";

const defaultQuestion = "配置发布后 Deployment 进入 CrashLoopBackOff，应该优先检查什么？";
const emptyResponse: QueryResponse = {
  answer: "",
  confidence: 0,
  citations: [],
  trace: { query_id: "", stages: [] }
};

export default function App() {
  const [tenant, setTenant] = useState<TenantContext | null | undefined>(undefined);
  const [active, setActive] = useState<NavKey>("ask");
  const [question, setQuestion] = useState(defaultQuestion);
  const [response, setResponse] = useState<QueryResponse>(emptyResponse);
  const [selectedCitation, setSelectedCitation] = useState(0);
  const [inspectorTab, setInspectorTab] = useState<"evidence" | "trace">("evidence");
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null);
  const [ingestionLoading, setIngestionLoading] = useState(false);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null);
  const [evaluationSuites, setEvaluationSuites] = useState<EvaluationSuite[]>([]);
  const [selectedEvaluationSuiteId, setSelectedEvaluationSuiteId] = useState("");
  const [evaluationCatalogLoading, setEvaluationCatalogLoading] = useState(false);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("platform");
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [systemHealthy, setSystemHealthy] = useState<boolean | null>(null);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [runtimeConfigError, setRuntimeConfigError] = useState<string | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [invitations, setInvitations] = useState<TenantInvitation[]>([]);
  const [createdInvitation, setCreatedInvitation] =
    useState<CreatedTenantInvitation | null>(null);
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamError, setTeamError] = useState<string | null>(null);

  useEffect(() => {
    void fetchCurrentUser()
      .then(setTenant)
      .catch(() => setTenant(null));
  }, []);

  useEffect(() => {
    if (!tenant) return;
    setCatalogLoading(true);
    setCatalogError(null);
    void Promise.allSettled([
      listKnowledgeBases(),
      fetchHealth(),
      fetchRuntimeConfig()
    ]).then(
      ([catalogResult, healthResult, runtimeConfigResult]) => {
        if (catalogResult.status === "fulfilled") {
          setKnowledgeBases(catalogResult.value);
          if (!catalogResult.value.some((item) => item.id === "platform")) {
            setSelectedKnowledgeBaseId(catalogResult.value[0]?.id ?? "");
          }
        } else {
          setCatalogError("知识库目录加载失败");
        }
        setSystemHealthy(
          healthResult.status === "fulfilled" && healthResult.value.status === "ok"
        );
        if (runtimeConfigResult.status === "fulfilled") {
          setRuntimeConfig(runtimeConfigResult.value);
        } else {
          setRuntimeConfigError("运行配置读取失败");
        }
        setCatalogLoading(false);
      }
    );
  }, [tenant]);

  useEffect(() => {
    if (!tenant) return;
    setTeamLoading(true);
    setTeamError(null);
    const invitationsRequest = tenant.role === "owner" || tenant.role === "admin"
      ? listOrganizationInvitations()
      : Promise.resolve([]);
    void Promise.all([listOrganizationMembers(), invitationsRequest])
      .then(([nextMembers, nextInvitations]) => {
        setMembers(nextMembers);
        setInvitations(nextInvitations);
      })
      .catch((error) => {
        setTeamError(error instanceof Error ? error.message : "团队信息加载失败");
      })
      .finally(() => setTeamLoading(false));
  }, [tenant]);

  useEffect(() => {
    if (!tenant || !selectedKnowledgeBaseId) {
      setEvaluationSuites([]);
      setSelectedEvaluationSuiteId("");
      setEvaluationReport(null);
      return;
    }

    let cancelled = false;
    setEvaluationCatalogLoading(true);
    setEvaluationError(null);
    setEvaluationSuites([]);
    setSelectedEvaluationSuiteId("");
    setEvaluationReport(null);

    void Promise.allSettled([
      listEvaluationSuites(selectedKnowledgeBaseId),
      fetchLatestEvaluation(selectedKnowledgeBaseId)
    ]).then(([suitesResult, latestResult]) => {
      if (cancelled) return;
      if (suitesResult.status === "fulfilled") {
        const suites = suitesResult.value;
        const latest = latestResult.status === "fulfilled" ? latestResult.value : null;
        setEvaluationSuites(suites);
        setEvaluationReport(latest);
        setSelectedEvaluationSuiteId(
          suites.some((suite) => suite.id === latest?.suite_id)
            ? latest?.suite_id ?? ""
            : suites[0]?.id ?? ""
        );
      } else {
        setEvaluationError("评测集目录加载失败");
      }
      setEvaluationCatalogLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedKnowledgeBaseId, tenant]);

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
    if (!selectedKnowledgeBaseId || !selectedEvaluationSuiteId) return;
    setEvaluationLoading(true);
    setEvaluationError(null);
    try {
      setEvaluationReport(
        await runEvaluation(selectedKnowledgeBaseId, selectedEvaluationSuiteId)
      );
    } catch (error) {
      setEvaluationError(error instanceof Error ? error.message : "质量评测失败");
    } finally {
      setEvaluationLoading(false);
    }
  }

  function selectKnowledgeBase(knowledgeBaseId: string) {
    setSelectedKnowledgeBaseId(knowledgeBaseId);
    setResponse(emptyResponse);
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
      if (selectedKnowledgeBaseId === knowledgeBaseId) {
        const nextId = knowledgeBases.find((item) => item.id !== knowledgeBaseId)?.id ?? "";
        selectKnowledgeBase(nextId);
      }
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "知识库删除失败");
    } finally {
      setCatalogLoading(false);
    }
  }

  async function inviteMember(
    email: string,
    role: Exclude<TenantRole, "owner">
  ) {
    setTeamLoading(true);
    setTeamError(null);
    try {
      const created = await createOrganizationInvitation(email, role);
      setCreatedInvitation(created);
      setInvitations((current) => [
        ...current,
        {
          id: created.id,
          email: created.email,
          role: created.role,
          expires_at: created.expires_at,
          created_at: created.created_at
        }
      ]);
    } catch (error) {
      setTeamError(error instanceof Error ? error.message : "成员邀请创建失败");
    } finally {
      setTeamLoading(false);
    }
  }

  async function revokeInvitation(invitationId: string) {
    setTeamLoading(true);
    setTeamError(null);
    try {
      await revokeOrganizationInvitation(invitationId);
      setInvitations((current) => current.filter((item) => item.id !== invitationId));
      if (createdInvitation?.id === invitationId) setCreatedInvitation(null);
    } catch (error) {
      setTeamError(error instanceof Error ? error.message : "邀请撤销失败");
    } finally {
      setTeamLoading(false);
    }
  }

  const selectedKnowledgeBase = knowledgeBases.find(
    (item) => item.id === selectedKnowledgeBaseId
  );

  async function signOut() {
    try {
      await logout();
    } finally {
      setTenant(null);
      setKnowledgeBases([]);
      setSelectedKnowledgeBaseId("");
      setResponse(emptyResponse);
    }
  }

  if (tenant === undefined) {
    return (
      <main className="session-loading" aria-live="polite">
        <span className="brand-mark">R</span>
        <strong>正在安全连接企业空间...</strong>
      </main>
    );
  }

  if (tenant === null) {
    return <AuthView onAuthenticated={setTenant} />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        active={active}
        onChange={setActive}
        organizationName={tenant.organization.name}
      />
      <div className="app-main">
        <Topbar
          healthy={systemHealthy}
          knowledgeBaseName={selectedKnowledgeBase?.name ?? "未选择知识库"}
          organizationName={tenant.organization.name}
          userEmail={tenant.user.email}
          onLogout={() => void signOut()}
        />
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
              evaluationSuites={evaluationSuites}
              selectedEvaluationSuiteId={selectedEvaluationSuiteId}
              evaluationCatalogLoading={evaluationCatalogLoading}
              evaluationLoading={evaluationLoading}
              canRunEvaluation={tenant.role !== "viewer"}
              onEvaluationSuiteChange={setSelectedEvaluationSuiteId}
              onEvaluate={evaluate}
              knowledgeBases={knowledgeBases}
              selectedKnowledgeBaseId={selectedKnowledgeBaseId}
              onKnowledgeBaseChange={selectKnowledgeBase}
              ingestionJob={ingestionJob}
              knowledgeBaseName={selectedKnowledgeBase?.name ?? "未选择知识库"}
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
              role={tenant.role}
              onStartUpload={() => setActive("ingestion")}
              onStartAsk={() => setActive("ask")}
            />
          ) : null}
          {active === "ingestion" ? <IngestionView knowledgeBaseName={selectedKnowledgeBase?.name ?? "未选择知识库"} job={ingestionJob} loading={ingestionLoading} error={ingestionError} onUpload={ingest} role={tenant.role} /> : null}
          {active === "evaluation" ? (
            <EvaluationView
              knowledgeBaseName={selectedKnowledgeBase?.name ?? "未选择知识库"}
              suites={evaluationSuites}
              selectedSuiteId={selectedEvaluationSuiteId}
              catalogLoading={evaluationCatalogLoading}
              report={evaluationReport}
              loading={evaluationLoading}
              error={evaluationError}
              onSuiteChange={setSelectedEvaluationSuiteId}
              onRun={evaluate}
              role={tenant.role}
            />
          ) : null}
          {active === "team" ? (
            <TeamView
              organizationName={tenant.organization.name}
              organizationUrl={tenant.organization.url}
              currentRole={tenant.role}
              members={members}
              invitations={invitations}
              createdInvitation={createdInvitation}
              loading={teamLoading}
              error={teamError}
              onInvite={inviteMember}
              onRevoke={revokeInvitation}
            />
          ) : null}
          {active === "settings" ? (
            <SettingsView config={runtimeConfig} error={runtimeConfigError} />
          ) : null}
        </main>
      </div>
    </div>
  );
}
