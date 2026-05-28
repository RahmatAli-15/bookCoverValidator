import { useEffect, useMemo, useState } from "react";

import { uploadCover } from "../services/coverApi";

const ACCEPTED_TYPES = ["application/pdf", "image/png"];
const FILENAME_PATTERN = /^\d{13}_text\.(pdf|png)$/i;

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const validationError = useMemo(() => {
    if (!selectedFile) return "";
    if (!FILENAME_PATTERN.test(selectedFile.name)) return "Invalid filename. Use ISBN_text.extension (example: 1234567890123_text.pdf).";
    if (!ACCEPTED_TYPES.includes(selectedFile.type)) return "Unsupported file type. Upload only PDF or PNG files.";
    return "";
  }, [selectedFile]);

  const requirementHint = useMemo(() => {
    if (!selectedFile) return "";
    if (!FILENAME_PATTERN.test(selectedFile.name)) {
      return `Filename "${selectedFile.name}" does not match required pattern.`;
    }
    if (!ACCEPTED_TYPES.includes(selectedFile.type)) {
      return `File type "${selectedFile.type || "unknown"}" is not supported.`;
    }
    return "";
  }, [selectedFile]);

  const onPickFile = (file) => {
    setError("");
    setReport(null);
    setProgress(0);
    setSelectedFile(file || null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl("");
    }
    if (file && file.type === "image/png") setPreviewUrl(URL.createObjectURL(file));
  };

  const handleDrop = (event) => {
    event.preventDefault();
    onPickFile(event.dataTransfer.files?.[0]);
  };

  const handleUpload = async () => {
    if (!selectedFile || validationError) return;
    setIsUploading(true);
    setError("");
    setReport(null);
    try {
      const payload = await uploadCover(selectedFile, setProgress);
      setReport(payload);
    } catch (uploadError) {
      setError(uploadError.message || "QA processing failed.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Upload Cover</h2>
        <p className="text-slate-600">Upload a publishing cover and run the QA workflow.</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-5">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <div className="rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>
            <p className="text-sm font-medium text-slate-700">Drag and drop PDF/PNG cover here</p>
            <p className="mt-1 text-xs text-slate-500">Filename must be: ISBN_text.extension</p>
            <label className="mt-4 inline-block cursor-pointer rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
              Select Cover
              <input type="file" className="hidden" accept=".pdf,.png,application/pdf,image/png" onChange={(e) => onPickFile(e.target.files?.[0])} />
            </label>
          </div>

          {selectedFile && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p className="font-semibold">{selectedFile.name}</p>
              <p className="text-xs text-slate-500">{formatBytes(selectedFile.size)}</p>
            </div>
          )}

          {!!validationError && <p className="mt-3 text-sm font-medium text-red-600">{validationError}</p>}
          {!!error && <p className="mt-3 text-sm font-medium text-red-600">{error}</p>}

          {(!!validationError || !!error) && (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-semibold">Workflow Automation Requirements</p>
              <ul className="mt-2 space-y-1">
                <li>- Trigger Mechanism: Upload cover into the monitored intake flow.</li>
                <li>- File naming convention: <span className="font-semibold">ISBN_text</span> (example: <span className="font-semibold">1234567890123_text.pdf</span>).</li>
                <li>- Supported formats: <span className="font-semibold">PDF</span> and <span className="font-semibold">PNG</span>.</li>
              </ul>
              {!!requirementHint && <p className="mt-3 text-xs font-semibold text-red-700">Failure detected: {requirementHint}</p>}
              <p className="mt-1 text-xs text-amber-800">Quick fix: rename your file to the required format, for example `9789378652616_text.png`.</p>
            </div>
          )}

          <button type="button" onClick={handleUpload} disabled={!selectedFile || !!validationError || isUploading} className="mt-5 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {isUploading ? "Running QA..." : "Upload and Run QA"}
          </button>

          {isUploading && (
            <div className="mt-4">
              <div className="h-2 w-full rounded-full bg-slate-200"><div className="h-2 rounded-full bg-brand-600" style={{ width: `${progress}%` }} /></div>
              <p className="mt-1 text-right text-xs text-slate-500">{progress}%</p>
            </div>
          )}

          {report && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
              <p className="font-semibold text-emerald-800">QA completed for Job #{report.job_id}</p>
              <p className="mt-1 text-emerald-700">Status: {report.validation?.status || report.operational_summary?.validation_status}</p>
            </div>
          )}
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="text-base font-semibold text-slate-900">Preview</h3>
          <div className="mt-3 min-h-64 rounded-xl border border-slate-200 bg-slate-50 p-4">
            {previewUrl ? <img src={previewUrl} alt="Cover preview" className="h-full w-full rounded-lg object-contain" /> : <p className="text-sm text-slate-500">PNG preview appears here.</p>}
          </div>
        </article>
      </div>
    </section>
  );
}
