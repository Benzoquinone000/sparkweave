import katex from "katex";
import { Children, Fragment, isValidElement, useEffect, useId, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownRendererProps = {
  children: string;
  className?: string;
};

type ContentPart =
  | { type: "markdown"; value: string; key: string }
  | { type: "display_math"; value: string; key: string };

const fencedBlockPattern = /(```[\s\S]*?```|~~~[\s\S]*?~~~)/g;
const displayMathPattern = /\$\$([\s\S]*?)\$\$/g;
const inlineMathPattern = /\$([^$\n]+?)\$/g;
const latexCommandPattern =
  /\\(?:begin|end|frac|dfrac|tfrac|sqrt|lim|sum|prod|int|sin|cos|tan|cot|sec|csc|log|ln|exp|to|infty|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|phi|omega|left|right|cdot|times|leq|geq|neq|approx)\b/;
const mermaidStartPattern =
  /^(?:graph\s+(?:TB|BT|RL|LR|TD)|flowchart\s+(?:TB|BT|RL|LR|TD)|sequenceDiagram|classDiagram(?:-v2)?|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie(?:\s+title)?|gitGraph|mindmap|timeline)\b/;
const mermaidLinePattern =
  /^(?:graph\b|flowchart\b|sequenceDiagram\b|classDiagram\b|stateDiagram\b|erDiagram\b|journey\b|gantt\b|pie\b|gitGraph\b|mindmap\b|timeline\b|style\b|classDef\b|class\b|linkStyle\b|click\b|subgraph\b|end\b|title\b|section\b|participant\b|actor\b|activate\b|deactivate\b|note\b|loop\b|alt\b|else\b|opt\b|par\b|and\b|rect\b|critical\b|break\b|%%|[A-Za-z0-9_:-]+.*(?:-->|---|-.->|==>|--|::=|\[|\]|\(|\)|\{|\}))/;

let mermaidConfigured = false;

const markdownComponents: Components = {
  pre({ children, ...props }) {
    const childArray = Children.toArray(children);
    if (childArray.length === 1 && isValidElement(childArray[0]) && childArray[0].type === MermaidDiagram) {
      return <>{children}</>;
    }
    return <pre {...props}>{children}</pre>;
  },
  code({ className, children, ...props }) {
    const language = /language-(\w+)/.exec(className || "")?.[1]?.toLowerCase();
    const code = String(children).replace(/\n$/, "");
    if (language === "mermaid") {
      return <MermaidDiagram code={code} />;
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  p({ children, ...props }) {
    return <p {...props}>{renderInlineMath(children)}</p>;
  },
  li({ children, ...props }) {
    return <li {...props}>{renderInlineMath(children)}</li>;
  },
  td({ children, ...props }) {
    return <td {...props}>{renderInlineMath(children)}</td>;
  },
  th({ children, ...props }) {
    return <th {...props}>{renderInlineMath(children)}</th>;
  },
};

export function MarkdownRenderer({ children, className }: MarkdownRendererProps) {
  const parts = splitContentParts(normalizeMermaidMarkdown(normalizeMathMarkdown(children)));
  return (
    <div className={className}>
      {parts.map((part) =>
        part.type === "display_math" ? (
          <KatexFormula key={part.key} expression={part.value} displayMode />
        ) : (
          <ReactMarkdown key={part.key} remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {part.value}
          </ReactMarkdown>
        ),
      )}
    </div>
  );
}

function MermaidDiagram({ code }: { code: string }) {
  const reactId = useId();
  const renderId = useMemo(() => `markdown-mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`, [reactId]);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      setLoading(true);
      setError(null);
      setSvg("");
      try {
        const runtime = await import("mermaid");
        const mermaid = runtime.default;
        ensureMermaidConfigured(mermaid);
        const rendered = await mermaid.render(renderId, code.trim());
        if (!cancelled) {
          setSvg(rendered.svg);
          setLoading(false);
        }
      } catch (renderError) {
        if (!cancelled) {
          setError(renderError instanceof Error ? renderError.message : String(renderError));
          setLoading(false);
        }
      }
    }

    void renderDiagram();
    return () => {
      cancelled = true;
    };
  }, [code, renderId]);

  if (loading) {
    return (
      <div className="my-3 rounded-lg border border-line bg-canvas p-4 text-sm text-slate-500">
        正在渲染图示...
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-700">
        <p className="font-semibold">Mermaid 图示渲染失败</p>
        <p className="mt-1 break-words">{error}</p>
        <pre className="mt-3 overflow-x-auto rounded-md bg-white p-3 text-xs text-slate-700">
          <code>{code}</code>
        </pre>
      </div>
    );
  }

  return (
    <div
      className="my-3 overflow-x-auto rounded-lg border border-line bg-white p-3"
      data-testid="markdown-mermaid"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function ensureMermaidConfigured(mermaid: typeof import("mermaid")["default"]) {
  if (mermaidConfigured) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    themeVariables: {
      primaryColor: "#F7FAFC",
      primaryBorderColor: "#0F766E",
      primaryTextColor: "#111827",
      lineColor: "#2563EB",
      fontFamily: "Inter, ui-sans-serif, system-ui",
    },
  });
  mermaidConfigured = true;
}

