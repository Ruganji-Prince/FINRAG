"""Append source-preserving sentence windows and layout table blocks.
Original chunks and citation IDs are retained. No cells/units are synthesized.
"""

import hashlib
import json
import re

from pypdf import PdfReader

from backend.config import ROOT
from backend.database import connection, documents, execute, initialize, now
from backend.embeddings import embed, identity


def units(reader):
    for page_number, page in enumerate(reader.pages, 1):
        text = " ".join((page.extract_text() or "").split())
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        for i, sentence in enumerate(sentences):
            if not re.search(
                r"\b(increased|decreased|grew|growth|contributed|estimated|methodology|sample|weights|base year|measures)\b",
                sentence,
                re.I,
            ):
                continue
            if len(sentence) < 40 or len(sentence) > 2400:
                continue
            # Keep a preceding sentence/heading as explicit source scope context.
            value = " ".join(sentences[max(0, i - 1) : i + 1])
            if len(value) > 3000:
                value = sentence
            yield page_number, "sentence-window-v2", value
        if re.search(r"\bTable\s*\d", text, re.I):
            layout = (
                page.extract_text(
                    extraction_mode="layout", layout_mode_space_vertically=False
                )
                or ""
            )
            lines = [line.rstrip() for line in layout.splitlines() if line.strip()]
            for start in range(0, len(lines), 18):
                block = "\n".join(lines[max(0, start - 3) : start + 18])
                if len(block) < 80 or len(block) > 6000:
                    continue
                yield page_number, "table-layout-v2", block


def run():
    initialize()
    summary = []
    for doc in documents():
        if "CC BY 4.0" not in doc["usage_notes"]:
            raise ValueError("Rights review required")
        path = ROOT / doc["path"]
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != doc["content_hash"]
        ):
            raise ValueError("Original source cache/hash required")
        with connection(True) as c:
            existing = {
                r["content_hash"]
                for r in execute(
                    c,
                    "SELECT content_hash FROM chunks WHERE document_id=?",
                    (doc["id"],),
                ).fetchall()
            }
        pending = []
        for page, section, text in units(PdfReader(path)):
            sha = hashlib.sha256(text.encode()).hexdigest()
            if sha not in existing:
                pending.append((page, section, text, sha))
                existing.add(sha)
        if not pending:
            continue
        vectors = embed([x[2] for x in pending])
        with connection() as c:
            for (page, section, text, sha), vector in zip(pending, vectors):
                execute(
                    c,
                    "INSERT INTO chunks(document_id,page,section,text,content_hash,embedding) VALUES(?,?,?,?,?,?) ON CONFLICT(document_id,content_hash) DO NOTHING",
                    (doc["id"], page, section, text, sha, json.dumps(vector)),
                )
            execute(
                c,
                "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
                (
                    now(),
                    doc["source_url"],
                    "refined",
                    json.dumps(
                        {
                            "version": "evidence-units-v2",
                            "added": len(pending),
                            "model": identity(),
                            "original_pdf_sha256": doc["content_hash"],
                        }
                    ),
                ),
            )
        summary.append(
            {
                "document_id": doc["id"],
                "added": len(pending),
                "original_pdf_sha256": doc["content_hash"],
            }
        )
        print(json.dumps(summary[-1]), flush=True)
    (ROOT / "evaluation/results/evidence-refinement.json").write_text(
        json.dumps(
            {
                "method": "Append exact source sentence windows and pypdf layout table blocks; original IDs retained. Table layout is not a validated cell parser.",
                "documents": summary,
                "added": sum(x["added"] for x in summary),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
