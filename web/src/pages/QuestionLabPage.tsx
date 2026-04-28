import { AnimatePresence, motion } from "framer-motion";
import { Activity, CheckCircle2, FileQuestion, Loader2, Save, Sparkles, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { QuizViewer } from "@/components/quiz/QuizViewer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { Metric } from "@/components/ui/Metric";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useKnowledgeBases, useNotebookMutations, useNotebooks } from "@/hooks/useApiQueries";
import { questionGenerateSocketUrl, questionMimicSocketUrl } from "@/lib/api";
import type { QuestionGenerationSummary, QuizQuestion } from "@/lib/types";

type RunMode = "topic" | "mimic";
type RunStatus = "idle" | "running" | "complete" | "error";

type QuestionEvent = {
  type?: string;
  stage?: string;
  source?: string;
  content?: unknown;
  metadata?: Record<string, unknown>;
  summary?: QuestionGenerationSummary;
  [key: string]: unknown;
};

const QUESTION_TYPES = [
  { value: "", label: "混合题型" },
  { value: "choice", label: "选择题" },
  { value: "true_false", label: "判断题" },
  { value: "fill_blank", label: "填空题" },
  { value: "written", label: "主观题" },
  { value: "coding", label: "编程题" },
];

const DIFFICULTIES = [
  { value: "", label: "自动难度" },
  { value: "easy", label: "基础" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "挑战" },
];

function safeParseEvent(data: string): QuestionEvent {
  try {
    const parsed = JSON.parse(data) as QuestionEvent;
    return parsed && typeof parsed === "object" ? parsed : { type: "message", content: data };
  } catch {
    return { type: "message", content: data };
  }
}

function eventText(event: QuestionEvent) {
  const content = event.content;
  if (typeof content === "string") return content;
  if (content == null) return event.type || "事件";
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

function extractSummary(event: QuestionEvent): QuestionGenerationSummary | null {
  if (event.summary && typeof event.summary === "object") return event.summary;
  const metadata = event.metadata;
  if (metadata?.summary && typeof metadata.summary === "object") {
    return metadata.summary as QuestionGenerationSummary;
  }
  if (event.type === "result" && event.metadata && "results" in event.metadata) {
    return event.metadata as QuestionGenerationSummary;
  }
  return null;
}

function normalizeQuestionType(value: unknown, options: unknown) {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("choice") || raw.includes("select") || raw.includes("选择")) return "choice";
  if (raw.includes("true_false") || raw.includes("true-false") || raw.includes("truefalse") || raw === "tf") return "true_false";
  if (raw.includes("judge") || raw.includes("判断") || raw.includes("是非")) return "true_false";
  if (raw.includes("fill") || raw.includes("blank") || raw.includes("cloze") || raw.includes("填空")) return "fill_blank";
  if (raw.includes("code") || raw.includes("编程")) return "coding";
  if (options && typeof options === "object" && Object.keys(options).length > 0) return "choice";
  return raw || "written";
}

function normalizeQuestions(summary: QuestionGenerationSummary | null): QuizQuestion[] {
  const results = summary?.results ?? [];
  return results
    .map((item, index) => {
      const qa = item.qa_pair ?? {};
      const question = String(qa.question || "").trim();
      if (!question) return null;
      const options = qa.options && typeof qa.options === "object" ? (qa.options as Record<string, string>) : undefined;
      return {
        question_id: String(qa.question_id || `generated-${index + 1}`),
        question,
        question_type: normalizeQuestionType(qa.question_type, options),
        options,
        correct_answer: String(qa.correct_answer || ""),
        explanation: String(qa.explanation || ""),
        difficulty: String(qa.difficulty || ""),
        concentration: String(qa.concentration || ""),
        knowledge_context: String(qa.knowledge_context || ""),
      } satisfies QuizQuestion;
    })
    .filter(Boolean) as QuizQuestion[];
}

function questionsToMarkdown(questions: QuizQuestion[]) {
  return questions
    .map((question, index) => {
      const lines = [`### ${index + 1}. ${question.question}`];
      if (question.options) {
        for (const [key, value] of Object.entries(question.options)) {
          lines.push(`- ${key}. ${value}`);
        }
      }
      if (question.correct_answer) lines.push(`\n**答案：** ${question.correct_answer}`);
      if (question.explanation) lines.push(`\n**解析：** ${question.explanation}`);
      return lines.join("\n");
    })
    .join("\n\n");
}

function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("PDF 读取失败"));
    reader.onload = () => {
      const raw = String(reader.result || "");
      resolve(raw.includes(",") ? raw.split(",").pop() || "" : raw);
    };
    reader.readAsDataURL(file);
  });
}

