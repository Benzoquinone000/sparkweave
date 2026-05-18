import { useRef, useState, type ChangeEvent, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

export function FieldShell({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium leading-5 text-charcoal">{label}</span>
      {hint ? <span className="ml-2 text-xs leading-5 text-steel">{hint}</span> : null}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

const controlClass =
  "w-full min-h-10 rounded-lg border border-line-strong bg-white px-3 py-1.5 text-sm leading-[1.45] text-ink outline-none transition placeholder:text-stone file:mr-2 file:rounded-md file:border file:border-line file:bg-surface file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-charcoal hover:border-charcoal focus:border-brand-purple focus:ring-2 focus:ring-[#e6e0f5]";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${controlClass} ${props.className ?? ""}`} {...props} />;
}

type FileInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "className"> & {
  buttonLabel?: string;
  emptyLabel?: string;
  className?: string;
};

export function FileInput({
  buttonLabel = "选择文件",
  emptyLabel = "未选择文件",
  className = "",
  multiple,
  onChange,
  ...props
}: FileInputProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [label, setLabel] = useState(emptyLabel);
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.currentTarget.files ?? []);
    if (!files.length) setLabel(emptyLabel);
    else if (files.length === 1) setLabel(files[0]?.name ?? emptyLabel);
    else setLabel(`已选择 ${files.length} 个文件`);
    onChange?.(event);
  };

  return (
    <div className={`flex min-h-10 w-full items-center gap-2.5 rounded-lg border border-line-strong bg-white px-2.5 py-1.5 text-sm transition hover:border-charcoal focus-within:border-brand-purple focus-within:ring-2 focus-within:ring-[#e6e0f5] ${className}`}>
      <input {...props} ref={inputRef} type="file" multiple={multiple} onChange={handleChange} className="sr-only" />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="dt-interactive shrink-0 rounded-md border border-line bg-tint-lavender px-2.5 py-1 text-xs font-medium text-brand-purple hover:border-brand-purple-300"
      >
        {buttonLabel}
      </button>
      <span className="min-w-0 flex-1 truncate text-steel">{label}</span>
    </div>
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${controlClass} min-h-24 resize-y leading-5 ${props.className ?? ""}`} {...props} />;
}

export function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${controlClass} ${props.className ?? ""}`} {...props} />;
}
