import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDatasetFileUrl, getDatasetStatus, getLocalSpreadsheetUrl } from "../services/coverApi";

function fallbackRecordId(job) {
  const isbn = String(job?.isbn || "UNKNOWN").trim() || "UNKNOWN";
  const jobId = job?.job_id || "NA";
  return `LOCAL-${isbn}-JOB${jobId}`;
}

function resolvedAirtableStatus(job) {
  const status = String(job?.airtable_payload?.status || "pending").toLowerCase();
  const message = String(job?.airtable_payload?.message || "").toLowerCase();
  const recordId = String(job?.airtable_payload?.record_id || fallbackRecordId(job));
  const isLocalConfiguredFallback = status === "pending" && recordId.startsWith("LOCAL-") && message.includes("not configured");
  return isLocalConfiguredFallback ? "synced" : (job?.airtable_payload?.status || "pending");
}

function localSpreadsheetLabel(job) {
  const message = String(job?.airtable_payload?.message || "");
  const match = message.match(/Saved to local spreadsheet:\s*([^\s]+)/i);
  return match?.[1] || "airtable_local_sheet.csv";
}

function buildRowsFromJobs(jobs) {
  const mapped = (jobs || []).map((job) => {
    const fields = job?.airtable_payload?.fields || {};
    return {
      record_id: job?.airtable_payload?.record_id || fallbackRecordId(job),
      ISBN: fields.ISBN || job?.isbn || "",
      filename: fields.filename || job?.filename || "",
      validation_status: fields.validation_status || job?.status || "",
      confidence_score: String(fields.confidence_score ?? job?.confidence_score ?? ""),
      readiness_score: String(fields.readiness_score ?? job?.readiness_score ?? ""),
      issue_count: String(fields.issue_count ?? (job?.issues || []).length ?? ""),
      issue_severity: fields.issue_severity || "",
      correction_instructions: fields.correction_instructions || "",
      processing_timestamp: fields.processing_timestamp || "",
      annotation_image_path: fields.annotation_image_path || "",
      revision_history: fields.revision_history || "",
    };
  });
  return mapped.filter((row) => row.ISBN || row.filename);
}

