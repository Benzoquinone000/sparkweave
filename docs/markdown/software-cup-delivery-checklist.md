# 软件杯交付检查清单

SparkWeave 面向 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”。作品把高校课程学习拆成一条可核验的主线：学生先说明目标和卡点，系统形成学习画像；随后围绕课程资料生成学习路径、图解、练习和讲解资源；学习结果再回到记录和画像里，影响下一步推荐。

本文用于评委快速核对赛题要求、演示入口和提交材料。

## 答辩时可以突出什么

SparkWeave 最值得讲的 idea 是“把教育智能体从功能展示变成学习闭环”。系统不要求学生先理解 RAG、Agent 或模型配置，而是把这些能力藏在学习动作后面：继续学习时读画像，问资料时走 Agentic RAG 查证据，卡住时由编排器自动调度图解、练习、动画或语音讲解，完成任务后把结果写回记录。课程助教还能通过通道配置接入 QQ，让系统从网页扩展到学生真实会用的入口。

答辩时可以把技术主张说得更具体一点：`RagSupportService` 会对复杂问题生成多路查询计划，并用质量门判断证据够不够；`LearningCapabilityRouter` 会在规则和可选 LLM intent coordinator 之间做调度，而不是让学生挑 Agent；`LearnerEvidenceService` 用追加式账本保存学习行为，`ProfileContextInjector` 再把精简画像提示送回下一轮问答；`QQChannel` 让课程助教可以从 Web 管理页延伸到 QQ 私聊、群聊和提醒。

| 创新点 | 现场怎么证明 | 代码依据 |
| --- | --- | --- |
| 课程主线是真实的 | 选择“深度学习”，展示 14 周课程、任务和课件资料 | `data/course_templates/deep_learning/`、`scripts/check_course_templates.py` |
| 画像是带证据更新的 | 提交反馈或练习后，到记录页看薄弱点和下一步建议 | `learner_evidence.py`、`learner_profile.py`、`profile_context.py` |
| Agentic RAG 有质量门 | 在资料页或问问题页展开来源，展示问题拆分、来源合并、覆盖度判断和弱证据补强 | `rag_support/service.py`、`agentic_quality.py`、`agentic_repair.py` |
| 多智能体会自动调度 | 同一个问题可以触发检索、图解、出题、动画或语音讲解，不要求学生手动挑 Agent | `runtime/capability_router.py`、`graphs/chat.py` |
| 资源生成服务路径规划 | 生成的图解、练习和讲解不是孤立素材，会回到当前任务里 | `guide_v2.py` 的任务、资源和证据写回接口 |
| 课程助教能进 QQ | 课程助教页展示长期助教、提醒任务和通道配置 | `sparkbot_support/channels.py`、`sparkbot.py` |
| 讯飞工具不是摆设 | 设置页能看到讯飞模型、Embedding、搜索、OCR、图片理解和语音入口，相关能力进入资料和辅导流程 | `iflytek_spark_ws.py`、`embedding_support/adapters/iflytek_spark.py`、`iflytek_formula.py`、`iflytek_vision.py`、`speech.py` |

## 赛题要求对应关系

| 赛题要求 | SparkWeave 中的呈现 | 评审时可查看 |
| --- | --- | --- |
| 对话式学习画像自主构建 | 学生目标、偏好、薄弱点、练习反馈和学习记录沉淀为画像；系统给出下一步建议，并保留证据来源 | [记录与画像页](../../web/screenshots-memory.png)、[学习画像与记忆设计](./learner-profile-memory-design.md) |
| 多智能体协同的资源生成 | 对话协调器根据任务自动调度解题、出题、检索、图解、动画、研究和课程助教等能力；复杂资料问题先进入 Agentic RAG 证据链 | [问问题页](../../web/screenshots-chat.png)、[智能体编排设计](./agent-orchestration-design.md)、[RAG 系统设计](./rag-system-design.md) |
| 个性化学习路径规划和资源推送 | 学习页按目标、时间预算和薄弱点生成当前任务、学习材料和提交反馈入口 | [学习页](../../web/screenshots-guide.png) |
| 智能辅导 | 资料问答、图解、练习生成、公开视频推荐、图片/公式理解、语音讲解和可接 QQ 的课程助教用于即时答疑 | [问问题页](../../web/screenshots-chat.png)、[资料页](../../web/screenshots-knowledge.png)、[课程助教页](../../web/screenshots-agents.png) |
| 学习效果评估 | 练习结果、资源使用、反思和记录进入学习报告，生成薄弱点和下一步学习处方 | [记录与画像页](../../web/screenshots-memory.png) |
| 科大讯飞相关工具 | 支持星火模型、MaaS Coding、星火 Embedding、ONE SEARCH、OCR、公式识别、图片理解、TTS、ASR、语音评测和星辰工作流 | [设置页](../../web/screenshots-settings.png)、[科大讯飞工具链说明](./iflytek-toolchain-guide.md)、[配置指南](./configuration-guide.md) |
| 至少一门完整高校专业课程 | 仓库内提供完整课程模板，主课程为“深度学习”，另接入“智能机器人系统” | `data/course_templates/deep_learning/deep_learning_foundations.json`、`data/course_templates/intelligent_robot_systems/intelligent_robot_systems.json`、[完整课程样例说明](./course-template-guide.md) |

