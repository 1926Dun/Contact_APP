document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("health-status");
  const tabs = document.querySelectorAll(".tab");
  const pastePanel = document.getElementById("tab-paste");
  const uploadPanel = document.getElementById("tab-upload");
  const textarea = document.getElementById("log-text");
  const fileInput = document.getElementById("log-file");
  const fileDrop = document.getElementById("file-drop");
  const fileName = document.getElementById("file-name");
  const assessBtn = document.getElementById("assess-btn");
  const results = document.getElementById("results");
  const resultsContent = document.getElementById("results-content");

  let activeTab = "paste";
  let selectedFile = null;

  // Health check
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    status.textContent = data.status === "ok" ? "Connected" : "Service unavailable";
  } catch {
    status.textContent = "Cannot reach server";
  }

  // Tab switching
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

  // Drag and drop
  fileDrop.addEventListener("dragover", e => { e.preventDefault(); fileDrop.classList.add("dragover"); });
  fileDrop.addEventListener("dragleave", () => fileDrop.classList.remove("dragover"));
  fileDrop.addEventListener("drop", e => {
    e.preventDefault();
    fileDrop.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith(".txt")) {
      selectedFile = file;
      fileName.textContent = file.name;
    }
  });

  // Submit
  assessBtn.addEventListener("click", async () => {
    assessBtn.disabled = true;
    assessBtn.textContent = "Assessing...";
    results.hidden = true;

    try {
      let res;
      if (activeTab === "upload" && selectedFile) {
        const form = new FormData();
        form.append("file", selectedFile);
        res = await fetch("/api/assess", { method: "POST", body: form });
      } else if (activeTab === "paste" && textarea.value.trim()) {
        res = await fetch("/api/assess/json", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textarea.value }),
        });
      } else {
        alert("Please paste a log or upload a .txt file.");
        return;
      }

      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Assessment failed");
        return;
      }

      const data = await res.json();
      resultsContent.innerHTML = renderAssessment(data);
      results.hidden = false;
    } catch {
      alert("Could not reach the server.");
    } finally {
      assessBtn.disabled = false;
      assessBtn.textContent = "Assess";
    }
  });
});

function renderAssessment(data) {
  const { log, assessment } = data;
  const a = assessment;

  let html = `<div class="result-card">
    <h3>Summary</h3>
    <p>${escapeHtml(a.summary)}</p>
    <p class="result-meta">Log ID: ${log.id} | ${log.created_at}</p>
  </div>`;

  // Metadata
  const m = a.metadata;
  if (m.reference_number || m.date || m.location) {
    html += `<div class="result-card"><h3>Log details</h3><ul>`;
    if (m.reference_number) html += `<li>Reference: ${escapeHtml(m.reference_number)}</li>`;
    if (m.date) html += `<li>Date: ${escapeHtml(m.date)}</li>`;
    if (m.times && m.times.length) html += `<li>Time(s): ${m.times.map(escapeHtml).join(", ")}</li>`;
    if (m.location) html += `<li>Location: ${escapeHtml(m.location)}</li>`;
    html += `</ul></div>`;
  }

  // People
  if (a.people.length) {
    html += `<div class="result-card"><h3>People</h3><table class="data-table">
      <tr><th>Name</th><th>Role</th><th>Basis</th></tr>`;
    for (const p of a.people) {
      html += `<tr><td>${escapeHtml(p.name)}</td>
        <td><span class="role-badge role-${p.role}">${escapeHtml(p.role)}</span></td>
        <td>${escapeHtml(p.basis)}</td></tr>`;
    }
    html += `</table></div>`;
  }

  // Vulnerabilities
  if (a.vulnerabilities.length) {
    html += `<div class="result-card"><h3>Vulnerabilities</h3><ul>`;
    for (const v of a.vulnerabilities) {
      html += `<li><strong>${escapeHtml(v.indicator)}</strong> (${escapeHtml(v.person)}): ${escapeHtml(v.detail)}</li>`;
    }
    html += `</ul></div>`;
  }

  // Candidate crimes
  if (a.candidates.length) {
    html += `<div class="result-card"><h3>Candidate crimes</h3>`;
    for (const c of a.candidates) {
      const band = c.certainty >= 70 ? "high" : c.certainty >= 40 ? "mid" : "low";
      html += `<div class="candidate">
        <div class="candidate-header">
          <span class="certainty-badge certainty-${band}">${c.certainty}%</span>
          <strong>${escapeHtml(c.offence_title)}</strong>
        </div>
        <p class="candidate-legislation">${escapeHtml(c.legislation)}${c.classification_code ? " [" + escapeHtml(c.classification_code) + "]" : ""}${c.notifiable ? " — Notifiable" : ""}</p>
        <p>${escapeHtml(c.rationale)}</p>`;

      if (c.points_to_prove && c.points_to_prove.length) {
        html += `<details><summary>Points to prove (${c.points_to_prove.length})</summary><table class="data-table ptp-table">
          <tr><th>Point</th><th>Status</th><th>Evidence</th></tr>`;
        for (const pt of c.points_to_prove) {
          const cls = pt.status === "met" ? "ptp-met" : pt.status === "not_met" ? "ptp-notmet" : "ptp-unclear";
          html += `<tr class="${cls}"><td>${escapeHtml(pt.point)}</td>
            <td>${escapeHtml(pt.status)}</td>
            <td>${escapeHtml(pt.supporting_text)}</td></tr>`;
        }
        html += `</table></details>`;
      }

      if (c.nsir_alternative) html += `<p class="result-meta">NSIR alternative: ${escapeHtml(c.nsir_alternative)}</p>`;
      if (c.guidance_applied && c.guidance_applied.length) html += `<p class="result-meta">Guidance: ${c.guidance_applied.map(escapeHtml).join(", ")}</p>`;
      html += `</div>`;
    }
    html += `</div>`;
  }

  return html;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
