import { Loader2, MessageSquareText, SendHorizontal, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { sparkBotSocketUrl } from "@/lib/api";
import type { SparkBotSummary } from "@/lib/types";

type AssistantQuickAction = {
  title: string;
  detail: string;
  prompt: string;
  icon: LucideIcon;
};

type BotChatMessage = {
  id: string;
  role: "user" | "bot" | "system";
  content: string;
  thinking?: string;
  status?: "streaming" | "done" | "error";
};

type SparkBotWsEvent = {
  type?: string;
  content?: string;
  delta?: boolean;
  append?: boolean;
};

export function SparkBotChat({
  botId,
  bot,
  running,
  draftPrompt,
  feedbackPending,
  quickActions,
  onFeedback,
}: {
  botId: string | null;
  bot?: SparkBotSummary;
  running: boolean;
  draftPrompt?: string;
  feedbackPending: boolean;
  quickActions: AssistantQuickAction[];
  onFeedback: (feedback: string, response: string) => Promise<unknown>;
}) {
  const [messages, setMessages] = useState<BotChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "connecting" | "streaming" | "error">("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const activeReplyIdRef = useRef<string | null>(null);
  const messageSequenceRef = useRef(0);
  const busy = status === "connecting" || status === "streaming";
  const canSend = Boolean(botId && running && !busy);

  useEffect(
    () => () => {
      wsRef.current?.close();
    },
    [],
  );

  const nextMessageId = (prefix: string) => {
    messageSequenceRef.current += 1;
    return `${prefix}-${messageSequenceRef.current}`;
  };

  const sendContent = (nextContent: string) => {
    if (!botId || !running || !nextContent.trim() || busy) return;
    wsRef.current?.close();
    const content = nextContent.trim();
    const replyId = nextMessageId("bot");
    activeReplyIdRef.current = replyId;
    setMessages((current) => [
      ...current,
      { id: nextMessageId("user"), role: "user", content, status: "done" },
      { id: replyId, role: "bot", content: "", status: "streaming" },
    ]);
    setStatus("connecting");

    const socket = new WebSocket(sparkBotSocketUrl(botId));
    wsRef.current = socket;
    const updateReply = (updater: (message: BotChatMessage) => BotChatMessage) => {
      setMessages((current) => current.map((item) => (item.id === replyId ? updater(item) : item)));
    };
    socket.onopen = () => {
      setStatus("streaming");
      socket.send(JSON.stringify({ content, chat_id: "web" }));
    };
    socket.onmessage = (message) => {
      try {
        const eventData = JSON.parse(message.data) as SparkBotWsEvent;
        if (eventData.type === "thinking") {
          updateReply((item) => ({ ...item, thinking: eventData.content || "正在思考", status: "streaming" }));
          return;
        }
        if (eventData.type === "content_delta" || eventData.type === "delta" || (eventData.type === "content" && (eventData.delta || eventData.append))) {
          updateReply((item) => ({
            ...item,
            content: `${item.content}${eventData.content || ""}`,
            status: "streaming",
          }));
          return;
        }
        if (eventData.type === "content") {
          updateReply((item) => ({ ...item, content: eventData.content || "", status: "streaming" }));
          return;
        }
        if (eventData.type === "proactive") {
          setMessages((current) => [
            ...current,
            { id: nextMessageId("proactive"), role: "bot", content: eventData.content || "主动提醒", status: "done" },
          ]);
          return;
        }
        if (eventData.type === "done") {
          updateReply((item) => ({ ...item, status: "done" }));
          activeReplyIdRef.current = null;
          setStatus("idle");
          socket.close();
          return;
        }
        if (eventData.type === "error") {
          setStatus("error");
          activeReplyIdRef.current = null;
          updateReply((item) => ({ ...item, content: eventData.content || "助教回复异常", status: "error" }));
        }
      } catch {
        setStatus("error");
        activeReplyIdRef.current = null;
      }
    };
    socket.onerror = () => {
      setStatus("error");
      activeReplyIdRef.current = null;
      updateReply((item) => ({ ...item, content: "无法连接助教实时通道", status: "error" }));
    };
    socket.onclose = () => {
      wsRef.current = null;
      setStatus((current) => (current === "connecting" || current === "streaming" ? "idle" : current));
    };
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-chat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <MessageSquareText size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink" aria-label="Bot 对话">
              助教对话
            </h2>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {botId ? `${bot?.name || botId} · ${running ? "可继续学习" : "先启动助教"}` : "选择一个课程助教后开始学习。"}
          </p>
        </div>
        <Badge tone={status === "error" ? "danger" : status === "idle" ? "neutral" : "brand"}>{formatBotChatStatus(status)}</Badge>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-5">
        {quickActions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.title}
              type="button"
              className="dt-interactive rounded-lg border border-line bg-canvas p-2 text-left transition hover:border-brand-purple-300 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => sendContent(action.prompt)}
              disabled={!canSend}
              data-testid={`sparkbot-quick-action-${action.title}`}
            >
              <span className="flex items-center gap-2">
                <Icon size={15} className="shrink-0 text-brand-purple" />
                <span className="truncate text-xs font-semibold text-ink">{action.title}</span>
              </span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">{action.detail}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-4 max-h-80 space-y-3 overflow-y-auto rounded-lg border border-line bg-white p-3">
        <AnimatePresence initial={false}>
          {messages.map((message) => (
            <motion.article
              key={message.id}
              className={`rounded-lg border p-3 text-sm leading-6 ${
                message.role === "user" ? "ml-auto max-w-[82%] border-brand-purple-300 bg-tint-lavender" : "mr-auto max-w-[82%] border-line bg-white"
              }`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <Badge tone={message.status === "error" ? "danger" : message.role === "user" ? "brand" : "neutral"}>
                {message.role === "user" ? "你" : "助教"}
              </Badge>
              {message.thinking && message.status !== "done" ? (
                <p className="mt-2 rounded-md border border-line bg-canvas px-2 py-1 text-xs leading-5 text-slate-500">{formatSparkBotThinking(message.thinking)}</p>
              ) : null}
              <p className="mt-2 whitespace-pre-wrap text-slate-700">{message.content || "等待回复..."}</p>
              {message.role === "bot" && message.status === "done" && message.content ? (
                <AssistantReplyActions pending={feedbackPending} response={message.content} onFeedback={onFeedback} />
              ) : null}
            </motion.article>
          ))}
        </AnimatePresence>
        {!messages.length ? (
          <p className="text-sm leading-6 text-slate-500">启动助教后，可以直接提问，也可以先点上方快捷动作继续学习、生成练习或复盘错因。</p>
        ) : null}
      </div>
      <SparkBotChatComposer key={draftPrompt || "blank-draft"} busy={busy} canSend={canSend} draftPrompt={draftPrompt} onSend={sendContent} />
    </section>
  );
}

function SparkBotChatComposer({
  busy,
  canSend,
  draftPrompt,
  onSend,
}: {
  busy: boolean;
  canSend: boolean;
  draftPrompt?: string;
  onSend: (content: string) => void;
}) {
  const [input, setInput] = useState(draftPrompt || "");
  const send = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = input.trim();
    if (!content) return;
    onSend(content);
    setInput("");
  };

  return (
    <form className="mt-4 flex gap-2" onSubmit={send}>
      <TextInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="向助教提问，或让它生成练习、图解、复盘..." data-testid="sparkbot-chat-input" />
      <Button tone="primary" type="submit" disabled={!canSend || !input.trim()}>
        {busy ? <Loader2 size={16} className="animate-spin" /> : <SendHorizontal size={16} />}
        发送
      </Button>
    </form>
  );
}

function formatBotChatStatus(status: "idle" | "connecting" | "streaming" | "error") {
  return {
    idle: "准备好",
    connecting: "连接助教",
    streaming: "生成中",
    error: "异常",
  }[status];
}

function formatSparkBotThinking(value?: string) {
  const text = (value || "").toLowerCase();
  if (text.includes("rag") || text.includes("search") || text.includes("fetch") || text.includes("read")) return "正在查看课程资料";
  if (text.includes("question") || text.includes("quiz") || text.includes("practice") || text.includes("exercise")) return "正在生成练习";
  if (text.includes("write") || text.includes("memory") || text.includes("profile") || text.includes("history")) return "正在写入学习记录";
  if (text.includes("tool") || text.includes("agent") || text.includes("team")) return "正在协调助教能力";
  return "正在整理讲解";
}

function AssistantReplyActions({
  pending,
  response,
  onFeedback,
}: {
  pending: boolean;
  response: string;
  onFeedback: (feedback: string, response: string) => Promise<unknown>;
}) {
  const [selected, setSelected] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(false);
  const feedback = ["有帮助", "太难了", "想要例子", "回答不准确"];
  const submitFeedback = async (item: string) => {
    setSelected(item);
    setSaved(false);
    setError(false);
    try {
      await onFeedback(item, response);
      setSaved(true);
    } catch {
      setError(true);
    }
  };
  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className="text-xs font-medium text-slate-500">这次回答之后，你可以：</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {feedback.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => void submitFeedback(item)}
            disabled={pending}
            className={`dt-interactive rounded-md border px-2 py-1 text-xs font-medium transition ${
              selected === item ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            }`}
          >
            {item}
          </button>
        ))}
      </div>
      {saved ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">谢谢，已写入学习效果证据。</p>
      ) : error ? (
        <p className="mt-2 text-xs leading-5 text-amber-700">反馈暂时没有写入，可以稍后再试。</p>
      ) : selected ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">正在记录这次反馈...</p>
      ) : null}
    </div>
  );
}
