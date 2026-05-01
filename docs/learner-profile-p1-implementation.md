# 学习画像 P1 只读统一画像实施方案

本文档把学习画像第一阶段开发收敛成可以直接施工的技术方案。P1 的目标不是一次性实现完整画像闭环，而是先建立一个稳定、可解释、只读的统一画像聚合层。

## P1 目标

P1 只做三件事：

1. 从现有数据源聚合画像，不改变现有数据写入链路。
2. 提供统一画像 API，供前端画像中心读取。
3. 用前端只读页面让用户看懂“当前目标、卡点、掌握度、学习偏好、下一步建议”。

P1 不做：

- 不自动写入证据账本。
- 不修改 Guide V2、Notebook、SessionStore 的现有 schema。
- 不做用户校准写入。
- 不让画像反向驱动导学路线。
- 不引入复杂知识追踪模型。

这些能力放到 P2/P3/P4。

## 实施边界

| 项目 | P1 决策 |
| --- | --- |
| 存储 | 新增 `data/user/learner_profile/profile.json` 作为缓存；P1 可由 refresh 生成 |
| 证据 | 不写正式 `evidence.jsonl`，但 API 返回 synthesized evidence preview |
| 来源 | Memory、Guide V2 learner memory、Guide V2 sessions、Question Notebook、Notebook |
| API | `/api/v1/learner-profile` |
| 前端入口 | 优先升级 `/memory` 为“学习画像中心”，高级 Markdown 记忆作为子页/高级入口 |
| 兼容 | 原 `/api/v1/memory`、`/api/v1/guide/v2/learner-memory` 全部保留 |
| 风险控制 | 画像声明全部带 `source`、`confidence`、`why`，避免黑箱 |

## 后端文件计划

```text
sparkweave/services/learner_profile.py
sparkweave/api/routers/learner_profile.py
tests/services/test_learner_profile.py
tests/api/test_learner_profile_router.py
```

路由挂载：

```python
from sparkweave.api.routers import learner_profile

app.include_router(
    learner_profile.router,
    prefix="/api/v1/learner-profile",
    tags=["learner-profile"],
)
```

## P1 数据结构

### LearnerProfileSource

```python
@dataclass
class LearnerProfileSource:
    source: str
    source_id: str = ""
    label: str = ""
    confidence: float = 0.5
    updated_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### LearnerProfileClaim

```python
@dataclass
class LearnerProfileClaim:
    id: str
    type: str
    label: str
    value: Any
    confidence: float = 0.5
    why: str = ""
    sources: list[LearnerProfileSource] = field(default_factory=list)
    updated_at: float | None = None
```

### LearnerMastery

```python
@dataclass
class LearnerMastery:
    node_id: str
    title: str
    score: float
    status: str
    confidence: float
    trend: str = "flat"
    evidence_count: int = 0
    why: str = ""
    sources: list[LearnerProfileSource] = field(default_factory=list)
```

### LearnerWeakPoint

```python
@dataclass
class LearnerWeakPoint:
    label: str
    severity: str
    confidence: float
    related_nodes: list[str] = field(default_factory=list)
    suggested_action: str = ""
    why: str = ""
    sources: list[LearnerProfileSource] = field(default_factory=list)
```

### LearnerProfileSnapshot

```python
@dataclass
class LearnerProfileSnapshot:
    learner_id: str = "local-user"
    version: int = 1
    generated_at: float = field(default_factory=time.time)
    confidence: float = 0.0
    current: dict[str, Any] = field(default_factory=dict)
    stable: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    mastery: list[LearnerMastery] = field(default_factory=list)
    weak_points: list[LearnerWeakPoint] = field(default_factory=list)
    strengths: list[LearnerProfileClaim] = field(default_factory=list)
    recommendations: list[LearnerProfileClaim] = field(default_factory=list)
    evidence_preview: list[dict[str, Any]] = field(default_factory=list)
    source_summary: dict[str, Any] = field(default_factory=dict)
    freshness: dict[str, Any] = field(default_factory=dict)
