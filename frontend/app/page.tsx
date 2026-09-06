import { loginUrl } from "@/lib/api";

export default function Home() {
  return (
    <main className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
      <h1 className="text-3xl font-bold mb-3">Inbox Categorizer</h1>
      <p className="text-slate-600 max-w-md mb-8">
        Connect your Gmail to automatically sort unread mail into Job/Interview,
        Bills, Personal, Newsletters, and everything else.
      </p>
      <a
        href={loginUrl()}
        className="bg-slate-900 text-white px-6 py-3 rounded-lg font-medium hover:bg-slate-700 transition"
      >
        Connect Gmail
      </a>
      <p className="text-xs text-slate-400 mt-6 max-w-sm">
        Read-only access. We only read subject lines and snippets to classify
        mail — we never send, delete, or modify anything in your inbox.
      </p>
    </main>
  );
}
