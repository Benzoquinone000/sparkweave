import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Brain,
  GraduationCap,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

const PROJECT_POINTS = [
  {
    title: "个性化学习主线",
    detail: "从课程目标、学习画像、前测诊断到路径规划，学生一进入系统就知道下一步做什么。",
    icon: GraduationCap,
  },
  {
    title: "Agentic RAG 证据链",
    detail: "课件和资料进入知识库后，问答会组织检索、重排和引用来源，方便评委现场核验。",
    icon: BookOpen,
  },
  {
    title: "学习画像与效果评估",
    detail: "练习、反馈、资源使用记录会回写画像，薄弱点和推荐任务随学习过程持续更新。",
    icon: Brain,
  },
  {
    title: "课程助教可接外部入口",
    detail: "助教支持定时任务、工作区技能和 QQ 等消息入口，适合演示自动跟进学习任务。",
    icon: Bot,
  },
];

const QUICK_LINKS = [
  { to: "/guide", label: "进入主页面", detail: "从学习页开始完整演示", icon: ArrowRight, primary: true },
  { to: "/knowledge", label: "资料库", detail: "查看 RAG 证据链", icon: BookOpen },
  { to: "/agents", label: "课程助教", detail: "演示 QQ 与定时任务", icon: Bot },
];

export function HomePage() {
  return (
    <main className="h-full overflow-y-auto bg-canvas text-ink">
      <header className="mx-auto flex max-w-[1180px] items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line bg-white shadow-sm">
            <img src="/logo-ver2.png" alt="" className="h-7 w-7 object-contain" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">SparkWeave</p>
            <p className="truncate text-xs text-steel">个性化学习多智能体系统</p>
          </div>
        </div>
        <Link
          to="/guide"
          className="dt-interactive inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-ink bg-ink px-3.5 text-sm font-medium text-white shadow-[rgba(15,23,42,0.12)_0_1px_2px]"
        >
          进入主页面
          <ArrowRight size={16} />
        </Link>
      </header>

      <section className="relative min-h-[72vh] overflow-hidden border-y border-line bg-white">
        <img
          src="/screenshots-guide.png"
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-top opacity-20"
        />
        <div className="absolute inset-0 bg-white/82" />
        <div className="relative mx-auto grid min-h-[72vh] max-w-[1180px] gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)] lg:items-center">
          <div className="max-w-3xl">
            <p className="inline-flex rounded-md border border-line bg-canvas px-2.5 py-1 text-xs font-semibold text-steel">
              软件杯 A3 赛题作品
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-tight text-ink sm:text-5xl">
              基于大模型的个性化资源生成与学习多智能体系统
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-slate-600">
              SparkWeave 面向高校课程学习，把学习画像、个性化路径、资料证据链、多模态资源和课程助教放进同一条学习流程里。这里是项目入口，点击后进入完整工作台。
            </p>
            <div className="mt-7 flex flex-wrap gap-2.5">
              <Link
                to="/guide"
                className="dt-interactive inline-flex min-h-11 items-center gap-2 rounded-lg border border-ink bg-ink px-4 text-sm font-semibold text-white shadow-[rgba(15,23,42,0.12)_0_1px_2px]"
              >
                <Sparkles size={17} />
                进入主页面
              </Link>
              <Link
                to="/knowledge"
                className="dt-interactive inline-flex min-h-11 items-center gap-2 rounded-lg border border-line bg-white/80 px-4 text-sm font-semibold text-ink hover:bg-white"
              >
                <MessageSquareText size={17} />
                查看资料问答
              </Link>
            </div>
          </div>

          <div className="rounded-lg border border-line bg-white p-2 shadow-panel">
            <img
              src="/screenshots-guide.png"
              alt="SparkWeave 学习主页面"
              className="aspect-[16/10] w-full rounded-md object-cover object-top"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-[1180px] gap-3 px-4 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-3 sm:grid-cols-2">
          {PROJECT_POINTS.map((item) => (
            <article key={item.title} className="rounded-lg border border-line bg-white p-4">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-canvas text-charcoal">
                <item.icon size={18} />
              </span>
              <h2 className="mt-4 text-base font-semibold text-ink">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
            </article>
          ))}
        </div>

        <aside className="rounded-lg border border-line bg-white p-4">
          <p className="text-xs font-semibold text-steel">快速跳转</p>
          <div className="mt-3 space-y-2">
            {QUICK_LINKS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`dt-interactive flex min-h-16 items-center gap-3 rounded-lg border p-3 ${
                  item.primary ? "border-ink bg-ink text-white" : "border-line bg-canvas text-ink hover:bg-white"
                }`}
              >
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${item.primary ? "bg-white/14" : "bg-white"}`}>
                  <item.icon size={17} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{item.label}</span>
                  <span className={`mt-1 block text-xs ${item.primary ? "text-white/74" : "text-steel"}`}>{item.detail}</span>
                </span>
                <ArrowRight size={16} className="shrink-0" />
              </Link>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}
