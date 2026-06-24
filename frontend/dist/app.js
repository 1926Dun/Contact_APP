document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("health-status");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    status.textContent = data.status === "ok" ? "Connected" : "Service unavailable";
  } catch {
    status.textContent = "Cannot reach server";
  }
});
