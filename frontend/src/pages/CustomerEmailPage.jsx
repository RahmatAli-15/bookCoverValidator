import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDatasetFileUrl, getDatasetStatus } from "../services/coverApi";

export default function CustomerEmailPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);

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
        if (active) setError(err.message || "Failed to load customer email data.");
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
          <h2 className="text-2xl font-bold text-slate-900">Customer Email</h2>
          <p className="text-slate-600">Book-wise email notification details.</p>
        </div>
        <button type="button" onClick={() => navigate("/")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
          Back To Dashboard
        </button>
      </header>

      {loading && <p className="text-sm text-slate-500">Loading customer email records...</p>}
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
                <img src={getDatasetFileUrl(job.filename)} alt={job.filename} className="h-16 w-12 rounded border border-slate-200 object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{job.filename}</p>
                  <p className="text-xs text-slate-500">ISBN: {job.isbn || "-"}</p>
                </div>
              </div>
              <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs">
                <p className="font-semibold text-slate-800">Email Information</p>
                <p className="mt-1 text-slate-600"><span className="font-medium">To:</span> {job?.email_preview?.recipient_email || "-"}</p>
                <p className="text-slate-600"><span className="font-medium">Subject:</span> {job?.email_preview?.subject || "No subject"}</p>
                <p className="text-slate-600"><span className="font-medium">Status:</span> {job?.email_preview?.status || "pending"}</p>
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
                <h3 className="text-lg font-bold text-slate-900">Full Customer Email Details</h3>
                <p className="text-sm text-slate-600">{selectedJob.filename}</p>
              </div>
              <button type="button" onClick={() => setSelectedJob(null)} className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">Close</button>
            </div>
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <p className="font-semibold text-slate-900">Email Information</p>
              <p className="mt-2 text-slate-700"><span className="font-medium">To:</span> {selectedJob?.email_preview?.recipient_email || "-"}</p>
              <p className="text-slate-700"><span className="font-medium">Subject:</span> {selectedJob?.email_preview?.subject || "No subject"}</p>
              <p className="text-slate-700"><span className="font-medium">Status:</span> {selectedJob?.email_preview?.status || "pending"}</p>
              <p className="mt-2 whitespace-pre-wrap text-xs text-slate-500">{selectedJob?.email_preview?.body || "No email body available."}</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
