const BLOCKED_SVG_TAGS = new Set(["script", "foreignobject", "iframe", "object", "embed", "link", "meta"]);
const URL_ATTRIBUTE_NAMES = new Set(["href", "xlink:href", "src"]);
const DANGEROUS_URL_PATTERN = /^\s*(?:javascript|vbscript|data:)/i;
const DANGEROUS_STYLE_PATTERN = /(?:url\s*\(|expression\s*\(|javascript:|vbscript|data:)/i;

function stripCodeFences(source: string) {
  const trimmed = source.trim();
  const fenced = trimmed.match(/^```[\w-]*\s*([\s\S]*?)\s*```$/);
  return fenced ? fenced[1].trim() : trimmed;
}

export function sanitizeSvgMarkup(svg: string) {
  const trimmed = stripCodeFences(svg).trim();
  if (!/^<svg(?:\s|>)/i.test(trimmed) || typeof DOMParser === "undefined" || typeof XMLSerializer === "undefined") {
    return "";
  }

  const parsed = new DOMParser().parseFromString(trimmed, "image/svg+xml");
  if (parsed.querySelector("parsererror")) {
    return "";
  }

  const root = parsed.documentElement;
  if (root.tagName.toLowerCase() !== "svg") {
    return "";
  }

  for (const element of [root, ...Array.from(root.querySelectorAll("*"))]) {
    if (BLOCKED_SVG_TAGS.has(element.tagName.toLowerCase())) {
      element.remove();
      continue;
    }

    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim();
      if (name.startsWith("on")) {
        element.removeAttribute(attribute.name);
      } else if (URL_ATTRIBUTE_NAMES.has(name) && DANGEROUS_URL_PATTERN.test(value)) {
        element.removeAttribute(attribute.name);
      } else if (name === "style" && DANGEROUS_STYLE_PATTERN.test(value)) {
        element.removeAttribute(attribute.name);
      }
    }
  }

  return new XMLSerializer().serializeToString(root);
}
