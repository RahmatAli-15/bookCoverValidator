const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

function parseResponse(xhr, fallbackMessage) {
  try {
    const payload = JSON.parse(xhr.responseText || "{}");
    if (xhr.status >= 200 && xhr.status < 300) return payload;
    throw new Error(payload.detail || fallbackMessage);
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error(fallbackMessage);
  }
}

export function uploadCover(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);
    xhr.open("POST", `${API_BASE_URL}/covers/upload`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && typeof onProgress === "function") {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        resolve(parseResponse(xhr, "Upload failed."));
      } catch (error) {
        reject(error);
      }
    };
    xhr.onerror = () => reject(new Error("Network error while uploading."));
    xhr.send(formData);
  });
}

export async function getCoverResults(jobId) {
  const response = await fetch(`${API_BASE_URL}/covers/results/${jobId}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Failed to fetch OCR results.");
  return payload;
}

export async function validateCover(jobId) {
  const response = await fetch(`${API_BASE_URL}/covers/validate/${jobId}`, { method: "POST" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Validation failed.");
  return payload;
}

export async function getReviewQueue(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await fetch(`${API_BASE_URL}/admin/review-queue${query}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Failed to load review queue.");
  return payload;
}

export async function ingestDataset(force = false) {
  const response = await fetch(`${API_BASE_URL}/admin/dataset/ingest${force ? "?force=true" : ""}`, { method: "POST" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Failed to ingest sample covers.");
  return payload;
}

export async function getDatasetStatus() {
  const response = await fetch(`${API_BASE_URL}/admin/dataset/status`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Failed to load ingestion status.");
  return payload;
}

export function getDatasetFileUrl(filename) {
  return `${API_BASE_URL}/admin/dataset/file/${encodeURIComponent(filename)}`;
}

export function getAnnotationImageUrl(jobId) {
  return `${API_BASE_URL}/covers/annotations/${jobId}`;
}

export function getLocalSpreadsheetUrl() {
  return `${API_BASE_URL}/admin/airtable/local-sheet`;
}
