export type Document = {
  id: number;
  title: string;
  organization: string;
  publication_date: string;
  source_url: string;
  document_type: string;
  content_hash: string;
  retrieved_at: string;
  usage_notes: string;
  status: string;
};
export type Evidence = {
  chunk_id: number;
  document_id: number;
  title: string;
  page: number;
  text: string;
  source_url: string;
  publication_date: string;
  organization: string;
};
export type Rag = {
  mode: string;
  abstained: boolean;
  answer: string;
  evidence: Evidence[];
  claims: { chunk_id: number; quote: string }[];
  latency_ms: number;
  provider?: string;
  support_assessment?: string;
};
export type Quality = {
  documents: number;
  chunks: number;
  failed_runs: number;
  duplicate_runs: number;
  last_success: string;
  database: string;
  lineage: string;
  quality: {
    id: number;
    title: string;
    pages: number;
    empty_pages: number;
    replacement_characters: number;
    ocr_required: boolean;
  }[];
};
export function sourceLink(source: {
  source_url: string;
  page?: number;
}): string | null {
  try {
    const url = new URL(source.source_url);
    if (
      url.protocol !== "https:" ||
      ![
        "statistics.gov.rw",
        "www.statistics.gov.rw",
        "bnr.rw",
        "www.bnr.rw",
      ].includes(url.hostname) ||
      url.username ||
      url.password ||
      (url.port && url.port !== "443")
    )
      return null;
    if (source.page !== undefined) {
      if (!Number.isSafeInteger(source.page) || source.page < 1) return null;
      url.hash = "page=" + source.page;
    }
    return url.href;
  } catch {
    return null;
  }
}
