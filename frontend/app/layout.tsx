import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LedgerFlow Agent — Autonomous Financial Operations",
  description:
    "AI-powered autonomous reconciliation, explainable cash flow forecasting, governance and immutable audit trail.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
