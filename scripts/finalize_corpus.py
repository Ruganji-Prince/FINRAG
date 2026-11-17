"""Record verified cover dates and explicitly catalogue BNR sources pending rights review."""

import hashlib
import json
import re
from datetime import datetime

from pypdf import PdfReader

from backend.config import ROOT
from backend.database import connection, execute, now, rows


def main():
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    for doc in rows("SELECT * FROM documents WHERE document_type='CPI monthly report'"):
        cover = " ".join(PdfReader(ROOT / doc["path"]).pages[0].extract_text().split())
        match = re.search(
            r"\b(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})\b",
            cover,
        )
        if not match:
            continue
        date = datetime.strptime(match.group(1), "%d %B %Y").date().isoformat()
        notes = (
            doc["usage_notes"].split("Date is official PDF LAST UPDATED")[0]
            + "Publication date verified against the full date on PDF cover page 1."
        )
        with connection() as c:
            execute(
                c,
                "UPDATE documents SET publication_date=?,usage_notes=? WHERE id=?",
                (date, notes, doc["id"]),
            )
            execute(
                c,
                "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
                (
                    now(),
                    doc["source_url"],
                    "metadata_verified",
                    "Publication date checked against PDF cover page 1; prior date basis was website LAST UPDATED proxy.",
                ),
            )
        for item in manifest:
            if item["source_url"] == doc["source_url"]:
                item.update(publication_date=date, usage_notes=notes)
    (ROOT / "data/manifest.json").write_text(json.dumps(manifest, indent=2))
    source = ROOT / "data/source-review.json"
    if source.exists():
        reviewed = json.loads(source.read_text())
        entries = [
            {
                "title": item["item"]["name"],
                "source_url": item["url"],
                "publication_date": item["item"]["publish_date"],
                "publisher": "BNR",
                "pages": item["pages"],
                "sha256": item["sha256"],
                "status": "pending_rights_review",
                "reason": "Public official source and robots allow download; a clear reproduction/redistribution permission was not established. Not indexed or included in prebuilt data.",
            }
            for item in reviewed
        ]
        record = {"reviewed_at": now(), "entries": entries}
        (ROOT / "docs/bnr-source-review.json").write_text(json.dumps(record, indent=2))
        payload = json.dumps(record, sort_keys=True)
        with connection() as c:
            execute(
                c,
                "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?) ON CONFLICT(registry_key) DO UPDATE SET payload_json=excluded.payload_json,payload_sha256=excluded.payload_sha256,recorded_at=excluded.recorded_at",
                (
                    "bnr_pending_rights_review",
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                    now(),
                    "Repository maintainer",
                ),
            )
    print(
        "Verified CPI cover dates; persisted source-rights review separately from indexed evidence."
    )


if __name__ == "__main__":
    main()
