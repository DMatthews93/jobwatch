// Jobwatch front end. Loads jobs.json (built by GitHub Actions) and renders it.
// The application tracker and home postcode live in this browser's localStorage.

const CATS = {
  nhs: ["NHS clinical", "#4da3ff"],
  priv: ["Private &amp; independent", "#ff6fa8"],
  res: ["Research", "#8b7bff"],
  adj: ["Medical-adjacent", "#2dd4a7"],
  soc: ["Social care &amp; support", "#f59e0b"],
  gen: ["Other work", "#94a3b8"],
  aes: ["Aesthetics", "#c084fc"],
};
const STAT = ["Saved", "Applied", "Interview", "Offer", "Rejected"];
const SRC = { nhs: "NHS Jobs", reed: "Reed", jobsac: "jobs.ac.uk", employer: "Employer site", adzuna: "Adzuna" };
// Toggle buttons: [key, label, on by default]
const TOG = [
  ["inside", "Pay fully inside salary range", 1],
  ["ft", "Full time only", 1],
  ["nmw", "At least minimum wage", 1],
  ["clean", "Hide non-doctor &amp; other-specialty", 1],
  ["closed", "Show closed &amp; stale", 0],
  ["mine", "My applications only", 0],
  ["hid", "Show hidden", 0],
];

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// D: jobs.json contents. ST: tracker state per job id ({st, at, hide}). HOME: {pc, lat, lng}.
let D = { jobs: [], settings: { nlw_full_time_annual: 24785 } }, ST = {}, HOME = null, shown = 100;
const on = {};
TOG.forEach(t => on[t[0]] = !!t[2]);
try {
  ST = JSON.parse(localStorage.getItem("jw2") || "{}");
  HOME = JSON.parse(localStorage.getItem("jwhome") || "null");
} catch (e) {}
const keep = () => {
  try { localStorage.setItem("jw2", JSON.stringify(ST)); } catch (e) {}
};

// Distance in miles between two lat/lng points (haversine).
const mi = (a, b, c, d) => {
  const r = Math.PI / 180,
    x = Math.sin((c - a) * r / 2) ** 2 + Math.cos(a * r) * Math.cos(c * r) * Math.sin((d - b) * r / 2) ** 2;
  return 3959 * 2 * Math.asin(Math.sqrt(x));
};
const k = n => "£" + (n >= 1000 ? Math.round(n / 100) / 10 + "k" : n);
const ago = iso => {
  const m = Math.round((Date.now() - new Date(iso)) / 6e4);
  return m < 2 ? "just now"
    : m < 90 ? m + " min ago"
    : m < 2880 ? Math.round(m / 60) + " hours ago"
    : Math.round(m / 1440) + " days ago";
};
// Days until a YYYY-MM-DD closing date (end of that day), or null.
const dleft = s => s ? Math.ceil((new Date(s + "T23:59:59") - Date.now()) / 864e5) : null;

const sel = new Set(Object.keys(CATS));
$("chips").innerHTML = Object.entries(CATS)
  .map(([c, [n, col]]) => `<button class="chip" data-k="${c}" style="--c:${col}" aria-pressed="true">${n}</button>`)
  .join("");
$("toggles").innerHTML = TOG
  .map(t => `<button class="chip" data-t="${t[0]}" aria-pressed="${!!t[2]}">${t[1]}</button>`)
  .join("");
if (HOME) {
  $("pc").value = HOME.pc;
  $("pcmsg").textContent = "✓ location set";
}

// Slider ends (0 and 100k) mean no limit. "inside": whole pay range within the slider; off: any overlap.
function payOk(j, mn, mx) {
  if (mn === 0 && mx >= 1e5) return true;
  if (!j.salary_stated) return false;
  const lo = j.salary_min ?? j.salary_max ?? 0, hi = j.salary_max ?? j.salary_min ?? 0;
  return on.inside ? (mn === 0 || lo >= mn) && (mx >= 1e5 || hi <= mx) : hi >= mn && lo <= mx;
}

