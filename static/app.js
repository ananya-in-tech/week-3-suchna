// Suchna: drop the notice, walk away. Everything stays on this computer.

const app = document.getElementById("app");
const queueEl = document.getElementById("queue");
let timer = null;
let DEMO = null; // the hosted demo: {shift_days, repo}. Read-only; your profile lives in a cookie.

function demoCard() {
  const moved = DEMO.shift_days ? ` Their dates are moved ${DEMO.shift_days} day${DEMO.shift_days > 1 ? "s" : ""} forward so the deadlines stay ahead.` : "";
  return `<div class="card demo">
    <h2>This is the hosted demo</h2>
    <p>Below are Gemma 4's real readings of four <b>sample notices</b> (made for testing, not real university notices).${moved}
      Change <a href="#/profile">your profile</a> and watch the answers change.</p>
    <p class="muted">A free server can't run Gemma, and your notices shouldn't leave your computer anyway, so reading
      new notices only works when you run Suchna yourself: <a href="${esc(DEMO.repo)}" target="_blank" rel="noopener">get it on GitHub</a>.</p>
  </div>`;
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function prettyDate(iso, withYear = false) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}) });
}

function daysWords(n) {
  if (n === null || n === undefined) return "";
  if (n < 0) return n === -1 ? "yesterday" : `${-n} days ago`;
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  return `in ${n} days`;
}

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const d = body?.detail;
    throw new Error(Array.isArray(d) ? `${d[0].loc.at(-1)}: ${d[0].msg}` : d || `Request failed (${res.status})`);
  }
  return body;
}

function toast(msg, tone = "warn") {
  const p = document.createElement("p");
  p.className = `banner ${tone}`;
  p.textContent = msg;
  app.prepend(p);
  setTimeout(() => p.remove(), 7000);
}

const ANSWER = {
  yes: ["Yes", "Yes, this affects you"],
  maybe: ["Maybe", "Maybe: check this one"],
  no: ["Not you", "No, this isn't for you"],
};

function verdictChip(n) {
  if (n.status === "queued") return `<span class="chip plain">Waiting</span>`;
  if (n.status === "reading") return `<span class="chip plain loading">Reading…</span>`;
  if (n.status === "failed") return `<span class="chip late">Couldn't read</span>`;
  const a = n.verdict.answer;
  return `<span class="chip ${a}">${ANSWER[a][0]}</span>`;
}

function dueBox(it) {
  const late = it.days_left < 0, soon = it.days_left >= 0 && it.days_left <= 3;
  const big = late ? "Late" : it.days_left === 0 ? "Today" : it.days_left;
  const small = late ? prettyDate(it.due) : it.days_left === 0 ? prettyDate(it.due) : `${it.days_left === 1 ? "day" : "days"} · ${prettyDate(it.due)}`;
  return `<div class="due ${late ? "late" : soon ? "soon" : ""}"><b>${big}</b><small>${esc(small)}</small></div>`;
}

function setQueue(health) {
  const busy = health.queued + health.reading;
  queueEl.textContent = busy ? `Gemma is reading ${busy} notice${busy > 1 ? "s" : ""}…` : "";
  queueEl.classList.toggle("loading", busy > 0);
}

function poll(fn, ms = 3000) {
  clearTimeout(timer);
  timer = setTimeout(fn, ms);
}

// --- inbox -----------------------------------------------------------------------------------

