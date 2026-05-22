import { FieldShell, TextArea } from "@/components/ui/Field";

const MAX_RAG_TEST_QUERY_CHARS = 2_000;

const RAG_TEST_QUERY_SUGGESTIONS = [
  {
    label: "概括主题",
    query: "请概括这个资料库最核心的学习主题，并说明来源。",
  },
  {
    label: "提取概念",
    query: "这份资料里最重要的关键概念有哪些？请按重要性排序。",
  },
  {
    label: "学习顺序",
    query: "如果我是第一次学习这份资料，应该先读哪几部分？",
  },
];

export function RagSearchQueryField({
  query,
  onQueryChange,
}: {
  query: string;
  onQueryChange: (value: string) => void;
}) {
  return (
    <FieldShell label="想问资料什么？" hint={`${query.length}/${MAX_RAG_TEST_QUERY_CHARS}`}>
      <TextArea
        value={query}
        maxLength={MAX_RAG_TEST_QUERY_CHARS}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="输入一个真实学习问题，系统会先检查能否找到可靠来源"
        className="min-h-20"
        data-testid="knowledge-rag-test-query"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="text-xs leading-5 text-steel">示例</span>
        {RAG_TEST_QUERY_SUGGESTIONS.map((item) => (
          <button
            key={item.label}
            type="button"
            className="dt-interactive rounded-md border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-purple-300 hover:bg-tint-lavender hover:text-brand-purple"
            onClick={() => onQueryChange(item.query)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </FieldShell>
  );
}
