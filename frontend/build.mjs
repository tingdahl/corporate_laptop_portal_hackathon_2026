import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "esbuild";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEMPLATE_DIR = path.join(__dirname, "templates");
const PUBLIC_DIR = path.join(__dirname, "public");
const ASSETS_DIR = path.join(PUBLIC_DIR, "assets");

const PAGES = [
  { name: "index", entryPoint: path.join(__dirname, "index.ts"), template: path.join(TEMPLATE_DIR, "index.html") },
  { name: "login", entryPoint: path.join(__dirname, "login.ts"), template: path.join(TEMPLATE_DIR, "login.html") },
  {
    name: "onboarding",
    entryPoint: path.join(__dirname, "onboarding.ts"),
    template: path.join(TEMPLATE_DIR, "onboarding.html"),
  },
  {
    name: "new_quote",
    entryPoint: path.join(__dirname, "new_quote.ts"),
    template: path.join(TEMPLATE_DIR, "new_quote.html"),
  },
  {
    name: "employees",
    entryPoint: path.join(__dirname, "employees.ts"),
    template: path.join(TEMPLATE_DIR, "employees.html"),
  },
];

function sri(content) {
  const hash = createHash("sha256").update(content).digest("base64");
  return `sha256-${hash}`;
}

async function cleanGeneratedAssets() {
  await rm(ASSETS_DIR, { recursive: true, force: true });
  await mkdir(ASSETS_DIR, { recursive: true });
}

function normalizeRelPath(fromPath, toPath) {
  return path.relative(fromPath, toPath).split(path.sep).join("/");
}

async function buildBundles() {
  const entryPoints = {};
  for (const page of PAGES) {
    entryPoints[page.name] = page.entryPoint;
  }

  const result = await build({
    entryPoints,
    outdir: ASSETS_DIR,
    bundle: true,
    format: "esm",
    platform: "browser",
    target: ["es2022"],
    minify: true,
    sourcemap: false,
    splitting: true,
    metafile: true,
    write: true,
    entryNames: "[name]-[hash]",
    chunkNames: "chunks/[name]-[hash]",
    assetNames: "assets/[name]-[hash]",
    logLevel: "info",
  });

  if (!result.metafile) {
    throw new Error("Build failed to produce a metafile.");
  }
  return result.metafile;
}

async function collectEntryAssets(metafile) {
  const entries = new Map();
  for (const page of PAGES) {
    entries.set(path.resolve(page.entryPoint), { js: null, css: null });
  }

  for (const [outputPath, outputMeta] of Object.entries(metafile.outputs)) {
    if (!outputMeta.entryPoint) {
      continue;
    }

    const entryKey = path.resolve(outputMeta.entryPoint);
    const target = entries.get(entryKey);
    if (!target) {
      continue;
    }

    const ext = path.extname(outputPath);
    if (ext === ".js") {
      target.js = outputPath;
    } else if (ext === ".css") {
      target.css = outputPath;
    }
  }

  return entries;
}

async function renderHtml(page, assets) {
  if (!assets?.js) {
    throw new Error(`Missing JS bundle for page '${page.name}'.`);
  }

  const template = await readFile(page.template, "utf8");

  const jsAbsolutePath = path.resolve(assets.js);
  const jsPublicPath = `/${normalizeRelPath(PUBLIC_DIR, jsAbsolutePath)}`;
  const jsIntegrity = sri(await readFile(jsAbsolutePath));
  const scriptTag = `<script src="${jsPublicPath}" integrity="${jsIntegrity}" type="module" crossorigin="anonymous"></script>`;

  let stylesTag = "";
  if (assets.css) {
    const cssAbsolutePath = path.resolve(assets.css);
    const cssPublicPath = `/${normalizeRelPath(PUBLIC_DIR, cssAbsolutePath)}`;
    const cssIntegrity = sri(await readFile(cssAbsolutePath));
    stylesTag = `<link rel="stylesheet" href="${cssPublicPath}" integrity="${cssIntegrity}" crossorigin="anonymous">`;
  }

  const html = template.replace("{{styles}}", stylesTag).replace("{{script}}", scriptTag);
  await writeFile(path.join(PUBLIC_DIR, `${page.name}.html`), html, "utf8");
}

async function main() {
  await cleanGeneratedAssets();
  const metafile = await buildBundles();
  const entryAssets = await collectEntryAssets(metafile);

  for (const page of PAGES) {
    const assets = entryAssets.get(path.resolve(page.entryPoint));
    await renderHtml(page, assets);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
