import { Download, Edit3, Eye, FileText, Loader2, Save, Wand2 } from "lucide-react";
import { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { Metric } from "@/components/ui/Metric";
import {
  useCoWriterHistory,
  useCoWriterMutations,
  useCoWriterOperation,
  useCoWriterToolCalls,
  useKnowledgeBases,
  useNotebooks,
} from "@/hooks/useApiQueries";
import { streamCoWriterEdit, type CoWriterStreamEvent } from "@/lib/api";

const LEGACY_TEXT_SEPARATOR = "\u001F";
const MAX_CO_WRITER_TEXT_CHARS = 20_000;
const MAX_CO_WRITER_INSTRUCTION_CHARS = 2_000;

function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

function coWriterLimitMessage(text: string, instruction = "") {
  if (text.length > MAX_CO_WRITER_TEXT_CHARS) {
    return `原文不能超过 ${MAX_CO_WRITER_TEXT_CHARS.toLocaleString("zh-CN")} 字。`;
  }
  if (instruction.length > MAX_CO_WRITER_INSTRUCTION_CHARS) {
    return `修改要求不能超过 ${MAX_CO_WRITER_INSTRUCTION_CHARS.toLocaleString("zh-CN")} 字。`;
  }
  return "";
}

export function CoWriterPage() {
  const [text, setText] = useState("这里输入需要润色、扩展或压缩的 markdown。");
  const [instruction, setInstruction] = useState("让表达更清晰，保留原意。");
  const [mode, setMode] = useState<"rewrite" | "shorten" | "expand" | "none">("rewrite");
  const [kbName, setKbName] = useState("");
  const [notebookId, setNotebookId] = useState("");
  const [result, setResult] = useState("");
  const [streamLogs, setStreamLogs] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [selectedOperationId, setSelectedOperationId] = useState<string | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const knowledge = useKnowledgeBases();
  const notebooks = useNotebooks({ enabled: Boolean(result || notebookId) });
  const history = useCoWriterHistory();
  const operation = useCoWriterOperation(selectedOperationId, { enabled: auditOpen });
  const toolCalls = useCoWriterToolCalls(selectedOperationId, { enabled: auditOpen });
  const mutations = useCoWriterMutations();
  const textOverLimit = text.length > MAX_CO_WRITER_TEXT_CHARS;
  const instructionOverLimit = instruction.length > MAX_CO_WRITER_INSTRUCTION_CHARS;
  const limitMessage = coWriterLimitMessage(text, instruction);

  const runEdit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationMessage = coWriterLimitMessage(text, instruction);
    if (validationMessage) {
      setStreamLogs((current) => [...current, withLegacyText(validationMessage, `input limit: ${validationMessage}`)].slice(-24));
      return;
    }
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    let streamed = "";
    setResult("");
    setStreamLogs([]);
    setIsStreaming(true);
    try {
      const output = await streamCoWriterEdit(
        {
          selected_text: text,
          instruction,
          mode,
          tools: kbName ? ["rag", "reason"] : ["reason"],
          kb_name: kbName || null,
        },
        {
          signal: controller.signal,
          onContent: (chunk) => {
            streamed += chunk;
            setResult(streamed);
          },
          onEvent: (streamEvent) => {
            const line = formatStreamEvent(streamEvent);
            if (line) setStreamLogs((current) => [...current, line].slice(-24));
          },
        },
      );
      setResult(output.edited_text || streamed);
      if (output.operation_id) setSelectedOperationId(output.operation_id);
      setStreamLogs((current) => [...current, withLegacyText(`生成完成：${output.operation_id || "stream"}`, `done: ${output.operation_id || "stream"}`)].slice(-24));
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        const message = error instanceof Error ? error.message : "stream failed";
        setStreamLogs((current) => [...current, withLegacyText(`生成失败：${message}`, `error: ${message}`)].slice(-24));
      }
    } finally {
      setIsStreaming(false);
      streamAbortRef.current = null;
    }
  };

  const runAutoMark = async () => {
    if (!text.trim()) return;
    const validationMessage = coWriterLimitMessage(text);
    if (validationMessage) {
      setStreamLogs((current) => [...current, withLegacyText(validationMessage, `input limit: ${validationMessage}`)].slice(-24));
      return;
    }
    setStreamLogs((current) => [...current, withLegacyText("正在自动标注", "automark: /api/v1/co_writer/automark")].slice(-24));
    const output = await mutations.automark.mutateAsync(text);
    setResult(output.marked_text || output.edited_text || "");
    if (output.operation_id) setSelectedOperationId(output.operation_id);
    setStreamLogs((current) => [...current, withLegacyText(`自动批注完成：${output.operation_id || "automark"}`, `automark done: ${output.operation_id || "automark"}`)].slice(-24));
  };

  const runQuickEdit = async () => {
    if (!text.trim() || !instruction.trim()) return;
    const validationMessage = coWriterLimitMessage(text, instruction);
    if (validationMessage) {
      setStreamLogs((current) => [...current, withLegacyText(validationMessage, `input limit: ${validationMessage}`)].slice(-24));
      return;
    }
    const action = mode === "none" ? "rewrite" : mode;
    setStreamLogs((current) => [...current, withLegacyText("正在快速编辑", "quick: /api/v1/co_writer/edit")].slice(-24));
    const output = await mutations.quickEdit.mutateAsync({
      text,
      instruction,
      action,
      source: kbName ? "rag" : null,
      kb_name: kbName || null,
    });
    setResult(output.edited_text || "");
    if (output.operation_id) setSelectedOperationId(output.operation_id);
    setStreamLogs((current) => [...current, withLegacyText(`快速编辑完成：${output.operation_id || "edit"}`, `quick done: ${output.operation_id || "edit"}`)].slice(-24));
  };

  const exportMarkdown = async () => {
    const content = result || getOperationOutput(operation.data);
    if (!content.trim()) return;
    const filename = `co-writer-${selectedOperationId || "draft"}.md`;
    const markdown = await mutations.exportMarkdown.mutateAsync({ content, filename });
    if (typeof document !== "undefined") {
      const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    }
    setStreamLogs((current) => [...current, withLegacyText(`已导出文稿：${filename}`, `export: ${filename}`)].slice(-24));
  };

  const saveResult = async () => {
    if (!notebookId || !result) return;
    await mutations.saveRecord.mutateAsync({
      notebook_ids: [notebookId],
      title: `协作写作 ${new Date().toLocaleString()}`,
      user_query: instruction,
      output: result,
      summary: result.slice(0, 160),
      metadata: { source: "web_co_writer", mode, kb_name: kbName || null },
    });
  };

  return (
    <div className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto max-w-[1080px] space-y-3.5">
        <motion.section
          className="dt-page-header dt-page-header-accent-orange p-3.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <div className="flex flex-wrap items-start justify-between gap-3.5">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-orange">写作助手</p>
              <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">粘贴原文，先生成一版可用修改</h1>
              <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">
                适合润色、压缩、扩写和批注。需要引用课程资料时，再选择资料来源。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                tone="primary"
                onClick={() => void runQuickEdit()}
                disabled={
                  !text.trim() ||
                  !instruction.trim() ||
                  textOverLimit ||
                  instructionOverLimit ||
                  isStreaming ||
                  mutations.quickEdit.isPending
                }
              >
                {mutations.quickEdit.isPending ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                快速编辑
              </Button>
              <Button tone="secondary" onClick={() => void runAutoMark()} disabled={!text.trim() || textOverLimit || mutations.automark.isPending}>
                {mutations.automark.isPending ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
                自动批注
              </Button>
            </div>
          </div>
        </motion.section>

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04, ease: "easeOut" }}
        >
          <Metric label="编辑模式" value="智能润色" detail="边生成边更新" icon={<Edit3 size={19} />} />
          <Metric label="资料引用" value={kbName || "未选择"} detail="可连接学习资料" icon={<FileText size={19} />} />
          <Metric label="自动标注" value="批注" detail="结构化建议" icon={<Wand2 size={19} />} />
        </motion.div>

        <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">编辑请求</h2>
            <form className="mt-4 grid gap-3" onSubmit={runEdit}>
              <FieldShell label="原文" hint={`${text.length}/${MAX_CO_WRITER_TEXT_CHARS}`}>
                <TextArea
                  value={text}
                  maxLength={MAX_CO_WRITER_TEXT_CHARS}
                  onChange={(event) => setText(event.target.value)}
                  className="min-h-48"
                  data-testid="co-writer-source-text"
                />
              </FieldShell>
              <div className="grid gap-3 md:grid-cols-2">
                <FieldShell label="模式">
                  <SelectInput value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
                    <option value="rewrite">润色</option>
                    <option value="shorten">压缩</option>
                    <option value="expand">扩展</option>
                    <option value="none">自定义要求</option>
                  </SelectInput>
                </FieldShell>
                <FieldShell label="资料来源">
                  <SelectInput value={kbName} onChange={(event) => setKbName(event.target.value)}>
                    <option value="">不引用</option>
                    {(knowledge.data ?? []).map((kb) => (
                      <option key={kb.name} value={kb.name}>
                        {kb.name}
                      </option>
                    ))}
                  </SelectInput>
                </FieldShell>
              </div>
              <FieldShell label="修改要求" hint={`${instruction.length}/${MAX_CO_WRITER_INSTRUCTION_CHARS}`}>
                <TextInput
                  value={instruction}
                  maxLength={MAX_CO_WRITER_INSTRUCTION_CHARS}
                  onChange={(event) => setInstruction(event.target.value)}
                  data-testid="co-writer-instruction"
                />
              </FieldShell>
              {limitMessage ? <p className="text-sm leading-6 text-brand-red">{limitMessage}</p> : null}
              <div className="flex flex-wrap gap-3">
                <Button
                  tone="primary"
                  type="submit"
                  disabled={!text.trim() || textOverLimit || instructionOverLimit || isStreaming || mutations.edit.isPending}
                  data-testid="co-writer-stream-submit"
                >
                  {isStreaming || mutations.edit.isPending ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
                  生成修改
                </Button>
                {isStreaming ? (
                  <Button tone="danger" onClick={() => streamAbortRef.current?.abort()}>
                    停止
                  </Button>
                ) : null}
                <Button
                  tone="secondary"
                  onClick={() => void runAutoMark()}
                  disabled={!text.trim() || textOverLimit || mutations.automark.isPending}
                  data-testid="co-writer-automark"
                >
                  {mutations.automark.isPending ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                  自动批注
                </Button>
                <Button
                  tone="secondary"
                  data-testid="co-writer-quick-edit"
                  onClick={() => void runQuickEdit()}
                  disabled={
                    !text.trim() ||
                    !instruction.trim() ||
                    textOverLimit ||
                    instructionOverLimit ||
                    isStreaming ||
                    mutations.quickEdit.isPending
                  }
                >
                  {mutations.quickEdit.isPending ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
                  快速编辑
                </Button>
              </div>
            </form>
          </section>

          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-ink">生成结果</h2>
              <div className="flex flex-wrap gap-2">
                <Badge tone={result ? "brand" : "neutral"}>{result ? "可用" : "等待"}</Badge>
                <Button
                  tone="secondary"
                  className="min-h-8 px-2 text-xs"
                  onClick={() => void exportMarkdown()}
                  disabled={mutations.exportMarkdown.isPending || !(result || getOperationOutput(operation.data))}
                  data-testid="co-writer-export"
                >
                  {mutations.exportMarkdown.isPending ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                  导出文稿
                </Button>
              </div>
            </div>
            <motion.div
              className="mt-4 min-h-64 whitespace-pre-wrap border-t border-line pt-4 text-sm leading-6 text-slate-700"
              data-testid="co-writer-result"
              animate={result ? { borderColor: "#99F6E4" } : { borderColor: "#DDE5E8" }}
              transition={{ duration: 0.25 }}
            >
              {result || "结果会显示在这里。"}
            </motion.div>
            <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden">
              <summary
                className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1"
                data-testid="co-writer-stream-toggle"
              >
                <span>
                  <span className="block text-sm font-semibold text-ink">生成进度</span>
                  <span className="mt-1 block text-sm text-slate-500">需要复盘修改过程时查看。</span>
                </span>
                <Badge tone={streamLogs.length ? "brand" : "neutral"}>{streamLogs.length ? `${streamLogs.length} 条` : "等待"}</Badge>
              </summary>
              <div className="dt-event-feed mt-4 min-h-24 rounded-lg p-3 text-xs leading-5" data-testid="co-writer-stream-log">
                {streamLogs.length ? (
                  <AnimatePresence initial={false}>
                    {streamLogs.map((line, index) => (
                      <motion.p
                        key={`${line}-${index}`}
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.16 }}
                        className="dt-event-row font-mono"
                      >
                        <LogText line={line} />
                      </motion.p>
                    ))}
                  </AnimatePresence>
                ) : (
                  <p className="text-slate-500">生成过程会显示在这里。</p>
                )}
              </div>
            </details>
            <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
              <SelectInput value={notebookId} onChange={(event) => setNotebookId(event.target.value)}>
                <option value="">
                  {notebooks.isLoading || notebooks.isFetching ? "正在读取记录本..." : "选择记录本"}
                </option>
                {(notebooks.data ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectInput>
              <Button
                tone="secondary"
                onClick={() => void saveResult()}
                disabled={!notebookId || !result || mutations.saveRecord.isPending}
                data-testid="co-writer-save"
              >
                {mutations.saveRecord.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                保存
              </Button>
            </div>
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">最近写作任务</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {(history.data ?? []).slice(0, 8).map((item, index) => {
                const operationId = String(item.id ?? item.operation_id ?? "");
                return (
                  <motion.button
                    key={String(item.id ?? index)}
                    type="button"
                    onClick={() => operationId && setSelectedOperationId(operationId)}
                    data-testid={operationId ? `co-writer-history-${operationId}` : undefined}
                    className={`rounded-lg border p-4 text-left text-sm text-slate-600 transition ${
                      selectedOperationId === operationId ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"
                    }`}
                    whileHover={{ y: -0.5 }}
                    whileTap={{ scale: 0.99 }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate font-semibold text-ink">{String(item.instruction ?? item.action ?? "写作任务")}</p>
                      <Eye size={15} className="shrink-0 text-brand-blue" />
                    </div>
                    <p className="mt-2 line-clamp-2 leading-6">{getHistoryPreview(item)}</p>
                    {operationId ? <p className="mt-2 text-xs text-slate-400">记录 {index + 1}</p> : null}
                  </motion.button>
                );
              })}
              {!history.data?.length ? <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">暂无历史写作任务。</p> : null}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-3">
            <details
              className="[&>summary::-webkit-details-marker]:hidden"
              onToggle={(event) => setAuditOpen(event.currentTarget.open)}
            >
              <summary
                className="dt-interactive flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 rounded-lg px-1 py-1"
                data-testid="co-writer-audit-toggle"
              >
                <span>
                  <h2 className="text-base font-semibold text-ink">修改记录</h2>
                  <span className="mt-1 block text-sm text-slate-500">{selectedOperationId || "选择历史任务后可查看输入、输出和参考来源。"}</span>
                </span>
                <Badge tone={toolCalls.data ? "brand" : "neutral"}>{toolCalls.data ? "有记录" : "详情"}</Badge>
              </summary>
              <div className="mt-4 space-y-3 border-t border-line pt-4">
                {operation.isFetching ? (
                  <p className="rounded-lg border border-line bg-white p-3 text-sm text-slate-500">正在读取修改记录...</p>
                ) : operation.data ? (
                  <>
                    <AuditBlock title="输入" content={getOperationInput(operation.data)} />
                    <AuditBlock title="输出" content={getOperationOutput(operation.data)} />
                    <AuditBlock title="修改参考" content={formatToolCallEvidence(toolCalls.data)} />
                  </>
                ) : (
                  <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
                    历史任务会保留输入、输出和修改参考，适合演示时说明系统如何完成编辑。
                  </p>
                )}
              </div>
            </details>
          </section>
        </div>
      </div>
    </div>
  );
}

function AuditBlock({ title, content, code = false }: { title: string; content: string; code?: boolean }) {
  return (
    <div className="border-t border-line pt-3 first:border-t-0 first:pt-0">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <pre className={`mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-700 ${code ? "font-mono" : ""}`}>
        {content || "暂无内容"}
      </pre>
    </div>
  );
}

function formatStreamEvent(event: CoWriterStreamEvent) {
  if (event.type === "content") return "";
  const label = event.stage || event.source || event.type || "event";
  const content = event.content || event.type || "";
  const legacy = content ? `${label}: ${event.type === "tool_call" ? `tool ${content}` : content}` : label;
  if (event.type === "tool_call") return withLegacyText(`查找参考：${formatCoWriterLogContent(content)}`, legacy);
  if (event.type === "tool_result") return withLegacyText("参考已返回", `${label}: tool result`);
  if (event.type === "stage_start") return withLegacyText(`${coWriterStageLabel(label)}开始`, `${label}: start`);
  if (event.type === "stage_end") return withLegacyText(`${coWriterStageLabel(label)}完成`, `${label}: done`);
  if (event.type === "thinking" || event.type === "progress") {
    return withLegacyText(`${coWriterStageLabel(label)}：${formatCoWriterLogContent(content)}`, `${label}: ${content}`);
  }
  return withLegacyText(content ? `进度更新：${formatCoWriterLogContent(content)}` : coWriterStageLabel(label), content ? `${label}: ${content}` : label);
}

function coWriterStageLabel(value: unknown) {
  const stage = String(value || "").toLowerCase();
  if (stage.includes("thinking") || stage.includes("plan")) return "规划修改";
  if (stage.includes("respond")) return "生成结果";
  if (stage.includes("tool")) return "查找参考";
  if (stage.includes("rewrite")) return "润色文本";
  if (stage.includes("shorten")) return "压缩文本";
  if (stage.includes("expand")) return "扩展文本";
  return "处理";
}

function formatCoWriterLogContent(value: unknown) {
  const text = String(value || "").trim();
  if (!text) return "正在处理";
  const lower = text.toLowerCase();
  if (lower === "planning edit") return "正在分析原文和修改要求";
  if (lower === "stream failed") return "流式生成失败";
  return text;
}

function formatToolCallEvidence(value: unknown) {
  const record = isRecord(value) ? value : {};
  const traces = Array.isArray(record.tool_traces) ? record.tool_traces : [];
  if (!traces.length) return "这次修改主要根据原文和你的编辑要求完成，没有额外查找资料参考。";
  return traces
    .slice(0, 5)
    .map((trace, index) => {
      const item = isRecord(trace) ? trace : {};
      const tool = formatToolName(item.tool ?? item.tool_name ?? item.name);
      const output = String(item.output ?? item.result ?? item.summary ?? item.content ?? "").trim();
      return `${index + 1}. ${tool}${output ? `：${output}` : " 已返回可参考信息。"}`;
    })
    .join("\n");
}

function formatToolName(value: unknown) {
  const text = String(value || "").trim();
  const lower = text.toLowerCase();
  if (!text) return "参考来源";
  if (lower.includes("rag")) return "资料查找";
  if (lower.includes("search")) return "资料查找";
  if (lower.includes("mark")) return "自动批注";
  if (lower.includes("edit") || lower.includes("rewrite")) return "文本编辑";
  return text.replace(/_/g, " ");
}

function getHistoryPreview(item: Record<string, unknown>) {
  const input = isRecord(item.input) ? item.input : {};
  const output = isRecord(item.output) ? item.output : {};
  return String(
    item.text ??
      item.edited_text ??
      item.result ??
      input.selected_text ??
      output.edited_text ??
      "历史记录",
  );
}

function LogText({ line }: { line: string }) {
  const [visible] = line.split(LEGACY_TEXT_SEPARATOR);
  return <>{visible}</>;
}

function getOperationInput(item: Record<string, unknown> | undefined) {
  if (!item) return "";
  const input = isRecord(item.input) ? item.input : {};
  return String(input.selected_text ?? item.text ?? item.selected_text ?? "");
}

function getOperationOutput(item: Record<string, unknown> | undefined) {
  if (!item) return "";
  const output = isRecord(item.output) ? item.output : {};
  return String(output.edited_text ?? item.edited_text ?? item.marked_text ?? item.result ?? "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
