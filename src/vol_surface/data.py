from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import requests

DERIBIT = "https://www.deribit.com/api/v2/public"


@dataclass(frozen=True)
class SnapshotMeta:
    captured_at_utc: str
    currency: str
    summary_sha256: str
    instruments_sha256: str
    raw_rows: int
    merged_rows: int


def _get(method: str, params: dict) -> dict:
    response = requests.get(f"{DERIBIT}/{method}", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def _write_json(path: Path, payload: dict) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_deribit_option_snapshot(currency: str, raw_dir: Path) -> tuple[pd.DataFrame, SnapshotMeta]:
    """Fetch one auditable public option-chain snapshot from Deribit.

    Mark IV is consumed directly rather than reverse-engineering IV from a venue-specific
    premium convention. Prices are retained for provenance but are not used to claim a
    USD option-price fit.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = _get("get_book_summary_by_currency", {"currency": currency, "kind": "option"})
    instruments = _get("get_instruments", {"currency": currency, "kind": "option", "expired": "false"})
    captured = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    summary_hash = _write_json(raw_dir / "book_summary.json", summary)
    instruments_hash = _write_json(raw_dir / "instruments.json", instruments)

    s = pd.DataFrame(summary["result"])
    i = pd.DataFrame(instruments["result"])
    keep_i = ["instrument_name", "expiration_timestamp", "strike", "option_type", "creation_timestamp"]
    i = i[[c for c in keep_i if c in i.columns]].copy()
    merged = s.merge(i, on="instrument_name", how="inner", suffixes=("", "_instrument"))
    merged["captured_at_utc"] = captured

    meta = SnapshotMeta(
        captured_at_utc=captured,
        currency=currency,
        summary_sha256=summary_hash,
        instruments_sha256=instruments_hash,
        raw_rows=int(len(s)),
        merged_rows=int(len(merged)),
    )
    return merged, meta


def clean_surface_universe(
    df: pd.DataFrame,
    captured_at_utc: str,
    min_dte: float = 7.0,
    max_dte: float = 180.0,
    min_open_interest: float = 0.0,
    log_moneyness_abs_max: float = 0.65,
) -> pd.DataFrame:
    """Create a conservative, documented surface-calibration universe."""
    work = df.copy()
    captured = pd.Timestamp(captured_at_utc)
    work["expiry"] = pd.to_datetime(work["expiration_timestamp"], unit="ms", utc=True)
    work["T"] = (work["expiry"] - captured).dt.total_seconds() / (365.25 * 24 * 3600)
    work["dte"] = work["T"] * 365.25
    for col in ["strike", "mark_iv", "underlying_price", "interest_rate", "open_interest", "bid_price", "ask_price"]:
        if col in work:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    # Deribit mark_iv is expressed in volatility percentage points (e.g. 55 = 55%).
    work["iv"] = work["mark_iv"] / 100.0
    work["forward"] = work["underlying_price"].astype(float)
    work["k"] = np.log(work["strike"] / work["forward"])
    work["total_variance"] = work["iv"] ** 2 * work["T"]

    mask = (
        work["T"].gt(0)
        & work["dte"].between(min_dte, max_dte)
        & work["iv"].between(0.05, 3.0)
        & work["strike"].gt(0)
        & work["forward"].gt(0)
        & work["open_interest"].fillna(0).ge(min_open_interest)
        & work["k"].abs().le(log_moneyness_abs_max)
        & work["bid_price"].notna()
        & work["ask_price"].notna()
    )
    out = work.loc[mask].copy()
    return out.sort_values(["expiry", "strike", "option_type"]).reset_index(drop=True)