export function QuestionLabPage() {
  const knowledgeBases = useKnowledgeBases();
  const notebooks = useNotebooks();
  const notebookMutations = useNotebookMutations();
  const socketRef = useRef<WebSocket | null>(null);

  const [mode, setMode] = useState<RunMode>("topic");
  const [topic, setTopic] = useState("函数极限与连续");
  const [preference, setPreference] = useState("贴近高等数学期末题，解析要指出易错点。");
  const [difficulty, setDifficulty] = useState("medium");
  const [questionType, setQuestionType] = useState("");
  const [count, setCount] = useState(3);
  const [kbName, setKbName] = useState("");
  const [paperPath, setPaperPath] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [targetNotebookId, setTargetNotebookId] = useState("");
  const [events, setEvents] = useState<QuestionEvent[]>([]);
  const [summary, setSummary] = useState<QuestionGenerationSummary | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState("");

  const kbItems = useMemo(() => knowledgeBases.data ?? [], [knowledgeBases.data]);
  const notebookItems = useMemo(() => notebooks.data ?? [], [notebooks.data]);
  const questions = useMemo(() => normalizeQuestions(summary), [summary]);
  const markdown = useMemo(() => questionsToMarkdown(questions), [questions]);
  const completed = summary?.completed ?? questions.length;
  const failed = summary?.failed ?? 0;

  useEffect(
    () => () => {
      socketRef.current?.close();
    },
    [],
  );

  const selectedKb = kbName || kbItems.find((item) => item.is_default)?.name || "ai_textbook";
  const selectedNotebookId = targetNotebookId || notebookItems[0]?.id || "";
  const running = status === "running";

  const resetRun = () => {
    socketRef.current?.close();
    socketRef.current = null;
    setEvents([]);
    setSummary(null);
    setError("");
    setStatus("idle");
  };

  const handleEvent = (event: QuestionEvent) => {
    setEvents((current) => [...current.slice(-79), event]);
    const nextSummary = extractSummary(event);
    if (nextSummary) setSummary(nextSummary);
    if (event.type === "error") {
      setStatus("error");
      setError(eventText(event));
    }
    if (event.type === "complete") {
      setStatus("complete");
    }
  };

  const openRunSocket = (url: string, payload: Record<string, unknown>) => {
    socketRef.current?.close();
    setEvents([]);
    setSummary(null);
    setError("");
    setStatus("running");

    const socket = new WebSocket(url);
    socketRef.current = socket;
    socket.onopen = () => socket.send(JSON.stringify(payload));
    socket.onmessage = (message) => handleEvent(safeParseEvent(String(message.data)));
    socket.onerror = () => {
      setStatus("error");
      setError("题目生成通道连接失败");
    };
    socket.onclose = () => {
      setStatus((current) => (current === "running" ? "complete" : current));
    };
  };

  const runTopicGeneration = () => {
    if (!topic.trim()) {
      setError("请先填写知识点或出题要求");
      return;
    }
    openRunSocket(questionGenerateSocketUrl(), {
      kb_name: selectedKb,
      count,
      requirement: {
        knowledge_point: topic.trim(),
        preference: preference.trim(),
        difficulty,
        question_type: questionType,
      },
    });
  };

  const runMimicGeneration = async () => {
    if (!paperPath.trim() && !pdfFile) {
      setError("请填写已解析试卷目录，或上传一份 PDF");
      return;
    }
    const payload: Record<string, unknown> = {
      kb_name: selectedKb,
      max_questions: count,
    };
    if (pdfFile) {
      payload.mode = "upload";
      payload.pdf_name = pdfFile.name;
      payload.pdf_data = await readFileAsBase64(pdfFile);
    } else {
      payload.mode = "parsed";
      payload.paper_path = paperPath.trim();
    }
    openRunSocket(questionMimicSocketUrl(), payload);
  };

  const saveToNotebook = () => {
    if (!selectedNotebookId || !questions.length) return;
    notebookMutations.addRecord.mutate({
      notebook_ids: [selectedNotebookId],
      record_type: "question",
      title: mode === "topic" ? `题目生成：${topic.trim()}` : `仿题生成：${pdfFile?.name || paperPath.trim()}`,
      user_query: mode === "topic" ? topic.trim() : pdfFile?.name || paperPath.trim(),
      output: markdown,
      summary: `${questions.length} 道题，完成 ${completed}，失败 ${failed}`,
      kb_name: selectedKb,
      metadata: {
        source: "question_lab",
        mode,
        summary,
      },
    });
  };

  return (
    <div className="h-full overflow-y-auto bg-canvas">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-4 pb-24 lg:px-5 lg:pb-5">
        <motion.section
          className="dt-page-header"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24 }}
        >
          <p className="dt-page-eyebrow">题库</p>
          <h1 className="mt-1 text-xl font-semibold text-ink">题目生成</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            从知识点生成练习，或根据试卷生成仿题。
          </p>
        </motion.section>

        <motion.section
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04 }}
        >
          <Metric label="生成状态" value={statusLabel(status)} detail="出题与仿题" icon={<FileQuestion size={19} />} />
          <Metric label="已生成" value={questions.length} detail={`完成 ${completed} · 失败 ${failed}`} icon={<CheckCircle2 size={19} />} />
          <Metric label="知识库" value={selectedKb} detail="用于题目语境" icon={<Activity size={19} />} />
        </motion.section>

        <motion.section
          className="grid min-h-0 gap-4 xl:grid-cols-[400px_minmax(0,1fr)]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.08 }}
        >
          <div className="space-y-4">
            <Panel>
              <PanelHeader
                title="题目工坊"
                description="从知识点生成练习，或基于试卷材料生成同风格仿题。"
                action={
                  running ? (
                    <Button tone="danger" onClick={resetRun}>
                      停止
                    </Button>
                  ) : (
                    <Button tone="quiet" onClick={resetRun}>
                      重置
                    </Button>
                  )
                }
              />

              <div className="mt-4 grid grid-cols-2 gap-2">
                <motion.button
                  type="button"
                  data-testid="question-mode-topic"
                  onClick={() => setMode("topic")}
                  layout
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.99 }}
                  className={`dt-interactive rounded-lg border px-3 py-3 text-left text-sm transition ${
                    mode === "topic" ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                  }`}
                >
                  <span className="block font-semibold">知识点出题</span>
                  <span className="mt-1 block text-xs text-slate-500">主题、难度、题型</span>
                </motion.button>
                <motion.button
                  type="button"
                  data-testid="question-mode-mimic"
                  onClick={() => setMode("mimic")}
                  layout
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.99 }}
                  className={`dt-interactive rounded-lg border px-3 py-3 text-left text-sm transition ${
                    mode === "mimic" ? "border-blue-200 bg-blue-50 text-brand-blue" : "border-line bg-white text-slate-600 hover:border-blue-200"
                  }`}
                >
                  <span className="block font-semibold">试卷仿题</span>
                  <span className="mt-1 block text-xs text-slate-500">PDF 或解析目录</span>
                </motion.button>
              </div>

              <div className="mt-4 space-y-3">
                <FieldShell label="知识库">
                  <SelectInput value={kbName} onChange={(event) => setKbName(event.target.value)}>
                    <option value="">{kbItems.length ? "自动选择默认知识库" : "ai_textbook"}</option>
                    {kbItems.map((item) => (
                      <option key={item.name} value={item.name}>
                        {item.name}
                        {item.is_default ? " · 默认" : ""}
                      </option>
                    ))}
                  </SelectInput>
                </FieldShell>

                <div className="grid grid-cols-2 gap-3">
                  <FieldShell label="数量">
                    <TextInput
                      type="number"
                      min={1}
                      max={10}
                      value={count}
                      onChange={(event) => setCount(Number(event.target.value || 1))}
                    />
                  </FieldShell>
                  <FieldShell label="难度">
                    <SelectInput value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                      {DIFFICULTIES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </SelectInput>
                  </FieldShell>
                </div>

                <AnimatePresence mode="wait">
                  {mode === "topic" ? (
                    <motion.div
                      key="topic"
                      className="space-y-3"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                    <FieldShell label="知识点或出题要求">
                      <TextInput
                        data-testid="question-topic-input"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        placeholder="例如：函数极限与连续"
                      />
                    </FieldShell>
                    <FieldShell label="题型">
                      <SelectInput value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
                        {QUESTION_TYPES.map((item) => (
                          <option key={item.value} value={item.value}>
                            {item.label}
                          </option>
                        ))}
                      </SelectInput>
                    </FieldShell>
                    <FieldShell label="偏好">
                      <TextArea value={preference} onChange={(event) => setPreference(event.target.value)} className="min-h-24" />
                    </FieldShell>
                    <Button tone="primary" onClick={runTopicGeneration} disabled={running} className="w-full" data-testid="question-generate-topic">
                      {running ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                      生成题目
                    </Button>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="mimic"
                      className="space-y-3"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                    <FieldShell label="已解析试卷目录" hint="与项目运行目录一致">
                      <TextInput
                        data-testid="question-mimic-paper-path"
                        value={paperPath}
                        onChange={(event) => setPaperPath(event.target.value)}
                        placeholder="mimic_papers/exam_2024"
                      />
                    </FieldShell>
                    <FieldShell label="上传 PDF">
                      <input
                        type="file"
                        accept="application/pdf,.pdf"
                        onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                        className="block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-teal"
                      />
                    </FieldShell>
                    <Button
                      tone="primary"
                      onClick={() => void runMimicGeneration()}
                      disabled={running}
                      className="w-full"
                      data-testid="question-generate-mimic"
                    >
                      {running ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                      生成仿题
                    </Button>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {error ? (
                    <motion.p
                      className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red"
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.16 }}
                    >
                      {error}
                    </motion.p>
                  ) : null}
                </AnimatePresence>
              </div>
            </Panel>

            <Panel>
              <PanelHeader title="保存到 Notebook" description="把本次题目作为一条结构化记录沉淀下来。" />
              <div className="mt-4 space-y-3">
                <SelectInput value={targetNotebookId} onChange={(event) => setTargetNotebookId(event.target.value)}>
                  <option value="">{notebookItems.length ? `默认：${notebookItems[0].name}` : "暂无 Notebook"}</option>
                  {notebookItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </SelectInput>
                <Button
                  tone="secondary"
                  onClick={saveToNotebook}
                  disabled={!selectedNotebookId || !questions.length || notebookMutations.addRecord.isPending}
                  className="w-full"
                  data-testid="question-lab-save"
                >
                  {notebookMutations.addRecord.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  保存生成结果
                </Button>
                <AnimatePresence>
                  {notebookMutations.addRecord.isSuccess ? (
                    <motion.div
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.16 }}
                    >
                      <Badge tone="success">已保存</Badge>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel>
              <details className="[&>summary::-webkit-details-marker]:hidden">
                <summary
                  className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1"
                  data-testid="question-lab-events-toggle"
                >
                  <span>
                    <span className="block text-base font-semibold text-ink">生成过程</span>
                    <span className="mt-1 block text-sm text-slate-500">出题进度和仿题事件，需要复盘时查看。</span>
                  </span>
                  <Badge tone={events.length ? "brand" : "neutral"}>{events.length ? `${events.length} 条` : "等待"}</Badge>
                </summary>
                <div className="dt-event-feed mt-4 max-h-72 overflow-y-auto rounded-lg p-3 text-sm" data-testid="question-lab-events">
                  <AnimatePresence initial={false} mode="wait">
                    {!events.length ? (
                      <motion.p key="empty" className="text-slate-500" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        等待任务开始。
                      </motion.p>
                    ) : (
                      <motion.div key="events" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <AnimatePresence initial={false}>
                          {events.map((event, index) => (
                            <motion.div
                              key={`${event.type}-${index}-${eventText(event).slice(0, 18)}`}
                              className="dt-event-row"
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.14 }}
                            >
                              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                <span>{event.type || "message"}</span>
                                {event.stage ? <span>{event.stage}</span> : null}
                                {event.source ? <span>{event.source}</span> : null}
                              </div>
                              <p className="mt-1 whitespace-pre-wrap break-words text-slate-700">{eventText(event)}</p>
                            </motion.div>
                          ))}
                        </AnimatePresence>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </details>
            </Panel>

            <Panel>
              <PanelHeader
                title="生成结果"
                description="结果会转成可答题预览；提交答案后可以在前端即时复盘。"
                action={summary ? <Badge tone={failed ? "warning" : "success"}>{failed ? "部分完成" : "完成"}</Badge> : null}
              />
              <div className="mt-4">
                <AnimatePresence mode="wait">
                  {questions.length ? (
                    <motion.div
                      key="quiz"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      <QuizViewer questions={questions} />
                    </motion.div>
                  ) : (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      <EmptyState
                        title="还没有题目"
                        description="从左侧启动一次生成任务，题目会在这里变成可交互练习。"
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </Panel>
          </div>
        </motion.section>
      </div>
    </div>
  );
}

function statusLabel(status: RunStatus) {
  if (status === "running") return "运行中";
  if (status === "complete") return "已完成";
  if (status === "error") return "异常";
  return "待开始";
}
