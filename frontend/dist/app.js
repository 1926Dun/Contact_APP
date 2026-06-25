document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("health-status");
  const navBtns = document.querySelectorAll(".nav-btn");
  const pageNew = document.getElementById("page-new");
  const pageHistory = document.getElementById("page-history");
  const pageKnowledge = document.getElementById("page-knowledge");
  const pages = { new: pageNew, history: pageHistory, knowledge: pageKnowledge };

  const tabs = document.querySelectorAll(".tab");
  const pastePanel = document.getElementById("tab-paste");
  const uploadPanel = document.getElementById("tab-upload");
  const textarea = document.getElementById("log-text");
  const fileInput = document.getElementById("log-file");
  const fileDrop = document.getElementById("file-drop");
  const fileName = document.getElementById("file-name");
  const assessBtn = document.getElementById("assess-btn");
  const logInput = document.getElementById("log-input");
  const results = document.getElementById("results");
  const resultsContent = document.getElementById("results-content");
  const reportSection = document.getElementById("report-section");
  const reportContent = document.getElementById("report-content");
  const redactToggle = document.getElementById("redact-toggle");

  let activeTab = "paste";
  let selectedFile = null;
  let currentLogId = null;

  const errorBanner = document.getElementById("error-banner");
  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.hidden = false;
    errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => { errorBanner.hidden = true; }, 8000);
  }

  // Health check — always runs on load to clear any stale error banner
  errorBanner.hidden = true;
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.status === "ok") {
      status.textContent = "Connected";
    } else {
      status.textContent = "Service unavailable";
      showError("Server is reachable but reports a problem. Check the backend logs.");
    }
  } catch {
    status.textContent = "Cannot reach server";
    showError("Could not reach the server. Please check the backend is running.");
  }

  // Navigation
  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const page = btn.id.replace("nav-", "");
      navBtns.forEach(b => b.classList.toggle("active", b === btn));
      Object.entries(pages).forEach(([k, el]) => { el.hidden = k !== page; });
      if (page === "history") loadHistory();
      if (page === "knowledge") loadKnowledge();
    });
  });

  // Input tabs
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      activeTab = tab.dataset.tab;
      tabs.forEach(t => t.classList.toggle("active", t === tab));
      pastePanel.hidden = activeTab !== "paste";
      uploadPanel.hidden = activeTab !== "upload";
    });
  });

  // File input
  fileInput.addEventListener("change", () => {
    selectedFile = fileInput.files[0] || null;
    fileName.textContent = selectedFile ? selectedFile.name : "";
  });

  fileDrop.addEventListener("dragover", e => { e.preventDefault(); fileDrop.classList.add("dragover"); });
  fileDrop.addEventListener("dragleave", () => fileDrop.classList.remove("dragover"));
  fileDrop.addEventListener("drop", e => {
    e.preventDefault();
    fileDrop.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file && /\.(txt|pdf|docx)$/i.test(file.name)) {
      selectedFile = file;
      fileName.textContent = file.name;
    }
  });

  // New assessment reset
  document.getElementById("new-assessment-btn").addEventListener("click", resetForm);

  // Export report
  document.getElementById("export-report-btn").addEventListener("click", () => {
    const printWindow = window.open("", "_blank");
    printWindow.document.write(`<!DOCTYPE html><html><head><title>Crime Recording Report</title>
      <link rel="stylesheet" href="/styles.css">
      <style>body{background:#fff;padding:2rem;max-width:900px;margin:0 auto}
      .btn-primary,.btn-secondary,.nav-btn,.candidate-checkbox,.selection-instruction{display:none!important}
      @media print{body{padding:0}}</style>
      </head><body>${reportContent.innerHTML}</body></html>`);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  });

  // Assess
  assessBtn.addEventListener("click", async () => {
    assessBtn.disabled = true;
    assessBtn.textContent = "Assessing...";
    results.hidden = true;
    reportSection.hidden = true;

    try {
      const useRedact = redactToggle.checked;
      let res;
      if (activeTab === "upload" && selectedFile) {
        const form = new FormData();
        form.append("file", selectedFile);
        if (useRedact) form.append("redact", "true");
        res = await fetch("/api/assess", { method: "POST", body: form });
      } else if (activeTab === "paste" && textarea.value.trim()) {
        res = await fetch("/api/assess/json", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textarea.value, redact: useRedact }),
        });
      } else {
        showError("Please paste a log or upload a file.");
        return;
      }

      if (!res.ok) {
        const err = await res.json();
        showError(err.detail || "Assessment failed.");
        return;
      }

      const data = await res.json();
      currentLogId = data.log.id;
      resultsContent.innerHTML = renderAssessment(data);
      logInput.hidden = true;
      results.hidden = false;

      document.getElementById("generate-report-btn")
        ?.addEventListener("click", () => generateReport());
    } catch {
      showError("Could not reach the server. Please check the backend is running.");
    } finally {
      assessBtn.disabled = false;
      assessBtn.textContent = "Assess";
    }
  });

  function resetForm() {
    logInput.hidden = false;
    results.hidden = true;
    reportSection.hidden = true;
    textarea.value = "";
    fileInput.value = "";
    selectedFile = null;
    fileName.textContent = "";
    currentLogId = null;
  }

  async function generateReport() {
    const checkboxes = document.querySelectorAll(".candidate-checkbox:checked");
    const selected = Array.from(checkboxes).map(cb => parseInt(cb.dataset.index));

    if (selected.length === 0) {
      showError("Select at least one candidate crime to generate a report.");
      return;
    }

    const btn = document.getElementById("generate-report-btn");
    btn.disabled = true;
    btn.textContent = "Generating...";

    try {
      const res = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ log_id: currentLogId, selected_indices: selected }),
      });

      if (!res.ok) {
        const err = await res.json();
        showError(err.detail || "Report generation failed.");
        return;
      }

      const report = await res.json();
      reportContent.innerHTML = renderReport(report);
      reportSection.hidden = false;
      reportSection.scrollIntoView({ behavior: "smooth" });
    } catch {
      showError("Could not reach the server. Please check the backend is running.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate report";
    }
  }

  async function loadHistory() {
    const container = document.getElementById("history-list");
    container.innerHTML = "<p>Loading...</p>";
    try {
      const res = await fetch("/api/logs");
      const logs = await res.json();
      if (logs.length === 0) {
        container.innerHTML = "<p class='empty-state'>No assessments yet.</p>";
        return;
      }
      let html = `<table class="data-table history-table">
        <tr><th>ID</th><th>Source</th><th>Preview</th><th>Date</th><th></th></tr>`;
      for (const l of logs) {
        const preview = esc(l.text.substring(0, 80)) + (l.text.length > 80 ? "..." : "");
        html += `<tr>
          <td>${l.id}</td>
          <td>${esc(l.source)}</td>
          <td>${preview}</td>
          <td>${esc(l.created_at)}</td>
          <td><button class="btn-link view-log-btn" data-id="${l.id}">View</button></td>
        </tr>`;
      }
      html += `</table>`;
      container.innerHTML = html;

      container.querySelectorAll(".view-log-btn").forEach(btn => {
        btn.addEventListener("click", () => viewLog(parseInt(btn.dataset.id)));
      });
    } catch {
      container.innerHTML = "<p>Failed to load history.</p>";
    }
  }

  async function viewLog(logId) {
    try {
      const res = await fetch(`/api/logs/${logId}`);
      const data = await res.json();
      if (!data.assessment) {
        showError("No assessment found for this log.");
        return;
      }
      currentLogId = logId;
      resultsContent.innerHTML = renderAssessment({ log: data.log, assessment: data.assessment });
      logInput.hidden = true;
      results.hidden = false;
      reportSection.hidden = true;

      document.getElementById("nav-new").click();

      document.getElementById("generate-report-btn")
        ?.addEventListener("click", () => generateReport());
    } catch {
      showError("Failed to load log.");
    }
  }

  async function loadKnowledge() {
    const container = document.getElementById("knowledge-list");
    container.innerHTML = "<p>Loading...</p>";
    try {
      const res = await fetch("/api/knowledge");
      const data = await res.json();
      let html = `<table class="data-table">
        <tr><th>Document</th><th>File</th><th>Hash</th><th>Pages</th><th>Size</th></tr>`;
      for (const d of data.documents) {
        html += `<tr>
          <td>${esc(d.label)}</td>
          <td>${esc(d.filename)}</td>
          <td><code>${esc(d.file_hash)}</code></td>
          <td>${d.pages ?? "-"}</td>
          <td>${d.table_rows ? d.table_rows + " rows" : Math.round(d.text_length / 1024) + " KB"}</td>
        </tr>`;
      }
      html += `</table>
        <button id="refresh-knowledge-btn" class="btn-secondary" style="margin-top:1rem">Refresh documents</button>`;
      container.innerHTML = html;

      document.getElementById("refresh-knowledge-btn").addEventListener("click", async () => {
        const btn = document.getElementById("refresh-knowledge-btn");
        btn.disabled = true;
        btn.textContent = "Refreshing...";
        await fetch("/api/knowledge/refresh", { method: "POST" });
        btn.textContent = "Refresh documents";
        btn.disabled = false;
        loadKnowledge();
      });
    } catch {
      container.innerHTML = "<p>Failed to load documents.</p>";
    }
  }
});

