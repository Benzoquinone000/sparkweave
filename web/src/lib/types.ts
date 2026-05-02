export type CapabilityId =
  | "chat"
  | "deep_solve"
  | "deep_question"
  | "deep_research"
  | "external_video_search"
  | "visualize"
  | "math_animator";

export type StreamEventType =
  | "stage_start"
  | "stage_end"
  | "thinking"
  | "observation"
  | "content"
  | "tool_call"
  | "tool_result"
  | "progress"
  | "sources"
  | "result"
  | "error"
  | "session"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  source: string;
  stage: string;
  content: string;
  metadata: Record<string, unknown>;
  session_id?: string;
  turn_id?: string;
  seq?: number;
  timestamp?: number;
}

export interface ChatAttachment {
  type: "file" | "image";
  filename: string;
  mime_type: string;
  base64: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  capability?: CapabilityId;
  status?: "streaming" | "done" | "error";
  events?: StreamEvent[];
  attachments?: ChatAttachment[];
  createdAt: number;
}

export interface SessionSummary {
  id: string;
  session_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
  last_message?: string;
  status?: string;
  active_turn_id?: string;
  preferences?: {
    capability?: string;
    tools?: string[];
    knowledge_bases?: string[];
    language?: string;
  };
}

export interface SessionDetail extends SessionSummary {
  messages: Array<{
    id: number;
    role: "user" | "assistant" | "system";
    content: string;
    capability?: string;
    events?: StreamEvent[];
    attachments?: ChatAttachment[];
    created_at: number;
  }>;
}

export interface KnowledgeBase {
  name: string;
  is_default?: boolean;
  status?: string;
  document_count?: number;
  file_count?: number;
  statistics?: Record<string, unknown>;
  progress?: Record<string, unknown>;
  rag_provider?: string;
}

export interface KnowledgeBaseDetail extends KnowledgeBase {
  path?: string;
  description?: string;
  metadata?: Record<string, unknown>;
  files?: unknown[];
  documents?: unknown[];
  [key: string]: unknown;
}

export interface KnowledgeConfig {
  default_kb?: string | null;
  rag_provider?: string;
  search_mode?: string;
  needs_reindex?: boolean;
  path?: string;
  description?: string;
  embedding_model?: string;
  embedding_dim?: number | string;
  embedding_mismatch?: boolean;
  [key: string]: unknown;
}

export interface KnowledgeConfigResponse {
  status?: string;
  kb_name: string;
  config: KnowledgeConfig;
}

export interface KnowledgeConfigRegistry {
  defaults?: KnowledgeConfig;
  knowledge_bases?: Record<string, KnowledgeConfig>;
  [key: string]: unknown;
}

export interface NotebookSummary {
  id: string;
  name: string;
  description?: string;
  color?: string;
  icon?: string;
  record_count?: number;
  updated_at?: string | number;
}

export interface NotebookRecord {
  id: string;
  record_id?: string;
  type?: "solve" | "question" | "research" | "co_writer" | "chat" | "guided_learning";
  record_type: "solve" | "question" | "research" | "co_writer" | "chat" | "guided_learning";
  title: string;
  summary?: string;
  user_query?: string;
  output?: string;
  metadata?: Record<string, unknown>;
  kb_name?: string | null;
  created_at?: string | number;
  updated_at?: string | number;
}

export interface NotebookDetail extends NotebookSummary {
  records?: NotebookRecord[];
  created_at?: string | number;
}

export interface NotebookHealth {
  status: string;
  service?: string;
  [key: string]: unknown;
}

export interface NotebookReference {
  notebook_id: string;
  record_ids: string[];
}

export interface QuestionCategory {
  id: number;
  name: string;
  created_at?: number;
  entry_count?: number;
}

export interface QuestionNotebookEntry {
  id: number;
  session_id: string;
  followup_session_id?: string | null;
  session_title?: string;
  question_id?: string;
  question: string;
  question_type?: string;
  options?: Record<string, string>;
  correct_answer?: string;
  explanation?: string;
  difficulty?: string;
  user_answer?: string;
  is_correct?: boolean;
  bookmarked?: boolean;
  categories?: QuestionCategory[] | null;
  created_at?: number;
  updated_at?: number;
}

export interface QuizQuestion {
  question_id?: string;
  question: string;
  question_type?: "choice" | "true_false" | "fill_blank" | "written" | "coding" | string;
  options?: Record<string, string>;
  correct_answer: string;
  explanation?: string;
  difficulty?: string;
  concentration?: string;
  knowledge_context?: string;
}

