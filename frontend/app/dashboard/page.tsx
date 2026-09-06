"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getMe,
  syncEmails,
  listEmails,
  logout,
  ClassifiedEmail,
} from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  "Job/Interview": "bg-emerald-100 text-emerald-800",
  "Bills/Payments": "bg-amber-100 text-amber-800",
  "Personal": "bg-blue-100 text-blue-800",
  "Newsletter/Promotions": "bg-slate-200 text-slate-700",
  "Other": "bg-slate-100 text-slate-600",
};

export default function Dashboard() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [emails, setEmails] = useState<ClassifiedEmail[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEmails = useCallback(async (category?: string | null) => {
    const data = await listEmails(category || undefined);
    setEmails(data);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        setEmail(me.email);
        await loadEmails();
      } catch (e) {
        if (e instanceof Error && e.message === "UNAUTHENTICATED") {
          router.replace("/");
          return;
        }
        setError("Failed to load your inbox — check that the backend is running.");
      } finally {
        setLoading(false);
      }
    })();
  }, [router, loadEmails]);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      await syncEmails();
      await loadEmails(activeCategory);
    } catch (e) {
      const message =
        e instanceof Error
          ? e.message
          : "Sync failed — check that the backend is running and Gmail access is still valid.";
      setError(message);
    } finally {
      setSyncing(false);
    }
  }

  async function handleFilter(category: string | null) {
    setActiveCategory(category);
    await loadEmails(category);
  }

  async function handleLogout() {
    await logout();
    router.replace("/");
  }

  if (loading) {
    return <main className="p-8 text-center text-slate-500">Loading…</main>;
  }

  const categories = Object.keys(CATEGORY_COLORS);

  return (
    <main className="max-w-3xl mx-auto p-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Inbox Categorizer</h1>
          <p className="text-sm text-slate-500">{email}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/tracker"
            className="border border-slate-300 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Job tracker
          </Link>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {syncing ? "Syncing…" : "Sync unread"}
          </button>
          <button
            onClick={handleLogout}
            className="border border-slate-300 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Log out
          </button>
        </div>
      </header>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => handleFilter(null)}
          className={`px-3 py-1 rounded-full text-sm ${
            activeCategory === null ? "bg-slate-900 text-white" : "bg-slate-100"
          }`}
        >
          All
        </button>
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => handleFilter(c)}
            className={`px-3 py-1 rounded-full text-sm ${
              activeCategory === c ? "bg-slate-900 text-white" : CATEGORY_COLORS[c]
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {emails.length === 0 ? (
        <p className="text-slate-500 text-sm">
          No emails yet — click &quot;Sync unread&quot; to pull and classify your inbox.
        </p>
      ) : (
        <ul className="space-y-3">
          {emails.map((e) => (
            <li key={e.gmail_message_id} className="border border-slate-200 rounded-lg p-4 bg-white">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium truncate">{e.subject || "(no subject)"}</p>
                  <p className="text-sm text-slate-500 truncate">{e.sender}</p>
                  <p className="text-sm text-slate-400 mt-1 line-clamp-2">{e.snippet}</p>
                </div>
                <span
                  className={`shrink-0 text-xs font-medium px-2 py-1 rounded-full ${
                    CATEGORY_COLORS[e.category] || CATEGORY_COLORS["Other"]
                  }`}
                >
                  {e.category}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
