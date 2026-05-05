import { TOOL_OPTIONS } from "@/lib/capabilities";

export function ToolSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (tools: string[]) => void;
}) {
  const toggle = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter((item) => item !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-1.5">
      {TOOL_OPTIONS.map((tool) => {
        const active = selected.includes(tool.id);
        return (
          <button
            key={tool.id}
            type="button"
            onClick={() => toggle(tool.id)}
            className={`dt-interactive flex min-h-9 items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm ${
              active
                ? "border-ink bg-ink text-white"
                : "border-line bg-white text-steel hover:border-brand-purple hover:text-ink"
            }`}
          >
            <tool.icon size={16} />
            <span>{tool.label}</span>
          </button>
        );
      })}
    </div>
  );
}
