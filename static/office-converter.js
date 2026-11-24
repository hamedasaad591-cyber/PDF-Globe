(() => {
  "use strict";
  const isArabic = document.documentElement.lang === "ar";
  const kind = document.body.dataset.converter;
  const config = {
    excel: { endpoint: "/api/pdf/to-excel", extension: "xlsx" },
    powerpoint: { endpoint: "/api/pdf/to-powerpoint", extension: "pptx" }
  };
  const selectedTool = config[kind];
  const apiBase = String(window.PDF_GLOBE_API_BASE || "https://pdf-globe.onrender.com").replace(/\/+$/, "");
  const input = document.getElementById("fileInput");
  const dropZone = document.getElementById("dropZone");
  const browseButton = document.getElementById("browseButton");
  const convertButton = document.getElementById("convertButton");
  const fileName = document.getElementById("fileName");
  const status = document.getElementById("status");
  const maxBytes = 50 * 1024 * 1024;
  let selectedFile = null;
  let busy = false;

  const messages = isArabic ? {
    noFile: "لم يتم اختيار ملف بعد",
    invalid: "يرجى اختيار ملف PDF صالح.",
    tooLarge: "حجم الملف يتجاوز 50 MB.",
    working: "جارٍ رفع الملف وتحويله. لا تغلق الصفحة...",
    success: "اكتمل التحويل وبدأ تنزيل الملف.",
    failed: "تعذر تنفيذ التحويل. حاول مرة أخرى.",
    empty: "الملف الناتج فارغ؛ تعذر إكمال التحويل."
  } : {
    noFile: "No file selected yet",
    invalid: "Please choose a valid PDF file.",
    tooLarge: "The file is larger than 50 MB.",
    working: "Uploading and converting your file. Please keep this page open...",
    success: "Conversion complete. Your download has started.",
    failed: "The conversion could not be completed. Please try again.",
    empty: "The generated file is empty; conversion could not be completed."
  };

  function setStatus(message, type) {
    status.textContent = message;
    status.dataset.kind = type || "";
  }

  function setFile(file) {
    setStatus("");
    if (!file) {
      selectedFile = null;
      fileName.textContent = messages.noFile;
      convertButton.disabled = true;
      return;
    }
    const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    if (!isPdf || file.size <= 0) {
      selectedFile = null;
      fileName.textContent = messages.noFile;
      convertButton.disabled = true;
      setStatus(messages.invalid, "error");
      return;
    }
    if (file.size > maxBytes) {
      selectedFile = null;
      fileName.textContent = messages.noFile;
      convertButton.disabled = true;
      setStatus(messages.tooLarge, "error");
      return;
    }
    selectedFile = file;
    fileName.textContent = file.name + " · " + (file.size / (1024 * 1024)).toFixed(2) + " MB";
    convertButton.disabled = false;
  }

  input.addEventListener("change", () => setFile(input.files && input.files[0]));
  browseButton.addEventListener("click", (event) => {
    event.stopPropagation();
    input.click();
  });
  dropZone.addEventListener("click", (event) => {
    if (event.target === input || event.target.closest("button")) return;
    input.click();
  });
  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  for (const eventName of ["dragenter", "dragover"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("is-dragging");
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("is-dragging");
    });
  }
  dropZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    setFile(file);
  });

  convertButton.addEventListener("click", async () => {
    if (!selectedFile || busy || !selectedTool) return;
    busy = true;
    convertButton.disabled = true;
    setStatus(messages.working);
    try {
      if (typeof window.PDF_GLOBE_WAIT_FOR_API_READY !== "function") {
        throw new Error(messages.failed);
      }
      await window.PDF_GLOBE_WAIT_FOR_API_READY();
      const form = new FormData();
      form.append("file", selectedFile);
      const response = await fetch(apiBase + selectedTool.endpoint, {
        method: "POST",
        body: form
      });
      if (!response.ok) {
        let detail = messages.failed;
        try {
          const payload = await response.json();
          if (payload && payload.detail) detail = String(payload.detail);
        } catch (_) {}
        throw new Error(detail);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error(messages.empty);
      const baseName = selectedFile.name.replace(/\.pdf$/i, "").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || "document";
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = baseName + "_converted." + selectedTool.extension;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
      setStatus(messages.success, "success");
    } catch (error) {
      setStatus(error && error.message ? error.message : messages.failed, "error");
    } finally {
      busy = false;
      convertButton.disabled = !selectedFile;
    }
  });
})();