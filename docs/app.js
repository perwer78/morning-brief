// Morning Brief — Frontend Logic

const REPORTS_BASE = "reports/";

// ── Helpers ───────────────────────────────────────────────────────────────────

function todayISO() {
  // Use local date (not UTC) to match the generator
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDateDisplay(iso) {
  // "2026-03-19" → "Miércoles 19 de Marzo, 2026"
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("es-MX", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function show(id) { document.getElementById(id).classList.remove("hidden"); }
function hide(id) { document.getElementById(id).classList.add("hidden"); }

// ── Report loading ────────────────────────────────────────────────────────────

async function loadReport(dateISO) {
  // Reset UI
  show("loading");
  hide("report-content");
  hide("empty-state");

  const url = `${REPORTS_BASE}${dateISO}.json`;

  try {
    const res = await fetch(url, { cache: "no-store" });

    if (!res.ok) {
      hide("loading");
      show("empty-state");
      document.getElementById("header-meta").textContent = "—";
      return;
    }

    const data = await res.json();

    // Configure marked options
    marked.setOptions({
      breaks: true,
      gfm: true,
    });

    // Content is already structured HTML — inject directly
    document.getElementById("report-content").innerHTML = data.content || "";

    // Update header meta
    const genAt = data.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("es-MX", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
    document.getElementById("header-meta").textContent = genAt
      ? `Generado ${genAt} CST`
      : formatDateDisplay(dateISO);

    hide("loading");
    show("report-content");
  } catch (err) {
    hide("loading");
    show("empty-state");
    document.getElementById("header-meta").textContent = "—";
  }
}

// ── Archive ───────────────────────────────────────────────────────────────────

let archiveOpen = false;
let loadedDates = [];

function toggleArchive() {
  archiveOpen = !archiveOpen;
  const dropdown = document.getElementById("archive-dropdown");
  const arrow = document.getElementById("archive-arrow");
  dropdown.classList.toggle("open", archiveOpen);
  arrow.textContent = archiveOpen ? "▴" : "▾";
}

async function buildArchive() {
  // Fetch the manifest of available reports
  try {
    const res = await fetch(`${REPORTS_BASE}manifest.json`, { cache: "no-store" });
    if (!res.ok) return;
    const dates = await res.json(); // array of ISO date strings, newest first
    loadedDates = dates;
    renderArchiveDropdown(dates);
  } catch {
    // No manifest yet — silently skip
  }
}

function renderArchiveDropdown(dates) {
  const container = document.getElementById("archive-dropdown");
  container.innerHTML = "";

  if (!dates.length) {
    container.innerHTML = '<p style="padding:12px 16px;color:var(--text-muted);font-size:13px;">Sin reportes anteriores</p>';
    return;
  }

  dates.forEach((iso) => {
    const btn = document.createElement("button");
    btn.className = "archive-item";
    btn.textContent = formatDateDisplay(iso);
    btn.onclick = () => {
      loadReport(iso);
      setActiveTab("archive", iso);
      toggleArchive();
    };
    container.appendChild(btn);
  });
}

// ── Tab state ─────────────────────────────────────────────────────────────────

let currentDate = todayISO();

function showToday() {
  currentDate = todayISO();
  setActiveTab("today", currentDate);
  loadReport(currentDate);
}

function setActiveTab(tab, dateISO) {
  currentDate = dateISO;

  document.getElementById("tab-today").classList.toggle("active", tab === "today");
  document.getElementById("tab-archive").classList.toggle("active", tab === "archive");

  // Update archive item highlights
  document.querySelectorAll(".archive-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.date === dateISO);
  });
}

// ── Close archive on outside click ────────────────────────────────────────────

document.addEventListener("click", (e) => {
  const wrapper = document.querySelector(".archive-wrapper");
  if (archiveOpen && !wrapper.contains(e.target)) {
    toggleArchive();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

(async () => {
  await buildArchive();
  showToday();
})();
