"""Resumable bounded-range fallback for large, stalled public model artifacts.

Verifies the assembled weight file against its publisher LFS SHA256 before use.
"""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = json.loads((ROOT / "docs/local-llm-model.json").read_text())
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(
            "https://huggingface.co/api/models/"
            + model["model"]
            + "/revision/"
            + model["revision"],
            params={"blobs": "true"},
        )
        r.raise_for_status()
        entry = next(
            s for s in r.json()["siblings"] if s["rfilename"] == "model.safetensors"
        )
    expected = entry["lfs"]["sha256"]
    size = entry["size"]
    block = 8 * 1024 * 1024
    folder = ROOT / ".runtime/model-parts" / expected
    folder.mkdir(parents=True, exist_ok=True)
    url = (
        "https://huggingface.co/"
        + model["model"]
        + "/resolve/"
        + model["revision"]
        + "/model.safetensors"
    )

    def fetch(i):
        start = i * block
        end = min(size - 1, start + block - 1)
        path = folder / f"{i:05}.part"
        if path.exists() and path.stat().st_size == end - start + 1:
            return i
        for attempt in range(4):
            try:
                with httpx.Client(timeout=90, follow_redirects=True) as c:
                    with c.stream(
                        "GET",
                        url,
                        params={"download": "true", "finrag_chunk": str(i)},
                        headers={"Range": f"bytes={start}-{end}"},
                    ) as response:
                        response.raise_for_status()
                        if response.status_code != 206 or not response.headers.get(
                            "content-range", ""
                        ).startswith(f"bytes {start}-{end}/"):
                            raise ValueError("Server did not honor bounded range")
                        data = bytearray()
                        for part in response.iter_bytes():
                            data.extend(part)
                            if len(data) > end - start + 1:
                                raise ValueError("Range exceeded bound")
                if len(data) != end - start + 1:
                    raise ValueError("Short model range")
                path.write_bytes(data)
                return i
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)

    count = (size + block - 1) // block
    completed = 0
    print(f"Downloading {size} bytes in {count} verified ranges", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for task in as_completed([pool.submit(fetch, i) for i in range(count)]):
            task.result()
            completed += 1
            if completed % 20 == 0 or completed == count:
                print(f"Model ranges {completed}/{count}", flush=True)
    cache = ROOT / ".models" / ("models--" + model["model"].replace("/", "--"))
    target = cache / "snapshots" / model["revision"] / "model.safetensors"
    target.parent.mkdir(parents=True, exist_ok=True)
    assembling = folder / "assembled.safetensors"
    digest = hashlib.sha256()
    with assembling.open("wb") as output:
        for i in range(count):
            data = (folder / f"{i:05}.part").read_bytes()
            digest.update(data)
            output.write(data)
    if digest.hexdigest() != expected:
        raise ValueError("Publisher model checksum mismatch")
    assembling.replace(target)
    (ROOT / "evaluation/results/model-artifact-verification.json").write_text(
        json.dumps(
            {
                "model": model["model"],
                "revision": model["revision"],
                "artifact": "model.safetensors",
                "size_bytes": size,
                "publisher_lfs_sha256": expected,
                "assembled_sha256": digest.hexdigest(),
                "status": "verified",
            },
            indent=2,
        )
    )
    print("Model artifact installed with matching publisher SHA256", flush=True)


if __name__ == "__main__":
    main()
