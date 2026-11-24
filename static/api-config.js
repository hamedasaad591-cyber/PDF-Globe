/* Public API base URL. Never place API tokens or secrets in this file. */
window.PDF_GLOBE_API_BASE = "https://pdf-globe.onrender.com";

/* Shared cold-start protection for standalone pages that call the API directly. */
window.PDF_GLOBE_WAIT_FOR_API_READY = async function (options = {}) {
  const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 95000;
  const retryMs = Number(options.retryMs) > 0 ? Number(options.retryMs) : 5000;
  const apiBase = String(window.PDF_GLOBE_API_BASE || window.location.origin).replace(/\\/+$/, "");
  const deadline = Date.now() + timeoutMs;
  let lastError = null;

  while (Date.now() < deadline) {
    const controller = new AbortController();
    const probeTimeout = Math.min(12000, Math.max(1000, deadline - Date.now()));
    const timer = setTimeout(() => controller.abort(), probeTimeout);
    try {
      const response = await fetch(apiBase + "/api/health", {
        cache: "no-store",
        signal: controller.signal
      });
      if (response.ok) {
        const data = await response.json();
        if (data && data.ok === true) return data;
      }
      lastError = new Error("API health returned HTTP " + response.status);
    } catch (error) {
      lastError = error;
    } finally {
      clearTimeout(timer);
    }

    const pause = Math.min(retryMs, Math.max(0, deadline - Date.now()));
    if (pause <= 0) break;
    await new Promise(resolve => setTimeout(resolve, pause));
  }

  const arabic = document.documentElement.lang === "ar";
  const message = options.message || (arabic
    ? "خادم المعالجة غير جاهز بعد محاولات متكررة. لم يتم إرسال الملف؛ حاول مجدداً بعد لحظات."
    : "The processing server did not become ready after repeated checks. Your file was not uploaded; please try again shortly.");
  const error = new Error(message);
  if (lastError) error.cause = lastError;
  throw error;
};
