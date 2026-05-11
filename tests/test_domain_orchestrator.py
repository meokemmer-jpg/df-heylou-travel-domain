"""Tests fuer domain_orchestrator.py [CRUX-MK]."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain_orchestrator import (
    HeyLouTravelDomainOrchestrator,
    DomainPhase,
    PhaseStatus,
    DomainLoopReport,
)


def test_orchestrator_runs_all_5_phases():
    """5-Phase-Loop: report contains exactly 5 PhaseResults."""
    orch = HeyLouTravelDomainOrchestrator()
    report = orch.run("hildesheim", "Daily Health Check")
    assert isinstance(report, DomainLoopReport)
    assert len(report.phases) == 5
    expected_phases = {
        DomainPhase.KG_QUERY,
        DomainPhase.ADAPTER_DISPATCH,
        DomainPhase.LLM_ROUTE,
        DomainPhase.AUDIT_LOG,
        DomainPhase.PUBLISH_SUMMARY,
    }
    actual_phases = {p.phase for p in report.phases}
    assert actual_phases == expected_phases


def test_orchestrator_sandbox_default_completes():
    """LC1 sandbox-default: full loop completes without real APIs."""
    orch = HeyLouTravelDomainOrchestrator()
    report = orch.run("hildesheim", "Test goal")
    assert report.sandbox_mode is True
    # In sandbox: most phases should complete (no real API failures)
    completed = sum(1 for p in report.phases if p.status == PhaseStatus.COMPLETE)
    assert completed >= 4  # at least 4/5 phases complete


def test_orchestrator_unknown_hotel_handled_gracefully():
    """K11 try/except: unknown hotel doesn't crash orchestrator."""
    orch = HeyLouTravelDomainOrchestrator()
    report = orch.run("nonexistent-hotel-xyz", "Test goal")
    # KG_QUERY phase should fail, but loop continues
    kg_phase = next(p for p in report.phases if p.phase == DomainPhase.KG_QUERY)
    assert kg_phase.status == PhaseStatus.FAILED
    assert kg_phase.error is not None
    # Final status: partial or failed (not complete)
    assert report.final_status in ("partial", "failed")


def test_loop_report_has_unique_id():
    """K12 provenance: each loop_id is unique (timestamp-based)."""
    orch = HeyLouTravelDomainOrchestrator()
    r1 = orch.run("hildesheim", "Goal 1")
    import time
    time.sleep(1.1)  # ensure timestamp differs
    r2 = orch.run("hildesheim", "Goal 2")
    assert r1.loop_id != r2.loop_id


def test_main_cli_dry_run_returns_0():
    """CLI dry-run: prints would-run, exits 0."""
    from src.domain_orchestrator import main
    rc = main(["--hotel-id", "hildesheim", "--goal", "Test", "--dry-run"])
    assert rc == 0


def test_main_cli_full_run_returns_0_or_1():
    """LaunchAgent-Pattern: complete/partial -> exit 0, failed -> exit 1."""
    from src.domain_orchestrator import main
    rc = main(["--hotel-id", "hildesheim", "--goal", "Test"])
    assert rc in (0, 1)
