import { AnimatePresence, motion } from "framer-motion";
import { Activity, Camera, CheckCircle2, Eye, FileImage, Loader2, Play, Save, ScanLine } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import { Metric } from "@/components/ui/Metric";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useNotebookMutations, useNotebooks } from "@/hooks/useApiQueries";
import { analyzeVisionImage, visionSolveSocketUrl } from "@/lib/api";
import type { VisionAnalyzeResponse, VisionCommand } from "@/lib/types";

type RunStatus = "idle" | "running" | "complete" | "error";

type VisionEvent = {
  type?: string;
  data?: Record<string, unknown>;
  content?: string;
  [key: string]: unknown;
};

function readImageFile(file: File) {
  return new Promise<{ base64: string; preview: string }>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.onload = () => {
      const preview = String(reader.result || "");
      resolve({
        base64: preview.includes(",") ? preview.split(",").pop() || "" : preview,
        preview,
      });
    };
    reader.readAsDataURL(file);
  });
}

function safeParseEvent(data: string): VisionEvent {
  try {
    const parsed = JSON.parse(data) as VisionEvent;
    return parsed && typeof parsed === "object" ? parsed : { type: "message", content: data };
  } catch {
    return { type: "message", content: data };
  }
}

function eventTitle(event: VisionEvent) {
  const type = String(event.type || "message");
  const stage = typeof event.data?.stage === "string" ? event.data.stage : "";
  return stage ? `${type} · ${stage}` : type;
}

function eventContent(event: VisionEvent) {
  if (event.content) return event.content;
  if (!event.data) return "";
  const data = event.data;
  if (typeof data.content === "string") return data.content;
  if (typeof data.message === "string") return data.message;
  if (typeof data.text === "string") return data.text;
  if (typeof data.ggb_block === "object" && data.ggb_block) return "GeoGebra 指令块已生成";
  if ("commands_count" in data) return `命令数：${String(data.commands_count)}`;
  if ("elements_count" in data) return `识别元素：${String(data.elements_count)}`;
  if ("status" in data) return `状态：${String(data.status)}`;
  return "过程状态已更新";
}

function commandsFromEvent(event: VisionEvent): VisionCommand[] {
  const data = event.data;
  if (!data) return [];
  const finalCommands = data.final_commands;
  if (Array.isArray(finalCommands)) return finalCommands as VisionCommand[];
  const commands = data.commands;
  if (Array.isArray(commands)) return commands as VisionCommand[];
  return [];
}

function scriptFromCommands(commands: VisionCommand[]) {
  return commands
    .flatMap((item) => {
      const lines: string[] = [];
      if (item.description) lines.push(`# ${item.description}`);
      if (item.command) lines.push(String(item.command));
      return lines;
    })
    .join("\n");
}

function ggbScriptFromEvent(event: VisionEvent) {
  const block = event.data?.ggb_block;
  if (!block || typeof block !== "object") return "";
  const content = (block as { content?: unknown }).content;
  return typeof content === "string" ? content : "";
}

function statusLabel(status: RunStatus) {
  if (status === "running") return "运行中";
  if (status === "complete") return "已完成";
  if (status === "error") return "异常";
  return "待开始";
}

function buildNotebookOutput(input: {
  question: string;
  answer: string;
  script: string;
  commands: VisionCommand[];
}) {
  const parts = [`## 图像题目\n${input.question}`];
  if (input.answer.trim()) parts.push(`## 导师讲解\n${input.answer.trim()}`);
  if (input.script.trim()) parts.push(`## GeoGebra 指令\n\`\`\`ggbscript\n${input.script.trim()}\n\`\`\``);
  if (input.commands.length) {
    parts.push(
      `## 指令摘要\n${input.commands
        .map((item, index) => `${index + 1}. ${item.description || "指令"}：${item.command || ""}`)
        .join("\n")}`,
    );
  }
  return parts.join("\n\n");
}

