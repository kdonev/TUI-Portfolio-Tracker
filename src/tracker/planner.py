from typing import List, Dict, Optional
from tracker.db import list_etfs, get_etf_holdings, get_portfolio_value
import math


def compute_plan(amount: float, mode: str = "new", precision: int = 6) -> Dict[str, object]:
    """Compute a buy plan.

    mode:
      - 'new' : allocate the provided amount according to target_pct
      - 'rebalance': compute target based on (current_portfolio_value + amount) and buy/sell to reach targets; we only provide buy plan for positive amounts

    precision: default number of decimal places to round shares down to (floor); overridden per ETF based on supports_fractions

    Returns a dict with rows, summary info, and list of tickers with missing prices.
    """
    etfs = list_etfs()
    rows: List[Dict[str, Optional[float]]] = []

    total_current = get_portfolio_value()
    total_after = total_current + amount

    planned_spend = 0.0
    missing_prices: List[str] = []

    for e in etfs:
        # Determine precision for this ETF
        etf_precision = precision if e.supports_fractions else 0
        
        shares, current_value = get_etf_holdings(e.id)
        price = e.last_price
        if mode == "new":
            target_value = amount * (e.target_pct / 100.0)
            raw_to_buy_amount = target_value
        else:  # rebalance
            target_value = total_after * (e.target_pct / 100.0)
            raw_to_buy_amount = target_value - current_value
        if raw_to_buy_amount < 0:
            raw_to_buy_amount = 0.0

        if not price or price <= 0:
            to_buy_shares = None
            to_buy_amount = 0.0
            missing_prices.append(e.ticker)
        else:
            raw_shares = raw_to_buy_amount / price
            # floor shares to precision based on ETF supports_fractions
            factor = 10 ** etf_precision
            floored_shares = math.floor(raw_shares * factor) / factor
            to_buy_shares = floored_shares
            to_buy_amount = floored_shares * price

        row = {
            "etf_id": e.id,
            "ticker": e.ticker,
            "target_pct": e.target_pct,
            "current_shares": shares,
            "last_price": price if price else None,
            "current_value": current_value,
            "target_value": target_value,
            "to_buy_amount": to_buy_amount,
            "to_buy_shares": to_buy_shares,
        }
        planned_spend += to_buy_amount
        rows.append(row)

    leftover = amount - planned_spend
    if leftover < 0:
        leftover = 0.0

    # Allocate leftover to fractional ETFs proportionally by target_pct
    if leftover > 0.001:  # Only if leftover is significant
        fractional_etfs = [r for r in rows if etfs[next(i for i, e in enumerate(etfs) if e.id == r['etf_id'])].supports_fractions]
        total_frac_pct = sum(r['target_pct'] for r in fractional_etfs)
        
        if total_frac_pct > 0:
            for row in fractional_etfs:
                if row['last_price'] and row['last_price'] > 0:
                    # Allocate proportional share of leftover based on target_pct
                    allocated = leftover * (row['target_pct'] / total_frac_pct)
                    extra_shares = allocated / row['last_price']
                    # Add to existing to_buy_shares (with full precision)
                    if row['to_buy_shares'] is not None:
                        row['to_buy_shares'] += extra_shares
                    else:
                        row['to_buy_shares'] = extra_shares
                    row['to_buy_amount'] += allocated
                    planned_spend += allocated
            
            leftover = amount - planned_spend
            if leftover < 0:
                leftover = 0.0

    return {
        "mode": mode,
        "amount": amount,
        "precision": precision,
        "total_current": total_current,
        "total_after": total_after,
        "rows": rows,
        "planned_spend": planned_spend,
        "leftover": leftover,
        "missing_prices": missing_prices,
    }