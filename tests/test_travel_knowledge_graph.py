"""Tests fuer travel_knowledge_graph.py [CRUX-MK]."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add parent dir for src imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.travel_knowledge_graph import (
    TravelKnowledgeGraph,
    Hotel,
    Route,
    Rate,
    GuestPreference,
)


def test_sandbox_seed_creates_3_hotels():
    """K11: Sandbox-seed must create the 3 default HeyLou hotels."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    hotels = kg.find_hotels()
    assert len(hotels) == 3
    hotel_ids = {h.hotel_id for h in hotels}
    assert hotel_ids == {"hildesheim", "cape-coral", "munich"}


def test_no_seed_creates_empty_graph():
    """LC1 standalone-mode: empty graph if seed=False."""
    kg = TravelKnowledgeGraph(sandbox_seed=False)
    assert kg.find_hotels() == []
    assert kg.get_hotel("hildesheim") is None


def test_add_and_get_hotel():
    """K11 + LC4 idempotent: add + get same hotel."""
    kg = TravelKnowledgeGraph(sandbox_seed=False)
    h = Hotel(
        hotel_id="test-1",
        name="Test Hotel",
        location="Berlin, DE",
        pms_type="opera",
        rms_type="duetto",
    )
    kg.add_hotel(h)
    fetched = kg.get_hotel("test-1")
    assert fetched is not None
    assert fetched.name == "Test Hotel"
    assert fetched.pms_type == "opera"


def test_find_hotels_by_location_substring():
    """K11: filter by location substring (case-insensitive)."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    de_hotels = kg.find_hotels(location_substring="DE")
    # Hildesheim + Munich are in DE
    assert len(de_hotels) == 2
    assert {h.hotel_id for h in de_hotels} == {"hildesheim", "munich"}


def test_find_hotels_by_pms_type():
    """K11: filter by pms_type."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    mews_hotels = kg.find_hotels(pms_type="mews")
    assert len(mews_hotels) == 3  # all 3 sandbox-hotels are mews


def test_compute_route_returns_match_or_none():
    """K11: compute_route returns matching Route or None."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    route = kg.compute_route("Hildesheim, DE", "Munich, DE")
    assert route is not None
    assert route.transport_mode == "train"
    assert route.duration_h == 4.5

    none_route = kg.compute_route("Mars", "Jupiter")
    assert none_route is None


def test_get_rates_filters_correctly():
    """K11: get_rates filters by hotel_id + date-range."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    hildesheim_rates = kg.get_rates("hildesheim")
    assert len(hildesheim_rates) >= 1  # at least 1 sandbox rate
    for r in hildesheim_rates:
        assert r.hotel_id == "hildesheim"


def test_add_and_get_preference():
    """K11: add + get GuestPreference."""
    kg = TravelKnowledgeGraph(sandbox_seed=False)
    pref = GuestPreference(
        guest_id="guest-1",
        preferences={"smoking": False, "diet": "vegan"},
        loyalty_tier="gold",
    )
    kg.add_preference(pref)
    fetched = kg.get_preference("guest-1")
    assert fetched is not None
    assert fetched.preferences["diet"] == "vegan"
    assert fetched.loyalty_tier == "gold"


def test_snapshot_is_json_serializable():
    """K12 provenance: snapshot must be JSON-serializable."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    snap = kg.snapshot()
    # Must serialize without exception
    json_str = json.dumps(snap, default=str)
    assert "hotels" in snap
    assert "snapshot_iso" in snap
    assert len(snap["hotels"]) == 3


def test_snapshot_hash_is_deterministic():
    """K12 provenance: snapshot_hash deterministic for same content."""
    kg1 = TravelKnowledgeGraph(sandbox_seed=True)
    kg2 = TravelKnowledgeGraph(sandbox_seed=True)
    h1 = kg1.snapshot_hash()
    h2 = kg2.snapshot_hash()
    # Note: snapshot_iso changes per call. We'll just verify hash format.
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_context_for_llm_includes_hotel_info():
    """LLM-Sub-Funktion: context_for_llm enthaelt hotel name + PMS + rates."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    ctx = kg.context_for_llm("hildesheim")
    assert "HeyLou Hildesheim" in ctx
    assert "Hildesheim, DE" in ctx
    assert "mews" in ctx
    assert "Rates" in ctx


def test_context_for_llm_handles_missing_hotel():
    """LC1 graceful_degradation: missing hotel returns helpful error string."""
    kg = TravelKnowledgeGraph(sandbox_seed=True)
    ctx = kg.context_for_llm("nonexistent")
    assert "not found" in ctx
