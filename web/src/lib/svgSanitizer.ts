const BLOCKED_SVG_TAGS = new Set(["script", "foreignobject", "iframe", "object", "embed", "link", "meta"]);
const URL_ATTRIBUTE_NAMES = new Set(["href", "xlink:href", "src"]);
const DANGEROUS_URL_PATTERN = /^\s*(?:javascript|vbscript|data:)/i;
const DANGEROUS_STYLE_PATTERN = /(?:url\s*\(|expression\s*\(|javascript:|vbscript|data:)/i;

function stripCodeFences(source: string) {
  const trimmed = source.trim();
  const fenced = trimmed.match(/^```[\w-]*\s*([\s\S]*?)\s*```$/);
  return fenced ? fenced[1].trim() : trimmed;
}

function extractSvgFragment(source: string) {
  const trimmed = stripCodeFences(source).trim();
  const start = trimmed.search(/<svg(?:\s|>)/i);
  if (start < 0) return "";
  const end = trimmed.toLowerCase().lastIndexOf("</svg>");
  if (end < start) return trimmed.slice(start).trim();
  return trimmed.slice(start, end + "</svg>".length).trim();
}

function localTagName(element: Element) {
  return (element.localName || element.tagName || "").toLowerCase();
}

function isSvgRoot(element: Element | null) {
  return Boolean(element && localTagName(element) === "svg");
}

function parseSvgRoot(svg: string) {
  const xmlParsed = new DOMParser().parseFromString(svg, "image/svg+xml");
  if (!xmlParsed.querySelector("parsererror") && isSvgRoot(xmlParsed.documentElement)) {
    return xmlParsed.documentElement;
  }

  const htmlParsed = new DOMParser().parseFromString(svg, "text/html");
  const htmlRoot = htmlParsed.querySelector("svg");
  return isSvgRoot(htmlRoot) ? htmlRoot : null;
}

export function sanitizeSvgMarkup(svg: string) {
  const fragment = extractSvgFragment(svg);
  if (!fragment || typeof DOMParser === "undefined" || typeof XMLSerializer === "undefined") {
    return "";
  }

  const root = parseSvgRoot(fragment);
  if (!root) {
    return "";
  }

  for (const element of [root, ...Array.from(root.querySelectorAll("*"))]) {
    if (BLOCKED_SVG_TAGS.has(localTagName(element))) {
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
