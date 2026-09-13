/* inbox-to-actions UI: vanilla JS, no build step. Three panels backed by the
   API; all state lives in the database, the page just renders it. */

const $ = (sel) => document.querySelector(sel);

let activePanel = "inbox";
let activeCrmTab = "contacts";

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

/* ---------------- panels ---------------- */

document.querySelectorAll(".tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    activePanel = btn.dataset.panel;
    document.querySelectorAll(".tabs .tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".panel").forEach((p) =>
      p.classList.toggle("active", p.id === `panel-${activePanel}`));
    refresh();
  });
});

document.querySelectorAll(".subtabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeCrmTab = btn.dataset.crm;
    document.querySelectorAll(".subtabs .tab").forEach((b) => b.classList.toggle("active", b === btn));
    loadCrm();
  });
});

$("#ingest-btn").addEventListener("click", async () => {
  const btn = $("#ingest-btn");
  btn.disabled = true;
  btn.textContent = "Ingesting…";
  try {
    const r = await api("/ingest/run", { method: "POST" });
    toast(`Processed ${r.processed} new email(s)`);
    await refresh();
  } catch (e) {
    toast(`Ingest failed: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run ingest";
  }
});

/* ---------------- inbox ---------------- */

async function loadInbox() {
  const emails = await api("/emails");
  const body = $("#inbox-body");
  if (!emails.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No emails yet — click “Run ingest” to process the sample inbox.</td></tr>`;
    return;
  }
  body.innerHTML = emails.map((e) => `
    <tr class="clickable" data-id="${e.id}">
      <td class="muted">${e.id}</td>
      <td>${esc(e.sender)}</td>
      <td>${esc(e.subject)}</td>
      <td>${e.category ? `<span class="badge ${esc(e.category)}">${esc(e.category)}</span>` : `<span class="muted">—</span>`}</td>
      <td class="mono">${e.confidence != null ? e.confidence.toFixed(2) : "—"}</td>
      <td><span class="badge ${esc(e.status)}">${esc(e.status)}</span></td>
    </tr>`).join("");
  body.querySelectorAll("tr").forEach((tr) =>
    tr.addEventListener("click", () => openDrawer(tr.dataset.id)));
}

async function openDrawer(id) {
  const d = await api(`/emails/${id}`);
  const drawer = $("#drawer");
  const payload = d.extraction?.payload ?? null;
  drawer.innerHTML = `
    <button class="btn close" id="drawer-close">Close</button>
    <h2>${esc(d.subject)}</h2>
    <div class="muted">${esc(d.sender)} &middot; ${esc(d.received_at ?? "")}</div>
    <div style="margin-top:8px">
      ${d.extraction ? `<span class="badge ${esc(d.extraction.category)}">${esc(d.extraction.category)}</span>` : ""}
      <span class="badge ${esc(d.status)}">${esc(d.status)}</span>
      ${d.review ? `<span class="badge review">reason: ${esc(d.review.reason)}</span>` : ""}
    </div>
    <section><h4>Body</h4><pre>${esc(d.body_text)}</pre></section>
    ${d.attachments.length ? `<section><h4>Attachments</h4>${d.attachments.map((a) =>
      `<div class="mono muted">${esc(a.filename)} (${a.text.length} chars extracted)</div>`).join("")}</section>` : ""}
    ${payload && Object.keys(payload).length ? `<section><h4>Extracted fields
      <span class="mono muted">(${esc(d.extraction.prompt_version)})</span></h4>
      <pre>${esc(JSON.stringify(payload, null, 2))}</pre></section>` : ""}
    <section><h4>Audit trail</h4>
      ${d.audit.map((a) => `
        <div class="audit-row">
          <span class="dot ${a.ok ? "ok" : "fail"}"></span>
          <span class="audit-stage">${esc(a.stage)}</span>
          <span class="muted mono">${esc(a.prompt_version)}</span>
          <span>${esc(a.detail)}</span>
        </div>`).join("") || `<div class="muted">no rows</div>`}
    </section>`;
  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#overlay").classList.add("open");
  drawer.classList.add("open");
}

function closeDrawer() {
  $("#overlay").classList.remove("open");
  $("#drawer").classList.remove("open");
}
$("#overlay").addEventListener("click", closeDrawer);

/* ---------------- review ---------------- */

async function loadReview() {
  const items = await api("/review");
  $("#review-count").textContent = items.length || "";
  const list = $("#review-list");
  // don't wipe the user's in-progress edits on the auto-refresh tick
  if (list.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;
  if (!items.length) {
    list.innerHTML = `<div class="card"><div class="empty">Review queue is empty. 🎉</div></div>`;
    return;
  }
  list.innerHTML = items.map((it) => `
    <div class="card review-card" data-id="${it.id}">
      <div class="review-head">
        <h3>${esc(it.subject)}</h3>
        <span class="muted">${esc(it.sender)}</span>
        <span class="badge ${esc(it.category)}">${esc(it.category)}</span>
        <span class="badge review">${esc(it.reason)}</span>
        <span class="mono muted">confidence ${it.confidence?.toFixed(2)}</span>
      </div>
      <div class="fields">
        ${Object.entries(flatten(it.payload)).map(([k, v]) => `
          <div><label>${esc(k)}</label>
          <input data-key="${esc(k)}" value="${esc(v ?? "")}"></div>`).join("")}
      </div>
      <div class="actions">
        <button class="btn primary" data-act="approve">Approve</button>
        <button class="btn danger" data-act="reject">Reject</button>
      </div>
    </div>`).join("");
  list.querySelectorAll(".review-card").forEach((card) => {
    card.querySelector('[data-act="approve"]').addEventListener("click", () => decide(card, true));
    card.querySelector('[data-act="reject"]').addEventListener("click", () => decide(card, false));
  });
  // remember original payload shapes to un-flatten edits
  list._payloads = Object.fromEntries(items.map((it) => [it.id, it.payload]));
}

function flatten(obj, prefix = "") {
  const out = {};
  for (const [k, v] of Object.entries(obj || {})) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(out, flatten(v, key));
    else out[key] = Array.isArray(v) ? v.join(", ") : v;
  }
  return out;
}

function unflatten(flat, original) {
  const out = JSON.parse(JSON.stringify(original || {}));
  for (const [key, raw] of Object.entries(flat)) {
    const parts = key.split(".");
    let node = out;
    for (const p of parts.slice(0, -1)) node = node[p] = node[p] ?? {};
    const leaf = parts[parts.length - 1];
    const orig = parts.slice(0, -1).reduce((n, p) => (n ? n[p] : undefined), original)?.[leaf];
    if (Array.isArray(orig)) {
      node[leaf] = raw.split(",").map((s) => s.trim()).filter(Boolean)
        .map((s) => (typeof orig[0] === "number" && !isNaN(Number(s)) ? Number(s) : s));
    } else if (typeof orig === "number") {
      node[leaf] = raw === "" ? null : Number(raw);
    } else {
      node[leaf] = raw === "" ? null : raw;
    }
  }
  return out;
}

async function decide(card, approve) {
  const id = card.dataset.id;
  try {
    if (approve) {
      const flat = {};
      card.querySelectorAll("input[data-key]").forEach((inp) => { flat[inp.dataset.key] = inp.value; });
      const payload = unflatten(flat, $("#review-list")._payloads[id]);
      await api(`/review/${id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      toast("Approved — CRM updated");
    } else {
      const reason = prompt("Reason for rejecting?") ?? "";
      if (reason === "" && !confirm("Reject without a reason?")) return;
      await api(`/review/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      toast("Rejected — note added to Activities");
    }
    await refresh();
  } catch (e) {
    toast(`Failed: ${e.message}`);
  }
}

/* ---------------- CRM ---------------- */

const CRM_COLUMNS = {
  contacts: ["id", "name", "email", "phone", "source_email_id"],
  deals: ["id", "reference", "stage", "amount", "contact_id", "key_dates"],
  activities: ["id", "kind", "note", "contact_id", "deal_id", "created_at"],
};

async function loadCrm() {
  const rows = await api(`/crm/${activeCrmTab}`);
  const cols = CRM_COLUMNS[activeCrmTab];
  $("#crm-head").innerHTML = `<tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;
  const body = $("#crm-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="${cols.length}" class="empty">Nothing here yet.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `<tr>${cols.map((c) => {
    let v = r[c];
    if (c === "key_dates" && v) v = Object.entries(v).map(([k, d]) => `${k}: ${d ?? "—"}`).join("  ");
    if (c === "created_at" && v) v = v.replace("T", " ").slice(0, 19);
    return `<td>${esc(v ?? "—")}</td>`;
  }).join("")}</tr>`).join("");
}

/* ---------------- refresh loop ---------------- */

async function refresh() {
  try {
    if (activePanel === "inbox") await loadInbox();
    if (activePanel === "crm") await loadCrm();
    await loadReview(); // always: keeps the badge count fresh
  } catch (e) {
    console.error(e);
  }
}

refresh();
setInterval(refresh, 20000);
