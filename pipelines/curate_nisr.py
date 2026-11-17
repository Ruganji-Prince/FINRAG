"""Curated official NISR expansion with rights review, download cache and date basis.

Only extracted data/analysis is indexed; publisher/third-party images are not redistributed.
"""

import hashlib
import html
import json
import re
from datetime import datetime
from urllib.parse import urljoin

from backend.config import ROOT
from backend.database import connection, execute, initialize, now
from pipelines.ingest import download, extract, ingest

BASE = "https://statistics.gov.rw"
TERMS = BASE + "/terms-use"


def curate(pages_override=None):
    initialize()
    # This exact official archive was inspected and links the ten target pages.
    archive = (
        BASE
        + "/data-sources/surveys/Consumer-Price-Index/consumer-price-index-cpi-2026"
    )
    body = download(archive).decode("utf-8")
    pages = list(
        dict.fromkeys(
            urljoin(BASE, html.unescape(x))
            for x in re.findall(r'href="([^"]+)"', body)
            if "/statistical-publications/" in x
            and "/consumer-price-index-cpi-" in x
            and x.endswith("2026")
        )
    )
    pages += [
        BASE
        + "/statistical-publications/gross-domestic-product/gdp-national-accounts-q1-2026",
        BASE
        + "/statistical-publications/gross-domestic-product/gdp-national-accounts-2024",
        BASE
        + "/statistical-publications/gross-domestic-product/gdp-national-accounts-2023",
    ]
    if pages_override is not None:
        pages = pages_override
    terms = download(TERMS).decode("utf-8")
    plain = html.unescape(re.sub("<[^>]+>", " ", terms))
    if "Creative Commons Attribution 4.0" not in plain:
        raise ValueError("NISR terms changed; review required")
    manifest_path = ROOT / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    seen = {m["source_url"] for m in manifest}
    review = []
    for page in pages:
        if any(item["landing_url"] == page for item in manifest):
            continue
        try:
            content = download(page).decode("utf-8")
            heading = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.S | re.I)
            if not heading:
                raise ValueError("Missing official title")
            title = html.unescape(re.sub("<[^>]+>", "", heading.group(1))).strip()
            links = list(
                dict.fromkeys(
                    html.unescape(x) for x in re.findall(r'href="([^"]+)"', content)
                )
            )
            pdfs = [
                urljoin(BASE, x)
                for x in links
                if ".pdf" in x.lower()
                and not any(
                    w in x.lower()
                    for w in ["igipimo", "indice", "french", "kinyarwanda", "francais"]
                )
            ]
            if not pdfs:
                raise ValueError("No English PDF link")
            url = pdfs[0]
            if url in seen:
                continue
            cache = (
                ROOT
                / "data/review"
                / (hashlib.sha256(url.encode()).hexdigest() + ".pdf")
            )
            cache.parent.mkdir(exist_ok=True)
            raw = cache.read_bytes() if cache.exists() else download(url)
            cache.write_bytes(raw)
            extracted, quality = extract(raw)
            text = " ".join(extracted)
            if re.search(r"no part.{0,100}reproduc|all rights reserved", text, re.I):
                raise ValueError("Document-specific rights restriction needs review")
            stamp = re.search(
                r"LAST UPDATED:\s*(\d{1,2} [A-Za-z]{3} \d{4})",
                html.unescape(re.sub("<[^>]+>", " ", content)),
            )
            if not stamp:
                raise ValueError("No verified official date metadata")
            date = datetime.strptime(stamp.group(1), "%d %b %Y").date().isoformat()
            item = {
                "title": title,
                "organization": "NISR",
                "publication_date": date,
                "source_url": url,
                "document_type": "CPI monthly report"
                if "consumer-price" in page
                else (
                    "Producer Price Index report"
                    if "producer-price" in page
                    else "Industrial Production report"
                    if "industrial-production" in page
                    else "GDP fiscal year report"
                    if "fiscal-year" in page
                    else "GDP quarterly report"
                    if re.search(r"q[1-4]-", page)
                    else "GDP annual report"
                ),
                "landing_url": page,
                "usage_notes": "CC BY 4.0 for NISR data and analysis under "
                + TERMS
                + ". Source: National Institute of Statistics of Rwanda, "
                + title
                + ". Document checked for overriding restrictions. Images/logos excluded. Date is official PDF LAST UPDATED metadata, a release-date proxy; original publication day not independently established.",
            }
            outcome = ingest(item, raw)
            manifest.append(item)
            seen.add(url)
            manifest_path.write_text(json.dumps(manifest, indent=2))
            review.append(
                {
                    "source_url": url,
                    "title": title,
                    "status": "indexed",
                    "license_basis": TERMS,
                    "date_basis": "official PDF LAST UPDATED metadata; proxy",
                    "content_hash": hashlib.sha256(raw).hexdigest(),
                    "quality": quality,
                }
            )
            print(json.dumps({"title": title, **outcome}), flush=True)
        except Exception as exc:
            review.append(
                {"landing_url": page, "status": "review_required", "reason": str(exc)}
            )
            print(json.dumps(review[-1]), flush=True)
    result = {
        "checked_at": now(),
        "publisher": "NISR",
        "terms_url": TERMS,
        "terms_sha256": hashlib.sha256(terms.encode()).hexdigest(),
        "review": review,
    }
    (
        ROOT
        / (
            "data/corpus-expansion-review.json"
            if pages_override is not None
            else "data/corpus-review.json"
        )
    ).write_text(json.dumps(result, indent=2))
    payload = json.dumps(result, sort_keys=True)
    with connection() as c:
        execute(
            c,
            "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?) ON CONFLICT(registry_key) DO UPDATE SET payload_json=excluded.payload_json,payload_sha256=excluded.payload_sha256,recorded_at=excluded.recorded_at",
            (
                "nisr_source_review",
                payload,
                hashlib.sha256(payload.encode()).hexdigest(),
                now(),
                "Repository maintainer",
            ),
        )


if __name__ == "__main__":
    import sys

    curate(json.loads((ROOT / sys.argv[1]).read_text()) if len(sys.argv) > 1 else None)