// --- Render functions ---

function renderAssessment(data) {
  const { log, assessment } = data;
  const a = assessment;

  let html = "";

  if (data.redacted) {
    html += `<div class="redact-notice">Names and identifiers were redacted before AI processing (${data.redaction_count} items pseudonymised). Original values restored in results below.</div>`;
  }

  html += `<div class="result-card">
    <h3>Summary</h3>
    <p>${esc(a.summary)}</p>
    <p class="result-meta">Log ID: ${log.id} | ${log.created_at}</p>
  </div>`;

  const m = a.metadata;
  if (m.reference_number || m.date || m.location) {
    html += `<div class="result-card"><h3>Log details</h3><ul>`;
    if (m.reference_number) html += `<li>Reference: ${esc(m.reference_number)}</li>`;
    if (m.date) html += `<li>Date: ${esc(m.date)}</li>`;
    if (m.times && m.times.length) html += `<li>Time(s): ${m.times.map(esc).join(", ")}</li>`;
    if (m.location) html += `<li>Location: ${esc(m.location)}</li>`;
    html += `</ul></div>`;
  }

  if (a.people.length) {
    html += `<div class="result-card"><h3>People</h3>` + renderPeopleTable(a.people) + `</div>`;
  }

  if (a.vulnerabilities.length) {
    html += `<div class="result-card"><h3>Vulnerabilities</h3><ul>`;
    for (const v of a.vulnerabilities) {
      html += `<li><strong>${esc(v.indicator)}</strong> (${esc(v.person)}): ${esc(v.detail)}</li>`;
    }
    html += `</ul></div>`;
  }

  if (a.candidates.length) {
    html += `<div class="result-card"><h3>Candidate crimes</h3>
      <p class="selection-instruction">Select the crimes you agree with, then generate the report.</p>`;
    for (let i = 0; i < a.candidates.length; i++) {
      html += renderCandidate(a.candidates[i], i, true);
    }
    html += `</div>`;
  }

  if (a.counting_rules) {
    const cr = a.counting_rules;
    html += `<div class="result-card counting-rules">
      <h3>HOCR counting rules</h3>
      <p class="counting-rules-note">These rules apply to the final recording decision, not to the candidate list above.</p>
      <div class="counting-rule">
        <h4>One Crime per Victim</h4>
        <p>${esc(cr.one_crime_per_victim)}</p>
      </div>
      <div class="counting-rule">
        <h4>Finished Incident Rule</h4>
        <p>${esc(cr.finished_incident_rule)}</p>
      </div>
      <div class="counting-rule">
        <h4>Principal Crime Rule</h4>
        <p>${esc(cr.principal_crime)}</p>
      </div>
    </div>`;
  }

  if (a.candidates.length) {
    html += `<div class="result-card-action">
      <button id="generate-report-btn" class="btn-primary btn-report">Generate report</button>
    </div>`;
  }

  return html;
}