export interface QuestionGenerationResult {
  template?: Record<string, unknown>;
  qa_pair?: Partial<QuizQuestion> & Record<string, unknown>;
  success?: boolean;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface QuestionGenerationSummary {
  success?: boolean;
  source?: string;
  requested?: number;
  template_count?: number;
  completed?: number;
  failed?: number;
  mode?: string;
  results?: QuestionGenerationResult[];
  templates?: Array<Record<string, unknown>>;
  trace?: Record<string, unknown>;
  errors?: string[];
}

export interface QuizResultItem {
  question_id?: string;
  question: string;
  question_type?: string;
  options?: Record<string, string>;
  concepts?: string[];
  knowledge_points?: string[];
  user_answer: string;
  correct_answer: string;
  explanation?: string;
  difficulty?: string;
  is_correct: boolean;
}

export interface MathAnimatorArtifact {
  type: "video" | "image";
  url: string;
  filename: string;
  content_type?: string;
  label?: string;
}

export interface MathAnimatorResult {
  response?: string;
  output_mode?: "video" | "image";
  learner_profile_hints?: Record<string, unknown>;
  style_hint?: string;
  code?: {
    language?: string;
    content?: string;
  };
  artifacts?: MathAnimatorArtifact[];
  timings?: Record<string, number>;
  render?: {
    quality?: string;
    retry_attempts?: number;
    render_skipped?: boolean;
    skip_reason?: string;
    visual_review?: {
      passed?: boolean;
      summary?: string;
      issues?: string[];
      suggested_fix?: string;
      reviewed_frames?: number;
    } | null;
  };
}

export interface VisualizeResult {
  response?: string;
  render_type: "svg" | "chartjs" | "mermaid";
  learner_profile_hints?: Record<string, unknown>;
  style_hint?: string;
  code: {
    language?: string;
    content: string;
  };
  analysis?: {
    render_type?: string;
    description?: string;
    data_description?: string;
    chart_type?: string;
    visual_elements?: string[];
    rationale?: string;
  };
  review?: {
    optimized_code?: string;
    changed?: boolean;
    review_notes?: string;
  };
}

export interface VisionCommand {
  command?: string;
  description?: string;
  [key: string]: unknown;
}

export interface VisionAnalyzeResponse {
  session_id: string;
  has_image: boolean;
  final_ggb_commands: VisionCommand[];
  ggb_script?: string | null;
  analysis_summary?: {
    image_is_reference?: boolean;
    elements_count?: number;
    commands_count?: number;
    [key: string]: unknown;
  };
}

export interface KnowledgeTaskResult {
  message?: string;
  name?: string;
  files?: Array<Record<string, unknown>>;
  task_id?: string;
}

export interface KnowledgeProgress {
  status?: string;
  stage?: string;
  message?: string;
  percent?: number;
  current?: number;
  total?: number;
  task_id?: string;
}

export interface KnowledgeHealth {
  status: string;
  config_file?: string;
  config_exists?: boolean;
  base_dir?: string;
  base_dir_exists?: boolean;
  knowledge_bases_count?: number;
  error?: string;
}

export interface KnowledgeDefaultResponse {
  default_kb?: string | null;
}

export interface LinkedFolder {
  id: string;
  path: string;
  added_at: string;
  file_count: number;
}

export type MemoryFile = "summary" | "profile";

export interface MemorySnapshot {
  summary: string;
  profile: string;
  summary_updated_at: string | null;
  profile_updated_at: string | null;
  saved?: boolean;
  changed?: boolean;
  cleared?: boolean;
}

export interface LearnerProfileSource {
  source_id: string;
  label: string;
  kind: string;
  evidence_count: number;
  updated_at?: string | null;
  confidence: number;
}

export interface LearnerProfileClaim {
  label: string;
  value: string;
  source_ids: string[];
  confidence: number;
  evidence_count: number;
}

export interface LearnerMastery {
  concept_id: string;
  title: string;
  score?: number | null;
  status: string;
  source_ids: string[];
  evidence_count: number;
  updated_at?: string | null;
}

export interface LearnerWeakPoint {
  label: string;
  reason?: string;
  severity: "low" | "medium" | "high" | string;
  source_ids: string[];
  evidence_count: number;
  confidence: number;
  updated_at?: string | null;
}

export interface LearnerEvidencePreview {
  evidence_id: string;
  source_id: string;
  source_label: string;
  title: string;
  summary?: string;
  created_at?: string | null;
  score?: number | null;
  metadata?: Record<string, unknown>;
}

export interface LearnerProfileSnapshot {
  version: number;
  generated_at: string;
  confidence: number;
  overview: {
    current_focus: string;
    suggested_level?: string;
    preferred_time_budget_minutes?: number;
    assessment_accuracy?: number | null;
    summary?: string;
    [key: string]: unknown;
  };
  stable_profile: {
    goals?: string[];
    preferences?: string[];
    strengths?: string[];
    constraints?: string[];
    [key: string]: unknown;
  };
  learning_state: {
    weak_points?: LearnerWeakPoint[];
    mastery?: LearnerMastery[];
    [key: string]: unknown;
  };
  next_action?: {
    kind?: string;
    title?: string;
    summary?: string;
    primary_label?: string;
    href?: string;
    estimated_minutes?: number;
    source_type?: string;
    source_label?: string;
    confidence?: number;
    suggested_prompt?: string;
    [key: string]: unknown;
  };
  recommendations: string[];
  sources: LearnerProfileSource[];
  evidence_preview: LearnerEvidencePreview[];
  data_quality: {
    source_count: number;
    evidence_count: number;
    warnings?: string[];
    read_only?: boolean;
    calibration_count?: number;
    [key: string]: unknown;
  };
}

export interface LearnerProfileEvidencePreviewResponse {
  items: LearnerEvidencePreview[];
  total: number;
}

export interface LearnerProfileCalibrationRequest {
  action: "confirm" | "reject" | "correct" | string;
  claim_type: string;
  value: string;
  corrected_value?: string;
  note?: string;
  source_id?: string;
}

export interface LearnerProfileCalibrationResponse {
  event: LearnerEvidenceEvent;
  profile: LearnerProfileSnapshot;
}

export interface LearnerEvidenceEvent {
  id: string;
  source: string;
  source_id?: string;
  actor: string;
  verb: string;
  object_type: string;
  object_id?: string;
  title: string;
  summary?: string;
  course_id?: string;
  node_id?: string;
  task_id?: string;
  resource_type?: string;
  score?: number | null;
  is_correct?: boolean | null;
  duration_seconds?: number | null;
  confidence: number;
  reflection?: string;
  mistake_types: string[];
  created_at: number;
  weight: number;
  metadata?: Record<string, unknown>;
}

export interface LearnerEvidenceListResponse {
  items: LearnerEvidenceEvent[];
  total: number;
  summary: {
    event_count: number;
    by_source?: Record<string, number>;
    by_verb?: Record<string, number>;
    by_object_type?: Record<string, number>;
    average_score?: number | null;
    accuracy?: number | null;
    latest_event_at?: number | null;
  };
}

export interface RagProvider {
  id?: string;
  name: string;
  label?: string;
  description?: string;
  available?: boolean;
  is_default?: boolean;
}

export interface PluginParameter {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
  default?: unknown;
  enum?: string[] | null;
}

export interface PlaygroundTool {
  name: string;
  description?: string;
  parameters?: PluginParameter[];
}

export interface PlaygroundCapability {
  name: string;
  description?: string;
  stages?: string[];
  tools_used?: string[];
  [key: string]: unknown;
}

export interface PlaygroundPlugin {
  name: string;
  type?: string;
  description?: string;
  stages?: string[];
  version?: string;
  author?: string;
}

export interface PluginsList {
  tools: PlaygroundTool[];
  capabilities: PlaygroundCapability[];
  plugins: PlaygroundPlugin[];
}

export interface PluginToolExecutionResult {
  success?: boolean;
  content?: unknown;
  sources?: unknown[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DashboardActivity {
  id: string;
  type: string;
  capability?: string;
  title?: string;
  timestamp?: number | string;
  summary?: string;
  session_ref?: string;
  message_count?: number;
  status?: string;
  active_turn_id?: string | null;
}

export interface DashboardActivityDetail extends Omit<DashboardActivity, "session_ref" | "message_count" | "status" | "summary"> {
  content?: {
    messages?: Array<{
      role?: string;
      content?: string;
      created_at?: number | string;
      [key: string]: unknown;
    }>;
    active_turns?: Array<Record<string, unknown>>;
    status?: string;
    summary?: string;
  };
}

export interface CoWriterResult {
  edited_text?: string;
  marked_text?: string;
  operation_id?: string;
  thinking?: string;
  tool_traces?: Array<Record<string, unknown>>;
}

export interface GuideSessionSummary {
  session_id: string;
  title?: string;
  user_input?: string;
  current_index?: number;
  total_points?: number;
  status?: string;
  created_at?: string | number;
  updated_at?: string | number;
}

export interface GuideSessionDetail extends GuideSessionSummary {
  knowledge_points?: Array<Record<string, unknown>>;
  current_knowledge?: Record<string, unknown>;
  chat_history?: Array<Record<string, unknown>>;
  summary?: string;
  notebook_context?: string;
}

export interface GuideHealth {
  status: string;
  service?: string;
  [key: string]: unknown;
}

export interface GuidePages {
  pages?: Array<Record<string, unknown>>;
  current_index?: number;
  total?: number;
  status?: string;
  [key: string]: unknown;
}

export type GuideV2ResourceType = "visual" | "video" | "external_video" | "quiz" | "research";

export interface ExternalVideoRecommendation {
  title?: string;
  url?: string;
  platform?: string;
  kind?: "video" | "search_fallback" | string;
  summary?: string;
  thumbnail?: string;
  embed_url?: string;
  channel?: string;
  duration_seconds?: number | null;
  published_at?: string;
  why_recommended?: string;
  score?: number;
}

export interface ExternalVideoResult {
  success?: boolean;
  render_type?: "external_video" | string;
  response?: string;
  watch_plan?: string[];
  reflection_prompt?: string;
  learner_profile_hints?: Record<string, unknown>;
  style_hint?: string;
  videos?: ExternalVideoRecommendation[];
  queries?: string[];
  search_errors?: string[];
  fallback_search?: boolean;
  agent_chain?: Array<{ label?: string; detail?: string }>;
}

export interface GuideV2Artifact {
  id: string;
  type: GuideV2ResourceType | string;
  capability?: CapabilityId | string;
  title?: string;
  status?: string;
  created_at?: number;
  config?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

export interface GuideV2Task {
  task_id: string;
  node_id: string;
  type: string;
  title: string;
  instruction: string;
  estimated_minutes?: number;
  status?: string;
  success_criteria?: string[];
  artifact_refs?: GuideV2Artifact[];
  origin?: string;
  metadata?: Record<string, unknown>;
}

export interface GuideV2PlanEvent {
  event_id: string;
  type: string;
  reason: string;
  created_at?: number;
  evidence_id?: string;
  task_id?: string;
  inserted_task_ids?: string[];
  skipped_task_ids?: string[];
}
export interface GuideV2Session {
  session_id: string;
  goal: string;
  status: string;
  created_at?: number;
  updated_at?: number;
  profile?: Record<string, unknown>;
  course_map?: {
    title?: string;
    nodes?: Array<Record<string, unknown>>;
    edges?: Array<Record<string, string>>;
    generated_by?: string;
    metadata?: Record<string, unknown>;
  };
  learning_path?: Record<string, unknown>;
  tasks?: GuideV2Task[];
  current_task?: GuideV2Task | null;
  evidence?: Array<Record<string, unknown>>;
  mastery?: Record<string, Record<string, unknown>>;
  recommendations?: string[];
  plan_events?: GuideV2PlanEvent[];
  progress?: number;
  notebook_context?: string;
}

export interface GuideV2SessionSummary {
  session_id: string;
  goal: string;
  status?: string;
  created_at?: number;
  updated_at?: number;
  progress?: number;
  current_task?: GuideV2Task | null;
  node_count?: number;
  task_count?: number;
}

export interface GuideV2LearnerMemory {
  success?: boolean;
  memory_version?: number;
  generated_at?: number;
  session_count?: number;
  completed_session_count?: number;
  evidence_count?: number;
  scored_evidence_count?: number;
  average_score?: number | null;
  low_score_count?: number;
  quiz_attempt_count?: number;
  resource_counts?: Record<string, number>;
  preferred_time_budget_minutes?: number;
  suggested_level?: string;
  confidence?: number;
  top_preferences?: Array<{ label?: string; count?: number }>;
  persistent_weak_points?: Array<{ label?: string; count?: number }>;
  common_mistakes?: Array<{ label?: string; count?: number }>;
  strengths?: Array<{ label?: string; count?: number }>;
  recent_goals?: Array<{
    session_id?: string;
    goal?: string;
    status?: string;
    updated_at?: number;
    progress?: number;
  }>;
  next_guidance?: string[];
  summary?: string;
  last_activity_at?: number | null;
}

export interface GuideV2CourseTemplate {
  id: string;
  title: string;
  course_id?: string;
  course_name?: string;
  description?: string;
  target_learners?: string;
  level?: string;
  suggested_weeks?: number;
  credits?: number;
  estimated_minutes?: number;
  tags?: string[];
  default_goal?: string;
  default_preferences?: string[];
  default_time_budget_minutes?: number;
  learning_outcomes?: string[];
  assessment?: Array<Record<string, unknown>>;
  project_milestones?: Array<Record<string, unknown>>;
  demo_seed?: GuideV2DemoSeedPack;
}

export interface GuideV2DemoSeedPack {
  title?: string;
  scenario?: string;
  persona?: {
    name?: string;
    level?: string;
    goal?: string;
    weak_points?: string[];
    preferences?: string[];
  };
  task_chain?: Array<{
    task_id?: string;
    title?: string;
    stage?: string;
    show?: string;
    resource_type?: string;
    prompt?: string;
    sample_score?: number;
    sample_reflection?: string;
    status?: string;
  }>;
  resource_prompts?: Array<{
    task_id?: string;
    type?: string;
    title?: string;
    prompt?: string;
  }>;
  sample_artifacts?: Array<{
    task_id?: string;
    type?: string;
    title?: string;
    preview?: string;
    demo_action?: string;
    talking_point?: string;
    status?: string;
  }>;
  rehearsal_notes?: string[];
  report_anchor?: {
    score?: number;
    readiness?: string;
    action?: string;
  };
}

export interface GuideV2StudyPlan {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  summary: string;
  horizon?: string;
  daily_time_budget?: number;
  remaining_minutes?: number;
  blocks: Array<{
    id: string;
    index?: number;
    title: string;
    focus?: string;
    status?: string;
    estimated_minutes?: number;
    completed_tasks?: number;
    total_tasks?: number;
    task_ids?: string[];
    tasks?: Array<{
      task_id?: string;
      node_id?: string;
      node_title?: string;
      type?: string;
      title?: string;
      status?: string;
      estimated_minutes?: number;
      success_criteria?: string[];
      artifact_count?: number;
    }>;
    recommended_actions?: string[];
  }>;
  checkpoints: Array<{
    id: string;
    title: string;
    trigger?: string;
    status?: string;
    average_score?: number | null;
    criteria?: string[];
    evidence?: Record<string, unknown>;
  }>;
  current_block?: Record<string, unknown> | null;
  next_checkpoint?: Record<string, unknown> | null;
  effect_assessment?: GuideV2LearningReport["effect_assessment"];
  strategy_adjustments?: string[];
  rules?: string[];
}

export interface GuideV2LearningBehaviorSummary {
  event_count?: number;
  evidence_count?: number;
  resource_count?: number;
  quiz_attempt_count?: number;
  path_adjustment_count?: number;
  profile_update_count?: number;
  last_activity_at?: number;
  average_scored_activity?: number;
  type_counts?: Record<string, number>;
}

export interface GuideV2LearningTimeline {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  summary: GuideV2LearningBehaviorSummary;
  events: GuideV2LearningTimelineEvent[];
  recent_events: GuideV2LearningTimelineEvent[];
  behavior_tags?: string[];
}

export interface GuideV2LearningTimelineEvent {
  id: string;
  type: string;
  label?: string;
  title: string;
  description?: string;
  created_at?: number;
  score?: number | null;
  task_id?: string;
  task_title?: string;
  node_title?: string;
  impact?: string;
  source?: string;
  resource_type?: string;
  mistake_types?: string[];
  inserted_task_ids?: string[];
  skipped_task_ids?: string[];
  feedback_title?: string;
  feedback_summary?: string;
  feedback_tone?: string;
  learning_feedback?: GuideV2LearningFeedback;
}

export interface GuideV2CoachBriefing {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  coach_mode?: string;
  priority_reason?: string;
  mistake_summary?: GuideV2MistakeReview["summary"];
  priority_mistake?: GuideV2MistakeReview["clusters"][number] | null;
  headline: string;
  summary: string;
  focus: {
    task_id?: string;
    task_title?: string;
    task_type?: string;
    node_id?: string;
    node_title?: string;
    estimated_minutes?: number;
    status?: string;
    mastery_score?: number;
    mastery_status?: string;
    success_criteria?: string[];
  };
  next_actions?: string[];
  blockers?: string[];
  evidence_reasons?: string[];
  micro_plan?: Array<{
    step?: number;
    title?: string;
    duration_minutes?: number;
    action_type?: string;
    resource_type?: string;
    target_task_id?: string;
  }>;
  coach_actions?: Array<{
    id?: string;
    action_type?: string;
    label?: string;
    title?: string;
    type?: GuideV2ResourceType;
    resource_type?: string;
    target_task_id?: string;
    target_task_title?: string;
    prompt?: string;
    primary?: boolean;
  }>;
  resource_shortcuts?: GuideV2ResourceRecommendation[];
  behavior_summary?: GuideV2LearningBehaviorSummary;
  feedback_digest?: GuideV2LearningReport["feedback_digest"];
  effect_assessment?: GuideV2LearningReport["effect_assessment"];
  strategy_adjustments?: string[];
  recent_events?: GuideV2LearningTimelineEvent[];
}

export interface GuideV2MistakeReview {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  summary: {
    cluster_count?: number;
    open_cluster_count?: number;
    closed_cluster_count?: number;
    low_score_evidence_count?: number;
    remediation_task_count?: number;
    pending_remediation_count?: number;
    retest_task_count?: number;
    pending_retest_count?: number;
    closed_loop?: boolean;
  };
  clusters: Array<{
    label?: string;
    count?: number;
    source?: string;
    task_ids?: string[];
    task_titles?: string[];
    latest_at?: number;
    latest_reflection?: string;
    average_score?: number | null;
    severity?: string;
    loop_status?: string;
    pending_remediation_task_ids?: string[];
    pending_retest_task_ids?: string[];
    related_remediation_task_ids?: string[];
    related_retest_task_ids?: string[];
    latest_retest_score?: number | null;
    closed_at?: number | null;
    passed_retest_count?: number;
    suggested_action?: string;
  }>;
  remediation_tasks?: GuideV2Task[];
  retest_tasks?: GuideV2Task[];
  retest_plan?: Array<{
    step?: number;
    title?: string;
    action_type?: string;
    task_id?: string;
  }>;
}

export type GuideV2DiagnosticValue = string | number | boolean | string[];

export interface GuideV2DiagnosticQuestion {
  question_id: string;
  type: "single_choice" | "multi_select" | "scale" | string;
  prompt: string;
  options?: Array<{ value: string; label: string }>;
  min?: number;
  max?: number;
  labels?: Record<string, string>;
  node_id?: string;
  node_title?: string;
}

export interface GuideV2Diagnostic {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  status?: string;
  summary: string;
  questions: GuideV2DiagnosticQuestion[];
  last_result?: {
    readiness_score?: number;
    readiness_label?: string;
    weak_points?: string[];
    current_bottleneck?: string;
    bottleneck_label?: string;
    learning_strategy?: Array<{
      phase?: string;
      action?: string;
      resource_type?: string;
      success_check?: string;
    }>;
    recommendations?: string[];
    [key: string]: unknown;
  } | null;
}

export interface GuideV2DiagnosticAnswer {
  question_id: string;
  value: GuideV2DiagnosticValue;
}

export interface GuideV2DiagnosticSubmitResult {
  success?: boolean;
  session_id: string;
  diagnosis: {
    readiness_score?: number;
    readiness_label?: string;
    weak_points?: string[];
    preferred_resource?: string;
    current_bottleneck?: string;
    bottleneck_label?: string;
    learning_strategy?: Array<{
      phase?: string;
      action?: string;
      resource_type?: string;
      success_check?: string;
    }>;
    recommendations?: string[];
    [key: string]: unknown;
  };
  evidence?: Record<string, unknown>;
  adjustments?: GuideV2PlanEvent[];
  session?: GuideV2Session;
}

export interface GuideV2ProfileDialogue {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  status?: string;
  summary: string;
  suggested_prompts: string[];
  last_signals?: Record<string, unknown> | null;
}

export interface GuideV2ProfileDialogueResult {
  success?: boolean;
  session_id: string;
  signals: Record<string, unknown>;
  assistant_reply: string;
  evidence?: Record<string, unknown>;
  adjustments?: GuideV2PlanEvent[];
  session?: GuideV2Session;
}

export interface GuideV2LearningFeedback {
  title?: string;
  summary?: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "brand" | string;
  score_percent?: number | null;
  concept_feedback?: Array<{
    concept?: string;
    score?: number;
    score_percent?: number;
    status?: "stable" | "developing" | "needs_support" | string;
    correct_count?: number;
    total_count?: number;
    wrong_questions?: string[];
    summary?: string;
    next_action?: string;
  }>;
  resource_actions?: Array<{
    id?: string;
    action_type?: string;
    label?: string;
    title?: string;
    resource_type?: GuideV2ResourceType | string;
    target_task_id?: string;
    target_task_title?: string;
    prompt?: string;
    primary?: boolean;
    concept?: string;
    concept_status?: string;
    concept_score_percent?: number;
  }>;
  evidence_quality?: {
    score?: number;
    label?: string;
    strengths?: string[];
    gaps?: string[];
    next_evidence_prompt?: string;
  };
  task_id?: string;
  task_title?: string;
  next_task_id?: string;
  next_task_title?: string;
  adjustment_types?: string[];
  actions?: string[];
  session_status?: string;
}

export interface GuideV2TaskCompletionResult {
  success?: boolean;
  session: GuideV2Session;
  completed_task?: GuideV2Task;
  evidence?: Record<string, unknown>;
  adjustments?: GuideV2PlanEvent[];
  next_task?: GuideV2Task | null;
  learning_feedback?: GuideV2LearningFeedback;
}

export interface GuideV2QuizSubmitResult {
  success?: boolean;
  session_id: string;
  task_id: string;
  artifact_id: string;
  attempt?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  adjustments?: GuideV2PlanEvent[];
  next_task?: GuideV2Task | null;
  learning_feedback?: GuideV2LearningFeedback;
  session?: GuideV2Session;
  question_notebook?: {
    saved?: boolean;
    count?: number;
    session_id?: string;
  };
}

export interface GuideV2Evaluation {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  overall_score: number;
  readiness: string;
  progress: number;
  completed_tasks: number;
  skipped_tasks?: number;
  total_tasks: number;
  path_adjustment_count?: number;
  average_evidence_score: number;
  average_mastery: number;
  mastery_distribution: Record<string, number>;
  resource_counts: Record<string, number>;
  question_count: number;
  evidence_count: number;
  evidence_trend: Array<{
    evidence_id?: string;
    task_id?: string;
    task_title?: string;
    score?: number | null;
    reflection?: string;
    created_at?: number;
  }>;
  node_evaluations: Array<Record<string, unknown>>;
  strengths: string[];
  risk_signals: string[];
  next_actions: string[];
  learner_profile_context?: Record<string, unknown>;
}

export interface GuideV2LearningReport {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  title: string;
  summary: string;
  overview: {
    overall_score?: number;
    readiness?: string;
    progress?: number;
    completed_tasks?: number;
    skipped_tasks?: number;
    total_tasks?: number;
    path_adjustment_count?: number;
    average_evidence_score?: number;
    average_mastery?: number;
  };
  profile?: Record<string, unknown>;
  node_cards: Array<{
    node_id?: string;
    title?: string;
    status?: string;
    mastery_score?: number;
    completed_tasks?: number;
    total_tasks?: number;
    artifact_count?: number;
    difficulty?: string;
    mastery_target?: string;
    suggestion?: string;
  }>;
  resource_summary?: Record<string, number>;
  evidence_summary?: {
    count?: number;
    trend?: Array<Record<string, unknown>>;
    latest_reflection?: string;
  };
  behavior_summary?: GuideV2LearningBehaviorSummary;
  behavior_tags?: string[];
  feedback_digest?: {
    count?: number;
    success_count?: number;
    warning_count?: number;
    brand_count?: number;
    latest?: {
      event_id?: string;
      task_id?: string;
      task_title?: string;
      title?: string;
      summary?: string;
      tone?: string;
      score_percent?: number | null;
      created_at?: number;
      actions?: string[];
    } | null;
    items?: Array<{
      event_id?: string;
      task_id?: string;
      task_title?: string;
      title?: string;
      summary?: string;
      tone?: string;
      score_percent?: number | null;
      created_at?: number;
      actions?: string[];
    }>;
  };
  effect_assessment?: {
    score?: number;
    label?: string;
    summary?: string;
    dimensions?: Array<{
      id?: string;
      label?: string;
      score?: number;
      status?: string;
      evidence?: string;
    }>;
    strategy_adjustments?: string[];
  };
  action_brief?: {
    title?: string;
    summary?: string;
    primary_action?: {
      label?: string;
      detail?: string;
      kind?: string;
      target_task_id?: string;
      resource_type?: GuideV2ResourceType | string;
      prompt?: string;
    };
    secondary_actions?: Array<{
      label?: string;
      detail?: string;
      kind?: string;
      target_task_id?: string;
      resource_type?: GuideV2ResourceType | string;
      prompt?: string;
    }>;
      signals?: Array<{
        label?: string;
        value?: string;
        tone?: "neutral" | "brand" | "success" | "warning" | "danger" | string;
      }>;
      steps?: Array<{
        label?: string;
        detail?: string;
      }>;
    };
  demo_readiness?: {
    score?: number;
    label?: string;
    summary?: string;
    checks?: Array<{
      id?: string;
      label?: string;
      status?: "ready" | "partial" | "missing" | string;
      detail?: string;
    }>;
    next_steps?: string[];
  };
  learner_profile_context?: Record<string, unknown>;
  timeline_events?: GuideV2LearningTimelineEvent[];
  mistake_review?: Pick<GuideV2MistakeReview, "summary" | "clusters" | "retest_plan">;
  interventions?: GuideV2PlanEvent[];
  risks?: string[];
  strengths?: string[];
  next_plan?: string[];
  demo_script?: string[];
  markdown?: string;
}

export interface GuideV2LearningStyle {
  label?: string;
  summary?: string;
  trend?: string;
  demo_talking_point?: string;
  path_effect?: string;
  signals?: Array<{
    label?: string;
    value?: string;
  }>;
}

export interface GuideV2CoursePackage {
  success?: boolean;
  session_id: string;
  generated_at?: number;
  title: string;
  summary: string;
  course_metadata?: Record<string, unknown>;
  capstone_project: {
    title?: string;
    scenario?: string;
    deliverables?: string[];
    steps?: string[];
    focus_nodes?: string[];
    estimated_minutes?: number;
  };
  rubric: Array<{
    criterion?: string;
    weight?: number;
    excellent?: string;
    baseline?: string;
  }>;
  portfolio: Array<{
    artifact_id?: string;
    task_id?: string;
    task_title?: string;
    type?: string;
    capability?: string;
    title?: string;
    status?: string;
    summary?: string;
  }>;
  review_plan: Array<{
    node_id?: string;
    title?: string;
    priority?: string;
    action?: string;
    mastery_score?: number;
  }>;
  learning_style?: GuideV2LearningStyle;
  demo_outline?: string[];
  demo_blueprint?: {
    title?: string;
    duration_minutes?: number;
    summary?: string;
    readiness_label?: string;
    readiness_score?: number;
    learning_style?: GuideV2LearningStyle;
    storyline?: Array<{
      minute?: string;
      title?: string;
      show?: string;
      talking_point?: string;
      requirement?: string;
    }>;
    fallbacks?: string[];
    judge_mapping?: Array<{
      requirement?: string;
      evidence?: string;
    }>;
  };
  demo_fallback_kit?: {
    title?: string;
    summary?: string;
    persona?: {
      name?: string;
      goal?: string;
      level?: string;
      weak_points?: string[];
      preferences?: string[];
      story?: string;
    };
    assets?: Array<{
      type?: string;
      title?: string;
      status?: string;
      show?: string;
      talking_point?: string;
      fallback_prompt?: string;
    }>;
    checklist?: string[];
    fallback_script?: string[];
  };
  demo_seed_pack?: GuideV2DemoSeedPack;
  demo_preflight?: {
    title?: string;
    summary?: string;
    status?: "ready" | "rehearsable" | "needs_attention" | string;
    score?: number;
    ready_count?: number;
    seed_count?: number;
    total_count?: number;
    next_action?: string;
    primary_gap?: {
      id?: string;
      label?: string;
      status?: string;
      evidence?: string;
      action?: string;
    } | null;
    checks?: Array<{
      id?: string;
      label?: string;
      status?: string;
      evidence?: string;
      action?: string;
    }>;
  };
  presentation_outline?: {
    title?: string;
    summary?: string;
    course_name?: string;
    slide_count?: number;
    next_action?: string;
    slides?: Array<{
      slide_no?: number;
      title?: string;
      purpose?: string;
      evidence?: string;
      speaker_note?: string;
    }>;
  };
  competition_submission?: {
    title?: string;
    summary?: string;
    course_name?: string;
    ready_count?: number;
    seed_count?: number;
    total_count?: number;
    next_action?: string;
    checklist?: Array<{
      item?: string;
      status?: "ready" | "seed" | "todo" | string;
      evidence?: string;
      action?: string;
    }>;
  };
  recording_script?: {
    title?: string;
    summary?: string;
    total_minutes?: number;
    next_action?: string;
    segments?: Array<{
      minute?: string;
      screen?: string;
      narration?: string;
      backup?: string;
    }>;
  };
  ai_coding_statement?: {
    title?: string;
    summary?: string;
    course_name?: string;
    usage_scope?: string[];
    human_review?: string[];
    privacy_boundary?: string[];
    evidence?: string[];
    next_action?: string;
  };
  competition_alignment?: {
    title?: string;
    summary?: string;
    course_name?: string;
    coverage_score?: number;
    ready_count?: number;
    seed_count?: number;
    total_count?: number;
    next_action?: string;
    primary_gap?: {
      id?: string;
      requirement?: string;
      status?: "ready" | "seed" | "todo" | string;
      evidence?: string[];
      demo_action?: string;
    } | null;
    requirements?: Array<{
      id?: string;
      requirement?: string;
      status?: "ready" | "seed" | "todo" | string;
      evidence?: string[];
      demo_action?: string;
    }>;
  };
  agent_collaboration_blueprint?: {
    title?: string;
    summary?: string;
    course_name?: string;
    current_task?: string;
    readiness?: {
      label?: string;
      score?: number;
      detail?: string;
    };
    roles?: Array<{
      id?: string;
      name?: string;
      responsibility?: string;
      uses?: string;
      output?: string;
      demo_action?: string;
    }>;
    route?: Array<{
      from?: string;
      to?: string;
      message?: string;
    }>;
    mermaid?: string;
    recording_tip?: string;
    next_action?: string;
  };
  defense_qa?: {
    title?: string;
    summary?: string;
    course_name?: string;
    question_count?: number;
    top_risk?: string;
    next_action?: string;
    questions?: Array<{
      question?: string;
      answer?: string;
      evidence?: string;
      demo_reference?: string;
    }>;
  };
  learning_report?: {
    overall_score?: number;
    readiness?: string;
    progress?: number;
    behavior_summary?: GuideV2LearningBehaviorSummary;
    behavior_tags?: string[];
    recent_timeline_events?: GuideV2LearningTimelineEvent[];
    effect_assessment?: GuideV2LearningReport["effect_assessment"];
    demo_readiness?: GuideV2LearningReport["demo_readiness"];
    mistake_summary?: GuideV2MistakeReview["summary"];
    mistake_clusters?: GuideV2MistakeReview["clusters"];
    risks?: string[];
    next_actions?: string[];
  };
  markdown?: string;
}

export interface GuideV2ResourceRecommendation {
  id: string;
  priority: "high" | "medium" | "low" | string;
  resource_type: GuideV2ResourceType | string;
  capability?: CapabilityId | string;
  title: string;
  reason: string;
  prompt: string;
  target_task_id: string;
  target_task_title?: string;
  target_node_id?: string;
  effect_score?: number;
  effect_label?: string;
}

export interface SparkBotSummary {
  bot_id: string;
  name?: string;
  description?: string;
  running?: boolean;
  model?: string;
  last_reload_error?: string | null;
  persona?: string;
  channels?: Record<string, unknown>;
  auto_start?: boolean;
  tools?: Record<string, unknown>;
  agent?: Record<string, unknown>;
  heartbeat?: Record<string, unknown>;
}

export interface SparkBotRecentItem {
  bot_id: string;
  name?: string;
  running?: boolean;
  last_message?: string;
  updated_at?: string;
}

export interface SparkBotFile {
  filename: string;
  content?: string;
}

export interface SparkBotChannelSchema {
  name: string;
  display_name?: string;
  default_config?: Record<string, unknown>;
  secret_fields?: string[];
  json_schema?: Record<string, unknown>;
}

export interface SparkBotSchemas {
  channels: Record<string, SparkBotChannelSchema>;
  global?: SparkBotChannelSchema;
}

export interface SparkBotSoul {
  id: string;
  name: string;
  content: string;
}

export interface AgentUiConfig {
  icon?: string;
  color?: string;
  label_key?: string;
  [key: string]: unknown;
}

export type AgentConfigMap = Record<string, AgentUiConfig>;

export interface SystemStatus {
  backend?: {
    status: string;
    timestamp?: string;
  };
  llm?: {
    status: string;
    model?: string | null;
    error?: string;
  };
  embeddings?: {
    status: string;
    model?: string | null;
    error?: string;
  };
  search?: {
    status: string;
    provider?: string | null;
    error?: string;
  };
  ocr?: {
    status: string;
    provider?: string | null;
    error?: string;
  };
}

export interface SystemTestResponse {
  success: boolean;
  message: string;
  model?: string | null;
  response_time_ms?: number | null;
  error?: string | null;
}

export interface RuntimeTopology {
  primary_runtime: {
    transport: string;
    manager: string;
    orchestrator: string;
    session_store: string;
    capability_entry: string;
    tool_entry: string;
    [key: string]: string;
  };
  compatibility_routes: Array<{
    router: string;
    mode: string;
  }>;
  isolated_subsystems: Array<{
    router: string;
    mode: string;
  }>;
}

export interface SetupTourStatus {
  active: boolean;
  status: string;
  launch_at?: number | null;
  redirect_at?: number | null;
}

export interface SetupTourReopenResponse {
  message: string;
  command: string;
}

export interface ProviderChoice {
  value: string;
  label: string;
  base_url?: string;
  default_model?: string;
  models?: string[];
  default_dim?: string;
}

export interface ModelItem {
  id: string;
  name: string;
  model: string;
  dimension?: string;
}

export interface EndpointProfile {
  id: string;
  name: string;
  binding?: string;
  provider?: string;
  base_url?: string;
  api_key?: string;
  api_version?: string;
  proxy?: string;
  strategy?: string;
  timeout?: string;
  max_pages?: string;
  dpi?: string;
  min_text_chars?: string;
  extra_headers?: Record<string, string>;
  models?: ModelItem[];
}

export interface ServiceCatalog {
  active_profile_id?: string;
  active_model_id?: string;
  profiles: EndpointProfile[];
}

export interface ModelCatalog {
  version: number;
  services: {
    llm: ServiceCatalog;
    embedding: ServiceCatalog;
    search: ServiceCatalog;
    ocr?: ServiceCatalog;
  };
}

export interface SettingsResponse {
  ui: {
    theme: "light" | "dark" | "glass" | "snow";
    language: "zh" | "en";
    sidebar_description?: string;
    sidebar_nav_order?: Record<string, string[]>;
  };
  catalog: ModelCatalog;
  providers: {
    llm: ProviderChoice[];
    embedding: ProviderChoice[];
    search: ProviderChoice[];
    ocr?: ProviderChoice[];
  };
}

export type UiThemeId = SettingsResponse["ui"]["theme"];
export type UiLanguageId = SettingsResponse["ui"]["language"];

export interface ThemeOption {
  id: UiThemeId;
  name: string;
}

export interface SidebarSettings {
  description: string;
  nav_order: {
    start: string[];
    learnResearch: string[];
    [key: string]: string[];
  };
}
