import { Badge } from "@/components/ui/Badge";
import type { RagDiagnostic } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import {
  formatRagDiagnosticSummary,
  knowledgeProviderLabel,
} from "./format";
import { isRecord, readNumber } from "./ragUtils";

export function RagReadinessFacts({ report }: { report: RagDiagnostic }) {
  const readiness = isRecord(report.readiness) ? report.readiness : {};
  const proxy = isRecord(report.proxy) ? report.proxy : {};
  const proxyLabel =
    proxy.http_proxy_configured || proxy.https_proxy_configured
      ? proxy.milvus_proxy_bypassed
        ? "已绕过"
        : "使用代理"
      : "未配置";
  const connectionKind = String(report.connection_error_kind || report.status || "-");

  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-ink">{String(readiness.label || "资料状态")}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{String(readiness.summary || formatRagDiagnosticSummary(report))}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">下一步：{String(readiness.primary_action || "查看检查项")}</p>
        </div>
        <Badge tone={String(readiness.state || "") === "ready" ? "success" : "warning"}>
          {String(readiness.state || "") === "ready" ? "可用" : "需处理"}
        </Badge>
      </div>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <ConfigFact label="查找服务" value={knowledgeProviderLabel(report.provider)} />
        <ConfigFact label="资料库" value={String(report.collection_name || report.collection_count || "-")} />
        <ConfigFact label="引用片段" value={String(readNumber(report, "vector_row_count") ?? "-")} />
        <ConfigFact label="查找模型" value={`${String(report.embedding_model || "-")} / ${String(report.embedding_dim || "-")}`} />
      </div>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <ConfigFact label="运行地址" value={String(report.uri || "-")} />
        <ConfigFact label="建库地址" value={String(report.indexed_uri || "-")} />
        <ConfigFact label="连接状态" value={connectionKind} tone={report.status === "error" ? "warning" : undefined} />
        <ConfigFact label="代理策略" value={proxyLabel} tone={proxyLabel === "使用代理" ? "warning" : undefined} />
      </div>
    </div>
  );
}
