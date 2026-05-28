import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getAnnotationImageUrl, getDatasetFileUrl, getDatasetStatus } from "../services/coverApi";

function detailValue(value, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  return value;
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
  return isLocalConfiguredFallback ? "synced" : detailValue(job?.airtable_payload?.status, "pending");
}

function localSpreadsheetLabel(job) {
  const message = String(job?.airtable_payload?.message || "");
  const match = message.match(/Saved to local spreadsheet:\s*([^\s]+)/i);
  return match?.[1] || "airtable_local_sheet.csv";
}

function invalidFilenameDiagnostics(fileName = "") {
  const hasExt = /\.[^.]+$/.test(fileName);
  const ext = hasExt ? fileName.split(".").pop().toLowerCase() : "";
  const supportedExt = ["pdf", "png"];
  const hasSupportedExt = supportedExt.includes(ext);
  const strictPattern = /^\d{13}_text\.(pdf|png)$/i;
  const matchesStrict = strictPattern.test(fileName);
  return {
    hasExt,
    ext: ext || "none",
    hasSupportedExt,
    matchesStrict,
  };
}

function Icon({ path, className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

export default function BookDetailsPage() {
  const { filename: filenameParam } = useParams();
  const location = useLocation();
  const [job, setJob] = useState(location.state?.job || null);
  const [loading, setLoading] = useState(!location.state?.job);
  const [error, setError] = useState("");
  const [annotationMissing, setAnnotationMissing] = useState(false);
  const decodedFilename = decodeURIComponent(filenameParam || "");

  useEffect(() => {
    if (job) return;
    let active = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await getDatasetStatus();
        if (!active) return;
        const match = (payload?.jobs || []).find((item) => item?.filename === decodedFilename);
        if (!match) {
          setError("Book details not found. Please open from Dashboard again.");
          return;
        }
        setJob(match);
      } catch (err) {
        if (active) setError(err.message || "Failed to load book details.");
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [decodedFilename, job]);

  useEffect(() => {
    setAnnotationMissing(false);
  }, [job?.job_id]);

  const sourceUrl = useMemo(() => (job?.filename ? getDatasetFileUrl(job.filename) : ""), [job]);
  const annotatedUrl = useMemo(() => (job?.job_id ? getAnnotationImageUrl(job.job_id) : ""), [job]);
  const isInvalidFilename = String(job?.status || "").toUpperCase() === "INVALID_FILENAME";
  const filenameChecks = useMemo(() => invalidFilenameDiagnostics(job?.filename || decodedFilename || ""), [job?.filename, decodedFilename]);

  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-50 to-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Book Full Details</h2>
            <p className="mt-1 text-sm text-slate-600">{detailValue(decodedFilename)}</p>
          </div>
          <Link to="/" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Back to Dashboard</Link>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading details...</p>}
      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}

      {!loading && !error && job && (
        <>
          <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${job.status === "PASS" ? "bg-emerald-100 text-emerald-700" : job.status === "REVIEW_NEEDED" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-700"}`}>{detailValue(job.status)}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Pipeline: {detailValue(job.pipeline_status)}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Severity: {detailValue((job.issues || [])[0]?.severity, "LOW")}</span>
            </div>
            <h3 className="text-base font-semibold text-slate-900">Book Information</h3>
            <div className="mt-3 grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">File Name</p><p className="mt-1 text-sm font-semibold text-slate-800 break-all">{detailValue(job.filename)}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">ISBN</p><p className="mt-1 text-sm font-semibold text-slate-800">{detailValue(job.isbn)}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Airtable</p><p className="mt-1 text-sm font-semibold text-slate-800">{resolvedAirtableStatus(job)}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Confidence</p><p className="mt-1 text-xl font-bold text-slate-900">{detailValue(job.confidence_score)}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Readiness</p><p className="mt-1 text-xl font-bold text-slate-900">{detailValue(job.readiness_score)}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Issue Count</p><p className="mt-1 text-xl font-bold text-slate-900">{(job.issues || []).length}</p></div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Processing Time (ms)</p><p className="mt-1 text-xl font-bold text-slate-900">{detailValue(job.processing_time_ms)}</p></div>
            </div>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-base font-semibold text-slate-900">Images</h3>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-2">
                <p className="mb-2 text-sm font-semibold text-slate-700">Original Cover</p>
                <img src={sourceUrl} alt="Original cover" className="max-h-[58vh] w-full rounded object-contain" />
              </div>
              <div className="rounded-xl border border-slate-200 p-2">
                <p className="mb-2 text-sm font-semibold text-slate-700">Annotated Preview</p>
                {annotatedUrl && !annotationMissing ? (
                  <img src={annotatedUrl} alt="Annotated cover" className="max-h-[58vh] w-full rounded object-contain" onError={() => setAnnotationMissing(true)} />
                ) : (
                  <p className="text-sm text-slate-500">Annotation preview not available.</p>
                )}
              </div>
            </div>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Icon path="M12 20h9M3 20h3m0 0a9 9 0 119 0m-9 0H3" />
              <h3>Summary And Guidance</h3>
            </div>
            <p className="mt-2 rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-slate-800">{detailValue(job.executive_summary, "No summary available.")}</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {(job.operational_guidance || []).map((line, idx) => (
                <li key={`guide-${idx}`} className="flex items-start gap-2 rounded-lg bg-slate-50 p-2">
                  <span className="mt-0.5 text-emerald-700"><Icon path="M20 6L9 17l-5-5" className="h-4 w-4" /></span>
                  <span>{line}</span>
                </li>
              ))}
              {(!job.operational_guidance || job.operational_guidance.length === 0) && <li>- No guidance generated.</li>}
            </ul>
          </article>

          {isInvalidFilename && (
            <article className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
              <h3 className="text-base font-semibold text-amber-900">Upload Requirement Failure Details</h3>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-amber-200 bg-white p-3 text-sm text-slate-700">
                  <p className="font-semibold text-slate-900">Workflow Automation Requirements</p>
                  <p className="mt-2">1. Trigger Mechanism: Book covers uploaded to designated intake folder.</p>
                  <p>2. File naming convention: <span className="font-semibold">ISBN_text</span> (example: <span className="font-semibold">1234567890123_text.pdf</span>).</p>
                  <p>3. Supported formats: <span className="font-semibold">PDF</span> and <span className="font-semibold">PNG</span>.</p>
                </div>
                <div className="rounded-lg border border-amber-200 bg-white p-3 text-sm text-slate-700">
                  <p className="font-semibold text-slate-900">Current File Validation</p>
                  <p className="mt-2"><span className="font-medium">Detected file:</span> {detailValue(job?.filename, decodedFilename)}</p>
                  <p><span className="font-medium">Extension found:</span> {filenameChecks.ext.toUpperCase()}</p>
                  <p><span className="font-medium">Supported extension:</span> {filenameChecks.hasSupportedExt ? "YES" : "NO"}</p>
                  <p><span className="font-medium">Matches ISBN_text pattern:</span> {filenameChecks.matchesStrict ? "YES" : "NO"}</p>
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-amber-200 bg-white p-3 text-sm text-slate-700">
                <p className="font-semibold text-slate-900">How To Fix</p>
                <p className="mt-2">1. Rename the file to `13-digit-ISBN_text`.</p>
                <p>2. Keep extension as `.png` or `.pdf`.</p>
                <p>3. Re-upload using a valid name such as `9789378652616_text.png`.</p>
              </div>
            </article>
          )}

          <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Icon path="M12 9v4m0 4h.01M10.29 3.86l-8.18 14A2 2 0 003.82 21h16.36a2 2 0 001.71-3.14l-8.18-14a2 2 0 00-3.42 0z" />
              <h3>Detected Issues</h3>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {(job.issues || []).map((issue, idx) => (
                <div key={`${issue.type}-${idx}`} className="rounded-xl border border-red-100 bg-red-50 p-3 text-xs">
                  <p className="font-semibold text-slate-800">{issue.type}{issue.severity ? ` | ${issue.severity}` : ""}</p>
                  <p className="mt-1 text-slate-600">{detailValue(issue.message, "No message.")}</p>
                </div>
              ))}
              {(!job.issues || job.issues.length === 0) && <p className="text-sm text-slate-600">No issues detected.</p>}
            </div>
          </article>

          <div className="grid gap-3 lg:grid-cols-2">
            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Icon path="M4 7h16M4 12h16M4 17h16" />
                <h3>Airtable Sync Information</h3>
                <Link
                  to="/airtable-sync"
                  className="ml-auto rounded-md bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-700"
                >
                  View Spreadsheet Data
                </Link>
              </div>
              <div className="mt-2 space-y-2 text-sm text-slate-700">
                <p><span className="font-medium">Status:</span> {resolvedAirtableStatus(job)}</p>
                <p><span className="font-medium">Record ID:</span> {detailValue(job?.airtable_payload?.record_id, fallbackRecordId(job))}</p>
                <p className="text-xs text-slate-500"><span className="font-medium">Spreadsheet:</span> {localSpreadsheetLabel(job)}</p>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Airtable Payload Preview</p>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-700">{JSON.stringify(job?.airtable_payload?.fields || {}, null, 2)}</pre>
                </div>
              </div>
            </article>

            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Icon path="M4 4h16v16H4z M4 7l8 6 8-6" />
                <h3>Email Notification</h3>
              </div>
              <div className="mt-2 space-y-1 text-sm text-slate-700">
                <p><span className="font-medium">To:</span> {detailValue(job?.email_preview?.recipient_email, "author@example.com")}</p>
                <p><span className="font-medium">Subject:</span> {detailValue(job?.email_preview?.subject, "Publishing QA Validation Update")}</p>
                <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600 whitespace-pre-wrap">{detailValue(job?.email_preview?.body, "Notification body template generated and ready.")}</p>
              </div>
            </article>
          </div>
        </>
      )}
    </section>
  );
}
