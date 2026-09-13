import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LedgerFlow | Finance Operations Control",
  description:
    "A finance operations workspace for reconciliation, cash forecasting, approvals and audit-ready decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