export function VisionPage() {
  const notebooks = useNotebooks();
  const notebookMutations = useNotebookMutations();
  const socketRef = useRef<WebSocket | null>(null);

  const [question, setQuestion] = useState("根据图像分析这道几何题，并给出可用于 GeoGebra 复现的作图指令。");
  const [imageUrl, setImageUrl] = useState("");
  const [imageBase64, setImageBase64] = useState("");
  const [preview, setPreview] = useState("");
  const [status, setStatus] = useState<RunStatus>("idle");
  const [activeRun, setActiveRun] = useState<"rest" | "live" | null>(null);
  const [error, setError] = useState("");
  const [events, setEvents] = useState<VisionEvent[]>([]);
  const [analysis, setAnalysis] = useState<VisionAnalyzeResponse | null>(null);
  const [liveCommands, setLiveCommands] = useState<VisionCommand[]>([]);
  const [liveScript, setLiveScript] = useState("");
  const [answer, setAnswer] = useState("");
  const [targetNotebookId, setTargetNotebookId] = useState("");

  const notebookItems = useMemo(() => notebooks.data ?? [], [notebooks.data]);
  const selectedNotebookId = targetNotebookId || notebookItems[0]?.id || "";
  const commands = liveCommands.length ? liveCommands : analysis?.final_ggb_commands ?? [];
  const ggbScript = liveScript || analysis?.ggb_script || scriptFromCommands(commands);
  const imageSource = preview || imageUrl;
  const running = status === "running";
  const output = buildNotebookOutput({ question, answer, script: ggbScript, commands });

  const handleFile = async (file: File | null) => {
    if (!file) return;
    const image = await readImageFile(file);
    setImageBase64(image.base64);
    setPreview(image.preview);
    setImageUrl("");
  };

  const ensureInput = () => {
    if (!question.trim()) {
      setError("请先填写题目或分析目标");
      return false;
    }
    if (!imageBase64 && !imageUrl.trim()) {
      setError("请上传图片或填写图片 URL");
      return false;
    }
    setError("");
    return true;
  };

  const quickAnalyze = async () => {
    if (!ensureInput()) return;
    socketRef.current?.close();
    setStatus("running");
    setActiveRun("rest");
    setEvents([]);
    setAnalysis(null);
    setAnswer("");
    setLiveCommands([]);
    setLiveScript("");
    try {
      const result = await analyzeVisionImage({
        question: question.trim(),
        image_base64: imageBase64 || null,
        image_url: imageUrl.trim() || null,
        session_id: `vision-${Date.now()}`,
      });
      setAnalysis(result);
      setStatus("complete");
    } catch (cause) {
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "视觉解析失败");
    } finally {
      setActiveRun(null);
    }
  };

  const startLiveSolve = () => {
    if (!ensureInput()) return;
    socketRef.current?.close();
    setStatus("running");
    setEvents([]);
    setAnalysis(null);
    setAnswer("");
    setLiveCommands([]);
    setLiveScript("");

    const socket = new WebSocket(visionSolveSocketUrl());
    setActiveRun("live");
    socketRef.current = socket;
    socket.onopen = () =>
      socket.send(
        JSON.stringify({
          question: question.trim(),
          image_base64: imageBase64 || null,
          image_url: imageUrl.trim() || null,
          session_id: `vision-${Date.now()}`,
        }),
      );
    socket.onmessage = (message) => {
      const event = safeParseEvent(String(message.data));
      setEvents((current) => [...current.slice(-79), event]);
      const nextCommands = commandsFromEvent(event);
      if (nextCommands.length) setLiveCommands(nextCommands);
      const nextScript = ggbScriptFromEvent(event);
      if (nextScript) setLiveScript(nextScript);
      if (event.type === "text" && typeof event.data?.content === "string") {
        setAnswer((current) => `${current}${event.data?.content as string}`);
      }
      if (event.type === "done") {
        setStatus("complete");
        setActiveRun(null);
      }
      if (event.type === "error") {
        setStatus("error");
        setActiveRun(null);
        setError(String(event.content || event.data?.content || "视觉解题失败"));
      }
    };
    socket.onerror = () => {
      setStatus("error");
      setActiveRun(null);
      setError("视觉解题通道连接失败");
    };
    socket.onclose = () => {
      setActiveRun(null);
      setStatus((current) => (current === "running" ? "complete" : current));
    };
  };

  const stopLiveSolve = () => {
    socketRef.current?.close();
    socketRef.current = null;
    setActiveRun(null);
    setStatus((current) => (current === "running" ? "complete" : current));
  };

  const saveToNotebook = () => {
    if (!selectedNotebookId || !output.trim()) return;
    notebookMutations.addRecord.mutate({
      notebook_ids: [selectedNotebookId],
      record_type: "solve",
      title: "图像题解析",
      user_query: question.trim(),
      output,
      summary: `识别 ${analysis?.analysis_summary?.elements_count ?? "-"} 个元素，生成 ${commands.length} 条 GeoGebra 指令。`,
      metadata: {
        source: "vision_lab",
        analysis,
        commands,
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
          <p className="dt-page-eyebrow">图像</p>
          <h1 className="mt-1 text-xl font-semibold text-ink">图像解题</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            上传题目图片，生成图形识别和讲解记录。
          </p>
        </motion.section>

        <motion.section
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04 }}
        >
          <Metric label="视觉状态" value={statusLabel(status)} detail="识别与讲解" icon={<Eye size={19} />} />
          <Metric label="GeoGebra 指令" value={commands.length} detail={ggbScript ? "可复制到 GeoGebra" : "等待图像解析"} icon={<ScanLine size={19} />} />
          <Metric label="图片输入" value={imageSource ? "已就绪" : "未选择"} detail="支持上传图片或远程 URL" icon={<FileImage size={19} />} />
        </motion.section>

        <motion.section
          className="grid gap-4 xl:grid-cols-[400px_minmax(0,1fr)]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.08 }}
        >
          <div className="space-y-4">
            <Panel>
              <PanelHeader title="上传题图" description="上传数学题配图，生成图形识别、GeoGebra 指令和导师讲解。" />
              <div className="mt-4 space-y-3">
                <FieldShell label="题目或分析目标">
                  <TextArea
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    className="min-h-28"
                    data-testid="vision-question"
                  />
                </FieldShell>
                <FieldShell label="上传图片">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
                    className="block w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-teal"
                    data-testid="vision-file-input"
                  />
                </FieldShell>
                <FieldShell label="图片 URL">
                  <TextInput
                    value={imageUrl}
                    onChange={(event) => {
                      setImageUrl(event.target.value);
                      setPreview("");
                      setImageBase64("");
                    }}
                    placeholder="https://example.com/problem.png"
                    data-testid="vision-image-url"
                  />
                </FieldShell>
                <AnimatePresence mode="wait">
                  {imageSource ? (
                    <motion.img
                      key="preview"
                      src={imageSource}
                      alt="待解析题目"
                      className="max-h-72 w-full rounded-lg border border-line bg-white object-contain"
                      data-testid="vision-image-preview"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    />
                  ) : (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      <EmptyState icon={<Camera size={22} />} title="等待图片" description="选择一张题目截图，或填写图片 URL。" />
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
                <div className="grid gap-2 sm:grid-cols-2">
                  <Button tone="primary" onClick={() => void quickAnalyze()} disabled={running} data-testid="vision-quick-analyze">
                    {running ? <Loader2 size={16} className="animate-spin" /> : <ScanLine size={16} />}
                    快速解析
                  </Button>
                  {running && activeRun === "live" ? (
                    <Button tone="danger" onClick={stopLiveSolve}>
                      停止实时解题
                    </Button>
                  ) : (
                    <Button tone="secondary" onClick={startLiveSolve} disabled={running} data-testid="vision-live-solve">
                      {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                      {running ? "解析中" : "实时解题"}
                    </Button>
                  )}
                </div>
              </div>
            </Panel>

            <Panel>
              <PanelHeader title="保存到 Notebook" description="把图像题、导师讲解和 GeoGebra 指令沉淀为解题记录。" />
              <div className="mt-4 space-y-3">
                <select
                  value={targetNotebookId}
                  onChange={(event) => setTargetNotebookId(event.target.value)}
                  className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand-teal focus:ring-2 focus:ring-teal-100"
                >
                  <option value="">{notebookItems.length ? `默认：${notebookItems[0].name}` : "暂无 Notebook"}</option>
                  {notebookItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                <Button
                  tone="secondary"
                  onClick={saveToNotebook}
                  disabled={!selectedNotebookId || (!ggbScript && !answer) || notebookMutations.addRecord.isPending}
                  className="w-full"
                  data-testid="vision-save"
                >
                  {notebookMutations.addRecord.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  保存解析结果
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
                  data-testid="vision-events-toggle"
                >
                  <span>
                    <span className="block text-base font-semibold text-ink">解题过程</span>
                    <span className="mt-1 block text-sm text-slate-500">实时识别、关系分析和导师回答的过程记录。</span>
                  </span>
                  <Badge tone={events.length ? "brand" : "neutral"}>{events.length ? `${events.length} 条` : "等待"}</Badge>
                </summary>
                <div className="dt-event-feed mt-4 max-h-72 overflow-y-auto rounded-lg p-3 text-sm" data-testid="vision-events">
                  <AnimatePresence initial={false} mode="wait">
                    {!events.length ? (
                      <motion.p key="empty" className="text-slate-500" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        快速解析不会产生流式轨迹；点击实时解题查看完整过程。
                      </motion.p>
                    ) : (
                      <motion.div key="events" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <AnimatePresence initial={false}>
                          {events.map((event, index) => (
                            <motion.div
                              key={`${event.type}-${index}-${eventContent(event).slice(0, 18)}`}
                              className="dt-event-row"
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.14 }}
                            >
                              <div className="flex items-center gap-2 text-xs text-slate-500">
                                <Activity size={12} />
                                <span>{eventTitle(event)}</span>
                              </div>
                              {eventContent(event) ? <p className="mt-1 whitespace-pre-wrap break-words text-slate-700">{eventContent(event)}</p> : null}
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
                title="GeoGebra 指令"
                description="可复制到 GeoGebra 或作为 Notebook 记录保存。"
                action={commands.length ? <Badge tone="brand">{commands.length} 条</Badge> : null}
              />
              <div className="mt-4">
                <AnimatePresence mode="wait">
                  {ggbScript ? (
                    <motion.pre
                      key="script"
                      className="dt-code-surface max-h-80 overflow-auto rounded-lg p-4 text-sm leading-6"
                      data-testid="vision-ggb-script"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      {ggbScript}
                    </motion.pre>
                  ) : (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      <EmptyState icon={<ScanLine size={22} />} title="暂无指令" description="解析完成后，GeoGebra 指令会显示在这里。" />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </Panel>

            <Panel>
              <PanelHeader title="导师讲解" description="实时解题会流式输出结合图形的解题说明。" />
              <div className="mt-4 border-t border-line pt-4 text-sm leading-7 text-slate-700" data-testid="vision-answer">
                <AnimatePresence mode="wait">
                  {answer ? (
                    <motion.p
                      key="answer"
                      className="whitespace-pre-wrap"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      {answer}
                    </motion.p>
                  ) : (
                    <motion.div
                      key="empty"
                      className="flex items-center gap-2 text-slate-500"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                      <CheckCircle2 size={16} />
                      <span>快速解析完成后可先查看指令；实时解题会在这里输出完整讲解。</span>
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
