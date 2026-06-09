let token = null;

const state = {
  dashboard: null,
  logs: [],
  selected: null,
  completedFilter: "all",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function statusLabel(status) {
  const map = {
    received: ["Otrzymane", "badge-blue"],
    queued: ["W kolejce", "badge-amber"],
    completed: ["Zakończone", "badge-green"],
    sent: ["Wysłane", "badge-green"],
    cancelled: ["Anulowane", "badge-red"],
    error: ["Błąd", "badge-red"],
  };
  return map[status] || [status || "unknown", "badge-gray"];
}

function prettyLabel(value) {
  return String(value || "-")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}

function renderCard(item, actionHtml = "", extraAttrs = "") {
  const [label, badgeClass] = statusLabel(item.status);
  const routeText = (item.route || []).join(" → ") || "-";
  const feeText = item.fee_total ? `Opłata ${item.fee_total}` : "Opłata -";
  const etaText = item.eta_seconds ? `ETA ${item.eta_seconds}s` : "ETA -";
  return `
    <article class="tx-card" data-uetr="${escapeHtml(item.uetr || "")}" ${extraAttrs}>
      <div class="tx-head">
        <div>
          <div class="tx-title">${escapeHtml(item.message_id || item.uetr)}</div>
              <div class="tx-subtitle">${escapeHtml(item.sender || "-")} → ${escapeHtml(item.receiver || item.bank || "-")}</div>
              <div class="tx-subtitle" style="font-size:0.78rem;color:var(--muted);">Trasa: ${escapeHtml(routeText)}</div>
        </div>
        <span class="badge ${badgeClass}">${escapeHtml(label)}</span>
      </div>
      <div class="tx-meta">
        <span>${escapeHtml(item.amount || "-")} ${escapeHtml(item.currency || "")}</span>
        <span>${escapeHtml(item.uetr || "")}</span>
      </div>
      <div class="tx-meta">
        <span>${escapeHtml(feeText)}</span>
        <span>${escapeHtml(etaText)}</span>
      </div>
      <div class="tx-footer">
        <span>${escapeHtml(item.details || item.timestamp || "")}</span>
        ${actionHtml}
      </div>
    </article>
  `;
}

function renderDetails(item) {
  if (!item) {
    document.getElementById("details-status-badge").className =
      "badge badge-gray";
    document.getElementById("details-status-badge").textContent = "Brak wyboru";
    return `<div class="empty-state">Wybierz transakcję, żeby zobaczyć szczegóły.</div>`;
  }

  const [label, badgeClass] = statusLabel(item.status);
  document.getElementById("details-status-badge").className =
    `badge ${badgeClass}`;
  document.getElementById("details-status-badge").textContent = label;

  return `
    <div class="details-grid">
      <div><span>Message ID</span><strong>${escapeHtml(item.message_id || "-")}</strong></div>
      <div><span>UETR</span><strong>${escapeHtml(item.uetr || "-")}</strong></div>
      <div><span>Nadawca</span><strong>${escapeHtml(item.sender || "-")}</strong></div>
      <div><span>Odbiorca / bank</span><strong>${escapeHtml(item.receiver || item.bank || "-")}</strong></div>
      <div><span>Kwota</span><strong>${escapeHtml(item.amount || "-")} ${escapeHtml(item.currency || "")}</strong></div>
      <div><span>Status</span><strong>${escapeHtml(label)}</strong></div>
      <div><span>Czas</span><strong>${escapeHtml(item.timestamp || "-")}</strong></div>
      <div><span>Szczegóły</span><strong>${escapeHtml(item.details || "-")}</strong></div>
      <div><span>Opłata</span><strong>${escapeHtml(item.fee_total || "-")}</strong></div>
      <div><span>Podział opłat</span><strong>${escapeHtml(item.fee_split || "-")}</strong></div>
      <div><span>Szacowany czas</span><strong>${escapeHtml(item.eta_seconds || "-")}</strong></div>
      <div style="grid-column: 1 / -1"><span>Trasa</span><strong>${escapeHtml((item.route || []).join(" → ") || "-")}</strong></div>
    </div>
  `;
}

function updateCounters(dashboard) {
  const counts = dashboard.metrics || { incoming: 0, pending: 0, completed: 0 };
  [
    ["count-incoming", counts.incoming],
    ["count-pending", counts.pending],
    ["count-completed", counts.completed],
    ["count-incoming-badge", counts.incoming],
    ["count-pending-badge", counts.pending],
    ["count-completed-badge", counts.completed],
  ].forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  });
}

