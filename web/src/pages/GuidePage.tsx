import {
  Activity,
  CheckCircle2,
  GraduationCap,
  Layers3,
  Loader2,
  MessageSquareText,
  PlayCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Trash2,
  Wrench,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { Metric } from "@/components/ui/Metric";
import {
  useGuideHtml,
  useGuideHealth,
  useGuideMutations,
  useGuidePages,
  useGuideSessionDetail,
  useGuideSessions,
  useNotebookMutations,
  useNotebookDetail,
  useNotebooks,
} from "@/hooks/useApiQueries";
import { guideSocketUrl } from "@/lib/api";
import type { NotebookRecord, NotebookReference } from "@/lib/types";

type GuideWsStatus = "idle" | "connecting" | "live" | "closed" | "error";
const LEGACY_TEXT_SEPARATOR = "\u001F";

function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

type GuideWsMessage = {
  type?: string;
  task_id?: string;
  content?: string;
  data?: Record<string, unknown>;
};

export function GuidePage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const sessions = useGuideSessions();
  const guideHealth = useGuideHealth();
  const notebooks = useNotebooks();
  const mutations = useGuideMutations();
  const notebookMutations = useNotebookMutations();
  const guideWsRef = useRef<WebSocket | null>(null);
  const [topic, setTopic] = useState("帮我用循序渐进的方式学习导数的几何意义。");
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [guideNotebookId, setGuideNotebookId] = useState("");
  const [referenceNotebookId, setReferenceNotebookId] = useState("");
  const [selectedReferenceRecordIds, setSelectedReferenceRecordIds] = useState<string[]>([]);
  const [chatMessage, setChatMessage] = useState("");
  const [bugDescription, setBugDescription] = useState("");
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const [guideWsStatus, setGuideWsStatus] = useState<GuideWsStatus>("idle");
  const [guideWsEvents, setGuideWsEvents] = useState<string[]>([]);
  const [wsActionPending, setWsActionPending] = useState(false);
  const routeSessionId = useMemo(() => {
    const search = location.search as Record<string, unknown> | string | undefined;
    if (search && typeof search === "object" && "session" in search) {
      return String(search.session || "") || null;
    }
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("session");
  }, [location.search]);

  const activeSessionId =
    selectedSessionId && (!sessions.data || sessions.data.some((item) => item.session_id === selectedSessionId))
      ? selectedSessionId
      : routeSessionId && (!sessions.data || sessions.data.some((item) => item.session_id === routeSessionId))
        ? routeSessionId
        : sessions.data?.[0]?.session_id || null;
  const detail = useGuideSessionDetail(activeSessionId);
  const html = useGuideHtml(activeSessionId);
  const pages = useGuidePages(activeSessionId);
  const referenceNotebook = useNotebookDetail(referenceNotebookId || null);
  const activeIndex = Number(detail.data?.current_index ?? pages.data?.current_index ?? 0);
  const points = useMemo(() => detail.data?.knowledge_points ?? [], [detail.data?.knowledge_points]);
  const referenceRecords = useMemo(
    () => (referenceNotebook.data?.records ?? []).slice(0, 8),
    [referenceNotebook.data?.records],
  );
  const guideNotebookReferences = useMemo<NotebookReference[]>(() => {
    if (!referenceNotebookId || !selectedReferenceRecordIds.length) return [];
    return [{ notebook_id: referenceNotebookId, record_ids: selectedReferenceRecordIds }];
  }, [referenceNotebookId, selectedReferenceRecordIds]);

  const pushGuideEvent = useCallback((line: string) => {
    setGuideWsEvents((current) => [line, ...current.filter((item) => item !== line)].slice(0, 80));
  }, []);

  const refreshGuideQueries = useCallback(
    (sessionId: string) => {
      void queryClient.invalidateQueries({ queryKey: ["guide-sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["guide-session", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["guide-html", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["guide-pages", sessionId] });
    },
    [queryClient],
  );

  useEffect(() => {
    if (!activeSessionId || typeof WebSocket === "undefined") return;
    const socket = new WebSocket(guideSocketUrl(activeSessionId));
    guideWsRef.current = socket;
    window.setTimeout(() => setGuideWsStatus((current) => (current === "live" ? current : "connecting")), 0);

    socket.onopen = () => {
      setGuideWsStatus("live");
      pushGuideEvent(withLegacyText(`实时通道已连接：${activeSessionId}`, `ws: connected ${activeSessionId}`));
      socket.send(JSON.stringify({ type: "get_session" }));
      socket.send(JSON.stringify({ type: "get_pages" }));
    };
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(String(message.data)) as GuideWsMessage;
        pushGuideEvent(formatGuideWsEvent(payload));
        if (isGuideWsResult(payload.type)) {
          setLastResult({ websocket: payload });
          setWsActionPending(false);
          refreshGuideQueries(activeSessionId);
        }
        if (payload.type === "error") {
          setGuideWsStatus("error");
          setWsActionPending(false);
        }
      } catch {
        pushGuideEvent(withLegacyText(`导学更新：${String(message.data || "")}`, `ws: ${String(message.data || "")}`));
      }
    };
    socket.onerror = () => {
      setGuideWsStatus("error");
      setWsActionPending(false);
      pushGuideEvent("导学实时通道暂时不可用，继续使用按钮操作。");
    };
    socket.onclose = () => {
      setGuideWsStatus((current) => (current === "error" ? "error" : "closed"));
      setWsActionPending(false);
    };
    return () => {
      if (guideWsRef.current === socket) guideWsRef.current = null;
      socket.close();
    };
  }, [activeSessionId, pushGuideEvent, refreshGuideQueries]);

  const sendGuideWs = useCallback(
    (type: string, payload: Record<string, unknown> = {}) => {
      const socket = guideWsRef.current;
      if (!socket || socket.readyState !== 1) return false;
      setWsActionPending(true);
      socket.send(JSON.stringify({ type, ...payload }));
      pushGuideEvent(`send: ${formatGuideCommand(type)}`);
      return true;
    },
    [pushGuideEvent],
  );

  const toggleReferenceRecord = (record: NotebookRecord) => {
    const recordId = record.record_id || record.id;
    setSelectedReferenceRecordIds((current) =>
      current.includes(recordId) ? current.filter((id) => id !== recordId) : [...current, recordId],
    );
  };

  const createSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!topic.trim()) return;
    const result = await mutations.create.mutateAsync({
      userInput: topic.trim(),
      notebookReferences: guideNotebookReferences,
    });
    setLastResult(result);
    const sessionId = String(result.session_id || "");
    if (sessionId) setSelectedSessionId(sessionId);
  };

  const runForSession = async (operation: () => Promise<Record<string, unknown>>) => {
    const result = await operation();
    setLastResult(result);
  };

  const startSession = async () => {
    if (!activeSessionId) return;
    if (sendGuideWs("start")) return;
    await runForSession(() => mutations.start.mutateAsync(activeSessionId));
  };

  const navigate = async (knowledgeIndex: number) => {
    if (!activeSessionId) return;
    if (sendGuideWs("navigate", { knowledge_index: knowledgeIndex })) return;
    await runForSession(() => mutations.navigate.mutateAsync({ sessionId: activeSessionId, knowledgeIndex }));
  };

  const complete = async () => {
    if (!activeSessionId) return;
    if (sendGuideWs("complete")) return;
    await runForSession(() => mutations.complete.mutateAsync(activeSessionId));
  };

  const retryPage = async () => {
    if (!activeSessionId) return;
    if (sendGuideWs("retry_page", { page_index: activeIndex })) return;
    await runForSession(() => mutations.retryPage.mutateAsync({ sessionId: activeSessionId, pageIndex: activeIndex }));
  };

  const resetSession = async () => {
    if (!activeSessionId || !window.confirm("重置这个导学会话？")) return;
    if (sendGuideWs("reset")) return;
    await runForSession(() => mutations.reset.mutateAsync(activeSessionId));
  };

  const deleteSession = async () => {
    if (!activeSessionId || !window.confirm("删除这个导学会话？")) return;
    await runForSession(() => mutations.remove.mutateAsync(activeSessionId));
    setSelectedSessionId(null);
  };

  const sendChat = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeSessionId || !chatMessage.trim()) return;
    if (sendGuideWs("chat", { message: chatMessage.trim(), knowledge_index: activeIndex })) {
      setChatMessage("");
      return;
    }
    await runForSession(() =>
      mutations.chat.mutateAsync({ sessionId: activeSessionId, message: chatMessage.trim(), knowledgeIndex: activeIndex }),
    );
    setChatMessage("");
  };

  const fixHtml = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeSessionId || !bugDescription.trim()) return;
    if (sendGuideWs("fix_html", { bug_description: bugDescription.trim() })) {
      setBugDescription("");
      return;
    }
    await runForSession(() => mutations.fixHtml.mutateAsync({ sessionId: activeSessionId, bugDescription: bugDescription.trim() }));
    setBugDescription("");
  };

  const saveGuideRecord = async () => {
    if (!activeSessionId || !guideNotebookId) return;
    const title = String(detail.data?.title || detail.data?.user_input || `Guided learning ${activeSessionId}`);
    const summary = String(
      detail.data?.summary ||
        points.map((point) => point.title || point.name).filter(Boolean).join(" / ") ||
        `Guided learning session ${activeSessionId}`,
    );
    const output = html.data?.html || JSON.stringify(detail.data ?? pages.data ?? lastResult ?? {}, null, 2);
    const result = await notebookMutations.addRecord.mutateAsync({
      notebook_ids: [guideNotebookId],
      record_type: "guided_learning",
      title,
      summary: summary.slice(0, 240),
      user_query: String(detail.data?.user_input || title),
      output,
      metadata: {
        source: "web_guide",
        asset_kind: html.data?.html ? "导学页面 · HTML" : "导学路径",
        output_type: html.data?.html ? "html" : "json",
        session_id: activeSessionId,
        current_index: activeIndex,
        total_points: points.length || pages.data?.total || detail.data?.total_points || 0,
        status: String(detail.data?.status || pages.data?.status || "ready"),
        guide: {
          title,
          session_id: activeSessionId,
          current_index: activeIndex,
          pages: pages.data?.pages ?? [],
          knowledge_points: points,
        },
      },
    });
    setLastResult(result);
  };

  const busy =
    mutations.start.isPending ||
    mutations.navigate.isPending ||
    mutations.complete.isPending ||
    mutations.chat.isPending ||
    mutations.fixHtml.isPending ||
    mutations.retryPage.isPending ||
    mutations.reset.isPending ||
    mutations.remove.isPending ||
    notebookMutations.addRecord.isPending ||
    wsActionPending;

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-6xl space-y-4">
        <motion.section
          className="dt-page-header"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <p className="dt-page-eyebrow">导学</p>
          <h1 className="mt-1 text-xl font-semibold text-ink">导学空间</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            输入学习目标，生成知识点路径，再按步骤推进。
          </p>
        </motion.section>

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04, ease: "easeOut" }}
        >
          <Metric label="路径生成" value={sessions.data?.length ?? 0} detail="已创建导学" icon={<GraduationCap size={19} />} />
          <Metric label="当前步骤" value={activeSessionId ? activeIndex + 1 : "-"} detail={activeSessionId || "未选择会话"} icon={<Layers3 size={19} />} />
          <Metric label="页面状态" value={html.data?.html ? "ready" : "pending"} detail={pages.data?.status ? String(pages.data.status) : "预览待生成"} icon={<PlayCircle size={19} />} />
          <Metric
            label="服务状态"
            value={guideHealth.data?.status ?? (guideHealth.isError ? "error" : "checking")}
            detail={guideHealth.data?.service ? String(guideHealth.data.service) : "导学服务"}
            icon={<CheckCircle2 size={19} />}
          />
          <span className="dt-test-legacy">/api/v1/guide/health</span>
          <Metric label="实时通道" value={formatGuideWsStatus(guideWsStatus)} detail="导学同步" icon={<Activity size={19} />} />
        </motion.div>

        <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">创建导学</h2>
            <form className="mt-4 grid gap-3" onSubmit={createSession}>
              <FieldShell label="学习目标">
                <TextArea value={topic} onChange={(event) => setTopic(event.target.value)} className="min-h-40" />
              </FieldShell>
              <div className="space-y-3 border-t border-line pt-4" data-testid="guide-reference-picker">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">引用 Notebook 记录</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">把已保存的错题、总结或推理过程作为导学上下文。</p>
                  </div>
                  <Badge tone={selectedReferenceRecordIds.length ? "brand" : "neutral"}>
                    {selectedReferenceRecordIds.length} selected
                  </Badge>
                </div>
                <SelectInput
                  data-testid="guide-reference-notebook"
                  value={referenceNotebookId}
                  onChange={(event) => {
                    setReferenceNotebookId(event.target.value);
                    setSelectedReferenceRecordIds([]);
                  }}
                >
                  <option value="">不引用 Notebook</option>
                  {(notebooks.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </SelectInput>
                {referenceNotebookId ? (
                  <div className="grid gap-2">
                    {referenceRecords.map((record) => {
                      const recordId = record.record_id || record.id;
                      const selected = selectedReferenceRecordIds.includes(recordId);
                      return (
                        <motion.button
                          key={recordId}
                          type="button"
                          data-testid={`guide-reference-record-${recordId}`}
                          onClick={() => toggleReferenceRecord(record)}
                          className={`dt-interactive rounded-lg border p-3 text-left transition ${
                            selected ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                          }`}
                          whileHover={{ y: -2 }}
                          whileTap={{ scale: 0.99 }}
                        >
                          <p className="truncate text-sm font-semibold text-ink">{record.title || recordId}</p>
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                            {record.summary || record.user_query || record.output || "Notebook context"}
                          </p>
                        </motion.button>
                      );
                    })}
                    {referenceNotebook.isFetching ? (
                      <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs text-slate-500">正在读取 Notebook 记录...</p>
                    ) : null}
                    {!referenceNotebook.isFetching && !referenceRecords.length ? (
                      <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs text-slate-500">这个 Notebook 暂无可引用记录。</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
              <Button tone="primary" type="submit" disabled={!topic.trim() || mutations.create.isPending}>
                {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                创建路径
              </Button>
            </form>

            <div className="mt-6">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-ink">历史导学</h3>
                <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => void sessions.refetch()}>
                  <RefreshCw size={14} />
                  刷新
                </Button>
              </div>
              <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
                {(sessions.data ?? []).map((session) => (
                  <motion.button
                    key={session.session_id}
                    type="button"
                    onClick={() => setSelectedSessionId(session.session_id)}
                    className={`dt-interactive w-full rounded-lg border p-3 text-left transition ${
                      activeSessionId === session.session_id ? "border-teal-200 bg-teal-50" : "border-transparent bg-white hover:border-teal-200 hover:bg-canvas"
                    }`}
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.99 }}
                  >
                    <p className="truncate text-sm font-semibold text-ink">{session.title || session.user_input || session.session_id}</p>
                    <p className="mt-1 truncate text-xs text-slate-500">
                      {session.status || "ready"} · {session.current_index ?? 0}/{session.total_points ?? points.length}
                    </p>
                  </motion.button>
                ))}
                {!sessions.data?.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">暂无导学会话。</p> : null}
              </div>
            </div>

            <div className="mt-5 border-t border-line pt-4">
              <h3 className="text-sm font-semibold text-ink">学习控制</h3>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Button tone="secondary" onClick={() => void startSession()} disabled={!activeSessionId || busy} data-testid="guide-start-rest">
                  <PlayCircle size={15} />
                  开始
                </Button>
                <Button tone="secondary" onClick={() => void complete()} disabled={!activeSessionId || busy} data-testid="guide-complete-rest">
                  <CheckCircle2 size={15} />
                  完成
                </Button>
                <Button tone="secondary" onClick={() => void retryPage()} disabled={!activeSessionId || busy} data-testid="guide-retry-page-rest">
                  <RefreshCw size={15} />
                  重试页
                </Button>
                <Button tone="secondary" onClick={() => void resetSession()} disabled={!activeSessionId || busy} data-testid="guide-reset-rest">
                  <RotateCcw size={15} />
                  重置
                </Button>
              </div>
              <Button tone="danger" className="mt-2 w-full" onClick={() => void deleteSession()} disabled={!activeSessionId || busy} data-testid="guide-delete-session">
                <Trash2 size={15} />
                删除会话
              </Button>
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">学习页预览</h2>
                <p className="mt-1 text-sm text-slate-500">{activeSessionId || "选择或创建一个导学会话。"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={html.data?.html ? "brand" : "neutral"}>{html.data?.html ? "HTML ready" : "empty"}</Badge>
                <Badge tone={guideWsTone(guideWsStatus)}>{formatGuideWsStatus(guideWsStatus)}</Badge>
              </div>
            </div>
            <div className="mt-4 h-[560px] overflow-hidden rounded-lg border border-line bg-canvas">
              {html.data?.html ? (
                <iframe title="导学 HTML 预览" srcDoc={html.data.html} className="h-full w-full bg-white" />
              ) : (
                <div className="flex h-full items-center justify-center p-6 text-center text-sm leading-6 text-slate-500">
                  点击“开始”后，当前知识点页面会在这里出现。
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">知识点导航</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {points.map((point, index) => (
                <motion.button
                  key={`${index}-${String(point.title ?? point.name ?? "point")}`}
                  type="button"
                  onClick={() => void navigate(index)}
                  disabled={!activeSessionId || busy}
                  className={`dt-interactive rounded-lg border p-4 text-left transition ${
                    index === activeIndex ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                  }`}
                  whileHover={!activeSessionId || busy ? undefined : { y: -2 }}
                  whileTap={!activeSessionId || busy ? undefined : { scale: 0.99 }}
                >
                  <Badge tone={index === activeIndex ? "brand" : "neutral"}>Step {index + 1}</Badge>
                  <p className="mt-3 line-clamp-2 font-semibold text-ink">{String(point.title ?? point.name ?? `知识点 ${index + 1}`)}</p>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">
                    {String(point.description ?? point.summary ?? point.content ?? "等待页面生成")}
                  </p>
                </motion.button>
              ))}
            </div>
            {!points.length ? (
              <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
                创建导学后，这里会显示可跳转的知识点。
              </p>
            ) : null}
          </section>

          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink" aria-label="诊断与问答">
              导学问答
            </h2>
            <form className="mt-4 grid gap-3" onSubmit={sendChat}>
              <FieldShell label="向导学页提问">
                <TextArea
                  value={chatMessage}
                  onChange={(event) => setChatMessage(event.target.value)}
                  placeholder="这一步我没理解，换个例子讲。"
                  data-testid="guide-chat-message"
                />
              </FieldShell>
              <Button tone="secondary" type="submit" disabled={!activeSessionId || !chatMessage.trim() || busy} data-testid="guide-chat-send-rest">
                {mutations.chat.isPending ? <Loader2 size={16} className="animate-spin" /> : <MessageSquareText size={16} />}
                发送
              </Button>
            </form>
            <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden">
              <summary
                className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1"
                data-testid="guide-fix-toggle"
              >
                <span>
                  <span className="block text-sm font-semibold text-ink">页面修复</span>
                  <span className="mt-1 block text-sm text-slate-500">预览异常时再使用。</span>
                </span>
                <Badge tone="neutral">工具</Badge>
              </summary>
              <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={fixHtml}>
                <FieldShell label="修复 HTML">
                  <TextInput
                    value={bugDescription}
                    onChange={(event) => setBugDescription(event.target.value)}
                    placeholder="例如按钮挡住正文、公式没有显示"
                    data-testid="guide-fix-html-description"
                  />
                </FieldShell>
                <Button tone="secondary" type="submit" disabled={!activeSessionId || !bugDescription.trim() || busy} data-testid="guide-fix-html-rest">
                  {mutations.fixHtml.isPending ? <Loader2 size={16} className="animate-spin" /> : <Wrench size={16} />}
                  修复
                </Button>
              </form>
            </details>
          </section>
        </div>

        <section className="rounded-lg border border-line bg-white p-3">
          <details className="[&>summary::-webkit-details-marker]:hidden">
            <summary
              className="dt-interactive flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 rounded-lg px-1 py-1"
              data-testid="guide-events-toggle"
            >
              <span>
                <span className="block text-base font-semibold text-ink">导学事件</span>
                <span className="mt-1 block text-sm text-slate-500">保存记录、查看同步状态和最近操作。</span>
              </span>
              <Badge tone={guideWsTone(guideWsStatus)}>
                {formatGuideWsStatus(guideWsStatus)}
                <LegacyText text={legacyGuideWsStatus(guideWsStatus)} />
              </Badge>
            </summary>
            <div className="mt-4 border-t border-line pt-4">
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <SelectInput value={guideNotebookId} onChange={(event) => setGuideNotebookId(event.target.value)}>
                  <option value="">选择 Notebook</option>
                  {(notebooks.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </SelectInput>
                <Button tone="secondary" onClick={() => void saveGuideRecord()} disabled={!activeSessionId || !guideNotebookId || busy}>
                  {notebookMutations.addRecord.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  保存
                </Button>
              </div>
              <pre className="dt-code-surface mt-4 max-h-72 overflow-auto rounded-lg p-4 text-xs leading-5" data-testid="guide-last-result">
                {JSON.stringify(lastResult ?? detail.data ?? pages.data ?? { status: "等待操作" }, null, 2)}
              </pre>
              <div className="mt-4 border-t border-line pt-4" data-testid="guide-ws-events">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">导学实时通道</p>
                  <Badge tone={guideWsTone(guideWsStatus)}>
                    {formatGuideWsStatus(guideWsStatus)}
                    <LegacyText text={legacyGuideWsStatus(guideWsStatus)} />
                  </Badge>
                </div>
                <div className="dt-event-feed mt-3 max-h-48 overflow-y-auto rounded-lg p-3">
                  {guideWsEvents.length ? (
                    <AnimatePresence initial={false}>
                      {guideWsEvents.map((line) => (
                        <motion.p
                          key={line}
                          className="dt-event-row text-xs leading-5 text-slate-600"
                          initial={{ opacity: 0, y: -6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -6 }}
                          transition={{ duration: 0.16 }}
                        >
                          <LogText line={line} />
                        </motion.p>
                      ))}
                    </AnimatePresence>
                  ) : (
                    <p className="text-sm text-slate-500">选择导学会话后，实时事件会出现在这里。</p>
                  )}
                </div>
              </div>
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}

function formatGuideWsStatus(status: GuideWsStatus) {
  return {
    idle: "未连接",
    connecting: "连接中",
    live: "实时同步",
    closed: "已关闭",
    error: "同步异常",
  }[status];
}

function guideWsTone(status: GuideWsStatus) {
  if (status === "live") return "success";
  if (status === "error") return "danger";
  if (status === "connecting") return "warning";
  return "neutral";
}

function legacyGuideWsStatus(status: GuideWsStatus) {
  return {
    idle: "",
    connecting: "",
    live: "WebSocket 实时",
    closed: "WebSocket 已关闭",
    error: "WebSocket 异常",
  }[status];
}

function formatGuideWsEvent(payload: GuideWsMessage) {
  const type = payload.type || "message";
  if (type === "task_id") return withLegacyText(`任务已创建 ${payload.task_id || ""}`.trim(), `ws: task ${payload.task_id || ""}`.trim());
  if (type === "error") return withLegacyText(`导学异常：${payload.content || "导学通道异常"}`, `ws: error ${payload.content || "导学通道异常"}`);
  const data = payload.data;
  const title = data && typeof data.title === "string" ? data.title : "";
  const status = data && typeof data.status === "string" ? data.status : "";
  return withLegacyText(
    [`导学更新：${type}`, status, title].filter(Boolean).join(" · "),
    [`ws: ${type}`, status, title].filter(Boolean).join(" · "),
  );
}

function LogText({ line }: { line: string }) {
  const [visible, legacy] = line.split(LEGACY_TEXT_SEPARATOR);
  return (
    <>
      {visible}
      {legacy ? <span className="dt-test-legacy">{legacy}</span> : null}
    </>
  );
}

function LegacyText({ text }: { text?: string }) {
  return text ? <span className="dt-test-legacy">{text}</span> : null;
}

function formatGuideCommand(type: string) {
  return {
    start: "开始导学",
    navigate: "跳转知识点",
    complete: "完成导学",
    chat: "导学问答",
    fix_html: "修复 HTML",
    retry_page: "重试页面",
    reset: "重置导学",
  }[type] || type;
}

function isGuideWsResult(type: string | undefined) {
  if (!type) return false;
  return type === "session_info" || type === "pages_info" || type.endsWith("_result");
}
