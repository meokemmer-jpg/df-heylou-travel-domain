from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.heylou_travel_domain import (
    Hotel,
    Rate,
    Route,
    SQLiteTravelRepository,
    TravelDomainKernel,
    TravelIntent,
    verify_result_signature,
)


def build_file_backed_domain(tmp_path):
    db_path = tmp_path / "travel-domain.sqlite3"
    repo = SQLiteTravelRepository(db_path)
    repo.replace_catalog(
        hotels=[
            Hotel("ber-business", "Mitte Business Base", "Berlin", "Germany", 52.52, 13.405, 4.1, ["wifi", "meeting_rooms"]),
            Hotel("bcn-sea", "Barcelona Sea Spa", "Barcelona", "Spain", 41.3874, 2.1686, 4.8, ["wifi", "pool", "spa"]),
            Hotel("inn-alpine", "Innsbruck Alpine Lodge", "Innsbruck", "Austria", 47.2692, 11.4041, 4.4, ["wifi", "ski_storage", "breakfast"]),
        ],
        rates=[
            Rate("ber-business", "standard", 95.0),
            Rate("bcn-sea", "standard", 150.0),
            Rate("inn-alpine", "single", 70.0),
        ],
        routes=[
            Route("Berlin", "Barcelona", "flight", 155, 70.0),
            Route("Berlin", "Innsbruck", "train", 360, 45.0),
            Route("Berlin", "Berlin", "train", 20, 3.0),
        ],
    )
    assert db_path.exists()
    assert db_path.stat().st_size > 0
    assert repo.catalog_counts() == {"hotels": 3, "rates": 3, "routes": 3}
    return TravelDomainKernel(repo)


def test_df_heylou_travel_domain_discriminates_adversarial_opposite_inputs(tmp_path):
    domain = build_file_backed_domain(tmp_path)

    seaside_intent = TravelIntent(
        user_id="traveler-sea",
        origin="Berlin",
        desired_city="Barcelona",
        avoid_cities=["Innsbruck"],
        max_budget_eur=240.0,
        required_amenities=["pool", "spa"],
        preferred_transport="flight",
        nights=1,
    )
    alpine_counter_intent = TravelIntent(
        user_id="traveler-snow",
        origin="Berlin",
        desired_city="Innsbruck",
        avoid_cities=["Barcelona"],
        max_budget_eur=130.0,
        required_amenities=["ski_storage", "breakfast"],
        preferred_transport="train",
        nights=1,
    )

    seaside = domain.recommend_trip(seaside_intent)
    alpine = domain.recommend_trip(alpine_counter_intent)

    assert verify_result_signature(seaside) is True
    assert verify_result_signature(alpine) is True
    assert seaside["recommendation"] is not None
    assert alpine["recommendation"] is not None

    assert seaside["recommendation"]["city"] == "Barcelona"
    assert seaside["recommendation"]["hotel_id"] == "bcn-sea"
    assert seaside["recommendation"]["transport_mode"] == "flight"
    assert "within_budget" in seaside["recommendation"]["reasons"]

    assert alpine["recommendation"]["city"] == "Innsbruck"
    assert alpine["recommendation"]["hotel_id"] == "inn-alpine"
    assert alpine["recommendation"]["transport_mode"] == "train"
    assert "within_budget" in alpine["recommendation"]["reasons"]

    assert seaside["recommendation"]["hotel_id"] != alpine["recommendation"]["hotel_id"]
    assert seaside["recommendation"]["city"] != alpine["recommendation"]["city"]
    assert seaside["payload_hash"] != alpine["payload_hash"]


def test_repository_rejects_in_memory_fixture():
    with pytest.raises(ValueError):
        SQLiteTravelRepository(":memory:")