function renderDashboard(dashboard) {
  state.dashboard = dashboard;
  updateCounters(dashboard);

  const incomingEl = document.getElementById("incoming-list");
  const pendingEl = document.getElementById("pending-list");
  const completedEl = document.getElementById("completed-list");

  incomingEl.innerHTML =
    (dashboard.incoming || [])
      .map((item) =>
        renderCard(
          item,
          `<button class="mini-btn" data-send="${escapeHtml(item.uetr)}">Wyślij</button>`,
        ),
      )
      .join("") ||
    `<div class="empty-state">Brak przychodzących płatności</div>`;

  pendingEl.innerHTML =
    (dashboard.pending || [])
      .map((item) =>
        renderCard(
          item,
          `<button class="mini-btn" data-cancel="${escapeHtml(item.uetr)}">Cancel</button>`,
        ),
      )
      .join("") ||
    `<div class="empty-state">Brak płatności do zaakceptowania</div>`;

  const completedItems = (dashboard.completed || []).filter((item) =>
    state.completedFilter === "all"
      ? true
      : item.status === state.completedFilter,
  );

  completedEl.innerHTML =
    completedItems
      .map((item) =>
        renderCard(item, "", `data-status="${escapeHtml(item.status || "")}"`),
      )
      .join("") ||
    `<div class="empty-state">Brak zakończonych transakcji</div>`;

  document.querySelectorAll("[data-cancel]").forEach((button) => {
    button.addEventListener("click", async () => {
      const uetr = button.getAttribute("data-cancel");
      const headers = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(`/api/cancel/${uetr}`, {
        method: "POST",
        headers,
      });
      const data = await response.json();
      document.getElementById("send-result").textContent = JSON.stringify(
        { status: response.status, body: data },
        null,
        2,
      );
      await refreshAll();
    });
  });

  document.querySelectorAll("[data-send]").forEach((button) => {
    button.addEventListener("click", async () => {
      const uetr = button.getAttribute("data-send");
      const headers = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(`/api/send/${uetr}`, {
        method: "POST",
        headers,
      });
      const data = await response.json();
      document.getElementById("send-result").textContent = JSON.stringify(
        { status: response.status, body: data },
        null,
        2,
      );
      await refreshAll();
    });
  });

  document.querySelectorAll("[data-uetr]").forEach((card) => {
    card.addEventListener("click", () => {
      const uetr = card.getAttribute("data-uetr");
      const selected =
        [
          ...(dashboard.incoming || []),
          ...(dashboard.pending || []),
          ...(dashboard.completed || []),
        ].find((item) => item.uetr === uetr) || null;
      state.selected = selected;
      document.getElementById("details-panel").innerHTML =
        renderDetails(selected);
    });
  });
}

async function loadBanks() {
  const select = document.getElementById("bank-select");
  if (!select) return;

  const response = await fetch("/api/banks");
  const data = await response.json();
  const banks = data.banks || [];

  select.innerHTML = banks
    .map(
      (bank) =>
        `<option value="${escapeHtml(bank.bic)}">${escapeHtml(bank.name)} (${escapeHtml(bank.bic)}) — ${escapeHtml(bank.currency)}</option>`,
    )
    .join("");
}

async function getToken() {
  const bankBic = document.getElementById("bank-select")?.value || "";
  const response = await fetch("/api/token", {
    method: "POST",
    body: new URLSearchParams({
      client_id: "test-client",
      client_secret: "test-secret",
      bank_bic: bankBic,
    }),
  });
  const data = await response.json();
  if (data.access_token) {
    token = data.access_token;
    const bank = data.bank || {};
    document.getElementById("token-box").innerHTML = `
      <strong>Token gotowy</strong>
      <div class="token-bank">
        <span>Bank</span>
        <strong>${escapeHtml(bank.name || "-")}</strong>
        <span>BIC</span>
        <strong>${escapeHtml(bank.bic || "-")}</strong>
        <span>Kraj</span>
        <strong>${escapeHtml(bank.country || "-")}</strong>
        <span>Waluta</span>
        <strong>${escapeHtml(bank.currency || "-")}</strong>
      </div>
      <code>${escapeHtml(token)}</code>
    `;
  } else {
    document.getElementById("token-box").textContent = JSON.stringify(data);
  }
}

async function sendMessage() {
  const file = document.getElementById("xml-file").files[0];
  if (!file) return alert("Wybierz plik XML, np. payment.xml");

  const headers = { "Content-Type": "application/xml" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch("/swift/message", {
    method: "POST",
    headers,
    body: await file.text(),
  });
  const data = await response.json();
  document.getElementById("send-result").textContent = JSON.stringify(
    { status: response.status, body: data },
    null,
    2,
  );
  await refreshAll();
}

async function refreshLogs() {
  const response = await fetch("/api/logs");
  const data = await response.json();
  state.logs = data.lines || [];
  document.getElementById("logs").textContent = state.logs.join("\n");
}

async function refreshAll() {
  const response = await fetch("/api/dashboard");
  const dashboard = await response.json();
  renderDashboard(dashboard);
  document.getElementById("details-panel").innerHTML = renderDetails(
    state.selected,
  );
  await refreshLogs();
}

function bindStatusFilters() {
  document
    .querySelectorAll("#status-filters [data-filter]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        state.completedFilter = button.getAttribute("data-filter") || "all";
        document
          .querySelectorAll("#status-filters [data-filter]")
          .forEach((item) => {
            item.classList.toggle("is-active", item === button);
          });
        await refreshAll();
      });
    });
}

document.getElementById("get-token").addEventListener("click", getToken);
document.getElementById("send-msg").addEventListener("click", sendMessage);
document.getElementById("refresh-all").addEventListener("click", refreshAll);
document.getElementById("refresh-logs").addEventListener("click", refreshLogs);

bindStatusFilters();
loadBanks();
refreshAll();
setInterval(refreshAll, 5000);