function filtered() {
  const q = $("q").value.toLowerCase(),
    R = +$("rad").value,
    mn = Math.min(+$("min").value, +$("max").value),
    mx = Math.max(+$("min").value, +$("max").value),
    E = $("emp").value,
    fl = D.settings.nlw_full_time_annual;
  let L = D.jobs
    .map(j => ({ ...j, dist: HOME && j.lat != null ? mi(HOME.lat, HOME.lng, j.lat, j.lng) : null }))
    .filter(j => {
      const s = ST[j.id] || {};
      return sel.has(j.category)
        && (E === "" || j.employer === E)
        && (!HOME || j.dist == null || j.dist <= R)
        && payOk(j, mn, mx)
        && (!on.ft || j.full_time !== false)
        && (!on.nmw || !j.salary_stated || j.salary_estimated || j.salary_min >= fl)
        && (!on.clean || !j.flags.some(f => f == "non-doctor-role" || f == "other-specialty"))
        && (on.closed || j.status == "open")
        && (!on.mine || s.st)
        && (on.hid || !s.hide)
        && `${j.title} ${j.employer} ${j.location}`.toLowerCase().includes(q);
    });
  const so = $("sort").value, t = x => Date.parse(x.first_seen);
  L.sort((a, b) =>
    so == "sal" ? (b.salary_max || 0) - (a.salary_max || 0)
    : so == "dist" ? (a.dist ?? 9e9) - (b.dist ?? 9e9)
    : so == "close" ? (dleft(a.closing) ?? 9e9) - (dleft(b.closing) ?? 9e9)
    : t(b) - t(a));
  return L;
}