function KatexFormula({ expression, displayMode }: { expression: string; displayMode: boolean }) {
  let html = "";
  try {
    html = katex.renderToString(expression, {
      displayMode,
      strict: false,
      throwOnError: false,
    });
  } catch {
    return <code className="katex-error">{expression}</code>;
  }
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function splitContentParts(content: string) {
  const parts: ContentPart[] = [];
  content.split(fencedBlockPattern).forEach((segment, segmentIndex) => {
    if (!segment) return;
    if (segment.startsWith("```") || segment.startsWith("~~~")) {
      parts.push({ type: "markdown", value: segment, key: `fence-${segmentIndex}` });
      return;
    }

    let cursor = 0;
    let match: RegExpExecArray | null;
    displayMathPattern.lastIndex = 0;
    while ((match = displayMathPattern.exec(segment))) {
      const before = segment.slice(cursor, match.index);
      if (before) parts.push({ type: "markdown", value: before, key: `md-${segmentIndex}-${cursor}` });
      const expression = match[1].trim();
      parts.push(
        shouldTreatDisplayMathAsText(expression)
          ? { type: "markdown", value: expression, key: `md-math-${segmentIndex}-${match.index}` }
          : { type: "display_math", value: expression, key: `math-${segmentIndex}-${match.index}` },
      );
      cursor = match.index + match[0].length;
    }

    const after = segment.slice(cursor);
    if (after) parts.push({ type: "markdown", value: after, key: `md-${segmentIndex}-${cursor}` });
  });
  return parts;
}

function renderInlineMath(children: ReactNode): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child === "string") return renderInlineMathString(child);
    return child;
  });
}

function renderInlineMathString(content: string): ReactNode {
  const parts: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  inlineMathPattern.lastIndex = 0;

  while ((match = inlineMathPattern.exec(content))) {
    const expression = match[1].trim();
    const before = content.slice(cursor, match.index);
    if (before) parts.push(before);
    parts.push(
      shouldRenderInlineMath(expression) ? (
        <KatexFormula key={`inline-${match.index}`} expression={expression} displayMode={false} />
      ) : (
        match[0]
      ),
    );
    cursor = match.index + match[0].length;
  }

  const after = content.slice(cursor);
  if (after) parts.push(after);
  return parts.length ? <Fragment>{parts}</Fragment> : content;
}

function shouldRenderInlineMath(expression: string) {
  if (!expression) return false;
  if (latexCommandPattern.test(expression)) return true;
  return /^[A-Za-z0-9+\-*/=<>()[\]{},._^\\\s]+$/.test(expression) && /[A-Za-z\\_^=<>]/.test(expression);
}

function shouldTreatDisplayMathAsText(expression: string) {
  return /[\u4e00-\u9fff]/.test(expression) && expression.includes("$");
}

function normalizeMathMarkdown(content: string) {
  if (!content) return "";
  return content
    .split(fencedBlockPattern)
    .map((part) => {
      if (part.startsWith("```") || part.startsWith("~~~")) return part;
      return normalizeMathSegment(part);
    })
    .join("");
}