function renderCandidate(c, index, withCheckbox) {
  const band = c.certainty >= 70 ? "high" : c.certainty >= 40 ? "mid" : "low";
  let html = `<div class="candidate">
    <div class="candidate-header">`;

  if (withCheckbox) {
    html += `<input type="checkbox" class="candidate-checkbox" data-index="${index}" checked>`;
  }

  html += `<span class="certainty-badge certainty-${band}">${c.certainty}%</span>
      <strong>${esc(c.offence_title)}</strong>
    </div>
    <p class="candidate-legislation">${esc(c.legislation)}${c.classification_code ? " [" + esc(c.classification_code) + "]" : ""}${c.notifiable ? " — Notifiable" : ""}</p>
    ${renderRationale(c.rationale)}`;

  if (c.points_to_prove && c.points_to_prove.length) {
    html += `<details><summary>Points to prove (${c.points_to_prove.length})</summary>
      <table class="data-table ptp-table">
      <tr><th>Point</th><th>Status</th><th>Evidence</th></tr>`;
    for (const pt of c.points_to_prove) {
      const cls = pt.status === "met" ? "ptp-met" : pt.status === "not_met" ? "ptp-notmet" : "ptp-unclear";
      html += `<tr class="${cls}"><td>${esc(pt.point)}</td>
        <td>${esc(pt.status)}</td><td>${esc(pt.supporting_text)}</td></tr>`;
    }
    html += `</table></details>`;
  }

  if (c.nsir_alternative) html += `<p class="result-meta">NSIR alternative: ${esc(c.nsir_alternative)}</p>`;
  if (c.guidance_applied && c.guidance_applied.length) html += `<p class="result-meta">Guidance: ${c.guidance_applied.map(esc).join(", ")}</p>`;
  html += `</div>`;
  return html;
}

