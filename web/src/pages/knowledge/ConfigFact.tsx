export function ConfigFact({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "success" | "warning";
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={tone === "warning" ? "mt-1 truncate font-semibold text-amber-700" : "mt-1 truncate font-semibold text-ink"}>
        {value}
      </p>
    </div>
  );
}
