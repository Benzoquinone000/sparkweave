import { Eye, Loader2, Search } from "lucide-react";

import { Button } from "@/components/ui/Button";
import type { RagSearchTestResult } from "@/lib/types";

export function RagSearchFormActions({
  query,
  result,
  running,
  onShowLastResult,
}: {
  query: string;
  result: RagSearchTestResult | null;
  running: boolean;
  onShowLastResult: () => void;
}) {
  return (
    <>
      <Button tone="primary" type="submit" disabled={!query.trim() || running} data-testid="knowledge-rag-test-submit">
        {running ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
        运行检索测试
      </Button>
      {result ? (
        <Button tone="secondary" type="button" onClick={onShowLastResult} data-testid="knowledge-rag-test-last-result">
          <Eye size={16} />
          查看上次结果
        </Button>
      ) : null}
    </>
  );
}
