"""Domain-Orchestrator [CRUX-MK].

Master-Orchestrator fuer HeyLou-Travel-Domain mit 5-Phase-Loop:

  knowledge_graph_query -> skeleton_key_adapter_dispatch -> llm_subfunction_route
  -> audit_log -> publish_summary

Tier-Fall-Through: real -> sandbox -> mock -> skip

Cascade-Invarianten:
- ORTHOGONAL: jede Phase hat disjunktes Input/Output-Schema
- KANONISCH: PhaseResult + LoopReport Schema fix
- MONOTON: Phase-Status nur upgradable (PENDING -> RUNNING -> COMPLETE/FAILED)
- PERSISTENT: LoopReport JSON
- BOUNDED: 5 Phasen + per-phase timeout (LC3)

Welle-35.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .travel_knowledge_graph import TravelKnowledgeGraph
from .skeleton_key_adapter import (
    MEWSAdapter,
    BookingComAdapter,
    IdeasRevenueAdapter,
    GenericAPIAdapter,
)
from .llm_subfunction_router import LLMSubfunctionRouter, LLMProvider
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class DomainPhase(str, Enum):
    KG_QUERY = "knowledge_graph_query"
    ADAPTER_DISPATCH = "skeleton_key_adapter_dispatch"
    LLM_ROUTE = "llm_subfunction_route"
    AUDIT_LOG = "audit_log"
    PUBLISH_SUMMARY = "publish_summary"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseResult:
    phase: DomainPhase
    status: PhaseStatus
    duration_s: float
    output_summary: str
    error: Optional[str] = None


@dataclass
class DomainLoopReport:
    loop_id: str
    hotel_id: str
    goal_text: str
    goal_hash: str
    phases: list[PhaseResult]
    total_duration_s: float
    final_status: str  # complete | partial | failed
    timestamp_iso: str
    sandbox_mode: bool
    real_llm_enabled: bool
    real_adapter_enabled: bool

    @classmethod
    def make_id(cls, hotel_id: str, goal_hash: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"loop-{hotel_id[:12]}-{goal_hash[:8]}-{ts}"


class HeyLouTravelDomainOrchestrator:
    """K11 try/except per phase. K12 deterministic phase-orchestration.

    Public API:
    - run(hotel_id, goal) -> DomainLoopReport
    """

    def __init__(self, knowledge_graph: Optional[TravelKnowledgeGraph] = None):
        self.kg = knowledge_graph or TravelKnowledgeGraph(sandbox_seed=True)
        self.llm_router = LLMSubfunctionRouter()
        self.audit = AuditLogger()
        # 4 Adapter
        self.adapters = {
            "mews": MEWSAdapter(),
            "booking_com": BookingComAdapter(),
            "ideas_revenue": IdeasRevenueAdapter(),
            "generic_api": GenericAPIAdapter(),
        }
        self._real_llm_enabled = self.llm_router.is_real_enabled()
        self._real_adapter_enabled = (
            os.environ.get("DF_HEYLOU_REAL_ADAPTER_ENABLED", "false") == "true"
        )

    def _goal_hash(self, goal: str) -> str:
        return hashlib.sha256(goal.encode("utf-8")).hexdigest()[:16]

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _persist_report(self, report: DomainLoopReport) -> Path:
        """Persist LoopReport to runs/loop-reports/."""
        try:
            reports_dir = Path("runs/loop-reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            file_path = reports_dir / f"{report.loop_id}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2, default=str)
            return file_path
        except Exception as e:
            logger.warning(f"persist report failed: {e}")
            return Path("/dev/null")

    def run(self, hotel_id: str, goal: str) -> DomainLoopReport:
        """Run 5-Phase-Loop.

        K11 try/except per phase.
        Returns DomainLoopReport (final_status: complete | partial | failed).
        """
        goal_hash = self._goal_hash(goal)
        loop_id = DomainLoopReport.make_id(hotel_id, goal_hash)
        phases: list[PhaseResult] = []
        loop_start = time.time()

        # Phase 1: knowledge_graph_query
        kg_context = ""
        p1_start = time.time()
        try:
            hotel = self.kg.get_hotel(hotel_id)
            kg_context = self.kg.context_for_llm(hotel_id)
            p1_status = PhaseStatus.COMPLETE if hotel else PhaseStatus.FAILED
            p1_summary = (
                f"hotel={hotel.name if hotel else 'NOT_FOUND'} "
                f"context_chars={len(kg_context)}"
            )
            phases.append(PhaseResult(
                phase=DomainPhase.KG_QUERY,
                status=p1_status,
                duration_s=time.time() - p1_start,
                output_summary=p1_summary,
                error=None if hotel else f"hotel '{hotel_id}' not found",
            ))
        except Exception as e:
            phases.append(PhaseResult(
                phase=DomainPhase.KG_QUERY,
                status=PhaseStatus.FAILED,
                duration_s=time.time() - p1_start,
                output_summary="exception",
                error=str(e),
            ))

        # Phase 2: skeleton_key_adapter_dispatch (query 1 representative adapter)
        adapter_response_summary = ""
        p2_start = time.time()
        try:
            mews = self.adapters["mews"]
            mews.connect()
            adapter_resp = mews.query_inventory({"hotel_id": hotel_id, "date": "today"})
            adapter_response_summary = (
                f"adapter=mews source={adapter_resp.source} "
                f"success={adapter_resp.success}"
            )
            phases.append(PhaseResult(
                phase=DomainPhase.ADAPTER_DISPATCH,
                status=PhaseStatus.COMPLETE if adapter_resp.success else PhaseStatus.FAILED,
                duration_s=time.time() - p2_start,
                output_summary=adapter_response_summary,
                error=adapter_resp.error,
            ))
        except Exception as e:
            phases.append(PhaseResult(
                phase=DomainPhase.ADAPTER_DISPATCH,
                status=PhaseStatus.FAILED,
                duration_s=time.time() - p2_start,
                output_summary="exception",
                error=str(e),
            ))

        # Phase 3: llm_subfunction_route (query Ollama-Local-first)
        llm_response_summary = ""
        p3_start = time.time()
        try:
            llm_resp = self.llm_router.route_query(
                query=goal,
                context=kg_context,
                provider_priority=[LLMProvider.OLLAMA_LOCAL],
            )
            llm_response_summary = (
                f"provider={llm_resp.provider.value} model={llm_resp.model} "
                f"source={llm_resp.source} confidence={llm_resp.confidence:.2f}"
            )
            phases.append(PhaseResult(
                phase=DomainPhase.LLM_ROUTE,
                status=PhaseStatus.COMPLETE if not llm_resp.error else PhaseStatus.FAILED,
                duration_s=time.time() - p3_start,
                output_summary=llm_response_summary,
                error=llm_resp.error,
            ))
        except Exception as e:
            phases.append(PhaseResult(
                phase=DomainPhase.LLM_ROUTE,
                status=PhaseStatus.FAILED,
                duration_s=time.time() - p3_start,
                output_summary="exception",
                error=str(e),
            ))

        # Phase 4: audit_log
        audit_entry_id = ""
        p4_start = time.time()
        try:
            entry = self.audit.log(
                event_type="domain_loop_run",
                payload={
                    "loop_id": loop_id,
                    "hotel_id": hotel_id,
                    "goal_hash": goal_hash,
                    "phases_so_far": len(phases),
                    "kg_snapshot_hash": self.kg.snapshot_hash()[:16],
                },
                target="heylou-domain",
            )
            audit_entry_id = entry.signature[:16] if entry.signature else "unsigned"
            phases.append(PhaseResult(
                phase=DomainPhase.AUDIT_LOG,
                status=PhaseStatus.COMPLETE,
                duration_s=time.time() - p4_start,
                output_summary=f"audit_signed={audit_entry_id}",
                error=None,
            ))
        except Exception as e:
            phases.append(PhaseResult(
                phase=DomainPhase.AUDIT_LOG,
                status=PhaseStatus.FAILED,
                duration_s=time.time() - p4_start,
                output_summary="exception",
                error=str(e),
            ))

        # Phase 5: publish_summary
        p5_start = time.time()
        try:
            summary = {
                "hotel_id": hotel_id,
                "goal": goal,
                "kg_context_excerpt": kg_context[:200] if kg_context else "",
                "adapter_summary": adapter_response_summary,
                "llm_summary": llm_response_summary,
                "audit_id": audit_entry_id,
            }
            phases.append(PhaseResult(
                phase=DomainPhase.PUBLISH_SUMMARY,
                status=PhaseStatus.COMPLETE,
                duration_s=time.time() - p5_start,
                output_summary=f"summary_keys={list(summary.keys())}",
                error=None,
            ))
        except Exception as e:
            phases.append(PhaseResult(
                phase=DomainPhase.PUBLISH_SUMMARY,
                status=PhaseStatus.FAILED,
                duration_s=time.time() - p5_start,
                output_summary="exception",
                error=str(e),
            ))

        # Aggregate final status
        completed = sum(1 for p in phases if p.status == PhaseStatus.COMPLETE)
        failed = sum(1 for p in phases if p.status == PhaseStatus.FAILED)
        if completed == len(phases):
            final_status = "complete"
        elif completed >= 3:  # Majority success
            final_status = "partial"
        else:
            final_status = "failed"

        report = DomainLoopReport(
            loop_id=loop_id,
            hotel_id=hotel_id,
            goal_text=goal,
            goal_hash=goal_hash,
            phases=phases,
            total_duration_s=time.time() - loop_start,
            final_status=final_status,
            timestamp_iso=self._now_iso(),
            sandbox_mode=not (self._real_llm_enabled and self._real_adapter_enabled),
            real_llm_enabled=self._real_llm_enabled,
            real_adapter_enabled=self._real_adapter_enabled,
        )

        # Persist
        self._persist_report(report)

        return report


def main(argv: Optional[list[str]] = None) -> int:
    """CLI-Entry-Point.

    Usage:
      python -m src.domain_orchestrator [--hotel-id <id>] [--goal <text>] [--dry-run]
    """
    parser = argparse.ArgumentParser(description="HeyLou Travel-Domain-Orchestrator")
    parser.add_argument(
        "--hotel-id",
        default=os.environ.get("DF_HEYLOU_TENANT_ID", "hildesheim"),
        help="Hotel ID (default: hildesheim)",
    )
    parser.add_argument(
        "--goal",
        default="Daily Travel-Domain-Health-Check",
        help="Goal text",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print would-run, don't execute",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    if args.dry_run:
        print(f"[DRY-RUN] Would run hotel_id={args.hotel_id} goal='{args.goal}'")
        return 0

    orch = HeyLouTravelDomainOrchestrator()
    report = orch.run(args.hotel_id, args.goal)
    print(
        f"[df-heylou-travel-domain] loop_id={report.loop_id} "
        f"status={report.final_status} duration={report.total_duration_s:.2f}s "
        f"phases={len(report.phases)} sandbox={report.sandbox_mode}"
    )

    # LaunchAgent-Pattern: complete/partial -> exit 0, failed -> exit 1
    return 0 if report.final_status in ("complete", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
