import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Inbox Categorizer",
  description: "Categorize your unread Gmail with AI",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 min-h-screen">{children}</body>
    </html>
  );
}
