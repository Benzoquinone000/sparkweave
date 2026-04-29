export type CapabilityId =
  | "chat"
  | "deep_solve"
  | "deep_question"
  | "deep_research"
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