function renderPeopleTable(people) {
  let html = `<table class="data-table">
    <tr><th>Name</th><th>Role</th><th>Basis</th></tr>`;
  for (const p of people) {
    html += `<tr><td>${esc(p.name)}</td>
      <td><span class="role-badge role-${p.role}">${esc(p.role)}</span></td>
      <td>${esc(p.basis)}</td></tr>`;
  }
  return html + `</table>`;
}

function renderReport(r) {
  let html = `<div class="report">
    <div class="result-card report-header">
      <h2>Crime Recording Assessment Report</h2>
      <p class="result-meta">Report ID: ${r.id} | Log ID: ${r.log_id} | Generated: ${esc(r.created_at)}</p>
    </div>`;

  const m = r.metadata;
  html += `<div class="result-card"><h3>Log details</h3><ul>`;
  if (m.reference_number) html += `<li>Reference: ${esc(m.reference_number)}</li>`;
  if (m.date) html += `<li>Date: ${esc(m.date)}</li>`;
  if (m.times && m.times.length) html += `<li>Time(s): ${m.times.map(esc).join(", ")}</li>`;
  if (m.location) html += `<li>Location: ${esc(m.location)}</li>`;
  html += `</ul></div>`;

  html += `<div class="result-card"><h3>Summary</h3><p>${esc(r.summary)}</p></div>`;

  if (r.people.length) {
    html += `<div class="result-card"><h3>People</h3>` + renderPeopleTable(r.people) + `</div>`;
  }

  if (r.crimes_selected.length) {
    html += `<div class="result-card report-selected"><h3>Crimes selected for recording</h3>`;
    for (const c of r.crimes_selected) html += renderCandidate(c, 0, false);
    html += `</div>`;
  }

  if (r.crimes_not_selected.length) {
    html += `<div class="result-card report-not-selected"><h3>Crimes considered but not selected</h3>`;
    for (const c of r.crimes_not_selected) html += renderCandidate(c, 0, false);
    html += `</div>`;
  }

  if (r.document_versions && r.document_versions.length) {
    html += `<div class="result-card provenance"><h3>Provenance</h3>
      <table class="data-table">
      <tr><th>Document</th><th>File</th><th>Hash</th></tr>`;
    for (const d of r.document_versions) {
      html += `<tr><td>${esc(d.label)}</td><td>${esc(d.filename)}</td><td><code>${esc(d.file_hash)}</code></td></tr>`;
    }
    html += `</table></div>`;
  }

  html += `</div>`;
  return html;
}

function renderRationale(text) {
  const stepPattern = /Step \d+[:\s]*[A-Z]/;
  if (!stepPattern.test(text)) {
    return `<p>${esc(text)}</p>`;
  }

  // Split on "Step N" boundaries, keeping the delimiter
  const parts = text.split(/(Step \d+)/);
  let preamble = "";
  const steps = [];
  let i = 0;

  // Collect any text before the first "Step N"
  if (parts[0] && !parts[0].match(/^Step \d+$/)) {
    preamble = parts[0].trim();
    i = 1;
  }

  // Pair up "Step N" with its following text
  for (; i < parts.length; i += 2) {
    const label = parts[i] || "";
    const body = (parts[i + 1] || "").replace(/^[\s:–—-]+/, "").trim();
    if (label && body) {
      steps.push({ label, body });
    }
  }

  let html = "";
  if (preamble) html += `<p>${esc(preamble)}</p>`;
  if (steps.length) {
    html += `<ul class="rationale-steps">`;
    for (const s of steps) {
      html += `<li><strong>${esc(s.label)}:</strong> ${esc(s.body)}</li>`;
    }
    html += `</ul>`;
  }
  return html;
}

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
