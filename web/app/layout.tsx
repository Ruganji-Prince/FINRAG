import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "FinRAG | Rwanda Financial Intelligence",
  description:
    "Experimental financial research with page-linked official evidence. Original holdout expected-statistic coverage: 41.7%.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
