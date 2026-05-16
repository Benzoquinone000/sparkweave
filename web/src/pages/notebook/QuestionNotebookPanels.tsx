import { ExternalLink, Loader2, RefreshCw, Save, Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { questionDifficultyLabel } from "@/lib/learningLabels";
import type { QuestionCategory, QuestionNotebookEntry } from "@/lib/types";

export type QuickQuestionDraft = {
  sessionId: string;
  questionId: string;
  question: string;
  correctAnswer: string;
  explanation: string;
  difficulty: string;
};

export function CategoryManager({
  categories,
  renamingCategoryId,
  categoryDraft,
  pending,
  onStartRename,
  onDraft,
  onRename,
  onCancelRename,
  onDelete,
}: {
  categories: QuestionCategory[];
  renamingCategoryId: number | null;
  categoryDraft: string;
  pending: boolean;
  onStartRename: (category: QuestionCategory) => void;
  onDraft: (value: string) => void;
  onRename: (categoryId: number) => Promise<void>;
  onCancelRename: () => void;
  onDelete: (categoryId: number) => void;
}) {
  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {categories.map((category) =>
        renamingCategoryId === category.id ? (
          <form
            key={category.id}
            className="dt-interactive flex items-center gap-2 rounded-lg border border-line bg-white p-2"
            onSubmit={(event) => {
              event.preventDefault();
              void onRename(category.id);
            }}
          >
            <TextInput
              value={categoryDraft}
              onChange={(event) => onDraft(event.target.value)}
              className="h-9 w-36"
              data-testid={`question-category-rename-input-${category.id}`}
            />
            <Button
              tone="primary"
              type="submit"
              className="min-h-9 px-2 text-xs"
              disabled={pending || !categoryDraft.trim()}
              data-testid={`question-category-rename-save-${category.id}`}
            >
              保存
            </Button>
            <Button tone="quiet" className="min-h-9 px-2 text-xs" onClick={onCancelRename}>
              取消
            </Button>
          </form>
        ) : (
          <div key={category.id} className="dt-interactive flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-sm hover:border-brand-purple-300">
            <span className="font-medium text-ink">{category.name}</span>
            <Badge tone="neutral">{category.entry_count ?? 0}</Badge>
            <button
              type="button"
              className="text-slate-500 hover:text-brand-purple"
              onClick={() => onStartRename(category)}
              data-testid={`question-category-rename-${category.id}`}
            >
              改名
            </button>
            <button
              type="button"
              className="text-slate-500 hover:text-brand-red"
              onClick={() => onDelete(category.id)}
              data-testid={`question-category-delete-${category.id}`}
            >
              删除
            </button>
          </div>
        ),
      )}
    </div>
  );
}

