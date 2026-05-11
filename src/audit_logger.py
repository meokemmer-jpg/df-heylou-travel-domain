"""Audit-Logger [CRUX-MK].

HMAC-SHA256-signed audit-entries als JSONL append-only.
Per W30-G aus df-100-forschen-research-pipeline.

Schreibt zu: audit/heylou-domain-<DATE>.jsonl + audit/llm-router-<DATE>.jsonl etc.

K11 try/except. K12 provenance. LC4 idempotent (append-only).

Welle-35.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEntry:
    """Kanonische Audit-Entry (HMAC-Signed per W30-G)."""
    event_type: str
    df_id: str
    timestamp_iso: str
    payload: dict
    signature: Optional[str] = None

    def canonical_payload(self) -> str:
        """W30-G: Deterministischer Payload fuer HMAC-Signature."""
        canonical_payload = json.dumps(self.payload, sort_keys=True, default=str)
        return f"{self.event_type}||{self.df_id}||{self.timestamp_iso}||{canonical_payload}"

    @staticmethod
    def sign_payload(payload: str, secret: Optional[str] = None) -> str:
        """W30-G: HMAC-SHA256.

        Secret-Quelle: DF_HEYLOU_HMAC_SECRET > DF_SERVICE_IDENTITY_SECRET > default.
        """
        if secret is None:
            secret = (
                os.environ.get("DF_HEYLOU_HMAC_SECRET")
                or os.environ.get("DF_SERVICE_IDENTITY_SECRET")
                or "df-heylou-travel-domain-runtime-default"
            )
        return hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def signed(self, secret: Optional[str] = None) -> "AuditEntry":
        sig = self.sign_payload(self.canonical_payload(), secret)
        return AuditEntry(
            event_type=self.event_type,
            df_id=self.df_id,
            timestamp_iso=self.timestamp_iso,
            payload=self.payload,
            signature=sig,
        )

    def verify_signature(self, secret: Optional[str] = None) -> bool:
        if not self.signature:
            return False
        expected = self.sign_payload(self.canonical_payload(), secret)
        return hmac.compare_digest(expected, self.signature)


class AuditLogger:
    """JSONL-append-only audit-logger mit HMAC-Signing.

    Public API:
    - log(event_type, payload, target='heylou-domain') -> AuditEntry
    - read_recent(target='heylou-domain', limit=10) -> list[AuditEntry]
    """

    DEFAULT_TARGETS = ["heylou-domain", "llm-router", "adapter-calls"]

    def __init__(self, audit_dir: str = "audit", df_id: str = "df-heylou-travel-domain"):
        self.audit_dir = Path(audit_dir)
        self.df_id = df_id
        # Ensure audit dir exists (best-effort)
        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"audit_dir create failed (using cwd): {e}")
            self.audit_dir = Path(".")

    def _today_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _target_file(self, target: str) -> Path:
        return self.audit_dir / f"{target}-{self._today_iso()}.jsonl"

    def log(
        self,
        event_type: str,
        payload: dict,
        target: str = "heylou-domain",
    ) -> AuditEntry:
        """Append signed audit-entry to JSONL.

        K11 try/except. Returns the signed entry (caller can verify).
        """
        entry = AuditEntry(
            event_type=event_type,
            df_id=self.df_id,
            timestamp_iso=self._now_iso(),
            payload=payload,
        ).signed()

        try:
            file_path = self._target_file(target)
            line = json.dumps(asdict(entry), default=str)
            with file_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.error(f"audit log write failed: {e}")
            # Failure-isolation: nicht raisen, damit Caller nicht crasht

        return entry

    def read_recent(
        self,
        target: str = "heylou-domain",
        limit: int = 10,
    ) -> list[AuditEntry]:
        """Read recent entries from today's JSONL."""
        try:
            file_path = self._target_file(target)
            if not file_path.exists():
                return []
            entries = []
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entries.append(AuditEntry(
                            event_type=data["event_type"],
                            df_id=data["df_id"],
                            timestamp_iso=data["timestamp_iso"],
                            payload=data["payload"],
                            signature=data.get("signature"),
                        ))
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"audit entry parse failed: {e}")
                        continue
            return entries[-limit:]
        except Exception as e:
            logger.error(f"audit read failed: {e}")
            return []
