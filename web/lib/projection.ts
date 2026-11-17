import "server-only";
const documentKeys = [
  "id",
  "title",
  "organization",
  "publication_date",
  "source_url",
  "document_type",
  "content_hash",
  "retrieved_at",
  "usage_notes",
  "status",
];
function pick(value: Record<string, unknown>, keys: string[]) {
  return Object.fromEntries(
    keys.filter((k) => k in value).map((k) => [k, value[k]]),
  );
}
export function project(endpoint: string, data: unknown): unknown {
  if (endpoint === "documents" && Array.isArray(data))
    return data.map((d) => pick(d, documentKeys));
  if (!data || typeof data !== "object") return data;
  const value = data as Record<string, unknown>;
  if (endpoint === "quality")
    return pick(value, [
      "documents",
      "chunks",
      "failed_runs",
      "duplicate_runs",
      "last_success",
      "quality",
      "database",
      "lineage",
    ]);
  if (endpoint === "governance")
    return {
      registry: {
        principles:
          (value.registry as { principles?: string[] })?.principles || [],
      },
      records: Array.isArray(value.records)
        ? value.records.map((r) =>
            pick(r, ["registry_key", "payload_sha256", "recorded_at", "owner"]),
          )
        : [],
      transfer_count: Array.isArray(value.transfers)
        ? value.transfers.length
        : 0,
      embedding_run_count: Array.isArray(value.embedding_runs)
        ? value.embedding_runs.length
        : 0,
      lineage: value.lineage,
    };
  if (endpoint === "evaluation")
    return pick(value, [
      "status",
      "run_at",
      "n",
      "planned",
      "metrics",
      "methodology",
      "retrieval_comparison",
    ]);
  return data;
}
