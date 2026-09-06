const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ClassifiedEmail = {
  gmail_message_id: string;
  subject: string;
  sender: string;
  snippet: string;
  category: string;
  confidence: number;
  method: string;
  classified_at: string;
};

export type SyncResult = {
  fetched: number;
  newly_classified: number;
  emails: ClassifiedEmail[];
};

export type Application = {
  id: number;
  gmail_thread_id: string;
  company: string | null;
  role: string | null;
  stage: string;
  last_email_subject: string;
  last_email_snippet: string;
  last_updated: string;
  created_at: string;
};

export type ApplicationUpdate = {
  stage?: string;
  company?: string | null;
  role?: string | null;
};

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include", // required so the session cookie is sent
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("UNAUTHENTICATED");
    let detail = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }
  return res.json();
}

export function loginUrl() {
  return `${API_URL}/auth/login`;
}

export async function getMe(): Promise<{ email: string }> {
  return apiFetch("/auth/me");
}

export async function syncEmails(): Promise<SyncResult> {
  return apiFetch("/emails/sync", { method: "POST" });
}

export async function listEmails(category?: string): Promise<ClassifiedEmail[]> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch(`/emails/${qs}`);
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export async function getApplications(): Promise<Application[]> {
  return apiFetch("/applications/");
}

export async function updateApplication(
  id: number,
  update: ApplicationUpdate
): Promise<Application> {
  return apiFetch(`/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function gmailThreadUrl(threadId: string): string {
  return `https://mail.google.com/mail/u/0/#inbox/${threadId}`;
}
