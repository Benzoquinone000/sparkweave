import type { RagTestHandoff } from "@/lib/ragHandoff";
import type { RagSearchTestResult } from "@/lib/types";

import {
  RagSearchAgenticSettingsPanel,
  RagSearchBasicSettingsGrid,
  RagSearchFormActions,
  RagSearchHandoffCard,
  RagSearchPresetPanel,
  RagSearchQueryField,
} from "./RagSearchSetupPanels";

export function RagSearchSetupForm({
  activeKb,
  query,
  profile,
  mode,
  agentic,
  topK,
  agenticMaxContextChars,
  agenticMaxSources,
  agenticMinRelevantCoverage,
  presetId,
  result,
  running,
  handoff,
  onQueryChange,
  onProfileChange,
  onModeChange,
  onAgenticChange,
  onTopKChange,
  onAgenticMaxContextCharsChange,
  onAgenticMaxSourcesChange,
  onAgenticMinRelevantCoverageChange,
  onPresetApply,
  onRun,
  onHandoffDismiss,
  onShowLastResult,
}: {
  activeKb: string;
  query: string;
  profile: string;
  mode: string;
  agentic: string;
  topK: number;
  agenticMaxContextChars: number;
  agenticMaxSources: number;
  agenticMinRelevantCoverage: number;
  presetId: string;
  result: RagSearchTestResult | null;
  running: boolean;
  handoff?: RagTestHandoff | null;
  onQueryChange: (value: string) => void;
  onProfileChange: (value: string) => void;
  onModeChange: (value: string) => void;
  onAgenticChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onAgenticMaxContextCharsChange: (value: number) => void;
  onAgenticMaxSourcesChange: (value: number) => void;
  onAgenticMinRelevantCoverageChange: (value: number) => void;
  onPresetApply: (presetId: string) => void;
  onRun: () => void;
  onHandoffDismiss?: () => void;
  onShowLastResult: () => void;
}) {
  return (
    <form
      className="mt-4 grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onRun();
      }}
    >
      {handoff && query.trim() ? (
        <RagSearchHandoffCard
          handoff={handoff}
          activeKb={activeKb}
          running={running}
          onRun={onRun}
          onDismiss={onHandoffDismiss}
        />
      ) : null}

      <RagSearchPresetPanel presetId={presetId} onPresetApply={onPresetApply} />
      <RagSearchQueryField query={query} onQueryChange={onQueryChange} />
      <RagSearchBasicSettingsGrid
        profile={profile}
        mode={mode}
        agentic={agentic}
        topK={topK}
        onProfileChange={onProfileChange}
        onModeChange={onModeChange}
        onAgenticChange={onAgenticChange}
        onTopKChange={onTopKChange}
      />
      <RagSearchAgenticSettingsPanel
        agentic={agentic}
        agenticMaxContextChars={agenticMaxContextChars}
        agenticMaxSources={agenticMaxSources}
        agenticMinRelevantCoverage={agenticMinRelevantCoverage}
        onAgenticMaxContextCharsChange={onAgenticMaxContextCharsChange}
        onAgenticMaxSourcesChange={onAgenticMaxSourcesChange}
        onAgenticMinRelevantCoverageChange={onAgenticMinRelevantCoverageChange}
      />
      <RagSearchFormActions
        query={query}
        result={result}
        running={running}
        onShowLastResult={onShowLastResult}
      />
    </form>
  );
}