async function inbox() {
  const [data, health] = await Promise.all([api("/notices"), api("/health")]);
  setQueue(health);
  const ns = data.notices;
  const done = ns.filter((n) => n.status === "done");
  const pending = ns.filter((n) => n.status !== "done").reverse(); // in reading order
  const by = (a) => done.filter((n) => n.verdict.answer === a);
  const sortNext = (list) => list.sort((a, b) => (a.next?.due || "9999").localeCompare(b.next?.due || "9999"));

  // every open action, from notices that are (or might be) yours, soonest first
  const next = done.filter((n) => n.verdict.answer !== "no")
    .flatMap((n) => n.items.filter((it) => it.kind === "action" && !it.done && it.due).map((it) => ({ ...it, notice: n })))
    .filter((it) => it.days_left >= -7)
    .sort((a, b) => a.due.localeCompare(b.due))
    .slice(0, 6);

  app.innerHTML = `
    <h1>Drop the notice. Walk away.</h1>
    <p class="lede">University notices in Hindi or English, PDFs or photos of the notice board. Suchna reads them and tells you,
      in plain English, <b>does this affect me, what do I do, and by when</b>.</p>
    ${DEMO ? demoCard() : `
    <p class="muted">${health.ai.available ? "● " : "○ "}${esc(health.ai.message)}</p>
    ${data.profile_set ? "" : `<p class="banner info">First, <a href="#/profile">tell Suchna your course and semester</a>. That's how it knows which notices are yours.</p>`}

    <label class="drop" id="drop">
      <b>Drop notices here</b>
      <span class="muted">PDF, JPG or PNG. Several at once is fine. Or click to choose, or take a photo on your phone.</span>
      <input type="file" id="files" accept="application/pdf,image/*" multiple>
    </label>`}

    ${next.length ? `<section><div class="row between"><h2>Next up</h2>
        <a class="btn ghost small" href="/api/calendar.ics" download>Add deadlines to calendar</a></div>
      <ul class="next">${next.map((it) => `<li>${dueBox(it)}<a href="#/notice/${it.notice.id}">
        <b>${esc(it.what)}</b><br><span class="muted">${esc(it.notice.title)}${it.notice.verdict.answer === "maybe" ? " · maybe yours" : ""}</span></a></li>`).join("")}
      </ul></section>` : ""}

    ${pending.length ? `<section><h2>Not read yet</h2>${list(pending)}</section>` : ""}
    ${by("yes").length ? `<section><h2>For you</h2>${list(sortNext(by("yes")))}</section>` : ""}
    ${by("maybe").length ? `<section><h2>Maybe for you</h2>${list(sortNext(by("maybe")))}</section>` : ""}
    ${by("no").length ? `<details class="group"><summary>Not for you (${by("no").length})</summary>${list(by("no"), "no")}</details>` : ""}
    ${ns.length ? "" : `<p class="muted" style="margin-top:20px">No notices yet. Tip: save notice PDFs from WhatsApp into the
      <code>data/inbox</code> folder and Suchna picks them up by itself.</p>`}`;

  const drop = document.getElementById("drop"), input = document.getElementById("files");
  if (!drop) return; // the hosted demo has no drop zone
  input.addEventListener("change", () => upload(input.files));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });

  if (health.queued + health.reading) poll(() => location.hash.length <= 2 && inbox());
}

function list(ns, cls = "") {
  return `<ul class="notices">${ns.map((n) => {
    const nx = n.next;
    const sub = n.status === "failed" ? esc(n.error) :
      n.status === "reading" ? "Gemma is reading this now. A few minutes on a laptop." :
      n.status === "queued" ? "Waiting its turn." :
      nx ? `Next: ${esc(nx.what)}, <b>${daysWords(nx.days_left)}</b> (${prettyDate(nx.due)})` :
      esc(n.summary);
    return `<li class="${cls}"><a href="#/notice/${n.id}">
      <div class="row between"><b>${esc(n.title || n.original_name)}</b>${verdictChip(n)}</div>
      <span class="muted">${sub}</span></a></li>`;
  }).join("")}</ul>`;
}

async function upload(files) {
  if (!files?.length) return;
  const form = new FormData();
  [...files].forEach((f) => form.append("files", f));
  try {
    const r = await api("/notices", { method: "POST", body: form });
    if (r.errors.length) toast(r.errors.join(" · "));
    else toast(`Got it. Gemma is reading ${r.ids.length > 1 ? `${r.ids.length} notices` : "it"}. You can close this tab.`, "ok");
  } catch (e) { toast(e.message); }
  if (files.length === 1) setTimeout(inbox, 400); else inbox();
}

// --- one notice ------------------------------------------------------------------------------

