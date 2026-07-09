"""Development-only self-signed Ed25519 receipt signer.

The keypair lives under ~/.chio-dev/keys by default. This is intentionally
not a production trust model; it gives local packs an offline-verifiable
receipt path before a real Chio capability signer is wired in.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - exercised in --no-project envs.
    InvalidSignature = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]

from .envelope import RetrievalReceipt


class DevSelfSignedSigner:
    signer_kind = "dev-selfsigned"

    def __init__(self, key_dir: Path | None = None) -> None:
        self.key_dir = key_dir or (Path.home() / ".chio-dev" / "keys")
        self.private_key_path = self.key_dir / "dev-selfsigned-ed25519.pem"
        self.public_key_path = self.key_dir / "dev-selfsigned-ed25519.pub.pem"
        self._private_key = self._load_or_create_private_key()
        self._public_key = (
            self._private_key.public_key()
            if self._private_key is not None
            else None
        )
        self._write_public_key()
        self.key_id = self._key_id()

    def sign(self, receipt: RetrievalReceipt) -> RetrievalReceipt:
        message = _canonical_payload(receipt.payload)
        signature = (
            self._private_key.sign(message)
            if self._private_key is not None
            else self._openssl_sign(message)
        )
        return receipt.with_signature(
            signer_kind=self.signer_kind,
            key_id=self.key_id,
            signature=base64.b64encode(signature).decode("ascii"),
        )

    def verify(self, receipt: RetrievalReceipt) -> bool:
        if receipt.signer_kind != self.signer_kind:
            return False
        if receipt.key_id != self.key_id or not receipt.signature:
            return False
        try:
            signature = base64.b64decode(receipt.signature.encode("ascii"), validate=True)
            message = _canonical_payload(receipt.payload)
            if self._public_key is not None:
                self._public_key.verify(signature, message)
            else:
                return self._openssl_verify(message, signature)
        except (ValueError, Exception if InvalidSignature is None else InvalidSignature):
            return False
        return True

    def _load_or_create_private_key(self) -> Any:
        self.key_dir.mkdir(parents=True, exist_ok=True)
        if Ed25519PrivateKey is None or serialization is None:
            self._ensure_openssl_keypair()
            return None
        if self.private_key_path.exists():
            data = self.private_key_path.read_bytes()
            key = serialization.load_pem_private_key(data, password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError(f"{self.private_key_path} is not an Ed25519 private key")
            return key
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.private_key_path.write_bytes(pem)
        self.private_key_path.chmod(0o600)
        return key

    def _write_public_key(self) -> None:
        if self._public_key is None or serialization is None:
            self._ensure_openssl_keypair()
            return
        pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.public_key_path.write_bytes(pem)

    def _key_id(self) -> str:
        if self._public_key is None or serialization is None:
            digest = hashlib.sha256(self.public_key_path.read_bytes()).hexdigest()
            return f"ed25519:{digest}"
        raw = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        digest = hashlib.sha256(raw).hexdigest()
        return f"ed25519:{digest}"

    def _ensure_openssl_keypair(self) -> None:
        if self.private_key_path.exists() and self.public_key_path.exists():
            return
        self.key_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(self.private_key_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.private_key_path.chmod(0o600)
        subprocess.run(
            [
                "openssl", "pkey",
                "-in", str(self.private_key_path),
                "-pubout",
                "-out", str(self.public_key_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _openssl_sign(self, message: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            msg = Path(tmp) / "message.bin"
            sig = Path(tmp) / "signature.bin"
            msg.write_bytes(message)
            subprocess.run(
                [
                    "openssl", "pkeyutl",
                    "-sign",
                    "-inkey", str(self.private_key_path),
                    "-rawin",
                    "-in", str(msg),
                    "-out", str(sig),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return sig.read_bytes()

    def _openssl_verify(self, message: bytes, signature: bytes) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            msg = Path(tmp) / "message.bin"
            sig = Path(tmp) / "signature.bin"
            msg.write_bytes(message)
            sig.write_bytes(signature)
            result = subprocess.run(
                [
                    "openssl", "pkeyutl",
                    "-verify",
                    "-pubin",
                    "-inkey", str(self.public_key_path),
                    "-rawin",
                    "-in", str(msg),
                    "-sigfile", str(sig),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.returncode == 0


def _canonical_payload(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
