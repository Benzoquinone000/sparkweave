export type SparkWeaveLightFieldMode = "idle" | "focus" | "thinking" | "complete";

interface SparkWeaveLightFieldProps {
  active?: boolean;
  mode?: SparkWeaveLightFieldMode;
  pulseKey?: number;
}

export function SparkWeaveLightField({ active = false, mode = "idle", pulseKey = 0 }: SparkWeaveLightFieldProps) {
  return (
    <div
      className="dt-gemini-light-field"
      data-active={active ? "true" : "false"}
      data-mode={mode}
      data-pulse={pulseKey > 0 ? "true" : "false"}
      aria-hidden="true"
    />
  );
}
