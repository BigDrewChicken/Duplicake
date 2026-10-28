const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const thumb = (p) => `/api/thumb?p=${encodeURIComponent(p)}`;
const full = (p) => `/api/image?p=${encodeURIComponent(p)}`;
const fmt = (b) => { const u = ["B", "KB", "MB", "GB"]; let i = 0; while (b >= 1024 && i < 3) { b /= 1024; i++; } return `${b.toFixed(i ? 1 : 0)} ${u[i]}`; };

let groups = [], stats = {};
const selected = new Set();

async function api(url, body) {
  const r = await fetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Something went wrong. Try again.");
  return d;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3800);
}

/* ---------- scanning ---------- */
const STAGES = { queued: "Preheating the oven", finding: "Looking through folders", reading: "Reading photos", comparing: "Comparing photos" };

function setProgress(text, frac) {
  $("#progress").hidden = false;
  $("#progressText").textContent = text;
  $("#barFill").style.width = `${Math.max(3, Math.round(frac * 100))}%`;
}

async function poll(id) {
  for (;;) {
    const j = await api(`/api/job/${id}`);
    if (j.stage === "error") throw new Error(j.error);
    if (j.stage === "done") { $("#progress").hidden = true; return load(j.result); }
    setProgress(`${STAGES[j.stage] || "Working"}${j.total ? ` (${j.done} of ${j.total})` : ""}`, j.total ? j.done / j.total : .04);
    await new Promise((r) => setTimeout(r, 400));
  }
}

async function startScan() {
  const path = $("#path").value.trim();
  if (!path) return toast("Enter a folder to scan first.");
  $("#scan").disabled = true;
  $("#results").innerHTML = "";
  $("#stats").hidden = $("#toolbar").hidden = true;
  setProgress(STAGES.queued, .04);
  try {
    const { job } = await api("/api/scan", { path, threshold: $("#thr").value / 100 });
    await poll(job);
  } catch (e) {
    $("#progress").hidden = true;
    toast(e.message);
  }
  $("#scan").disabled = false;
}

function load(result) {
  groups = result.groups;
  stats = result.stats;
  selected.clear();
  render();
  if (stats.skipped) toast(`${stats.skipped} file${stats.skipped > 1 ? "s" : ""} couldn't be read and were skipped.`);
}

/* ---------- rendering ---------- */
const reclaim = (g) => g.items.filter((i) => !i.best).reduce((s, i) => s + i.bytes, 0);

function batchHTML(g) {
  const n = g.items.length;
  const collage = `<div class="collage n${Math.min(4, n)}">${g.items.slice(0, 4).map((i) => `<img src="${thumb(i.path)}" alt="">`).join("")}${n > 4 ? `<span class="more">+${n - 4}</span>` : ""}</div>`;
  const tiles = g.items.map((i, k) => `
    <figure class="tile${i.best ? " best" : ""}" data-path="${esc(i.path)}" role="checkbox" aria-checked="false" tabindex="0">
      <div class="ph">
        <img loading="lazy" src="${thumb(i.path)}" alt="${esc(i.name)}">
        ${i.best ? `<span class="crown">🍰 Best slice</span>` : ""}
        <span class="pick"></span>
        <span class="count">${k + 1}/${n}</span>
        <a class="open" href="${full(i.path)}" target="_blank" rel="noopener">Open</a>
      </div>
      <figcaption>
        <b title="${esc(i.path)}">${esc(i.name)}</b>
        <span>${i.w}×${i.h}, ${fmt(i.bytes)}, ${i.match}% match</span>
        ${i.best ? `<em>${esc(g.why)}</em>` : ""}
      </figcaption>
    </figure>`).join("");
  return `
    <article class="card batch" data-id="${g.id}">
      <div class="head">
        ${collage}
        <div>
          <h3>Batch ${g.id}</h3>
          <div class="sub"><span class="chip ${g.kind === "Identical" ? "id" : "near"}">${g.kind}</span><span>${n} photos</span><span>frees ${fmt(reclaim(g))}</span></div>
        </div>
      </div>
      <div class="rail">${tiles}</div>
      <div class="actions">
        <button class="btn soft" data-act="extras">Select all but best</button>
        <button class="btn danger" data-act="delsel" disabled>Delete selected</button>
        <button class="btn primary" data-act="keepbest">Keep best, delete ${n - 1}</button>
      </div>
    </article>`;
}

function render() {
  $("#stats").hidden = false;
  $("#toolbar").hidden = !groups.length;
  $("#sImages").textContent = stats.images;
  $("#sFolders").textContent = stats.folders;
  $("#sBatches").textContent = groups.length;
  $("#sSpace").textContent = fmt(groups.reduce((s, g) => s + reclaim(g), 0));
  $("#results").innerHTML = groups.length
    ? groups.map(batchHTML).join("")
    : `<div class="card empty"><span>🎂</span><h2>No duplicakes found</h2><p class="muted">Every photo looks unique at this strictness. Slide it toward Looser to catch more.</p></div>`;
}