```

## API 合约

### GET `/api/v1/learner-profile`

返回当前画像。如果缓存不存在，自动执行一次只读 refresh。

响应：

```json
{
  "success": true,
  "profile": {
    "learner_id": "local-user",
    "version": 1,
    "generated_at": 1760000000.0,
    "confidence": 0.62,
    "current": {
      "active_goal": "理解梯度下降",
      "active_course_id": "ml_foundations",
      "readiness": "beginner",
      "time_budget_minutes": 30,
      "next_best_action": "先完成当前补基任务，再提交一次练习。"
    },
    "stable": {
      "long_term_goals": ["机器学习基础"],
      "course_focus": ["ml_foundations"]
    },
    "preferences": {
      "resource_types": ["visual", "quiz"],
      "explanation_style": ["step_by_step"],
      "language": "zh"
    },
    "mastery": [],
    "weak_points": [],
    "strengths": [],
    "recommendations": [],
    "evidence_preview": [],
    "source_summary": {
      "memory": 1,
      "guide_v2": 2,
      "question_notebook": 8,
      "notebook": 3
    },
    "freshness": {
      "latest_activity_at": 1760000000.0,
      "stale": false
    }
  }
}
```

### POST `/api/v1/learner-profile/refresh`

重新从现有来源聚合画像并写入 `profile.json`。

请求：

```json
{
  "include_sources": ["memory", "guide_v2", "question_notebook", "notebook"],
  "force": true
}
```

响应同 `GET`，额外带：

```json
{
  "refreshed": true,
  "warnings": []
}
```

### GET `/api/v1/learner-profile/evidence-preview`

P1 只读证据预览，不等于正式 P2 证据账本。

查询参数：

```text
source?
limit=30
```

响应：

```json
{
  "success": true,
  "items": [
    {
      "id": "preview-guide-task-...",
      "source": "guide_v2",
      "verb": "completed",
      "label": "完成任务：梯度下降直观理解",
      "score": 0.8,
      "created_at": 1760000000.0,
      "why": "来自 Guide V2 task evidence"
    }
  ],
  "total": 1
}
```

## 聚合规则

### Memory 聚合

来源：

- `data/memory/PROFILE.md`
- `data/memory/SUMMARY.md`

P1 不用 LLM 解析，只做轻量启发式：

- 包含 `目标`、`goal`、`当前重点` 的行进入 `stable.long_term_goals` 或 `current.active_goal` 候选。
- 包含 `偏好`、`喜欢`、`图解`、`视频`、`练习` 的行进入 `preferences` 候选。
- 置信度：手动 Memory 默认 `0.75`，但如果内容过短降到 `0.45`。

### Guide V2 learner memory 聚合

来源：

- `GuideV2Manager.build_learner_memory(refresh=True)`

映射：

| learner memory 字段 | 画像字段 |
| --- | --- |
| `recent_goals[0].goal` | `current.active_goal` |
| `suggested_level` | `current.readiness` |
| `preferred_time_budget_minutes` | `current.time_budget_minutes` |
| `top_preferences` | `preferences.resource_types` |
| `persistent_weak_points` | `weak_points` |
| `common_mistakes` | `weak_points` |
| `strengths` | `strengths` |
| `next_guidance` | `recommendations` |

### Guide V2 session 聚合

来源：

- `data/user/workspace/guide/v2/session_*.json`

规则：

- 读取最近 10 个 session。
- 最新 session 的 `goal` 优先作为 `current.active_goal`。
- `profile.level` 作为 readiness 候选。
- `profile.preferences` 合并到 resource/explanation preferences。
- `profile.weak_points` 进入 weak_points，置信度 `0.55`。
- `mastery` 转换为 LearnerMastery：
  - score 使用原 score。
  - status 直接映射。
  - confidence = `min(0.9, 0.35 + evidence_count * 0.12)`。
  - why 从 node title、score、evidence_count 合成。
- `evidence` 转为 evidence_preview。

### Question Notebook 聚合

来源：

- `SQLiteSessionStore.list_notebook_entries(limit=200)`

规则：

- 统计总题数、正确题数、正确率。
- 按 `question_type` 统计正确率。
- `is_correct=false` 的题目：
  - 如果有关联 categories，category 名作为 weak point。
  - 否则使用 question_type 作为 weak point。
- bookmarked 的题目不一定代表薄弱点，只代表用户认为重要。
- 整体正确率映射 readiness：
  - `>= 0.85` -> advanced candidate
  - `0.65-0.85` -> intermediate candidate
  - `< 0.65` -> beginner candidate

### Notebook 聚合

来源：

- `NotebookManager.list_notebooks()`
- `NotebookManager.get_notebook(id)`

规则：

- 读取最近 5 个 notebook，每个最多 10 条 record。
- `record.type`、`title`、`summary` 用于 evidence_preview。
- `guided_learning`、`question`、`solve` 类型优先级更高。
- 保存频繁的 record type 可作为资源偏好弱信号。
- 不读取完整 `output` 进入画像，避免上下文污染和隐私风险。

## 冲突处理

### active_goal

优先级：

1. 最近 Guide V2 session goal。
2. Guide V2 learner memory recent goals。
3. Memory SUMMARY 当前重点。
4. Notebook 最近 guided_learning record title。

### readiness

优先级：

1. 最近 Guide V2 diagnostic/result。
2. Guide V2 profile.level。
3. Question Notebook 正确率。
4. Memory 中人工描述。

如果来源冲突，返回：

```json
{
  "readiness": "beginner",
  "readiness_conflict": true,
  "why": "导学前测显示 beginner，但题目本整体正确率接近 intermediate，建议继续用当前任务校准。"
}
```

### preferences

合并去重，不做强覆盖。用户手动 Memory 优先于行为弱信号。

## 前端 P1 页面结构

建议改造 `/memory`，默认显示画像中心。

页面层级：

```text
学习画像
  顶部：当前目标 + 下一步建议
  左侧：画像导航
    总览
    掌握度
    卡点
    证据
    高级记忆
  右侧：当前子页
