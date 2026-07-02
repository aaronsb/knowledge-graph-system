#!/usr/bin/env node
/**
 * Render the interactive Entity-Relationship diagram from schema.dbml.
 *
 * Source of truth: docs/reference/schema.dbml (emitted by
 * generate-schema-docs.py from the SQL DDL). This script turns that DBML into
 * a self-contained interactive HTML page — no database, no system Graphviz:
 * @softwaretechnik/dbml-renderer produces the Graphviz `dot`, and the bundled
 * @aduh95/viz.js (Graphviz compiled to WebAssembly) lays it out to SVG. We
 * inject `pack` so the ~60 mostly-disconnected tables tile into a compact,
 * near-square block instead of one tall vertical strip, then wrap the SVG in a
 * viewer with pan, zoom, table search, and click-to-highlight relationships.
 *
 * Runs in CI with nothing but Node (see .github/workflows/docs.yml). The
 * output page is copied verbatim into the mkdocs site and embedded (via iframe)
 * by docs/reference/schema.md.
 *
 * Run directly or via `make docs-schema`.
 *
 * Output: docs/reference/schema-erd.html
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
// Both deps are CommonJS; load them through require from this package's
// node_modules so the script works regardless of the caller's cwd.
const { run } = require("@softwaretechnik/dbml-renderer");
const vizRenderStringSync = require("@aduh95/viz.js/sync");

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(SCRIPT_DIR, "..", "..");
const DBML_FILE = resolve(PROJECT_ROOT, "docs", "reference", "schema.dbml");
const OUTPUT_FILE = resolve(PROJECT_ROOT, "docs", "reference", "schema-erd.html");

// The two theme-sensitive colors baked into the dbml-renderer 1.0.31 SVG (cell
// fill, ink for text/borders/edges). The viewer recolors these per theme; if a
// renderer bump changes the palette, prepareSvg() asserts they still appear so
// the mismatch fails loudly instead of rendering unreadably in dark mode.
const BAKED_CELL = "#e7e2dd";
const BAKED_INK = "#29235c";

/**
 * Schema → header fill, read back from the DBML's own `headercolor:` settings
 * so the legend can never drift from the colors generate-schema-docs.py baked
 * into the diagram (single source of truth: the .dbml).
 */