export function QuickQuestionPanel({
  value,
  status,
  pending,
  onChange,
  onLookup,
  onSubmit,
}: {
  value: QuickQuestionDraft;
  status: string;
  pending: boolean;
  onChange: (value: QuickQuestionDraft) => void;
  onLookup: () => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const patch = (next: Partial<typeof value>) => onChange({ ...value, ...next });
  return (
    <form className="mt-4 border-t border-line pt-4" onSubmit={onSubmit}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">题目快录</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            如果你从聊天或题目生成结果里复制了记录编号，可以在这里找回或补录单题。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            tone="secondary"
            type="button"
            onClick={onLookup}
            disabled={pending || !value.sessionId.trim() || !value.questionId.trim()}
            data-testid="question-lookup-submit"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            查找
          </Button>
          <Button
            tone="primary"
            type="submit"
            disabled={pending || !value.sessionId.trim() || !value.questionId.trim() || !value.question.trim()}
            data-testid="question-upsert-submit"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            写入题目
          </Button>
        </div>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <FieldShell label="答题记录">
          <TextInput value={value.sessionId} onChange={(event) => patch({ sessionId: event.target.value })} data-testid="question-upsert-session" />
        </FieldShell>
        <FieldShell label="题目编号">
          <TextInput value={value.questionId} onChange={(event) => patch({ questionId: event.target.value })} data-testid="question-upsert-id" />
        </FieldShell>
        <FieldShell label="难度">
          <SelectInput value={value.difficulty} onChange={(event) => patch({ difficulty: event.target.value })} data-testid="question-upsert-difficulty">
            <option value="easy">基础</option>
            <option value="medium">中等</option>
            <option value="hard">挑战</option>
          </SelectInput>
        </FieldShell>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <FieldShell label="题干">
          <TextArea value={value.question} onChange={(event) => patch({ question: event.target.value })} data-testid="question-upsert-question" />
        </FieldShell>
        <div className="grid gap-3">
          <FieldShell label="参考答案">
            <TextInput value={value.correctAnswer} onChange={(event) => patch({ correctAnswer: event.target.value })} data-testid="question-upsert-answer" />
          </FieldShell>
          <FieldShell label="解析">
            <TextArea value={value.explanation} onChange={(event) => patch({ explanation: event.target.value })} data-testid="question-upsert-explanation" />
          </FieldShell>
        </div>
      </div>
      {status ? <p className="mt-3 rounded-lg border border-line bg-white p-3 text-sm text-slate-600">{status}</p> : null}
    </form>
  );
}

export function QuestionCard({
  entry,
  active,
  pending,
  onSelect,
  onToggleBookmark,
  onDelete,
}: {
  entry: QuestionNotebookEntry;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onToggleBookmark: () => Promise<unknown>;
  onDelete: () => void;
}) {
  return (
    <article
      className={`dt-interactive rounded-lg border px-4 py-3 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      data-testid={`question-entry-${entry.id}`}
    >
      <button type="button" className="w-full text-left" onClick={onSelect} data-testid={`question-entry-select-${entry.id}`}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={entry.bookmarked ? "brand" : "neutral"}>{entry.bookmarked ? "已收藏" : "题目"}</Badge>
          <Badge tone={entry.is_correct ? "success" : "warning"}>{entry.is_correct ? "正确" : "待复盘"}</Badge>
          {entry.difficulty ? <Badge tone="neutral">{questionDifficultyLabel(entry.difficulty)}</Badge> : null}
        </div>
        <h3 className="mt-3 line-clamp-2 font-semibold text-ink">{entry.question}</h3>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{entry.explanation || entry.correct_answer || "暂无解析"}</p>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          tone="secondary"
          className="min-h-9 text-xs"
          onClick={() => void onToggleBookmark()}
          disabled={pending}
          data-testid={`question-entry-bookmark-${entry.id}`}
        >
          <Star size={14} />
          {entry.bookmarked ? "取消收藏" : "收藏"}
        </Button>
        <Button
          tone="danger"
          className="min-h-9 text-xs"
          onClick={onDelete}
          disabled={pending}
          data-testid={`question-entry-delete-${entry.id}`}
        >
          <Trash2 size={14} />
          删除
        </Button>
      </div>
    </article>
  );
}

export function QuestionDetail({
  entry,
  categories,
  pending,
  onAddCategory,
  onRemoveCategory,
}: {
  entry?: QuestionNotebookEntry;
  categories: QuestionCategory[];
  pending: boolean;
  onAddCategory: (entryId: number, categoryId: number) => Promise<unknown>;
  onRemoveCategory: (entryId: number, categoryId: number) => Promise<unknown>;
}) {
  const [categoryId, setCategoryId] = useState("");
  if (!entry) {
    return <div className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">选择一道题查看详情。</div>;
  }
  const linkedIds = new Set((entry.categories ?? []).map((item) => item.id));
  return (
    <aside className="rounded-lg border border-line bg-white p-3">
      <Badge tone="brand">题目详情</Badge>
      <h3 className="mt-3 font-semibold text-ink">{entry.question}</h3>
      {entry.options && Object.keys(entry.options).length ? (
        <div className="mt-4 grid gap-2">
          {Object.entries(entry.options).map(([key, value]) => (
            <p key={key} className="rounded-lg bg-canvas p-3 text-sm">
              <span className="font-semibold text-brand-purple">{key}.</span> {value}
            </p>
          ))}
        </div>
      ) : null}
      <div className="mt-4 grid gap-3 text-sm leading-6 text-slate-700">
        <p><span className="font-semibold text-ink">正确答案：</span>{entry.correct_answer || "未记录"}</p>
        <p><span className="font-semibold text-ink">我的答案：</span>{entry.user_answer || "未记录"}</p>
        <p><span className="font-semibold text-ink">解析：</span>{entry.explanation || "暂无解析"}</p>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {entry.session_id ? (
          <Button tone="secondary" className="min-h-9 text-xs" onClick={() => window.location.assign(`/chat/${encodeURIComponent(entry.session_id)}`)}>
            <ExternalLink size={14} />
            原会话
          </Button>
        ) : null}
        {entry.followup_session_id ? (
          <Button
            tone="secondary"
            className="min-h-9 text-xs"
            onClick={() => window.location.assign(`/chat/${encodeURIComponent(entry.followup_session_id || "")}`)}
          >
            <ExternalLink size={14} />
            追问会话
          </Button>
        ) : null}
      </div>
      <div className="mt-5">
        <p className="text-sm font-semibold text-ink">分类</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(entry.categories ?? []).map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => void onRemoveCategory(entry.id, category.id)}
              disabled={pending}
              data-testid={`question-detail-category-remove-${category.id}`}
              className="rounded-md border border-line bg-white px-2 py-1 text-xs text-slate-600 hover:border-red-200 hover:text-brand-red"
            >
              {category.name} ×
            </button>
          ))}
          {!entry.categories?.length ? <span className="text-sm text-slate-500">未分类</span> : null}
        </div>
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <SelectInput
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
            data-testid="question-detail-category-select"
          >
            <option value="">选择分类</option>
            {categories.filter((category) => !linkedIds.has(category.id)).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectInput>
          <Button
            tone="secondary"
            disabled={!categoryId || pending}
            data-testid="question-detail-category-add"
            onClick={async () => {
              await onAddCategory(entry.id, Number(categoryId));
              setCategoryId("");
            }}
          >
            添加
          </Button>
        </div>
      </div>
    </aside>
  );
}
