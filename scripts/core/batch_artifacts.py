"""Immutable content-addressed artifacts; callers cannot choose filesystem paths."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .batch_repository import BatchConflict, encode


def fingerprint(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BatchArtifacts:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, digest):
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise BatchConflict("invalid_artifact_id", "Invalid artifact identifier.", 400)
        path = self.root / (digest + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise BatchConflict("unsafe_artifact_path", "Artifact path is unsafe.")
        return path

    def put(self, value):
        payload = encode(value).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        path = self.path(digest)
        if path.exists():
            self.get(digest)
            return digest
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
                temporary = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            # Identical hashes have identical bytes; concurrent writers converge.
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        return digest

    def get(self, digest):
        path = self.path(digest)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise BatchConflict("artifact_missing", "A persisted artifact is missing.") from exc
        if hashlib.sha256(payload).hexdigest() != digest:
            raise BatchConflict("artifact_integrity_error", "A persisted artifact changed.")
        return json.loads(payload.decode("utf-8"))
