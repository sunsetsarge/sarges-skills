#!/usr/bin/env python3
"""
projections.py -- fills analysis.debt, analysis.emergency_fund, analysis.retirement,
analysis.cash_flow, analysis.net_worth in a plan_model.json document.

Python 3.10, stdlib only.

Usage:
    python projections.py plan_model.json --out plan_model.json

This script NEVER mutates inputs (accounts, transactions, holdings, assumptions,
profile, market_context). It only reads them and (re)writes the `analysis` block.
All math degrades to nulls on empty/zero/missing inputs -- it never crashes.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Safe helpers
# --------------------------------------------------------------------------- #

def safe_div(numerator: float, denominator: float) -> Optional[float]:
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return numerator / denominator


def round2(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Net worth
# --------------------------------------------------------------------------- #

def compute_net_worth(model: dict) -> dict:
    accounts = model.get("accounts") or []
    assets = 0.0
    liabilities = 0.0
    for acct in accounts:
        bal = acct.get("balance")
        if bal is None:
            continue
        if acct.get("is_liability"):
            liabilities += abs(bal)
        else:
            assets += bal

    net = assets - liabilities
    return {
        "assets": round2(assets),
        "liabilities": round2(liabilities),
        "net": round2(net),
        "trend": [],  # no historical snapshots available from a single parse
    }


# --------------------------------------------------------------------------- #
# Cash flow
# --------------------------------------------------------------------------- #

def compute_cash_flow(model: dict) -> dict:
    transactions = model.get("transactions") or []
    non_transfer = [t for t in transactions if not t.get("is_transfer")]

    if not non_transfer:
        return {
            "monthly_income_avg": None,
            "monthly_expenses_avg": None,
            "surplus": None,
            "savings_rate_pct": None,
            "by_category": {},
            "income_streams": [],
        }

    # Determine number of distinct months covered, to average correctly.
    months_seen = set()
    for t in non_transfer:
        date = t.get("date") or ""
        if len(date) >= 7:
            months_seen.add(date[:7])
    n_months = max(len(months_seen), 1)

    total_income = 0.0
    total_expenses = 0.0
    by_category: dict[str, float] = {}
    income_by_desc: dict[str, list[float]] = {}

    for t in non_transfer:
        amount = t.get("amount")
        if amount is None:
            continue
        category = t.get("category") or "uncategorized"

        if amount > 0:
            total_income += amount
        else:
            total_expenses += -amount
            by_category[category] = by_category.get(category, 0.0) + (-amount)

        if t.get("is_income") or (amount > 0 and category == "income"):
            key = category
            income_by_desc.setdefault(key, []).append(amount)

    monthly_income_avg = total_income / n_months
    monthly_expenses_avg = total_expenses / n_months
    surplus = monthly_income_avg - monthly_expenses_avg
    savings_rate = safe_div(surplus, monthly_income_avg)
    savings_rate_pct = round2(savings_rate * 100) if savings_rate is not None else None

    by_category_avg = {k: round2(v / n_months) for k, v in by_category.items()}

    # Build income streams: classify volatility by coefficient of variation across months.
    income_streams = []
    monthly_income_totals: dict[str, float] = {}
    for t in non_transfer:
        if t.get("is_income") or (t.get("amount", 0) > 0 and (t.get("category") == "income")):
            date = t.get("date") or ""
            ym = date[:7] if len(date) >= 7 else "unknown"
            monthly_income_totals[ym] = monthly_income_totals.get(ym, 0.0) + t.get("amount", 0.0)

    if monthly_income_totals:
        vals = list(monthly_income_totals.values())
        avg = sum(vals) / len(vals)
        variance = sum((v - avg) ** 2 for v in vals) / len(vals) if len(vals) > 0 else 0.0
        std = variance ** 0.5
        cv = safe_div(std, avg) or 0.0
        volatility = "irregular" if cv > 0.15 else "steady"
        income_streams.append({
            "name": "combined income",
            "monthly_avg": round2(avg),
            "volatility": volatility,
        })

    return {
        "monthly_income_avg": round2(monthly_income_avg),
        "monthly_expenses_avg": round2(monthly_expenses_avg),
        "surplus": round2(surplus),
        "savings_rate_pct": savings_rate_pct,
        "by_category": by_category_avg,
        "income_streams": income_streams,
    }


# --------------------------------------------------------------------------- #
# Emergency fund
# --------------------------------------------------------------------------- #

def compute_emergency_fund(model: dict, cash_flow: dict) -> dict:
    accounts = model.get("accounts") or []
    liquid_types = {"checking", "savings"}
    liquid_cash = sum(
        (a.get("balance") or 0.0)
        for a in accounts
        if a.get("type") in liquid_types and not a.get("is_liability")
    )

    monthly_expenses = cash_flow.get("monthly_expenses_avg")
    if not monthly_expenses:
        return {
            "runway_months": None,
            "target_months": (model.get("assumptions") or {}).get("emergency_fund_months", 6),
            "target_amount": None,
            "gap": None,
        }

    runway = safe_div(liquid_cash, monthly_expenses)

    base_target_months = (model.get("assumptions") or {}).get("emergency_fund_months", 6) or 6
    # Widen target if any income stream is irregular, or profile says irregular/mixed income.
    income_streams = cash_flow.get("income_streams") or []
    has_irregular = any(s.get("volatility") == "irregular" for s in income_streams)
    profile_income_structure = (model.get("profile") or {}).get("income_structure")
    if has_irregular or profile_income_structure in ("irregular", "mixed"):
        target_months = max(base_target_months, 9)
    else:
        target_months = base_target_months

    target_amount = monthly_expenses * target_months
    gap = target_amount - liquid_cash

    return {
        "runway_months": round2(runway),
        "target_months": target_months,
        "target_amount": round2(target_amount),
        "gap": round2(gap),
    }


# --------------------------------------------------------------------------- #
# Debt payoff simulation (avalanche & snowball)
# --------------------------------------------------------------------------- #

def _simulate_payoff(
    debts: list[dict], extra_monthly_payment: float, order_key: str, max_months: int = 1200
) -> dict:
    """
    debts: list of {"account_id", "balance", "apr", "min_payment"}
    order_key: "avalanche" (highest apr first) or "snowball" (smallest balance first)
    Returns {"months_to_free": int|None, "total_interest": float, "order": [account_id,...]}
    """
    working = [dict(d) for d in debts if (d.get("balance") or 0) > 0]
    if not working:
        return {"months_to_free": 0, "total_interest": 0.0, "order": []}

    if order_key == "avalanche":
        priority_order = sorted(working, key=lambda d: (-(d.get("apr") or 0.0)))
    else:  # snowball
        priority_order = sorted(working, key=lambda d: (d.get("balance") or 0.0))

    order_ids = [d["account_id"] for d in priority_order]

    balances = {d["account_id"]: float(d.get("balance") or 0.0) for d in working}
    aprs = {d["account_id"]: float(d.get("apr") or 0.0) for d in working}
    mins = {d["account_id"]: float(d.get("min_payment") or 0.0) for d in working}

    total_interest = 0.0
    month = 0
    extra_pool = float(extra_monthly_payment or 0.0)

    while any(b > 0.005 for b in balances.values()) and month < max_months:
        month += 1
        # Accrue interest first.
        for acct_id, bal in balances.items():
            if bal <= 0:
                continue
            monthly_rate = aprs[acct_id] / 12.0
            interest = bal * monthly_rate
            total_interest += interest
            balances[acct_id] = bal + interest

        # Pay minimums on all open debts.
        for acct_id in balances:
            if balances[acct_id] <= 0:
                continue
            pay = min(mins.get(acct_id, 0.0), balances[acct_id])
            balances[acct_id] -= pay

        # Apply extra payment pool to priority order (avalanche/snowball).
        remaining_extra = extra_pool
        for acct_id in order_ids:
            if remaining_extra <= 0:
                break
            bal = balances.get(acct_id, 0.0)
            if bal <= 0:
                continue
            pay = min(remaining_extra, bal)
            balances[acct_id] -= pay
            remaining_extra -= pay

        # Rollover: if a debt was paid to zero, its min payment becomes available as
        # extra next cycle (standard avalanche/snowball rollover behavior).
        newly_free_min = sum(
            mins.get(acct_id, 0.0) for acct_id in order_ids if balances.get(acct_id, 0.0) <= 0.005
        )
        # Recompute extra pool for next iteration: original extra + freed minimums,
        # minus minimums of accounts already closed (they no longer need a minimum).
        extra_pool = extra_monthly_payment + sum(
            mins.get(acct_id, 0.0)
            for acct_id in order_ids
            if balances.get(acct_id, 0.0) <= 0.005
        )

        if all(b <= 0.005 for b in balances.values()):
            break

    months_to_free = month if month < max_months else None

    return {
        "months_to_free": months_to_free,
        "total_interest": round2(total_interest),
        "order": order_ids,
    }


def compute_debt(model: dict) -> dict:
    accounts = model.get("accounts") or []
    debt_accounts = [a for a in accounts if a.get("is_liability") and (a.get("balance") or 0) != 0]

    if not debt_accounts:
        return {
            "total": 0.0,
            "items": [],
            "avalanche": {"months_to_free": 0, "total_interest": 0.0, "order": []},
            "snowball": {"months_to_free": 0, "total_interest": 0.0, "order": []},
        }

    items = []
    debts_for_sim = []
    total = 0.0
    for a in debt_accounts:
        bal = abs(a.get("balance") or 0.0)
        apr = a.get("apr_or_apy") or 0.0
        # Heuristic min payment if not otherwise known: 2% of balance or $25, whichever
        # is greater -- a common card-issuer floor. This is a modeling assumption, not
        # an observed fact; callers should treat min_payment as editable.
        min_payment = max(bal * 0.02, 25.0) if bal > 0 else 0.0
        total += bal
        items.append({
            "account_id": a["id"],
            "balance": round2(bal),
            "apr": apr,
            "min_payment": round2(min_payment),
        })
        debts_for_sim.append({
            "account_id": a["id"], "balance": bal, "apr": apr, "min_payment": min_payment,
        })

    # Extra monthly payment pool for acceleration: assumption-driven. We use a modest
    # default extra of $200/mo split across the priority order if no monthly_contribution
    # signal exists; if assumptions.monthly_contribution is present we don't raid it here
    # (that's for retirement) -- debt extra is independent and conservative.
    extra_monthly = 200.0

    avalanche = _simulate_payoff(debts_for_sim, extra_monthly, "avalanche")
    snowball = _simulate_payoff(debts_for_sim, extra_monthly, "snowball")

    return {
        "total": round2(total),
        "items": items,
        "avalanche": avalanche,
        "snowball": snowball,
    }


# --------------------------------------------------------------------------- #
# Retirement projection
# --------------------------------------------------------------------------- #

def _project_fv(
    current_value: float, monthly_contribution: float, annual_return_pct: float,
    months: int
) -> float:
    """Future value of a lump sum + monthly contributions, compounded monthly."""
    monthly_rate = (annual_return_pct or 0.0) / 100.0 / 12.0
    value = current_value
    for _ in range(months):
        value = value * (1 + monthly_rate) + monthly_contribution
    return value


def compute_retirement(model: dict) -> dict:
    assumptions = model.get("assumptions") or {}
    current_age = assumptions.get("current_age")
    retirement_age = assumptions.get("retirement_age")
    monthly_contribution = assumptions.get("monthly_contribution") or 0.0
    base_return = assumptions.get("expected_return_pct")

    scenarios_default = {
        "best": {"return_pct": 8.0},
        "base": {"return_pct": base_return if base_return is not None else 6.0},
        "worst": {"return_pct": 3.0},
    }

    if current_age is None or retirement_age is None or retirement_age <= current_age:
        return {
            "scenarios": {
                "best": {"return_pct": scenarios_default["best"]["return_pct"], "value_at_retirement": None},
                "base": {"return_pct": scenarios_default["base"]["return_pct"], "value_at_retirement": None},
                "worst": {"return_pct": scenarios_default["worst"]["return_pct"], "value_at_retirement": None},
            },
            "projection_series": [],
        }

    # Starting value: sum of retirement + brokerage account balances (investable assets).
    accounts = model.get("accounts") or []
    investable_types = {"retirement", "brokerage"}
    current_value = sum(
        (a.get("balance") or 0.0) for a in accounts
        if a.get("type") in investable_types and not a.get("is_liability")
    )

    months_total = int(round((retirement_age - current_age) * 12))
    months_total = max(months_total, 0)

    scenarios = {}
    for key, cfg in scenarios_default.items():
        fv = _project_fv(current_value, monthly_contribution, cfg["return_pct"], months_total)
        scenarios[key] = {"return_pct": cfg["return_pct"], "value_at_retirement": round2(fv)}

    # Build a yearly projection series across all three scenarios.
    projection_series = []
    years_total = months_total // 12
    for year_offset in range(years_total + 1):
        age = current_age + year_offset
        months_elapsed = year_offset * 12
        row = {"age": age}
        for key, cfg in scenarios_default.items():
            row[key] = round2(_project_fv(current_value, monthly_contribution, cfg["return_pct"], months_elapsed))
        projection_series.append(row)

    return {"scenarios": scenarios, "projection_series": projection_series}


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def build_analysis(model: dict) -> dict:
    net_worth = compute_net_worth(model)
    cash_flow = compute_cash_flow(model)
    emergency_fund = compute_emergency_fund(model, cash_flow)
    debt = compute_debt(model)
    retirement = compute_retirement(model)

    existing_analysis = model.get("analysis") or {}

    analysis = dict(existing_analysis)  # preserve any fields projections.py doesn't own
    analysis["net_worth"] = net_worth
    analysis["cash_flow"] = cash_flow
    analysis["emergency_fund"] = emergency_fund
    analysis["debt"] = debt
    analysis["retirement"] = retirement
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill analysis.debt/emergency_fund/retirement/cash_flow/net_worth "
                    "in a plan_model.json document. Never mutates inputs."
    )
    parser.add_argument("model_path", help="Path to plan_model.json")
    parser.add_argument("--out", required=True, help="Output path (may equal input)")
    args = parser.parse_args()

    try:
        with open(args.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading {args.model_path}: {e}", file=sys.stderr)
        return 1

    # Never mutate inputs: work on a deep copy for anything we read from, and only
    # write back the analysis block onto the original structure's other fields.
    model_in = copy.deepcopy(model)

    try:
        analysis = build_analysis(model_in)
    except Exception as e:  # pragma: no cover - guard rail per spec: never crash
        print(f"Projection error (degrading to nulls): {e}", file=sys.stderr)
        analysis = (model_in.get("analysis") or {})

    output_model = copy.deepcopy(model)
    output_model["analysis"] = analysis

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output_model, f, indent=2)

    print(f"Wrote analysis (debt/emergency_fund/retirement/cash_flow/net_worth) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