async function noticeView(id) {
  const n = await api(`/notices/${id}`);
  const back = `<p class="muted"><a href="#/">← All notices</a></p>`;
  const side = `<div>
      <a href="/api/notices/${n.id}/file" target="_blank" rel="noopener"><img class="preview" src="/api/notices/${n.id}/preview.jpg" alt="The notice"></a>
      <p class="muted">${esc(n.original_name)} · <a href="/api/notices/${n.id}/file" target="_blank" rel="noopener">open original</a></p>
      ${n.page_notes.map((p) => `<p class="muted">${esc(p)}</p>`).join("")}
      ${n.text ? `<details class="transcript"><summary class="muted">What Gemma read off the page</summary><pre lang="hi">${esc(n.text)}</pre></details>` : ""}
      ${n.latency_ms ? `<p class="muted">Read in ${Math.round(n.latency_ms / 1000)} s ${DEMO ? "by Gemma on a laptop CPU" : "on this computer"}${n.pages_total > n.pages_read ? ` (first ${n.pages_read} of ${n.pages_total} pages)` : ""}.</p>` : ""}
      ${DEMO ? "" : `<div class="row" style="margin-top:10px">
        <button class="btn ghost small" id="reread">Read again</button>
        <button class="btn ghost small" id="delete">Delete</button>
      </div>`}
    </div>`;

  if (n.status !== "done") {
    app.innerHTML = `${back}<div class="layout"><div>
      <h1>${esc(n.original_name)}</h1>
      ${n.status === "failed" ? `<p class="banner warn">${esc(n.error)}</p>` :
        `<p class="banner info loading">${n.status === "reading" ? "Gemma is reading this notice…" : "Waiting its turn…"}
          On a laptop CPU this takes a minute or two. You don't have to watch.</p>`}
    </div>${side}</div>`;
    wire(n);
    if (n.status !== "failed") poll(() => location.hash === `#/notice/${id}` && noticeView(id));
    return;
  }

  const v = n.verdict, a = n.audience;
  const actions = n.items.filter((it) => it.kind === "action"), events = n.items.filter((it) => it.kind === "event");
  app.innerHTML = `${back}<div class="layout"><div>
    <h1>${esc(n.title)}</h1>
    <p class="muted">${[n.issued_by, n.notice_date && `dated ${prettyDate(n.notice_date, true)}`].filter(Boolean).map(esc).join(" · ")}
      <span class="chip plain">${esc(n.language)}</span></p>

    <div class="answer ${v.answer}">
      <h2>${ANSWER[v.answer][1]}</h2>
      <ul>${v.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      ${a.quote ? `<p class="quote" lang="hi">${esc(a.quote)}</p>` : ""}
      <div class="row" style="margin-top:8px" ${DEMO ? "hidden" : ""}>
        ${n.override ?`<button class="btn ghost small" data-override="">Undo my answer</button>` : `
        ${v.answer !== "yes" ? `<button class="btn ghost small" data-override="yes">It's for me</button>` : ""}
        ${v.answer !== "no" ? `<button class="btn ghost small" data-override="no">Not for me</button>` : ""}`}
      </div>
    </div>

    <p>${esc(n.summary)}</p>

    <div class="card"><h2>What to do</h2>
      ${actions.length ? `<ul class="todo">${actions.map(itemRow).join("")}</ul>` : `<p class="muted">Nothing to do. It's for your information.</p>`}
    </div>
    ${events.length ? `<div class="card"><h2>Dates to know</h2><ul class="todo">${events.map(itemRow).join("")}</ul></div>` : ""}
  </div>${side}</div>`;

  app.querySelectorAll("[data-item]").forEach((box) => box.addEventListener("change", async () => {
    try { await api(`/items/${box.dataset.item}`, { method: "PATCH", body: JSON.stringify({ done: box.checked }) }); noticeView(id); }
    catch (e) { toast(e.message); }
  }));
  app.querySelectorAll("[data-override]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/notices/${id}`, { method: "PATCH", body: JSON.stringify({ override: b.dataset.override || null }) });
    noticeView(id);
  }));
  wire(n);
}

