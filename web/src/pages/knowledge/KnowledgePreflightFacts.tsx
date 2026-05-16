import { ClipboardCheck, Loader2, RefreshCw, Search, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { RagPreflight } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import { formatDiagnosticError } from "./format";
import { isRecord } from "./ragUtils";

export function RagPreflightFacts({
  preflight,
  error,
  fetching,
  reindexing,
  onOpenRecovery,
  onOpenTest,
  onReindex,
}: {
  preflight?: RagPreflight;
  error: unknown;
  fetching: boolean;
  reindexing: boolean;
  onOpenRecovery: () => void;
  onOpenTest: () => void;
  onReindex: () => void;
}) {
  if (!preflight && !fetching && !error) return null;

  const status = String(preflight?.status || "").toLowerCase();
  const ready = ["ready", "ok"].includes(status);
  const commands = Array.isArray(preflight?.recommended_commands)
    ? preflight.recommended_commands.filter((item): item is string => typeof item === "string" && Boolean(item.trim())).slice(0, 3)
    : [];
  const docker = isRecord(preflight?.docker) ? preflight?.docker : {};
  const diagnostic = isRecord(preflight?.diagnostic) ? preflight?.diagnostic : {};
  const checkTone = ready ? "success" : error ? "danger" : "warning";
  const label = fetching ? "环境预检中" : error ? "环境预检失败" : preflight?.label || "环境预检";
  const summary = fetching
    ? "正在确认检索服务、知识库索引和本地运行环境。"
    : error
      ? formatDiagnosticError(error)
      : preflight?.summary || "预检会在创建验收知识库前确认环境是否可用。";

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface p-3" data-testid="knowledge-preflight-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ClipboardCheck size={16} className="text-brand-purple" />
            <p className="text-xs font-semibold text-ink">{label}</p>
            <Badge tone={checkTone}>{ready ? "可验收" : "需处理"}</Badge>
          </div>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">{summary}</p>
          {preflight?.primary_action ? (
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">建议：{preflight.primary_action}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {ready ? (
            <Button tone="primary" className="min-h-8 px-3 text-xs" onClick={onOpenTest}>
              <Search size={14} />
              提问预检
            </Button>
          ) : (
            <Button tone="primary" className="min-h-8 px-3 text-xs" onClick={onOpenRecovery}>
              <Wrench size={14} />
              打开修复向导
            </Button>
          )}
          <Button tone="secondary" className="min-h-8 bg-white px-3 text-xs" disabled={reindexing} onClick={onReindex}>
            {reindexing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            重建索引
          </Button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <ConfigFact label="目标资料库" value={String(preflight?.kb_name || "全局环境")} />
        <ConfigFact
          label="Milvus 服务"
          value={formatBooleanStatus(diagnostic.milvus_service_running)}
          tone={diagnostic.milvus_service_running === false ? "warning" : undefined}
        />
        <ConfigFact label="Docker" value={formatDockerStatus(docker)} tone={docker?.docker_running === false ? "warning" : undefined} />
        <ConfigFact label="连接类型" value={String(diagnostic.connection_error_kind || diagnostic.status || status || "-")} tone={ready ? undefined : "warning"} />
      </div>

      {commands.length ? (
        <div className="mt-3 rounded-lg border border-line bg-white p-3">
          <p className="text-xs font-semibold text-ink">开发环境修复命令</p>
          <div className="mt-2 grid gap-2">
            {commands.map((command) => (
              <code key={command} className="block break-all rounded-md bg-surface px-2 py-1 text-xs leading-5 text-slate-700">
                {command}
              </code>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatBooleanStatus(value: unknown) {
  if (value === true) return "已启动";
  if (value === false) return "未启动";
  return "未检查";
}

function formatDockerStatus(docker: Record<string, unknown> | undefined) {
  if (!docker || docker.skipped) return "未检查";
  if (docker.docker_running === true) return "可用";
  if (docker.docker_cli_present === false) return "未安装";
  if (docker.docker_running === false) return "未运行";
  return "未检查";
}
