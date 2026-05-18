import type { RagDiagnostic } from "@/lib/types";

import {
  formatRagCheckName,
  formatRagDiagnosticStatus,
} from "./format";

export function RagDiagnosticChecksPanel({ report }: { report?: RagDiagnostic }) {
  if (!report?.checks?.length) return null;

  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {report.checks.map((check, index) => (
        <div key={`${check.name || "check"}-${index}`} className="rounded-lg border border-line bg-white p-2">
          <p className="text-xs font-semibold text-ink">{formatRagCheckName(check.name)}</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
            {check.message || formatRagDiagnosticStatus(check.status)}
          </p>
        </div>
      ))}
    </div>
  );
}