function card(j) {
  const s = ST[j.id] || {},
    c = CATS[j.category]?.[1] || "#888",
    dl = dleft(j.closing),
    isNew = Date.now() - Date.parse(j.first_seen) < 864e5;
  const pay = j.salary_stated
    ? `${k(j.salary_min)}${j.salary_max != j.salary_min ? " – " + k(j.salary_max) : ""}<small>${j.salary_estimated ? "estimated by site" : j.salary_converted ? "converted to full-time yearly" : "per year"}</small>`
    : `<span class="meta">Pay not stated</span>`;
  const hrs = j.hours_per_week ? `${j.hours_per_week} hrs/wk`
    : j.full_time === true ? "Full time"
    : j.full_time === false ? "Part time"
    : "Hours not stated";
  return `<article class="job${j.status != "open" || s.hide ? " dim" : ""}" style="--c:${c}">
 <div><div class="emp">${esc(j.employer)}</div><h3>${esc(j.title)}</h3><div class="meta">${esc(j.location || "Location not stated")}${j.dist != null ? " · " + Math.round(j.dist) + " mi" : ""} · ${hrs} · ${esc(j.contract_type == "unknown" ? "Contract not stated" : j.contract_type)}</div></div>
 <div class="sal">${pay}</div>${j.snippet ? `<p class="desc" title="Click to read more">${esc(j.snippet)}</p>` : ""}
 <div class="tags"><span class="tag">${CATS[j.category]?.[0] || ""}</span>${isNew ? '<span class="tag new">New</span>' : ""}${j.status == "stale" ? '<span class="tag warn">May have gone: not seen on source</span>' : ""}${j.status == "closed" ? '<span class="tag warn">Closed</span>' : ""}
 ${j.closing ? (dl != null && dl <= 3 && dl >= 0 ? `<span class="tag hot">Closes in ${dl}d</span>` : `<span class="meta">closes ${esc(j.closing)}</span>`) : '<span class="meta">no closing date</span>'}
 ${j.tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}${j.flags.includes("needs-nhs-experience") ? '<span class="tag warn">NHS experience asked for</span>' : ""}</div>
 <div class="links">${j.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${SRC[l.source] || esc(l.source)}</a>`).join("")}
 <select data-a="st" data-i="${j.id}" aria-label="Application status"><option value="">Track…</option>${STAT.map(x => `<option${s.st == x ? " selected" : ""}>${x}</option>`).join("")}</select>
 ${j.closing && dl >= 0 ? `<button class="btn sm" data-a="ics" data-i="${j.id}">📅 Remind me</button>` : ""}
 <button class="btn sm" data-a="hide" data-i="${j.id}">${s.hide ? "Unhide" : "Hide"}</button></div></article>`;
}

function render() {
  $("radv").textContent = $("rad").value;
  {
    const lo = Math.min(+$("min").value, +$("max").value), hi = Math.max(+$("min").value, +$("max").value);
    $("minv").textContent = lo == 0 && hi >= 1e5 ? "Any"
      : lo == 0 ? "up to £" + hi / 1000 + "k"
      : hi >= 1e5 ? "£" + lo / 1000 + "k+"
      : "£" + lo / 1000 + "k – £" + hi / 1000 + "k";
  }
  const L = filtered();
  $("count").textContent = `${L.length} role${L.length == 1 ? "" : "s"} match`;
  $("list").innerHTML = L.length
    ? L.slice(0, shown).map(card).join("")
    : '<div class="empty">Nothing matches. Try widening the radius or turning a filter off.</div>';
  $("more").hidden = L.length <= shown;
}

// Download a calendar file with a reminder the day before the job closes.
function ics(j) {
  const d = j.closing.replace(/-/g, ""), n = new Date(j.closing + "T00:00:00Z");
  n.setUTCDate(n.getUTCDate() + 1);
  const e = n.toISOString().slice(0, 10).replace(/-/g, ""), t = s => String(s).replace(/([,;\\])/g, "\\$1");
  const body = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jobwatch//EN", "BEGIN:VEVENT",
    `UID:${j.id}@jobwatch`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
    `DTSTART;VALUE=DATE:${d}`,
    `DTEND;VALUE=DATE:${e}`,
    `SUMMARY:${t("Closes: " + j.title + " (" + j.employer + ")")}`,
    `URL:${j.links[0].url}`,
    "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:Job closes tomorrow", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([body], { type: "text/calendar" }));
  a.download = "job-closing.ics";
  a.click();
}

document.addEventListener("input", e => {
  if (e.target.dataset.a) return;
  shown = 100;
  render();
});
$("chips").onclick = e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  const c = b.dataset.k;
  sel.has(c) ? sel.delete(c) : sel.add(c);
  b.setAttribute("aria-pressed", sel.has(c));
  shown = 100;
  render();
};
$("toggles").onclick = e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  const t = b.dataset.t;
  on[t] = !on[t];
  b.setAttribute("aria-pressed", on[t]);
  shown = 100;
  render();
};
$("list").onclick = e => {
  const d = e.target.closest(".desc");
  if (d) {
    d.classList.toggle("open");
    return;
  }
  const b = e.target.closest("[data-a]");
  if (!b || b.tagName == "SELECT") return;
  const i = b.dataset.i, j = D.jobs.find(x => x.id == i);
  if (b.dataset.a == "ics") ics(j);
  if (b.dataset.a == "hide") {
    ST[i] = { ...ST[i], hide: !(ST[i] || {}).hide };
    keep();
    render();
  }
};
$("list").onchange = e => {
  const b = e.target;
  if (b.dataset.a != "st") return;
  ST[b.dataset.i] = { ...ST[b.dataset.i], st: b.value, at: new Date().toISOString().slice(0, 10) };
  keep();
};
$("more").onclick = () => {
  shown += 100;
  render();
};
$("ftog").onclick = () => {
  const o = $("fbody").classList.toggle("open");
  $("ftog").setAttribute("aria-pressed", o);
};
$("theme").onclick = () => {
  const r = document.documentElement;
  r.dataset.theme = getComputedStyle(r).colorScheme == "dark" ? "light" : "dark";
};
$("setpc").onclick = async () => {
  const pc = $("pc").value.trim();
  if (!pc) {
    HOME = null;
    try { localStorage.removeItem("jwhome"); } catch (e) {}
    $("pcmsg").textContent = "";
    return render();
  }
  $("pcmsg").textContent = "Looking up…";
  try {
    const r = await fetch("https://api.postcodes.io/postcodes/" + encodeURIComponent(pc)), d = await r.json();
    if (!d.result) throw 0;
    HOME = { pc: pc.toUpperCase(), lat: d.result.latitude, lng: d.result.longitude };
    try { localStorage.setItem("jwhome", JSON.stringify(HOME)); } catch (e) {}
    $("pcmsg").textContent = "✓ location set";
  } catch (e) {
    $("pcmsg").textContent = "Couldn’t find that postcode";
  }
  render();
};

fetch("jobs.json?" + Date.now())
  .then(r => r.json())
  .then(d => {
    D = d;
    const old = Date.now() - Date.parse(d.generated) > 36e5 * 3;
    $("upd").innerHTML = `<span class="dot${old ? " old" : ""}"></span>Updated ${ago(d.generated)}${d.sources.not_updated.length ? ` · not updated this time: ${d.sources.not_updated.map(s => SRC[s] || s).join(", ")}` : ""}`;
    const E = [...new Set(d.jobs.map(j => j.employer))].filter(Boolean).sort((a, b) => a.localeCompare(b));
    $("emp").innerHTML = '<option value="">All employers</option>' + E.map(e => `<option>${esc(e)}</option>`).join("");
    render();
  })
  .catch(() => {
    $("upd").textContent = "Couldn’t load jobs.json yet. Run the workflow once, then refresh.";
    $("count").textContent = "";
  });