function itemRow(it) {
  const when = it.due ? `<b>${prettyDate(it.due, true)}</b><br><span class="${it.days_left < 0 ? "chip late" : "muted"}">${daysWords(it.days_left)}</span>` :
    it.date_text ? `<span class="muted">${esc(it.date_text)}</span>` : "";
  return `<li class="${it.done ? "done" : ""}">
    ${it.kind === "action" ? `<input type="checkbox" data-item="${it.id}" ${it.done ? "checked" : ""} ${DEMO ? 'disabled title="Ticking works when you run Suchna yourself"' : ""} aria-label="Done">` : "<span></span>"}
    <div><span class="what">${esc(it.what)}</span>
      ${it.date_note ? `<br><span class="chip maybe">${esc(it.date_note)}</span>` : ""}
      ${it.quote ? `<details><summary>From the notice</summary><p class="quote" lang="hi">${esc(it.quote)}</p></details>` : ""}</div>
    <div class="when">${when}</div></li>`;
}

function wire(n) {
  document.getElementById("reread")?.addEventListener("click", async () => {
    try { await api(`/notices/${n.id}/read`, { method: "POST" }); noticeView(n.id); } catch (e) { toast(e.message); }
  });
  document.getElementById("delete")?.addEventListener("click", async () => {
    if (!confirm("Delete this notice from Suchna?")) return;
    try { await api(`/notices/${n.id}`, { method: "DELETE" }); location.hash = "#/"; } catch (e) { toast(e.message); }
  });
}

// --- profile ---------------------------------------------------------------------------------

async function profileView() {
  const p = await api("/profile");
  app.innerHTML = `
    <p class="muted"><a href="#/">← All notices</a></p>
    <h1>About you</h1>
    <p class="lede">Suchna checks every notice against this. ${DEMO ? "In this demo it's kept only in a cookie in your browser." :
      "It stays on this computer."} Gemma never sees it: the matching is plain code, so changing it re-sorts your notices instantly.</p>
    <form id="profile" class="card grid2">
      <label>Course <input name="program" value="${esc(p.program)}" placeholder="B.Tech, BA, M.Sc, PhD…" maxlength="40"></label>
      <label>Semester <input name="semester" type="number" min="1" max="12" value="${esc(p.semester)}" placeholder="3"></label>
      <label>Department / branch <input name="department" value="${esc(p.department)}" placeholder="Computer Science, Physics…" maxlength="80"></label>
      <label>University <input name="university" value="${esc(p.university)}" maxlength="120"></label>
      <label>Roll number <input name="roll_no" value="${esc(p.roll_no)}" maxlength="30" placeholder="Finds you in lists of students"></label>
      <label>Name <input name="name" value="${esc(p.name)}" maxlength="80" placeholder="As on the university records"></label>
      <label>Where you live
        <select name="hostel">
          <option value="" ${p.hostel === null ? "selected" : ""}>Don't say</option>
          <option value="true" ${p.hostel === true ? "selected" : ""}>Hostel</option>
          <option value="false" ${p.hostel === false ? "selected" : ""}>Day scholar</option>
        </select></label>
      <div class="row" style="align-self:end"><button class="btn">Save</button></div>
    </form>`;
  document.getElementById("profile").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const body = Object.fromEntries([...f].map(([k, v]) => [k, v === "" ? null : v]));
    body.semester = body.semester ? Number(body.semester) : null;
    body.hostel = body.hostel === null ? null : body.hostel === "true";
    try { await api("/profile", { method: "PUT", body: JSON.stringify(body) }); location.hash = "#/"; }
    catch (err) { toast(err.message); }
  });
}

// --- router ----------------------------------------------------------------------------------

async function route() {
  clearTimeout(timer);
  const h = location.hash || "#/";
  try {
    const m = h.match(/^#\/notice\/(\d+)/);
    if (m) await noticeView(Number(m[1]));
    else if (h.startsWith("#/profile")) await profileView();
    else await inbox();
  } catch (e) {
    app.innerHTML = `<p class="banner warn">${esc(e.message)}</p>`;
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
api("/health").then((h) => { DEMO = h.demo; }).catch(() => {}).finally(route);
