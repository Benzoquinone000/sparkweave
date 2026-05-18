import type { FormEvent } from "react";
import { motion } from "framer-motion";
import { FolderSync, Link2, Loader2, Unlink } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextInput } from "@/components/ui/Field";
import type { LinkedFolder } from "@/lib/types";

import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function KnowledgeFoldersPanel({
  activeKb,
  folderPath,
  folders,
  linking,
  syncing,
  unlinking,
  onFolderPathChange,
  onLink,
  onSync,
  onUnlink,
}: {
  activeKb: string;
  folderPath: string;
  folders: LinkedFolder[];
  linking: boolean;
  syncing: boolean;
  unlinking: boolean;
  onFolderPathChange: (path: string) => void;
  onLink: (event: FormEvent<HTMLFormElement>) => void;
  onSync: (folderId: string) => void;
  onUnlink: (folderId: string) => void;
}) {
  return (
    <section className={KNOWLEDGE_PANEL_CLASS} data-testid="knowledge-folder-details">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-mint px-3 py-3" data-testid="knowledge-folder-toggle">
        <div>
          <h2 className="text-base font-semibold text-ink">文件夹同步</h2>
          <p className="mt-1 text-sm text-slate-500">链接本地目录，按需同步新增资料。</p>
        </div>
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={onLink}>
          <FieldShell label="本地文件夹路径">
            <TextInput
              value={folderPath}
              onChange={(event) => onFolderPathChange(event.target.value)}
              placeholder="例如 C:\Users\name\Documents\course"
              data-testid="knowledge-folder-path"
            />
          </FieldShell>
          <div className="flex items-end">
            <Button
              tone="secondary"
              type="submit"
              disabled={!activeKb || !folderPath.trim() || linking}
              data-testid="knowledge-folder-link"
            >
              {linking ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
              链接
            </Button>
          </div>
        </form>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {folders.map((folder) => (
            <motion.article
              key={folder.id}
              className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300"
              data-testid={`knowledge-folder-${folder.id}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-ink">{folder.path}</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {folder.file_count} 个文件 · {folder.added_at}
                  </p>
                </div>
                <Badge tone="neutral">{folder.id.slice(0, 8)}</Badge>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  tone="secondary"
                  className="min-h-9 text-xs"
                  onClick={() => onSync(folder.id)}
                  disabled={syncing}
                  data-testid={`knowledge-folder-sync-${folder.id}`}
                >
                  {syncing ? <Loader2 size={14} className="animate-spin" /> : <FolderSync size={14} />}
                  同步
                </Button>
                <Button
                  tone="danger"
                  className="min-h-9 text-xs"
                  data-testid={`knowledge-folder-unlink-${folder.id}`}
                  onClick={() => {
                    if (window.confirm(`解除链接 ${folder.path}？`)) onUnlink(folder.id);
                  }}
                  disabled={unlinking}
                >
                  <Unlink size={14} />
                  解除
                </Button>
              </div>
            </motion.article>
          ))}
        </div>

        {activeKb && !folders.length ? (
          <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
            当前资料库还没有链接文件夹。适合课程资料目录、同步盘目录或挂载卷。
          </p>
        ) : null}
        {!activeKb ? (
          <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
            先选择一个资料库，再链接需要持续同步的本地目录。
          </p>
        ) : null}
      </div>
    </section>
  );
}
