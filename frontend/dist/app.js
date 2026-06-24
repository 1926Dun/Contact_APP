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

      const log = await res.json();
      resultsContent.innerHTML = `
        <div class="result-card">
          <h3>Log received</h3>
          <pre>${escapeHtml(log.text)}</pre>
          <p class="result-meta">
            ID: ${log.id} | Source: ${log.source}${log.filename ? " | File: " + escapeHtml(log.filename) : ""} | ${log.created_at}
          </p>
        </div>
      `;
      results.hidden = false;
    } catch {
      alert("Could not reach the server.");
    } finally {
      assessBtn.disabled = false;
      assessBtn.textContent = "Assess";
    }
  });
});

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