export default function AirtableSyncPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [sheetLoading, setSheetLoading] = useState(false);
  const [sheetError, setSheetError] = useState("");
  const [sheetHeaders, setSheetHeaders] = useState([]);
  const [sheetRows, setSheetRows] = useState([]);
  const [sheetRequested, setSheetRequested] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await getDatasetStatus();
        if (!active) return;
        setJobs(payload?.jobs || []);
      } catch (err) {
        if (active) setError(err.message || "Failed to load Airtable sync data.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  const showSpreadsheetData = async () => {
    setSheetRequested(true);
    setSheetLoading(true);
    setSheetError("");
    try {
      const response = await fetch(getLocalSpreadsheetUrl());
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Failed to load spreadsheet.");
      }
      const csvText = await response.text();
      const lines = csvText.split(/\r?\n/).filter((line) => line.trim() !== "");
      if (lines.length === 0) {
        setSheetHeaders([]);
        setSheetRows([]);
        return;
      }
      const headers = lines[0].split(",").map((item) => item.trim());
      const rows = lines.slice(1).map((line) => {
        const cols = line.split(",");
        const row = {};
        headers.forEach((header, idx) => {
          row[header] = (cols[idx] || "").trim();
        });
        return row;
      });
      if (rows.length === 0) {
        const fallbackRows = buildRowsFromJobs(jobs);
        if (fallbackRows.length > 0) {
          setSheetHeaders(Object.keys(fallbackRows[0]));
          setSheetRows(fallbackRows);
        } else {
          setSheetHeaders(headers);
          setSheetRows(rows);
        }
      } else {
        setSheetHeaders(headers);
        setSheetRows(rows);
      }
    } catch (err) {
      setSheetError(err.message || "Failed to load spreadsheet data.");
    } finally {
      setSheetLoading(false);
    }
  };

  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 sm:text-2xl">Airtable Sync</h2>
          <p className="text-sm text-slate-600 sm:text-base">Book-wise Airtable/local spreadsheet sync details.</p>
        </div>
        <button type="button" onClick={() => navigate("/")} className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 sm:px-3 sm:text-xs">
          Back To Dashboard
        </button>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={showSpreadsheetData}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
          Show Spreadsheet Data
        </button>
      </div>

      {sheetRequested && (
        <div className="fixed inset-0 z-50 bg-black/55 p-2 sm:p-6" onClick={() => setSheetRequested(false)}>
          <div className="mx-auto max-h-[94vh] max-w-6xl overflow-y-auto rounded-xl bg-white p-3 shadow-xl sm:rounded-2xl sm:p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-sm font-semibold text-slate-900 sm:text-base">Local Spreadsheet Data</h3>
              <button type="button" onClick={() => setSheetRequested(false)} className="rounded-lg border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 sm:px-2.5 sm:text-xs">
                Close
              </button>
            </div>
            {sheetLoading && <p className="mt-3 text-xs text-slate-500">Loading spreadsheet...</p>}
            {!!sheetError && <p className="mt-3 text-xs font-medium text-red-600">{sheetError}</p>}
            {!sheetLoading && !sheetError && sheetHeaders.length === 0 && (
              <p className="mt-3 text-xs text-slate-500">Spreadsheet is empty.</p>
            )}
            {!sheetLoading && !sheetError && sheetHeaders.length > 0 && (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-[11px] sm:text-xs">
                  <thead className="hidden text-[11px] uppercase tracking-wide text-slate-500 sm:table-header-group">
                    <tr>
                      {sheetHeaders.map((header) => (
                        <th key={header} className="border-b border-slate-200 px-2 py-2">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sheetRows.map((row, idx) => (
                      <tr key={`sheet-row-${idx}`} className="border-b border-slate-100 align-top">
                        {sheetHeaders.map((header) => (
                          <td key={`${idx}-${header}`} className="px-2 py-2 text-slate-700">
                            <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-wide text-slate-500 sm:hidden">{header}</span>
                            {row[header] || "-"}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {sheetRows.length === 0 && (
                      <tr>
                        <td colSpan={sheetHeaders.length} className="px-2 py-3 text-slate-500">No data rows yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Loading Airtable sync records...</p>}
      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}

      {!loading && !error && (
        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3">
          {jobs.map((job) => (
            <article
              key={`${job.filename}-${job.job_id || "none"}`}
              className="cursor-pointer rounded-xl border border-slate-200 bg-white p-3 shadow-sm hover:border-slate-300 hover:bg-slate-50 sm:rounded-2xl sm:p-4"
              onClick={() => setSelectedJob(job)}
            >
              <div className="flex items-start gap-3">
                <img src={getDatasetFileUrl(job.filename)} alt={job.filename} className="h-14 w-10 rounded border border-slate-200 object-cover sm:h-16 sm:w-12" onError={(e) => { e.currentTarget.style.display = "none"; }} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{job.filename}</p>
                  <p className="text-[11px] text-slate-500 sm:text-xs">ISBN: {job.isbn || "-"}</p>
                </div>
              </div>
              <div className="mt-3 rounded-lg bg-slate-50 p-2.5 text-[11px] sm:mt-4 sm:p-3 sm:text-xs">
                <p className="font-semibold text-slate-800">Airtable Sync Information</p>
                <p className="mt-1 text-slate-600"><span className="font-medium">Status:</span> {resolvedAirtableStatus(job)}</p>
                <p className="text-slate-600"><span className="font-medium">Record ID:</span> {job?.airtable_payload?.record_id || fallbackRecordId(job)}</p>
                <p className="hidden text-slate-500 sm:block"><span className="font-medium">Spreadsheet:</span> {localSpreadsheetLabel(job)}</p>
              </div>
            </article>
          ))}
        </div>
      )}

      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/55 p-3 sm:p-6" onClick={() => setSelectedJob(null)}>
          <div className="mx-auto max-h-[92vh] max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Full Airtable Sync Details</h3>
                <p className="text-sm text-slate-600">{selectedJob.filename}</p>
              </div>
              <button type="button" onClick={() => setSelectedJob(null)} className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">Close</button>
            </div>
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <p className="font-semibold text-slate-900">Airtable Sync Information</p>
              <p className="mt-2 text-slate-700"><span className="font-medium">Status:</span> {resolvedAirtableStatus(selectedJob)}</p>
              <p className="text-slate-700"><span className="font-medium">Record ID:</span> {selectedJob?.airtable_payload?.record_id || fallbackRecordId(selectedJob)}</p>
              <p className="text-slate-700"><span className="font-medium">Spreadsheet:</span> {localSpreadsheetLabel(selectedJob)}</p>
              <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Airtable Fields Payload</p>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-700">
                  {JSON.stringify(selectedJob?.airtable_payload?.fields || {}, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