function normalizeMermaidMarkdown(content: string) {
  if (!content) return "";
  return content
    .split(fencedBlockPattern)
    .map((part) => {
      if (part.startsWith("```") || part.startsWith("~~~")) return part;
      return wrapBareMermaidBlocks(part);
    })
    .join("");
}

function wrapBareMermaidBlocks(content: string) {
  const lines = content.split("\n");
  const output: string[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!isMermaidStartLine(line)) {
      output.push(line);
      index += 1;
      continue;
    }

    const block: string[] = [line];
    index += 1;
    while (index < lines.length && isLikelyMermaidLine(lines[index])) {
      block.push(lines[index]);
      index += 1;
    }

    output.push("", "```mermaid", block.join("\n"), "```", "");
  }

  return output.join("\n");
}

function isMermaidStartLine(line: string) {
  return mermaidStartPattern.test(line.trim());
}

function isLikelyMermaidLine(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^#{1,6}\s/.test(trimmed) || /^[-*+]\s/.test(trimmed) || /^\d+[.)]\s/.test(trimmed)) return false;
  return mermaidLinePattern.test(trimmed);
}

function normalizeMathSegment(content: string) {
  const withDollarDelimiters = content
    .replace(/(?<!\\)\\\[([\s\S]*?)(?<!\\)\\\]/g, (_match, formula: string) => `$$${formula}$$`)
    .replace(/(?<!\\)\\\(([\s\S]*?)(?<!\\)\\\)/g, (_match, formula: string) => `$${formula}$`);

  return normalizeBareMathLines(normalizeMalformedMath(withDollarDelimiters));
}

function normalizeMalformedMath(content: string) {
  return content
    .replace(
      /\$\$\s*\\begin\{([a-zA-Z*]+)\}\s*\$\$([\s\S]*?)\$\$\s*\\end\{\1\}\s*\$\$(\s*\\tag\{[^}]+\})?/g,
      (_match, environment: string, body: string, tag: string = "") => {
        const normalizedBody = body
          .replace(/\$\$/g, "")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .join("\n");
        return `$$\\begin{${environment}}\n${normalizedBody}\n\\end{${environment}}${tag.trim() ? ` ${tag.trim()}` : ""}$$`;
      },
    )
    .replace(/\$\$([^\n]*[\u4e00-\u9fff][^\n]*)\$\$/g, (_match, text: string) => text)
    .replace(/\$\$([\s\S]*?)\$\$\s*(\\tag\{[^}]+\})/g, (_match, formula: string, tag: string) => {
      const trimmed = formula.trim();
      return trimmed ? `$$${trimmed} ${tag}$$` : _match;
    });
}

function normalizeBareMathLines(content: string) {
  let cursor = 0;
  let normalized = "";
  let match: RegExpExecArray | null;
  displayMathPattern.lastIndex = 0;

  while ((match = displayMathPattern.exec(content))) {
    normalized += normalizeBareMathTextLines(content.slice(cursor, match.index));
    normalized += match[0];
    cursor = match.index + match[0].length;
  }

  normalized += normalizeBareMathTextLines(content.slice(cursor));
  return normalized;
}

function normalizeBareMathTextLines(content: string) {
  return content
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      if (!shouldWrapBareMathLine(trimmed)) return line;
      const prefix = line.slice(0, line.indexOf(trimmed));
      const suffix = line.slice(line.indexOf(trimmed) + trimmed.length);
      return `${prefix}$$${trimmed}$$${suffix}`;
    })
    .join("\n");
}

function shouldWrapBareMathLine(line: string) {
  if (!line) return false;
  if (line.startsWith("$") || line.startsWith("|") || line.startsWith(">")) return false;
  if (/^#{1,6}\s/.test(line) || /^[-*+]\s/.test(line) || /^\d+[.)]\s/.test(line)) return false;
  if (line.includes("`")) return false;
  if (!latexCommandPattern.test(line)) return false;
  return /[=<>+\-*/^_{}]/.test(line);
}