## 展示主线

7 分钟视频建议按学生视角展开，不按技术模块堆功能。

| 时间 | 页面 | 内容 |
| --- | --- | --- |
| 0:00-0:50 | 学习 | 选择课程目标，展示当前任务和学习路径 |
| 0:50-1:40 | 记录 / 画像 | 展示系统如何根据目标、薄弱点和偏好给出下一步建议 |
| 1:40-2:40 | 资料 | 打开课程资料库，展示资料入库状态和可引用资料 |
| 2:40-3:50 | 问问题 | 围绕资料提问，展示 Agentic RAG 的问题拆分、证据来源和智能辅导回答 |
| 3:50-5:00 | 问问题 / 学习 | 生成图解、练习、语音讲解或短视频讲解素材，体现智能体自动调度 |
| 5:00-6:00 | 记录 / 画像 | 提交练习或反馈，展示学习效果评估和下一步处方 |
| 6:00-7:00 | 设置 / 课程助教 | 展示讯飞工具链配置、课程助教、QQ 通道和提交材料完整性 |

这条路线的重点是证明“学习行为会改变系统下一步动作”，而不是只停留在一次问答。

## 完整课程

推荐主课程使用：

| 项目 | 内容 |
| --- | --- |
| 模板文件 | `data/course_templates/deep_learning/deep_learning_foundations.json` |
| 课程名称 | 深度学习 |
| 课程定位 | 面向高校 AI / 计算机相关专业的 14 周、3 学分课程 |
| 课件来源 | `ppts/深度学习/` |
| RAG 资料库 | `data/knowledge_bases/深度学习/raw/`，由 `scripts/sync_course_materials_to_kb.py` 从课程模板同步 |
| 课程主线 | 绪论、前馈神经网络、CNN、图像检索、多模态、RNN、注意力、Transformer、大模型应用、强化学习、无监督学习、生成模型 |
| 适合使用原因 | 课程本身足够完整，又自然需要图解、资料证据、练习反馈、路径规划和学习评估 |

课程的周次、节点、任务和考核方式见 [完整课程样例说明](./course-template-guide.md)。

仓库还提供 `data/course_templates/intelligent_robot_systems/intelligent_robot_systems.json`，对应 `ppts/智能机器人系统/` 下的 11 章课件。视频主线建议仍用深度学习，机器人课程可作为答辩时的补充验证。

同步课程资料库时运行：

```powershell
python scripts/sync_course_materials_to_kb.py --stage-only
```

如果要现场演示资料问答命中课件来源，需要在 Docker Compose、Milvus 和 Embedding 可用后重建索引：

```powershell
python scripts/sync_course_materials_to_kb.py --index
```

## 科大讯飞工具链

| 讯飞能力 | 系统落点 | 学习价值 |
| --- | --- | --- |
| 星火大模型 | 模型配置入口 | 对话式辅导、资源生成、学习路径解释 |
| MaaS Coding / Astron Code | 模型配置入口 | 工程化实现、代码智能体和工具编排 |
| 星火 Embedding | 向量模型配置入口 | 课程资料向量化和资料问答 |
| ONE SEARCH | 搜索服务配置入口 | 公开资料、公开视频和外部材料补充 |
| OCR for LLM | 文档和图片解析 | 扫描讲义、图片资料入库 |
| 公式识别 | `iflytek_formula_ocr` | 数学题图、手写公式进入解题和辅导链路 |
| 图片理解 | `iflytek_image_understanding` | 板书、实验图、截图先被解释，再进入答疑 |
| TTS | 语音讲解 | 为短视频讲解或音频辅导生成旁白 |
| ASR | 语音输入 | 学生口述问题、课堂录音转文字 |
| 语音评测 | 学习效果证据 | 口语或朗读类任务可写入评估记录 |
| 星辰工作流 | `iflytek_workflow` | 接入已发布工作流，生成课程资源或诊断报告 |

## 提交材料清单

| 提交物 | SparkWeave 对应内容 |
| --- | --- |
| 演示 PPT | 建议围绕“画像 -> 资源生成 -> 路径规划 -> 智能辅导 -> 效果评估”五段组织 |
| 可运行源码 | `sparkweave/`、`sparkweave_cli/`、`web/`、`scripts/`、`requirements/`、`docker-compose.yml` |
| 数据集 / 课程数据 | `data/course_templates/` 中的完整课程模板 |
| 模型部署配置 | `.env.example`、`docker-compose.yml`、`Dockerfile`、设置页模型与工具配置 |
| 演示视频 | 7 分钟内按上方演示主线录制 |
| 配套文档 | 根目录 README、`docs/` 下各设计说明和[提交包整理说明](./submission-package-guide.md) |
| AI Coding 说明 | 见 [AI Coding 使用说明](./ai-coding-disclosure.md)，说明辅助范围、人工复核、密钥和隐私边界 |

## 边界说明

- 展示环境不提交真实 API Key、账号凭证和用户私有资料。
- 真实讯飞服务需要在本地环境中配置密钥；未配置密钥时，相关工具会返回明确标记的替代结果，避免把展示材料误认为真实服务调用。
- 画像和学习效果评估基于学习行为证据，不等同于正式教育测量模型。
- 多智能体协作以当前项目内可运行能力为准，第三方插件能力不作为核心评分依赖。