```

### 总览页

只展示：

- 当前目标。
- 当前水平。
- Top 3 卡点。
- 偏好资源。
- 下一步建议。

### 掌握度页

- 知识点列表。
- score/status/trend/confidence。
- “为什么这样判断”摘要。

### 卡点页

- weak_points 列表。
- severity、related_nodes、suggested_action、why。

### 证据页

- evidence_preview。
- 默认只显示用户友好的 label、source、score、时间。

### 高级记忆页

- 复用原 MemoryPage 的 SUMMARY/PROFILE 编辑能力。
- 文案改为“高级记忆”，避免主体验像开发工具。

## TypeScript 类型草案

```ts
export interface LearnerProfileSource {
  source: string;
  source_id?: string;
  label?: string;
  confidence?: number;
  updated_at?: number | null;
  metadata?: Record<string, unknown>;
}

export interface LearnerProfileClaim {
  id: string;
  type: string;
  label: string;
  value: unknown;
  confidence?: number;
  why?: string;
  sources?: LearnerProfileSource[];
  updated_at?: number | null;
}

export interface LearnerMastery {
  node_id: string;
  title: string;
  score: number;
  status: string;
  confidence: number;
  trend?: string;
  evidence_count?: number;
  why?: string;
  sources?: LearnerProfileSource[];
}

export interface LearnerWeakPoint {
  label: string;
  severity: string;
  confidence: number;
  related_nodes?: string[];
  suggested_action?: string;
  why?: string;
  sources?: LearnerProfileSource[];
}

export interface LearnerProfileSnapshot {
  learner_id: string;
  version: number;
  generated_at: number;
  confidence: number;
  current: Record<string, unknown>;
  stable: Record<string, unknown>;
  preferences: Record<string, unknown>;
  mastery: LearnerMastery[];
  weak_points: LearnerWeakPoint[];
  strengths: LearnerProfileClaim[];
  recommendations: LearnerProfileClaim[];
  evidence_preview: LearnerEvidencePreview[];
  source_summary: Record<string, unknown>;
  freshness: Record<string, unknown>;
}
```

## 测试计划

### 服务层

文件：`tests/services/test_learner_profile.py`

用例：

1. 空数据目录返回空画像，不抛异常。
2. Memory 中的目标和偏好能进入画像。
3. Guide V2 session mastery 能进入 `mastery`。
4. Guide V2 learner memory weak points 能进入 `weak_points`。
5. Question Notebook 错题能生成 weak point。
6. Notebook 最近记录能生成 evidence_preview。
7. 损坏的 session JSON 被跳过，并产生 warning。

### API

文件：`tests/api/test_learner_profile_router.py`

用例：

1. `GET /api/v1/learner-profile` 返回 `success=true`。
2. `POST /refresh` 生成缓存。
3. `GET /evidence-preview` 支持 limit。
4. 没有本地数据时前端可用字段完整。

### 前端

建议：

1. `npm run build`。
2. 画像中心空状态。
3. mock 已有画像时，总览、掌握度、卡点、证据页都可渲染。
4. 高级记忆仍能保存 SUMMARY/PROFILE。

## 开发顺序

1. 后端 dataclass 和 store。
2. 聚合 Memory。
3. 聚合 Guide V2 learner memory 和 session。
4. 聚合 Question Notebook。
5. 聚合 Notebook。
6. API router。
7. 后端测试。
8. 前端类型和 API hook。
9. `/memory` 画像中心改造。
10. 前端构建验证。

## P1 完成标准

- 打开画像中心时，用户能看到当前学习目标、卡点、偏好、掌握度和下一步建议。
- 画像结论有来源和 why。
- 旧 Memory Markdown 编辑仍可用。
- 不影响 Guide V2、Notebook、Question Notebook、Chat 的现有功能。
- 文档、测试和前端入口同步完成。
