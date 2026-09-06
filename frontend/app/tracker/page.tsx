"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getMe,
  getApplications,
  updateApplication,
  logout,
  gmailThreadUrl,
  Application,
} from "@/lib/api";

const KANBAN_STAGES = ["Applied", "Interview", "Offer", "Rejected"] as const;
type KanbanStage = (typeof KANBAN_STAGES)[number];

const STAGE_COLORS: Record<KanbanStage, string> = {
  Applied: "border-blue-200 bg-blue-50",
  Interview: "border-violet-200 bg-violet-50",
  Offer: "border-emerald-200 bg-emerald-50",
  Rejected: "border-rose-200 bg-rose-50",
};

/** Unknown-stage applications are shown in the Applied column. */
function kanbanStage(stage: string): KanbanStage {
  return KANBAN_STAGES.includes(stage as KanbanStage) ? (stage as KanbanStage) : "Applied";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function TrackerPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [draggedAppId, setDraggedAppId] = useState<number | null>(null);
  const [dragOverStage, setDragOverStage] = useState<KanbanStage | null>(null);
  const didDragRef = useRef(false);

  const loadApplications = useCallback(async () => {
    const data = await getApplications();
    setApplications(data);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        setEmail(me.email);
        await loadApplications();
      } catch (e) {
        if (e instanceof Error && e.message === "UNAUTHENTICATED") {
          router.replace("/");
          return;
        }
        setError("Failed to load applications — check that the backend is running.");
      } finally {
        setLoading(false);
      }
    })();
  }, [router, loadApplications]);

  async function handleStageChange(app: Application, newStage: KanbanStage) {
    if (newStage === kanbanStage(app.stage)) return;
    setSavingId(app.id);
    setError(null);
    try {
      const updated = await updateApplication(app.id, { stage: newStage });
      setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch {
      setError("Failed to update stage — please try again.");
    } finally {
      setSavingId(null);
    }
  }

  function handleCardClick(app: Application) {
    if (didDragRef.current) return;
    window.open(gmailThreadUrl(app.gmail_thread_id), "_blank", "noopener,noreferrer");
  }

  function handleDragStart(e: React.DragEvent, appId: number) {
    didDragRef.current = false;
    setDraggedAppId(appId);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(appId));
  }

  function handleDragEnd() {
    didDragRef.current = true;
    setDraggedAppId(null);
    setDragOverStage(null);
    requestAnimationFrame(() => {
      didDragRef.current = false;
    });
  }

  function handleDragOver(e: React.DragEvent, stage: KanbanStage) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverStage(stage);
  }

  function handleDrop(e: React.DragEvent, stage: KanbanStage) {
    e.preventDefault();
    setDragOverStage(null);
    const appId = draggedAppId ?? Number(e.dataTransfer.getData("text/plain"));
    setDraggedAppId(null);
    if (!appId) return;
    const app = applications.find((a) => a.id === appId);
    if (!app) return;
    handleStageChange(app, stage);
  }

  async function handleLogout() {
    await logout();
    router.replace("/");
  }

  if (loading) {
    return <main className="p-8 text-center text-slate-500">Loading…</main>;
  }

  const byStage = KANBAN_STAGES.reduce(
    (acc, stage) => {
      acc[stage] = applications.filter((a) => kanbanStage(a.stage) === stage);
      return acc;
    },
    {} as Record<KanbanStage, Application[]>
  );

  return (
    <main className="max-w-6xl mx-auto p-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Job Application Tracker</h1>
          <p className="text-sm text-slate-500">{email}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/dashboard"
            className="border border-slate-300 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Inbox
          </Link>
          <button
            onClick={handleLogout}
            className="border border-slate-300 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Log out
          </button>
        </div>
      </header>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {applications.length === 0 ? (
        <p className="text-slate-500 text-sm">
          No job applications yet — sync your inbox from the{" "}
          <Link href="/dashboard" className="underline">dashboard</Link> to track
          Job/Interview emails.
        </p>
      ) : (
        <>
          <p className="text-xs text-slate-400 mb-4">
            Drag cards between columns to update stage. Click a card to open the email in Gmail.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {KANBAN_STAGES.map((stage) => (
              <section
                key={stage}
                className={`rounded-xl border p-3 transition-colors ${STAGE_COLORS[stage]} ${
                  dragOverStage === stage ? "ring-2 ring-slate-400 ring-offset-1" : ""
                }`}
                onDragOver={(e) => handleDragOver(e, stage)}
                onDragLeave={() => setDragOverStage(null)}
                onDrop={(e) => handleDrop(e, stage)}
              >
                <h2 className="text-sm font-semibold mb-3">
                  {stage}
                  <span className="ml-2 text-slate-500 font-normal">({byStage[stage].length})</span>
                </h2>
                <ul className="space-y-2 min-h-[4rem]">
                  {byStage[stage].map((app) => (
                    <li
                      key={app.id}
                      draggable={savingId !== app.id}
                      onDragStart={(e) => handleDragStart(e, app.id)}
                      onDragEnd={handleDragEnd}
                      onClick={() => handleCardClick(app)}
                      className={`bg-white border border-slate-200 rounded-lg p-3 shadow-sm cursor-grab active:cursor-grabbing hover:border-slate-300 transition-opacity ${
                        draggedAppId === app.id ? "opacity-50" : ""
                      } ${savingId === app.id ? "opacity-60 pointer-events-none" : ""}`}
                    >
                      <p className="font-medium truncate">
                        {app.company || "Unknown company"}
                      </p>
                      <p className="text-sm text-slate-600 truncate">
                        {app.role || "Unknown role"}
                      </p>
                      <p className="text-xs text-slate-400 mt-1 truncate">
                        {app.last_email_subject || "(no subject)"}
                      </p>
                      <p className="text-xs text-slate-400 mt-1">
                        Updated {formatDate(app.last_updated)}
                      </p>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
