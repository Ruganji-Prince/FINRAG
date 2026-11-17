"""Pinned MiniLM CPU inference without PyTorch for a bounded serverless profile.
Mean pooling and normalization follow the publisher's model card. No quantization.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np

from backend.config import ROOT, settings

_INIT_LOCK = Lock()
_RUN_LOCK = Lock()
_INSTANCE = None


@lru_cache(maxsize=1)
def model():
    global _INSTANCE
    with _INIT_LOCK:
        if _INSTANCE is not None:
            return _INSTANCE
        folder = (
            Path(settings.onnx_model_dir)
            if settings.onnx_model_dir
            else ROOT / ".models/minilm-onnx"
        )
        manifest = json.loads((folder / "manifest.json").read_text())
        if (
            manifest["repository"] != settings.embedding_model
            or manifest["revision"] != settings.embedding_revision
        ):
            raise ValueError("ONNX asset identity mismatch")
        for name in ["model.onnx", "tokenizer.json"]:
            if (
                hashlib.sha256((folder / name).read_bytes()).hexdigest()
                != manifest["sha256"][name]
            ):
                raise ValueError("ONNX asset checksum mismatch")
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=256)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(folder / "model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        _INSTANCE = (tokenizer, session)
        return _INSTANCE


def _encode(texts):
    tokenizer, session = model()
    result = []
    for start in range(0, len(texts), settings.embedding_batch_size):
        batch = tokenizer.encode_batch(
            texts[start : start + settings.embedding_batch_size]
        )
        data = {
            "input_ids": np.array([x.ids for x in batch], dtype=np.int64),
            "attention_mask": np.array(
                [x.attention_mask for x in batch], dtype=np.int64
            ),
            "token_type_ids": np.array([x.type_ids for x in batch], dtype=np.int64),
        }
        hidden = session.run(
            None, {x.name: data[x.name] for x in session.get_inputs()}
        )[0]
        if hidden.ndim == 3:
            mask = data["attention_mask"][..., None].astype(np.float32)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        else:
            pooled = hidden
        pooled = pooled / np.clip(
            np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None
        )
        if pooled.shape[1] != 384 or not np.isfinite(pooled).all():
            raise ValueError("Invalid ONNX embedding")
        result.extend(pooled.tolist())
    return result


def encode(texts):
    if not _RUN_LOCK.acquire(timeout=settings.local_queue_timeout_seconds):
        raise TimeoutError("Embedding inference capacity exhausted")
    try:
        return _encode(texts)
    finally:
        _RUN_LOCK.release()
