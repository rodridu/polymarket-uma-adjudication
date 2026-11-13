"""Value semantics for UMA YES_OR_NO_QUERY prices as consumed by Polymarket adapters.

Two layers are kept separate on purpose:

* UMA layer   -- what the number means under the YES_OR_NO_QUERY identifier
                 (p1 / p2 / p3 / p4 defaults; UMA verification guide).
* Adapter layer -- what Polymarket's UmaCtfAdapter does with that number
                 (`_constructPayouts` and `_ignorePrice` in UmaCtfAdapter.sol).

`ctf_payout` is the CTF payout vector [outcome slot 0, outcome slot 1]. Slot labels are
market-specific (the ancillary data names p1/p2: "Yes"/"No", or two team names), so this
module never calls 1e18 "YES". It is "p2 -> payout [1,0]".
"""
from __future__ import annotations

from decimal import Decimal

E18 = 10 ** 18
INT256_MIN = -(2 ** 255)
USDC_DECIMALS = 6

# raw price -> (uma_value_class, ctf_payout, adapter_effect)
_KNOWN = {
    0:          ("P1",          "[0,1]", "SETTLE"),
    E18:        ("P2",          "[1,0]", "SETTLE"),
    E18 // 2:   ("P3_UNKNOWN",  "[1,1]", "SETTLE"),
    INT256_MIN: ("P4_TOO_EARLY", None,   "RESET"),
}


def signed256(u: int) -> int:
    """uint256 word -> int256."""
    return u - 2 ** 256 if u >= 2 ** 255 else u


def usdc_amount(raw: int) -> Decimal:
    """Raw USDC ERC-20 integer (6 decimals) → exact Decimal. Never use float."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError(f"expected int, got {type(raw).__name__}")
    if raw < 0:
        raise ValueError(f"USDC amount cannot be negative: {raw}")
    return Decimal(raw) / Decimal(10 ** USDC_DECIMALS)


def classify(price_raw: int | str) -> tuple[str, str | None, str]:
    """Return (uma_value_class, ctf_payout, adapter_effect) for a raw int256 price."""
    p = int(price_raw)
    if p in _KNOWN:
        return _KNOWN[p]
    # Any other value: the adapter reverts with InvalidOOPrice; UMA-side it is nonstandard.
    return ("NONSTANDARD", None, "ADAPTER_REVERT")
