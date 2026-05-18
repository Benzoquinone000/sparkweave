import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, "..");

const scanRoots = [
  path.join(projectRoot, "src"),
  path.join(projectRoot, "tailwind.config.js"),
];

const checks = [
  {
    pattern: /\brounded-(xl|2xl|3xl|full)\b/g,
    message: "border radius must stay at 8px or below",
  },
  {
    pattern: /\btracking-(tight|tighter|\[[^\]]*-\d[^\]]*\])\b/g,
    message: "letter spacing must stay at 0 and not go negative",
  },
  {
    pattern: /\b(?:bg|text|border|from|via|to)-(?:purple|violet|fuchsia|indigo|orange|brown|stone|beige|cream|sand|tan)-/g,
    message: "avoid off-palette dominant hues; use canvas, teal, blue, red, or neutral status colors",
  },
  {
    pattern: /\b(?:bg-gradient|from-|via-|to-)\b/g,
    message: "avoid decorative gradients in the redesigned workbench",
  },
];

function collectFiles(target) {
  const stats = fs.statSync(target);
  if (stats.isFile()) return [target];
  return fs.readdirSync(target, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(target, entry.name);
    if (entry.isDirectory()) return collectFiles(fullPath);
    if (!/\.(css|js|ts|tsx)$/.test(entry.name)) return [];
    return [fullPath];
  });
}

const files = scanRoots.flatMap((target) => (fs.existsSync(target) ? collectFiles(target) : []));
const violations = [];

for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  for (const check of checks) {
    for (const match of text.matchAll(check.pattern)) {
      const line = text.slice(0, match.index).split(/\r?\n/).length;
      violations.push({
        file: path.relative(projectRoot, file),
        line,
        value: match[0],
        message: check.message,
      });
    }
  }
}

if (violations.length > 0) {
  console.error("[design] SparkWeave visual contract failed:");
  for (const violation of violations) {
    console.error(`- ${violation.file}:${violation.line} ${violation.value} - ${violation.message}`);
  }
  process.exitCode = 1;
} else {
  console.log("[design] SparkWeave visual contract passed.");
}
