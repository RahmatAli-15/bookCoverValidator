import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDatasetFileUrl, getDatasetStatus } from "../services/coverApi";

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

export default function CustomerCommsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [activeView, setActiveView] = useState("email");

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
        if (active) setError(err.message || "Failed to load customer communication data.");
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Customer Email & Airtable Sync</h2>
          <p className="text-slate-600">Book-wise communication and sync status overview.</p>
          <div className="mt-3 inline-flex rounded-lg border border-slate-300 bg-white p-1">
            <button
              type="button"
              onClick={() => setActiveView("email")}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${activeView === "email" ? "bg-brand-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}
            >
              Customer Email
            </button>
            <button
              type="button"
              onClick={() => setActiveView("airtable")}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${activeView === "airtable" ? "bg-emerald-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}
            >
              Airtable
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={() => navigate("/")}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          Back To Dashboard
        </button>
      </header>

      {loading && <p className="text-sm text-slate-500">Loading customer communication records...</p>}
      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}

      {!loading && !error && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <article
              key={`${job.filename}-${job.job_id || "none"}`}
              className="cursor-pointer rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 hover:bg-slate-50"
              onClick={() => setSelectedJob(job)}
            >
              <div className="flex items-start gap-3">
                <img
                  src={getDatasetFileUrl(job.filename)}
                  alt={job.filename}
                  className="h-16 w-12 rounded border border-slate-200 object-cover"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{job.filename}</p>
                  <p className="text-xs text-slate-500">ISBN: {job.isbn || "-"}</p>
                </div>
              </div>

              <div className="mt-4 space-y-3 text-xs">
                {activeView === "email" ? (
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="font-semibold text-slate-800">Email Information</p>
                    <p className="mt-1 text-slate-600"><span className="font-medium">To:</span> {job?.email_preview?.recipient_email || "-"}</p>
                    <p className="text-slate-600"><span className="font-medium">Subject:</span> {job?.email_preview?.subject || "No subject"}</p>
                    <p className="text-slate-600"><span className="font-medium">Status:</span> {job?.email_preview?.status || "pending"}</p>
                  </div>
                ) : (
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="font-semibold text-slate-800">Airtable Sync Information</p>
                    <p className="mt-1 text-slate-600"><span className="font-medium">Status:</span> {resolvedAirtableStatus(job)}</p>
                    <p className="text-slate-600"><span className="font-medium">Record ID:</span> {job?.airtable_payload?.record_id || fallbackRecordId(job)}</p>
                    <p className="text-slate-500"><span className="font-medium">Spreadsheet:</span> {localSpreadsheetLabel(job)}</p>
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/55 p-3 sm:p-6" onClick={() => setSelectedJob(null)}>
          <div
            className="mx-auto max-h-[92vh] max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Full Customer Communication Details</h3>
                <p className="text-sm text-slate-600">{selectedJob.filename}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
            </div>

            {activeView === "email" ? (
              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                <p className="font-semibold text-slate-900">Email Information</p>
                <p className="mt-2 text-slate-700"><span className="font-medium">To:</span> {selectedJob?.email_preview?.recipient_email || "-"}</p>
                <p className="text-slate-700"><span className="font-medium">Subject:</span> {selectedJob?.email_preview?.subject || "No subject"}</p>
                <p className="text-slate-700"><span className="font-medium">Status:</span> {selectedJob?.email_preview?.status || "pending"}</p>
                <p className="mt-2 text-xs text-slate-500 whitespace-pre-wrap">{selectedJob?.email_preview?.body || "No email body available."}</p>
              </div>
            ) : (
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
            )}

          </div>
        </div>
      )}
    </section>
  );
}