function refresh(card) {
  const g = groups.find((x) => x.id == card.dataset.id);
  const order = [...selected].filter((p) => g.items.some((i) => i.path === p));
  card.querySelectorAll(".tile").forEach((t) => {
    const idx = order.indexOf(t.dataset.path);
    t.classList.toggle("sel", idx > -1);
    t.setAttribute("aria-checked", idx > -1);
    t.querySelector(".pick").textContent = idx > -1 ? idx + 1 : "";
  });
  const b = card.querySelector('[data-act="delsel"]');
  b.disabled = !order.length;
  b.textContent = order.length ? `Delete selected (${order.length})` : "Delete selected";
}

/* ---------- deleting ---------- */
async function removePhotos(paths) {
  if (!paths.length) return;
  const permanent = $("#perm").checked;
  const label = `${paths.length} photo${paths.length > 1 ? "s" : ""}`;
  if (!confirm(`Delete ${label}? ${permanent ? "This can't be undone." : "They'll move to your Recycle Bin / Trash."}`)) return;
  try {
    const res = await api("/api/delete", { paths, permanent });
    const gone = new Set(res.deleted);
    groups.forEach((g) => (g.items = g.items.filter((i) => !gone.has(i.path))));
    gone.forEach((p) => selected.delete(p));
    groups = groups.filter((g) => g.items.length > 1);
    groups.forEach((g) => {
      if (!g.items.some((i) => i.best)) g.items.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a)).best = true;
    });
    stats.images -= gone.size;
    render();
    toast(res.failed.length ? `Deleted ${gone.size}. ${res.failed.length} couldn't be removed.` : `Deleted ${gone.size} photo${gone.size === 1 ? "" : "s"}.`);
  } catch (e) {
    toast(e.message);
  }
}

const actions = {
  extras(g, card) { g.items.forEach((i) => (i.best ? selected.delete(i.path) : selected.add(i.path))); refresh(card); },
  delsel(g) { removePhotos(g.items.map((i) => i.path).filter((p) => selected.has(p))); },
  keepbest(g) { removePhotos(g.items.filter((i) => !i.best).map((i) => i.path)); },
};

$("#results").addEventListener("click", (e) => {
  if (e.target.closest(".open")) return;
  const card = e.target.closest(".batch");
  if (!card) return;
  const g = groups.find((x) => x.id == card.dataset.id);
  const act = e.target.closest("[data-act]");
  const tile = e.target.closest(".tile");
  if (act) return actions[act.dataset.act](g, card);
  if (tile) {
    const p = tile.dataset.path;
    selected.has(p) ? selected.delete(p) : selected.add(p);
    refresh(card);
  }
});
$("#results").addEventListener("keydown", (e) => {
  if ((e.key === " " || e.key === "Enter") && e.target.classList.contains("tile")) { e.preventDefault(); e.target.click(); }
});
$("#keepAll").onclick = () => removePhotos(groups.flatMap((g) => g.items.filter((i) => !i.best).map((i) => i.path)));

/* ---------- controls + folder picker ---------- */
$("#scan").onclick = startScan;
$("#path").addEventListener("keydown", (e) => e.key === "Enter" && startScan());
$("#thr").oninput = (e) => ($("#thrVal").textContent = `${e.target.value}%`);

const dlg = $("#browser");
let browsePath = "";
async function browse(p = "") {
  const d = await api(`/api/browse?p=${encodeURIComponent(p)}`);
  browsePath = d.path;
  $("#curPath").textContent = d.path;
  const row = (label, path) => `<li><button type="button" data-p="${esc(path)}">${esc(label)}</button></li>`;
  const html = d.drives.map((x) => row(`💽 ${x}`, x)).join("") + (d.parent ? row("⬆ Up one level", d.parent) : "") + d.dirs.map((x) => row(`📁 ${x.name}`, x.path)).join("");
  $("#dirList").innerHTML = html || `<li class="muted">No subfolders here</li>`;
}
$("#browse").onclick = async () => {
  try { await browse($("#path").value.trim()); dlg.showModal(); } catch (e) { toast(e.message); }
};
$("#dirList").onclick = (e) => { const b = e.target.closest("button"); if (b) browse(b.dataset.p).catch((err) => toast(err.message)); };
$("#useFolder").onclick = () => { $("#path").value = browsePath; dlg.close(); };
$("#cancelBrowse").onclick = () => dlg.close();