function schemaColors(dbml) {
  const re = /Table\s+"([^"]+)"\."[^"]+"\s+\[headercolor:\s*(#[0-9a-fA-F]{6})\]/g;
  const map = {};
  let m;
  while ((m = re.exec(dbml)) !== null) {
    if (!(m[1] in map)) map[m[1]] = m[2];
  }
  return map;
}

/** Turn schema.dbml into a packed, near-square Graphviz SVG string. */
function renderSvg(dbml) {
  const dot = run(dbml, "dot");
  // Component packing: lay out each connected piece, then tile them into a
  // grid (array_c4 = row-major, 4 columns) so disconnected tables don't stack
  // into a strip. Modest separations keep the packed block dense.
  const packed = dot.replace(
    "rankdir=LR;",
    'rankdir=LR;\n  pack=true;\n  packmode="array_c4";\n  ranksep=0.6;\n  nodesep=0.4;'
  );
  if (packed === dot) {
    throw new Error(
      "pack injection failed: 'rankdir=LR;' not found in dbml-renderer dot " +
        "output — the renderer's format likely changed. Update renderSvg()."
    );
  }
  return vizRenderStringSync(packed, { engine: "dot", format: "svg" });
}

/**
 * Prepare the Graphviz SVG for embedding: drop the fixed pt width/height so it
 * scales to its container, and tag it with an id the viewer script targets.
 * The viewBox (which carries the true coordinate extent) is preserved.
 */
function prepareSvg(svg) {
  // The viewer's dark theme recolors these two baked colors via CSS. If a
  // renderer upgrade changes the palette they'd silently stop matching and dark
  // mode would render unreadably, so fail the build instead.
  for (const color of [BAKED_CELL, BAKED_INK]) {
    if (!svg.includes(color)) {
      throw new Error(
        `expected baked color ${color} not found in the rendered SVG — the ` +
          "dbml-renderer palette changed; update BAKED_* and the viewer CSS."
      );
    }
  }
  const viewBox = (svg.match(/viewBox="([^"]+)"/) || [])[1] || "0 0 1000 1000";
  const inner = svg.slice(svg.indexOf("<svg"));
  const openTagEnd = inner.indexOf(">") + 1;
  const body = inner.slice(openTagEnd);
  const open =
    `<svg id="erd" xmlns="http://www.w3.org/2000/svg" ` +
    `xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="${viewBox}" ` +
    `preserveAspectRatio="xMidYMid meet">`;
  return { svg: open + body, viewBox };
}

/** Build the standalone interactive HTML page. */
function buildHtml(svg, viewBox, colors) {
  const legend = Object.entries(colors)
    .map(
      ([name, color]) =>
        `<span class="chip"><i style="background:${color}"></i>${name}</span>`
    )
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph — Schema ER Diagram</title>
<style>
  /* --erd-cell / --erd-ink recolor the two theme-sensitive fills baked into
     the Graphviz SVG (light beige cells, navy ink for text/borders/edges).
     Schema header fills and their white text work in both modes, so they stay
     fixed. The attribute-selector rules further down apply these vars. */
  :root {
    --bg: #ffffff; --fg: #1a2233; --panel: #f4f5f7; --border: #d0d5dd;
    --muted: #667085; --accent: #7c3aed; --dim: 0.12;
    --erd-cell: #e7e2dd; --erd-ink: #29235c;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0f1419; --fg: #e6e9ee; --panel: #1a222c; --border: #2c3745;
            --muted: #93a0b4; --dim: 0.08;
            --erd-cell: #212a36; --erd-ink: #cfd8e6; }
  }
  html.dark {
    --bg: #0f1419; --fg: #e6e9ee; --panel: #1a222c; --border: #2c3745;
    --muted: #93a0b4; --dim: 0.08;
    --erd-cell: #212a36; --erd-ink: #cfd8e6;
  }
  html.light {
    --bg: #ffffff; --fg: #1a2233; --panel: #f4f5f7; --border: #d0d5dd;
    --muted: #667085; --dim: 0.12;
    --erd-cell: #e7e2dd; --erd-ink: #29235c;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); color: var(--fg);
    font: 14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  #stage { position: fixed; inset: 0; overflow: hidden; cursor: grab; }
  #stage.grabbing { cursor: grabbing; }
  #erd { width: 100%; height: 100%; display: block; touch-action: none; }
  #erd .node, #erd .edge { transition: opacity 0.15s ease; }
  /* Recolor the two theme-sensitive baked colors to the active theme. A CSS
     fill/stroke property overrides the SVG presentation attribute, and the
     attribute selector targets exactly those elements. Schema header fills
     (#7c3aed etc.) and white header text are intentionally left alone. */
  #erd [fill="${BAKED_CELL}"] { fill: var(--erd-cell); }
  #erd [fill="${BAKED_INK}"] { fill: var(--erd-ink); }
  #erd [stroke="${BAKED_INK}"] { stroke: var(--erd-ink); }
  #erd.focusing .node.dim, #erd.focusing .edge.dim { opacity: var(--dim); }
  #erd .node.hit > * { outline: none; }
  .toolbar {
    position: fixed; top: 12px; left: 12px; right: 12px; display: flex;
    gap: 8px; align-items: center; flex-wrap: wrap; z-index: 10;
    pointer-events: none;
  }
  .toolbar > * { pointer-events: auto; }
  .group {
    display: flex; gap: 4px; align-items: center; background: var(--panel);
    border: 1px solid var(--border); border-radius: 10px; padding: 4px 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
  }
  button {
    font: inherit; color: var(--fg); background: transparent; border: 0;
    border-radius: 7px; padding: 6px 10px; cursor: pointer; white-space: nowrap;
  }
  button:hover { background: var(--border); }
  input[type=search] {
    font: inherit; color: var(--fg); background: var(--bg);
    border: 1px solid var(--border); border-radius: 7px; padding: 6px 10px;
    width: 190px; outline: none;
  }
  input[type=search]:focus { border-color: var(--accent); }
  .legend { gap: 12px; }
  .chip { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }
  .chip i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .hint {
    position: fixed; bottom: 10px; left: 12px; color: var(--muted);
    font-size: 12px; z-index: 10; background: var(--panel);
    border: 1px solid var(--border); border-radius: 8px; padding: 4px 9px;
  }
  #count { color: var(--muted); font-size: 12px; padding: 0 4px; }
  #matches {
    position: absolute; top: 40px; left: 0; background: var(--panel);
    border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
    min-width: 220px; max-height: 260px; overflow-y: auto; display: none;
  }
  #matches div { padding: 6px 10px; cursor: pointer; }
  #matches div:hover, #matches div.active { background: var(--border); }
  .searchwrap { position: relative; }
</style>
</head>
<body>
<div id="stage">
${svg}
</div>

<div class="toolbar">
  <div class="group searchwrap">
    <input id="search" type="search" placeholder="Find a table…" autocomplete="off" spellcheck="false">
    <div id="matches"></div>
  </div>
  <div class="group">
    <button id="fit" title="Fit to screen">Fit</button>
    <button id="zin" title="Zoom in">+</button>
    <button id="zout" title="Zoom out">−</button>
    <button id="reset" title="Clear highlight">Clear</button>
    <span id="count"></span>
  </div>
  <div class="group legend">${legend}</div>
  <div class="group">
    <button id="theme" title="Toggle light/dark">◐</button>
  </div>
</div>
<div class="hint">Drag to pan · scroll to zoom · click a table to trace its relationships</div>

<script>
(function () {
  "use strict";
  var svg = document.getElementById("erd");
  var stage = document.getElementById("stage");
  var vb = "${viewBox}".split(/\\s+/).map(Number); // x y w h
  var full = { x: vb[0], y: vb[1], w: vb[2], h: vb[3] };
  var view = { x: full.x, y: full.y, w: full.w, h: full.h };

  function apply() {
    svg.setAttribute("viewBox", view.x + " " + view.y + " " + view.w + " " + view.h);
  }
  function fit() { view = { x: full.x, y: full.y, w: full.w, h: full.h }; apply(); }
  apply();

  // ---- pan ----
  var panning = false, sx = 0, sy = 0;
  stage.addEventListener("pointerdown", function (e) {
    if (e.target.closest("g.node")) return; // let clicks select tables
    panning = true; sx = e.clientX; sy = e.clientY;
    stage.classList.add("grabbing"); stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener("pointermove", function (e) {
    if (!panning) return;
    var r = stage.getBoundingClientRect();
    view.x -= (e.clientX - sx) * (view.w / r.width);
    view.y -= (e.clientY - sy) * (view.h / r.height);
    sx = e.clientX; sy = e.clientY; apply();
  });
  function endPan() { panning = false; stage.classList.remove("grabbing"); }
  stage.addEventListener("pointerup", endPan);
  stage.addEventListener("pointercancel", endPan);

  // ---- zoom (toward cursor) ----
  function zoomAt(cx, cy, factor) {
    var r = stage.getBoundingClientRect();
    var px = view.x + ((cx - r.left) / r.width) * view.w;
    var py = view.y + ((cy - r.top) / r.height) * view.h;
    var nw = Math.min(full.w * 4, Math.max(full.w / 400, view.w * factor));
    var nh = nw * (view.h / view.w);
    view.x = px - ((cx - r.left) / r.width) * nw;
    view.y = py - ((cy - r.top) / r.height) * nh;
    view.w = nw; view.h = nh; apply();
  }
  stage.addEventListener("wheel", function (e) {
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY > 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });
  document.getElementById("zin").onclick = function () {
    var r = stage.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1 / 1.3);
  };
  document.getElementById("zout").onclick = function () {
    var r = stage.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1.3);
  };
  document.getElementById("fit").onclick = fit;

  // ---- build adjacency from the SVG ----
  var nodes = {};   // id -> <g>
  Array.prototype.forEach.call(svg.querySelectorAll("g.node"), function (g) {
    if (g.id) nodes[g.id] = g;
  });
  var edges = [];   // { g, a, b }
  Array.prototype.forEach.call(svg.querySelectorAll("g.edge"), function (g) {
    var t = g.querySelector("title");
    if (!t) return;
    var m = t.textContent.split("->");
    if (m.length !== 2) return;
    var a = m[0].split(":")[0].trim();
    var b = m[1].split(":")[0].trim();
    edges.push({ g: g, a: a, b: b });
  });
  var neighbors = {};
  edges.forEach(function (e) {
    (neighbors[e.a] = neighbors[e.a] || {})[e.b] = true;
    (neighbors[e.b] = neighbors[e.b] || {})[e.a] = true;
  });

  var countEl = document.getElementById("count");
  function clearFocus() {
    svg.classList.remove("focusing");
    Object.keys(nodes).forEach(function (id) { nodes[id].classList.remove("dim", "hit"); });
    edges.forEach(function (e) { e.g.classList.remove("dim"); });
    countEl.textContent = "";
  }
  function focus(id) {
    if (!nodes[id]) return;
    var keep = {}; keep[id] = true;
    Object.keys(neighbors[id] || {}).forEach(function (n) { keep[n] = true; });
    svg.classList.add("focusing");
    Object.keys(nodes).forEach(function (nid) {
      nodes[nid].classList.toggle("dim", !keep[nid]);
      nodes[nid].classList.toggle("hit", nid === id);
    });
    var deg = 0;
    edges.forEach(function (e) {
      var on = e.a === id || e.b === id;
      e.g.classList.toggle("dim", !on);
      if (on) deg++;
    });
    countEl.textContent = id.replace(/^[^.]+\\./, "") + " · " + deg + " relationship" + (deg === 1 ? "" : "s");
  }
  svg.addEventListener("click", function (e) {
    var g = e.target.closest("g.node");
    if (g && g.id) focus(g.id);
  });
  document.getElementById("reset").onclick = clearFocus;

  // center the viewBox on a node's bounding box (in SVG user units)
  function centerOn(id) {
    var g = nodes[id]; if (!g) return;
    var bb = g.getBBox();
    var pad = Math.max(bb.width, bb.height) * 1.6 + 40;
    view.w = Math.max(bb.width + pad, full.w / 40);
    var r = stage.getBoundingClientRect();
    view.h = view.w * (r.height / r.width); // match the stage aspect ratio

    view.x = bb.x + bb.width / 2 - view.w / 2;
    view.y = bb.y + bb.height / 2 - view.h / 2;
    apply();
  }

  // ---- search ----
  var ids = Object.keys(nodes).sort();
  var search = document.getElementById("search");
  var matchBox = document.getElementById("matches");
  var active = -1, shown = [];
  function renderMatches(q) {
    q = q.trim().toLowerCase();
    shown = q ? ids.filter(function (id) { return id.toLowerCase().indexOf(q) >= 0; }).slice(0, 12) : [];
    active = -1;
    matchBox.textContent = "";
    if (!shown.length) { matchBox.style.display = "none"; return; }
    // Build rows via the DOM (setAttribute + textContent) rather than an HTML
    // string, so a table name is never parsed as markup — future identifiers
    // with unusual characters stay inert.
    shown.forEach(function (id) {
      var row = document.createElement("div");
      row.setAttribute("data-id", id);
      row.textContent = id;
      matchBox.appendChild(row);
    });
    matchBox.style.display = "block";
  }
  function choose(id) {
    search.value = id; matchBox.style.display = "none";
    focus(id); centerOn(id);
  }
  search.addEventListener("input", function () { renderMatches(search.value); });
  search.addEventListener("keydown", function (e) {
    if (!shown.length) return;
    if (e.key === "ArrowDown") { active = (active + 1) % shown.length; }
    else if (e.key === "ArrowUp") { active = (active - 1 + shown.length) % shown.length; }
    else if (e.key === "Enter") { choose(shown[active >= 0 ? active : 0]); return; }
    else return;
    e.preventDefault();
    Array.prototype.forEach.call(matchBox.children, function (c, i) {
      c.classList.toggle("active", i === active);
    });
  });
  matchBox.addEventListener("click", function (e) {
    var d = e.target.closest("[data-id]"); if (d) choose(d.getAttribute("data-id"));
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".searchwrap")) matchBox.style.display = "none";
  });

  // ---- theme toggle (embeds respect ?theme=) ----
  var root = document.documentElement;
  var q = new URLSearchParams(location.search).get("theme");
  if (q === "dark" || q === "light") root.classList.add(q);
  document.getElementById("theme").onclick = function () {
    var dark = root.classList.contains("dark") ||
      (!root.classList.contains("light") &&
       window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.classList.remove("dark", "light");
    root.classList.add(dark ? "light" : "dark");
  };
})();
</script>
</body>
</html>
`;
}

function main() {
  const dbml = readFileSync(DBML_FILE, "utf8");
  const { svg, viewBox } = prepareSvg(renderSvg(dbml));
  const html = buildHtml(svg, viewBox, schemaColors(dbml));
  writeFileSync(OUTPUT_FILE, html);
  const nodes = (svg.match(/class="node"/g) || []).length;
  const edges = (svg.match(/class="edge"/g) || []).length;
  console.log(
    `Generated docs/reference/schema-erd.html ` +
      `(${nodes} tables, ${edges} relationships, viewBox ${viewBox})`
  );
}

main();
