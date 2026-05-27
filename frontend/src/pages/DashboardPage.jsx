import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDatasetFileUrl, getDatasetStatus, ingestDataset } from "../services/coverApi";

function maxSeverity(issues = []) {
  const order = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
  let top = "LOW";
  issues.forEach((issue) => {
    const sev = String(issue?.severity || "LOW").toUpperCase();
    if (order[sev] > order[top]) top = sev;
  });
  return issues.length ? top : "LOW";
}

function severityTone(level) {
  if (level === "CRITICAL") return "bg-red-900 text-white";
  if (level === "HIGH") return "bg-red-100 text-red-700";
  if (level === "MEDIUM") return "bg-orange-100 text-orange-700";
  return "bg-yellow-100 text-yellow-800";
}

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

export default function DashboardPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const timerRef = useRef(null);

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      setLoading(true);
      setError("");
      try {
        let payload = await ingestDataset(false);
        if (!active) return;
        setStatus(payload);

        while (active && (payload?.summary?.processing_queue_count ?? 0) > 0) {
          await new Promise((resolve) => {
            timerRef.current = setTimeout(resolve, 1200);
          });
          payload = await ingestDataset(false);
          if (!active) return;
          setStatus(payload);
        }

        const finalPayload = await getDatasetStatus();
        if (active) setStatus(finalPayload);
      } catch (err) {
        if (active) setError(err.message || "Failed to load publishing ingestion dashboard.");
      } finally {
        if (active) setLoading(false);
      }
    };

    bootstrap();

    return () => {
      active = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const summary = status?.summary || {};
  const jobs = status?.jobs || [];
  const visibleJobs = jobs.filter((job) => {
    const statusText = String(job?.status || "").toUpperCase();
    if (statusFilter !== "ALL" && statusText !== statusFilter) return false;
    if (severityFilter !== "ALL" && maxSeverity(job.issues || []) !== severityFilter) return false;
    return true;
  });

  const openDetailsPage = (job) => {
    navigate(`/book/${encodeURIComponent(job.filename)}`, { state: { job } });
  };

  return (
    <section className="mx-auto max-w-7xl space-y-6">
      <header>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Publishing Production QA Console</h2>
            <p className="text-slate-600">Automated one-by-one ingestion and validation pipeline for sample publishing covers.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => navigate("/customer-email")}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-brand-700"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 6h16v12H4z" />
                <path d="M4 8l8 6 8-6" />
              </svg>
              <span>Customer Email</span>
            </button>
            <button
              type="button"
              onClick={() => navigate("/airtable-sync")}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
              <span>Airtable Sync</span>
            </button>
          </div>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Total Files Detected</p><p className="mt-1 text-2xl font-bold text-slate-900">{summary.total_files_detected ?? 0}</p></article>
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Processing Queue</p><p className="mt-1 text-2xl font-bold text-slate-900">{summary.processing_queue_count ?? 0}</p></article>
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Completed Jobs</p><p className="mt-1 text-2xl font-bold text-slate-900">{summary.completed_jobs ?? 0}</p></article>
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">PASS</p><p className="mt-1 text-2xl font-bold text-emerald-700">{summary.pass_count ?? 0}</p></article>
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">REVIEW_NEEDED</p><p className="mt-1 text-2xl font-bold text-amber-700">{summary.review_needed_count ?? 0}</p></article>
        <article className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Overlap Detections</p><p className="mt-1 text-2xl font-bold text-red-700">{summary.overlap_detections ?? 0}</p></article>
      </div>

      <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Processed Covers</h3>
            <p className="mt-1 text-xs text-slate-500">{status?.last_run ? `Last ingestion update: ${status.last_run}` : "No ingestion run yet."}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="text-xs text-slate-600">
              Status
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="ml-2 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
              >
                <option value="ALL">All</option>
                <option value="PASS">PASS</option>
                <option value="REVIEW_NEEDED">REVIEW_NEEDED</option>
                <option value="INVALID_FILENAME">INVALID_FILENAME</option>
              </select>
            </label>
            <label className="text-xs text-slate-600">
              Severity
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="ml-2 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
              >
                <option value="ALL">All</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </label>
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2">Preview</th>
                <th>ISBN</th>
                <th>Status</th>
                <th>Severity</th>
                <th>Pipeline Status</th>
                <th>Airtable</th>
                <th>Confidence</th>
                <th>Readiness</th>
              </tr>
            </thead>
            <tbody>
              {visibleJobs.map((job, idx) => (
                <tr
                  key={`${job.filename}-${job.job_id || "none"}`}
                  className={`cursor-pointer border-t border-slate-100 ${idx % 2 === 0 ? "bg-white" : "bg-slate-50/70"} hover:bg-sky-50`}
                  onClick={() => openDetailsPage(job)}
                >
                  <td className="py-2">
                    <img
                      src={getDatasetFileUrl(job.filename)}
                      alt={job.filename}
                      className="h-10 w-8 rounded border border-slate-200 object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  </td>
                  <td>{job.isbn || "-"}</td>
                  <td>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${job.status === "PASS" ? "bg-emerald-100 text-emerald-700" : job.status === "REVIEW_NEEDED" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                      {job.status}
                    </span>
                  </td>
                  <td>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${severityTone(maxSeverity(job.issues || []))}`}>
                      {maxSeverity(job.issues || [])}
                    </span>
                  </td>
                  <td><span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{job.pipeline_status}</span></td>
                  <td>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${resolvedAirtableStatus(job).toLowerCase().startsWith("synced") ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                      {resolvedAirtableStatus(job)}
                    </span>
                  </td>
                  <td>{job.confidence_score}</td>
                  <td>{job.readiness_score}</td>
                </tr>
              ))}
              {visibleJobs.length === 0 && (
                <tr className="border-t border-slate-100">
                  <td className="py-4 text-sm text-slate-500" colSpan={8}>No detected files to display yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>

      {loading && <p className="text-sm text-slate-500">Processing one file at a time...</p>}
      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}
    </section>
  );
}
