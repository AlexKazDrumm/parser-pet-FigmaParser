"use strict";

const el = (sel) => document.querySelector(sel);

const treeEl = el("#tree");
const fileRefEl = el("#fileRef");
const tokenEl = el("#token");
const normalizeEl = el("#normalize");
const labelFullPathEl = el("#labelFullPath");

const cssOut = el("#cssOut");
const htmlOut = el("#htmlOut");
const jsonOut = el("#jsonOut");
const previewFrame = el("#preview");

let currentTree = null;

function nodeRow(node) {
  const hasChildren = !!(node.children && node.children.length);
  const wrapper = document.createElement("div");
  wrapper.className = "node";

  const toggle = document.createElement("div");
  toggle.className = "toggle" + (hasChildren ? "" : " empty");
  toggle.textContent = hasChildren ? "+" : "";
  wrapper.appendChild(toggle);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.dataset.nodeId = node.id || "";
  wrapper.appendChild(checkbox);

  const title = document.createElement("span");
  title.textContent = node.name || "(no name)";
  wrapper.appendChild(title);

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = node.type || "UNKNOWN";
  wrapper.appendChild(badge);

  const idSpan = document.createElement("span");
  idSpan.className = "id";
  idSpan.textContent = node.id ? `#${node.id}` : "";
  wrapper.appendChild(idSpan);

  const childrenWrap = document.createElement("div");
  childrenWrap.className = "children";

  if (hasChildren) {
    for (const child of node.children) {
      const { row, childrenWrap: childWrap } = nodeRow(child);
      childrenWrap.appendChild(row);
      childrenWrap.appendChild(childWrap);
    }
    toggle.addEventListener("click", () => {
      const open = childrenWrap.classList.toggle("open");
      toggle.textContent = open ? "−" : "+";
    });
  }

  return { row: wrapper, childrenWrap };
}

function renderTree(tree) {
  treeEl.innerHTML = "";
  if (!tree) return;
  const { row, childrenWrap } = nodeRow(tree);
  treeEl.appendChild(row);
  treeEl.appendChild(childrenWrap);
}

function getSelectedIds() {
  return Array.from(treeEl.querySelectorAll('input[type="checkbox"]'))
    .filter((i) => i.checked && i.dataset.nodeId)
    .map((i) => i.dataset.nodeId);
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    /* ignore */
  }
  if (!resp.ok) throw new Error((data && data.error) || `HTTP ${resp.status}`);
  return data;
}

function setPreview(css, html, container) {
  const width = (container && container.width) || 0;
  const height = (container && container.height) || 0;
  previewFrame.srcdoc = `<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;padding:16px;background:#111;color:#eee;font-family:system-ui,sans-serif;}
.figma-export-canvas{position:relative;background:#fff;}
${css || ""}</style></head>
<body><div class="figma-export-canvas" style="width:${width}px;height:${height}px;">${html || ""}</div></body></html>`;
}

function baseBody() {
  return {
    file: fileRefEl.value.trim(),
    token: tokenEl.value.trim() || null,
    normalize: !!normalizeEl.checked,
  };
}

function selectionBody(status) {
  const ids = getSelectedIds();
  if (!fileRefEl.value.trim()) {
    status.textContent = "Укажите Figma URL или file key.";
    return null;
  }
  if (ids.length === 0) {
    status.textContent = "Ничего не выбрано в дереве.";
    return null;
  }
  return Object.assign(baseBody(), { node_ids: ids });
}

document.addEventListener("DOMContentLoaded", () => {
  el("#loadBtn").addEventListener("click", async () => {
    const status = el("#loadStatus");
    if (!fileRefEl.value.trim()) {
      status.textContent = "Укажите Figma URL или file key.";
      return;
    }
    status.textContent = "Загрузка…";
    cssOut.value = htmlOut.value = jsonOut.value = "";
    setPreview("", "", { width: 0, height: 0 });
    try {
      const data = await postJSON("/api/figma/tree", baseBody());
      currentTree = data.tree;
      renderTree(currentTree);
      status.textContent = "Дерево построено.";
    } catch (e) {
      status.textContent = "Ошибка: " + e.message;
    }
  });

  el("#structuredBtn").addEventListener("click", async () => {
    const status = el("#structuredStatus");
    const body = selectionBody(status);
    if (!body) return;
    body.label_full_path = !!labelFullPathEl.checked;
    status.textContent = "Экспорт…";
    try {
      const data = await postJSON("/api/figma/export/structured", body);
      cssOut.value = data.css || "";
      htmlOut.value = data.html || "";
      jsonOut.value = JSON.stringify(data.json || [], null, 2);
      setPreview(data.css, data.html, data.container);
      status.textContent = "Готово.";
    } catch (e) {
      status.textContent = "Ошибка: " + e.message;
    }
  });

  el("#pixelBtn").addEventListener("click", async () => {
    const status = el("#pixelStatus");
    const body = selectionBody(status);
    if (!body) return;
    body.format = el("#pixelFormat").value;
    body.scale = parseFloat(el("#pixelScale").value || "1.0");
    status.textContent = "Экспорт…";
    try {
      const data = await postJSON("/api/figma/export/pixel", body);
      htmlOut.value = data.html || "";
      cssOut.value = "";
      jsonOut.value = "";
      setPreview("", data.html, data.container);
      status.textContent = "Готово.";
    } catch (e) {
      status.textContent = "Ошибка: " + e.message;
    }
  });

  el("#aiBtn").addEventListener("click", async () => {
    const status = el("#aiStatus");
    const body = selectionBody(status);
    if (!body) return;
    body.model = el("#aiModel").value.trim() || "gpt-4o";
    status.textContent = "Запрос к модели…";
    try {
      const data = await postJSON("/api/figma/export/ai", body);
      cssOut.value = data.css || "";
      htmlOut.value = data.html || "";
      jsonOut.value = data.warning ? JSON.stringify(data.warning, null, 2) : "";
      setPreview(data.css, data.html, data.container);
      status.textContent = "Готово.";
    } catch (e) {
      status.textContent = "Ошибка: " + e.message;
    }
  });

  el("#imgBtn").addEventListener("click", async () => {
    const status = el("#imgStatus");
    const file = el("#imgFile").files && el("#imgFile").files[0];
    if (!file) {
      status.textContent = "Выберите изображение.";
      return;
    }
    status.textContent = "Генерация…";
    try {
      const fd = new FormData();
      fd.append("image", file);
      fd.append("model", el("#aiModel").value.trim() || "gpt-4o");
      const resp = await fetch("/api/image/export", { method: "POST", body: fd });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      cssOut.value = data.css || "";
      htmlOut.value = data.html || "";
      jsonOut.value = data.warnings ? JSON.stringify(data.warnings, null, 2) : "";
      setPreview(data.css, data.html, data.container);
      status.textContent = "Готово.";
    } catch (e) {
      status.textContent = "Ошибка: " + e.message;
    }
  });
});
