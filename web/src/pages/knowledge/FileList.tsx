import { formatBytes } from "./format";

export function FileList({ files }: { files: File[] }) {
  return (
    <div className="dt-event-feed rounded-lg p-3 text-xs leading-5 text-slate-600">
      {files.slice(0, 5).map((file) => (
        <p key={`${file.name}-${file.size}`} className="truncate">
          {file.name} · {formatBytes(file.size)}
        </p>
      ))}
      {files.length > 5 ? <p>还有 {files.length - 5} 个文件</p> : null}
    </div>
  );
}
