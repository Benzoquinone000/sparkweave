import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, Tag } from "lucide-react";
import type { FormEvent, Ref } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { QUESTION_LIMITS } from "@/lib/requestLimits";
import type { QuestionCategory, QuestionNotebookEntry } from "@/lib/types";

import {
  CategoryManager,
  QuestionCard,
  QuestionDetail,
  QuickQuestionPanel,
  type QuickQuestionDraft,
} from "./QuestionNotebookPanels";

type QuestionNotebookWorkspaceProps = {
  sectionRef: Ref<HTMLElement>;
  categories: QuestionCategory[];
  entries: QuestionNotebookEntry[];
  activeQuestion?: QuestionNotebookEntry;
  categoryName: string;
  renamingCategoryId: number | null;
  categoryDraft: string;
  quickQuestion: QuickQuestionDraft;
  quickQuestionStatus: string;
  createCategoryPending: boolean;
  manageCategoryPending: boolean;
  entryActionPending: boolean;
  categoryLinkPending: boolean;
  quickQuestionPending: boolean;
  onBack: () => void;
  onCategoryNameChange: (value: string) => void;
  onCreateCategory: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onStartRename: (category: QuestionCategory) => void;
  onCategoryDraft: (value: string) => void;
  onRenameCategory: (categoryId: number) => Promise<void>;
  onCancelRename: () => void;
  onDeleteCategory: (categoryId: number) => void | Promise<unknown>;
  onSelectQuestion: (entryId: number) => void;
  onToggleBookmark: (entry: QuestionNotebookEntry) => void | Promise<unknown>;
  onDeleteQuestion: (entryId: number) => void | Promise<unknown>;
  onAddCategory: (entryId: number, categoryId: number) => Promise<unknown>;
  onRemoveCategory: (entryId: number, categoryId: number) => Promise<unknown>;
  onQuickQuestionChange: (draft: QuickQuestionDraft) => void;
  onQuickQuestionLookup: () => void;
  onQuickQuestionSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
};

export function QuestionNotebookWorkspace({
  sectionRef,
  categories,
  entries,
  activeQuestion,
  categoryName,
  renamingCategoryId,
  categoryDraft,
  quickQuestion,
  quickQuestionStatus,
  createCategoryPending,
  manageCategoryPending,
  entryActionPending,
  categoryLinkPending,
  quickQuestionPending,
  onBack,
  onCategoryNameChange,
  onCreateCategory,
  onStartRename,
  onCategoryDraft,
  onRenameCategory,
  onCancelRename,
  onDeleteCategory,
  onSelectQuestion,
  onToggleBookmark,
  onDeleteQuestion,
  onAddCategory,
  onRemoveCategory,
  onQuickQuestionChange,
  onQuickQuestionLookup,
  onQuickQuestionSubmit,
}: QuestionNotebookWorkspaceProps) {
  return (
    <motion.section
      key="question-notebook"
      ref={sectionRef}
      className="rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={onBack}>
        <ChevronLeft size={14} />
        返回记录本
      </Button>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Badge tone="brand">题目本</Badge>
          <h2 className="mt-3 text-lg font-semibold text-ink">收藏题目与错题复盘</h2>
          <p className="mt-1 text-sm text-slate-500">集中查看题目、答案、解析和分类。</p>
        </div>
        <form className="flex gap-2" onSubmit={onCreateCategory}>
          <TextInput
            value={categoryName}
            onChange={(event) => onCategoryNameChange(event.target.value)}
            maxLength={QUESTION_LIMITS.categoryName}
            placeholder="新分类"
            className="min-w-40"
            data-testid="question-category-create-name"
          />
          <Button
            tone="secondary"
            type="submit"
            disabled={!categoryName.trim() || createCategoryPending}
            data-testid="question-category-create-submit"
          >
            <Tag size={16} />
            添加
          </Button>
        </form>
      </div>

      <CategoryManager
        categories={categories}
        renamingCategoryId={renamingCategoryId}
        categoryDraft={categoryDraft}
        pending={manageCategoryPending}
        onStartRename={onStartRename}
        onDraft={onCategoryDraft}
        onRename={onRenameCategory}
        onCancelRename={onCancelRename}
        onDelete={(categoryId) => {
          if (window.confirm("删除这个分类？")) void onDeleteCategory(categoryId);
        }}
      />

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-3">
          <AnimatePresence initial={false}>
            {entries.slice(0, 12).map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
              >
                <QuestionCard
                  entry={entry}
                  active={activeQuestion?.id === entry.id}
                  pending={entryActionPending}
                  onSelect={() => onSelectQuestion(entry.id)}
                  onToggleBookmark={async () => {
                    await onToggleBookmark(entry);
                  }}
                  onDelete={() => {
                    if (window.confirm("删除这道题？")) void onDeleteQuestion(entry.id);
                  }}
                />
              </motion.div>
            ))}
          </AnimatePresence>
          {!entries.length ? <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">暂无题目记录。</p> : null}
        </div>

        <QuestionDetail
          entry={activeQuestion}
          categories={categories}
          pending={categoryLinkPending}
          onAddCategory={onAddCategory}
          onRemoveCategory={onRemoveCategory}
        />
      </div>

      <section className="mt-5 rounded-lg border border-line bg-canvas p-3">
        <QuickQuestionPanel
          value={quickQuestion}
          status={quickQuestionStatus}
          pending={quickQuestionPending}
          onChange={onQuickQuestionChange}
          onLookup={onQuickQuestionLookup}
          onSubmit={onQuickQuestionSubmit}
        />
      </section>
    </motion.section>
  );
}
