import argparse
import hashlib
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from pypdf import PdfReader

from backend.config import ROOT, settings
from backend.database import audit, connection, execute, initialize, now
from backend.embeddings import embed, identity
from backend.schemas import DocumentMetadata, safe_url

AGENT = "FinRAGResearchBot/1.0"


def download(url):
    safe_url(url)
    origin = "https://" + urlsplit(url).netloc
    with httpx.Client(
        timeout=45, follow_redirects=False, headers={"User-Agent": AGENT}
    ) as client:
        robots = client.get(origin + "/robots.txt")
        if robots.status_code == 200:
            parser = RobotFileParser()
            parser.parse(robots.text.splitlines())
            if not parser.can_fetch(AGENT, url):
                raise ValueError("robots.txt disallows download")
            delay = parser.crawl_delay(AGENT) or parser.crawl_delay("*") or 2
        elif robots.status_code in (404, 410):
            delay = 2
        else:
            raise ValueError(f"Cannot verify robots.txt: HTTP {robots.status_code}")
        time.sleep(max(2, delay))
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if (
                int(response.headers.get("content-length", "0"))
                > settings.max_download_bytes
            ):
                raise ValueError("Document exceeds download limit")
            parts = []
            size = 0
            for part in response.iter_bytes():
                size += len(part)
                if size > settings.max_download_bytes:
                    raise ValueError("Document exceeds download limit")
                parts.append(part)
            return b"".join(parts)


def extract(raw):
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Only PDF documents supported in MVP")
    reader = PdfReader(io.BytesIO(raw), strict=False)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF unsupported")
    if len(reader.pages) > 1500:
        raise ValueError("Too many pages")
    pages = [
        re.sub(r"[ \t]+", " ", p.extract_text() or "").strip() for p in reader.pages
    ]
    empty = sum(len(p) < 40 for p in pages)
    bad = sum(p.count("\ufffd") for p in pages)
    if not pages or empty / len(pages) > 0.3 or sum(map(len, pages)) < 200:
        raise ValueError("Low quality extraction; OCR/review required")
    if bad > max(10, sum(map(len, pages)) * 0.01):
        raise ValueError("Corrupted extraction; review required")
    return pages, {
        "pages": len(pages),
        "empty_pages": empty,
        "missing_metadata": 0,
        "replacement_characters": bad,
        "ocr_required": False,
    }


def chunk_pages(pages, size=160, overlap=30):
    if size <= overlap or overlap < 0:
        raise ValueError("Invalid chunk settings")
    result = []
    seen = set()
    for page, text in enumerate(pages, 1):
        words = text.split()
        section = next(
            (line[:160] for line in text.splitlines() if line.strip()),
            "Page " + str(page),
        )
        for start in range(0, len(words), size - overlap):
            part = " ".join(words[start : start + size])
            digest = hashlib.sha256(part.encode()).hexdigest()
            if len(part) >= 50 and digest not in seen:
                result.append(
                    {
                        "page": page,
                        "section": section,
                        "text": part,
                        "content_hash": digest,
                    }
                )
                seen.add(digest)
            if start + size >= len(words):
                break
    return result


def ingest(metadata, raw=None):
    meta = DocumentMetadata.model_validate(metadata)
    if (meta.organization == "NISR") != (
        "statistics.gov.rw" in urlsplit(meta.source_url).hostname
    ):
        raise ValueError("Publisher and source host do not match")
    url = meta.source_url
    try:
        raw = download(url) if raw is None else raw
        digest = hashlib.sha256(raw).hexdigest()
        with connection(True) as c:
            existing = execute(
                c, "SELECT id,path FROM documents WHERE content_hash=?", (digest,)
            ).fetchone()
        if existing:
            # A public prebuilt index intentionally omits raw PDFs. Hydrate its source
            # cache on a real refresh without duplicating documents or chunk IDs.
            cache = ROOT / "data" / "raw" / (digest + ".pdf")
            relative = str(cache.relative_to(ROOT))
            restored = (
                not cache.exists()
                or hashlib.sha256(cache.read_bytes()).hexdigest() != digest
            )
            if restored:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(raw)
            if existing["path"] != relative:
                with connection() as c:
                    execute(
                        c,
                        "UPDATE documents SET path=? WHERE id=?",
                        (relative, existing["id"]),
                    )
            audit(
                url,
                "duplicate",
                json.dumps({"sha256": digest, "cache_restored": restored}),
            )
            return {
                "status": "duplicate",
                "document_id": existing["id"],
                "cache_restored": restored,
            }
        pages, quality = extract(raw)
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("No usable chunks")
        vectors = embed([x["text"] for x in chunks])
        cache = ROOT / "data" / "raw" / (digest + ".pdf")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
        data = meta.model_dump(mode="json")
        data.update(
            content_hash=digest,
            retrieved_at=now(),
            status="indexed",
            embedding_model=identity(),
            quality_json=json.dumps(quality),
            path=str(cache.relative_to(ROOT)),
        )
        with connection() as c:
            keys = list(data)
            doc_id = execute(
                c,
                "INSERT INTO documents ("
                + ",".join(keys)
                + ") VALUES ("
                + ",".join("?" for _ in keys)
                + ") RETURNING id",
                tuple(data.values()),
            ).fetchone()["id"]
            for chunk, vector in zip(chunks, vectors):
                execute(
                    c,
                    "INSERT INTO chunks(document_id,page,section,text,content_hash,embedding) VALUES(?,?,?,?,?,?)",
                    (
                        doc_id,
                        chunk["page"],
                        chunk["section"],
                        chunk["text"],
                        chunk["content_hash"],
                        json.dumps(vector),
                    ),
                )
            execute(
                c,
                "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
                (
                    now(),
                    url,
                    "indexed",
                    json.dumps(
                        {"document_id": doc_id, "chunks": len(chunks), "sha256": digest}
                    ),
                ),
            )
        return {"status": "indexed", "document_id": doc_id, "chunks": len(chunks)}
    except Exception as exc:
        audit(url, "failed", type(exc).__name__ + ": " + str(exc))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    initialize()
    failed = 0
    for item in json.loads(args.manifest.read_text(encoding="utf-8")):
        try:
            print(json.dumps(ingest(item)))
        except Exception as exc:
            failed += 1
            print(json.dumps({"status": "failed", "error": str(exc)}))
        time.sleep(2)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
