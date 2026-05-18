
# K12+K13+K16 Trinity-CONTRARIAN 2026-05-17 (Cross-LLM-validated)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-contrarian-v1") -> dict:
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

def k13_anchor(payload_hash: str) -> dict:
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }

def k16_lock_or_exit(df_name: str):
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)

"""Tests fuer audit_logger.py [CRUX-MK]."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audit_logger import AuditLogger, AuditEntry


def test_audit_log_creates_jsonl_file(tmp_path):
    """K11 + LC4: log() writes to JSONL append-only file."""
    audit = AuditLogger(audit_dir=str(tmp_path))
    entry = audit.log(
        event_type="test_event",
        payload={"foo": "bar", "n": 42},
    )
    assert entry.signature is not None
    assert entry.event_type == "test_event"
    # File should exist with at least 1 line
    today_files = list(tmp_path.glob("heylou-domain-*.jsonl"))
    assert len(today_files) == 1
    contents = today_files[0].read_text(encoding="utf-8")
    assert contents.count("\n") >= 1


def test_audit_log_signature_verifies(tmp_path):
    """W30-G: written entry's signature verifies."""
    audit = AuditLogger(audit_dir=str(tmp_path))
    entry = audit.log(
        event_type="domain_loop_run",
        payload={"loop_id": "test-loop", "hotel_id": "hildesheim"},
    )
    assert entry.verify_signature() is True


def test_read_recent_returns_signed_entries(tmp_path):
    """LC4 idempotent + W30-G: read_recent returns entries with signatures."""
    audit = AuditLogger(audit_dir=str(tmp_path))
    audit.log(event_type="evt1", payload={"a": 1})
    audit.log(event_type="evt2", payload={"a": 2})
    audit.log(event_type="evt3", payload={"a": 3})
    recent = audit.read_recent(limit=2)
    assert len(recent) == 2
    for e in recent:
        assert e.signature is not None
        assert len(e.signature) == 64
        assert e.verify_signature() is True


def test_audit_handles_missing_dir_gracefully(tmp_path):
    """LC1 graceful_degradation: missing audit_dir doesn't crash."""
    nonexistent = tmp_path / "deeply" / "nested" / "missing"
    audit = AuditLogger(audit_dir=str(nonexistent))
    # Should still log without crashing
    entry = audit.log(event_type="test", payload={})
    assert entry.signature is not None
