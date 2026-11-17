"""Probe the generated minimal runtime without making database or paid LLM requests."""

import ctypes
import json
import os
import sys
import sysconfig
import time
from pathlib import Path


def peak_memory():
    if os.name != "nt":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    from ctypes import wintypes

    class Memory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in [
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            ]
        ]

    data = Memory()
    data.cb = ctypes.sizeof(data)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = wintypes.HANDLE
    measure = ctypes.windll.psapi.GetProcessMemoryInfo
    measure.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    measure.restype = wintypes.BOOL
    if not measure(current(), ctypes.byref(data), data.cb):
        raise RuntimeError("Memory probe failed")
    return data.PeakWorkingSetSize


def run():
    stage = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(stage))
    os.environ.update(
        PUBLIC_MODE="true",
        API_ACCESS_TOKEN="test-only-api-token-" * 3,
        DATABASE_URL="postgresql://finrag_reader:test-only@database.invalid/finrag?sslmode=require",
        QUERY_DATABASE_URL="",
        LLM_PROVIDER="gemini",
        LLM_API_KEY="test-only-placeholder",
        LLM_MODEL="test-model",
        EMBEDDING_BACKEND="onnx",
        EMBEDDING_BATCH_SIZE="8",
        AUTO_MIGRATE="false",
        PRELOAD_MODELS="false",
        STARTUP_DATABASE_CHECK="false",
        HEALTH_REQUIRES_AUTH="true",
        ONNX_MODEL_DIR=str(stage / "models/minilm"),
    )
    import numpy as np
    from cloud_entry import app
    from fastapi.testclient import TestClient

    from backend.onnx_embeddings import encode

    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        assert client.post("/ask", json={"question": "GDP growth?"}).status_code == 401
    start = time.perf_counter()
    vectors = np.array(encode(["GDP growth Rwanda " * 100] * 32))
    latency = (time.perf_counter() - start) * 1000
    assert vectors.shape == (32, 384) and np.allclose(
        np.linalg.norm(vectors, axis=1), 1, atol=1e-5
    )
    assert "torch" not in sys.modules
    memory = peak_memory()
    assert memory < 1_800_000_000
    roots = {
        Path(sysconfig.get_paths()["purelib"]),
        Path(sysconfig.get_paths()["platlib"]),
        stage,
    }
    installed_bytes = sum(
        p.stat().st_size for root in roots for p in root.rglob("*") if p.is_file()
    )
    assert installed_bytes < 500_000_000, (
        "Installed runtime exceeds standard Python bundle budget"
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "installed_dependencies_and_stage_bytes": installed_bytes,
                "actual_vercel_bundle_verified": False,
                "runtime_import_and_onnx_inference": True,
                "unauthenticated_health_and_ask_status": 401,
                "texts": 32,
                "embedding_batch_size": 8,
                "max_tokens": 256,
                "dimensions": 384,
                "first_batch_ms": latency,
                "peak_working_set_bytes": memory,
                "torch_loaded": False,
                "platform": sys.platform,
                "scope": "Isolated minimal runtime; hosted database/LLM requests were not made.",
            }
        )
    )


if __name__ == "__main__":
    run()
