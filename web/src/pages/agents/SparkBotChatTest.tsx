import { Loader2, MessageSquareText, SendHorizontal } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { sparkBotSocketUrl } from "@/lib/api/sparkbot";
import type { SparkBotSummary } from "@/lib/types";

type ChatMessage = {
  role: "user" | "bot";
  content: string;
};

export function SparkBotChatTest({
  bot,
  initialInput,
}: {
  bot?: SparkBotSummary;
  initialInput: string;
}) {
  const [input, setInput] = useState(initialInput);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const canSend = Boolean(bot?.bot_id && bot.running && !busy);

  useEffect(
    () => () => {
      socketRef.current?.close();
    },
    [],
  );

  const send = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!bot?.bot_id || !input.trim() || !canSend) return;
    const content = input.trim();
    setInput("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", content }, { role: "bot", content: "" }]);
    socketRef.current?.close();
    const socket = new WebSocket(sparkBotSocketUrl(bot.bot_id));
    socketRef.current = socket;
    socket.onopen = () => socket.send(JSON.stringify({ content, chat_id: "web" }));
    socket.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data) as { type?: string; content?: string; delta?: boolean; append?: boolean };
        if (data.type === "content_delta" || data.type === "delta" || data.delta || data.append) {
          setMessages((current) => appendLastBotMessage(current, data.content || ""));
        } else if (data.type === "content" || data.type === "proactive") {
          setMessages((current) => replaceLastBotMessage(current, data.content || ""));
        } else if (data.type === "done") {
          setBusy(false);
          socket.close();
        } else if (data.type === "error") {
          setMessages((current) => replaceLastBotMessage(current, data.content || "助教回复失败。"));
          setBusy(false);
        }
      } catch {
        setMessages((current) => replaceLastBotMessage(current, "助教回复格式异常。"));
        setBusy(false);
      }
    };
    socket.onerror = () => {
      setMessages((current) => replaceLastBotMessage(current, "无法连接助教服务。"));
      setBusy(false);
    };
    socket.onclose = () => setBusy(false);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-chat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquareText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">试问助教</h2>
        </div>
        <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "可测试" : "先启动助教"}</Badge>
      </div>
      <div className="mt-4 max-h-60 space-y-2 overflow-y-auto rounded-lg border border-line bg-canvas p-3">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`rounded-lg border p-3 text-sm leading-6 ${
              message.role === "user" ? "ml-auto max-w-[82%] border-brand-purple-300 bg-tint-lavender" : "mr-auto max-w-[82%] border-line bg-white"
            }`}
          >
            <p className="text-xs font-semibold text-slate-500">{message.role === "user" ? "我" : "助教"}</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-700">{message.content || "等待回复..."}</p>
          </div>
        ))}
        {!messages.length ? <p className="text-sm leading-6 text-slate-500">这里仅用于测试助教回复。正式任务优先通过群聊和定时提醒运行。</p> : null}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={send}>
        <TextInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入一句测试消息，例如：列出提醒" data-testid="sparkbot-chat-input" />
        <Button tone="primary" type="submit" disabled={!canSend || !input.trim()}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <SendHorizontal size={16} />}
          发送
        </Button>
      </form>
    </section>
  );
}

function appendLastBotMessage(messages: ChatMessage[], delta: string) {
  return messages.map((message, index) =>
    index === messages.length - 1 && message.role === "bot" ? { ...message, content: `${message.content}${delta}` } : message,
  );
}

function replaceLastBotMessage(messages: ChatMessage[], content: string) {
  return messages.map((message, index) => (index === messages.length - 1 && message.role === "bot" ? { ...message, content } : message));
}
