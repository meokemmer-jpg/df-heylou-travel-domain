"""DF-HeyLou-Travel-Domain Ground-Truth-Anchor [CRUX-MK].

K13 Independent-Ground-Truth (Patch-2 W35-C).

Pre-bound + Domain-Anker-Hook fuer Travel-Industry-Vendors
(MEWS / Booking / IDeaS) als systemische externe Anker zusaetzlich
zu GitHub-Daily + RFC3161.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DF_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_DF_ROOT))

from _df_common.ground_truth_anchor import (  # noqa: E402
    github_daily_anchor as _github_daily_anchor,
    rfc3161_anchor as _rfc3161_anchor,
    anchor_to_file,
    compute_chain_hash,
)
from _df_common.provenance_envelope import iso_now  # noqa: E402

DF_NAME = "df-heylou-travel-domain"


def github_daily_anchor(chain_hash: str, **kwargs) -> dict:
    """Pre-bound: df_name='df-heylou-travel-domain'."""
    kwargs.setdefault("df_name", DF_NAME)
    return _github_daily_anchor(chain_hash, **kwargs)


def rfc3161_anchor(chain_hash: str, **kwargs) -> dict:
    """Pre-bound: df_name='df-heylou-travel-domain'."""
    kwargs.setdefault("df_name", DF_NAME)
    return _rfc3161_anchor(chain_hash, **kwargs)


def domain_vendor_anchor(
    chain_hash: str,
    vendor: str = "mews",
    *,
    real_call: bool = False,
) -> dict:
    """Travel-Domain-specific anchor via vendor-API.

    Vendors supported (skeleton):
        - 'mews': PMS API booking-reference echo
        - 'booking': OTA booking confirmation
        - 'ideas': RMS rate-snapshot

    Returns:
        Skeleton record by default. real_call=True attempts vendor-API call.
    """
    record = {
        "anchor_type": f"domain_vendor_{vendor}",
        "df_name": DF_NAME,
        "vendor": vendor,
        "chain_hash": chain_hash,
        "iso_timestamp": iso_now(),
        "real_call": False,
        "vendor_ref": None,
        "skipped_reason": None,
    }
    if not real_call:
        record["skipped_reason"] = f"vendor={vendor} real_call=False (skeleton mode)"
        return record

    # Real-call would dispatch to vendor-API; skeleton-stub
    record["skipped_reason"] = f"vendor={vendor} real-call not implemented (skeleton)"
    return record


__all__ = [
    "github_daily_anchor",
    "rfc3161_anchor",
    "domain_vendor_anchor",
    "anchor_to_file",
    "compute_chain_hash",
    "DF_NAME",
]
