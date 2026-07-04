#!/usr/bin/env python3
"""
tests/run_tests.py -- stdlib-only test runner for financial-plan-architect scripts.

Run from the skill directory:
    C:\\AI-Shared\\python.exe tests\\run_tests.py

Exits nonzero on any assertion failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
SAMPLE_DIR = os.path.join(HERE, "sample_data")

PYTHON = sys.executable

failures: list[str] = []
passed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        passed.append(name)
        print(f"PASS: {name}")
    else:
        failures.append(f"{name} -- {detail}")
        print(f"FAIL: {name} -- {detail}")


def run_script(script_name: str, args: list[str]) -> subprocess.CompletedProcess:
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [PYTHON, script_path] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL_DIR)


def test_parse_csv() -> None:
    csv_path = os.path.join(SAMPLE_DIR, "bank_sample.csv")
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "csv_out.json")
        proc = run_script("parse_statements.py", [csv_path, "--out", out_path])
        check("parse_statements.py (CSV) exits 0", proc.returncode == 0,
              f"stderr={proc.stderr}")

        if proc.returncode != 0:
            return

        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        txns = data.get("transactions", [])
        check("CSV: transaction count == 25", len(txns) == 25, f"got {len(txns)}")

        # Signs: income positive, expenses negative
        income_txns = [t for t in txns if t["description"].startswith("DIRECT DEPOSIT")]
        check("CSV: income transactions are positive amounts",
              all(t["amount"] > 0 for t in income_txns) and len(income_txns) == 2,
              f"income_txns={income_txns}")

        expense_txns = [t for t in txns if "HARRIS TEETER" in t["description"]]
        check("CSV: expense transaction is negative",
              len(expense_txns) == 1 and expense_txns[0]["amount"] < 0,
              f"expense_txns={expense_txns}")

        # Parentheses-negative parsing: "(53.00)" -> -53.00
        misc_txn = [t for t in txns if "MISC MERCHANT" in t["description"]]
        check("CSV: parenthesized amount parsed as negative -53.00",
              len(misc_txn) == 1 and misc_txn[0]["amount"] == -53.00,
              f"misc_txn={misc_txn}")

        # Transfers flagged
        transfer_txns = [t for t in txns if t.get("is_transfer")]
        check("CSV: at least 2 transfer-flagged transactions",
              len(transfer_txns) >= 2, f"count={len(transfer_txns)}")

        # Categorization spot checks
        groceries = [t for t in txns if "HARRIS TEETER" in t["description"] or "KROGER" in t["description"] or "WALMART GROCERY" in t["description"]]
        check("CSV: grocery transactions categorized as groceries",
              all(t["category"] == "groceries" for t in groceries) and len(groceries) == 3,
              f"groceries={groceries}")

        gas_txns = [t for t in txns if t["description"] in ("SHELL OIL 57493022", "EXXON 4471")]
        check("CSV: gas station transactions categorized as gas",
              all(t["category"] == "gas" for t in gas_txns) and len(gas_txns) == 2,
              f"gas_txns={gas_txns}")

        income_cat = [t for t in txns if t["description"].startswith("TAX REFUND")]
        check("CSV: tax refund categorized as income",
              len(income_cat) == 1 and income_cat[0]["category"] == "income",
              f"income_cat={income_cat}")

        # Account masking: no full account numbers ever present (fixture has none to
        # begin with, so mask should be null, never a fabricated raw number)
        accounts = data.get("accounts", [])
        check("CSV: account produced", len(accounts) >= 1, f"accounts={accounts}")
        check("CSV: no account mask exceeds 4 chars",
              all((a.get("mask") is None or len(str(a["mask"])) <= 4) for a in accounts),
              f"accounts={accounts}")


def test_parse_qfx() -> None:
    qfx_path = os.path.join(SAMPLE_DIR, "brokerage_sample.qfx")
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "qfx_out.json")
        proc = run_script("parse_statements.py", [qfx_path, "--out", out_path])
        check("parse_statements.py (QFX) exits 0", proc.returncode == 0,
              f"stderr={proc.stderr}")

        if proc.returncode != 0:
            return

        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        txns = data.get("transactions", [])
        check("QFX: transaction count == 10", len(txns) == 10, f"got {len(txns)}")

        income_txns = [t for t in txns if t["description"].startswith("PAYROLL DEPOSIT")]
        check("QFX: payroll deposits are positive",
              len(income_txns) == 2 and all(t["amount"] > 0 for t in income_txns),
              f"income_txns={income_txns}")

        expense_txns = [t for t in txns if "WHOLE FOODS" in t["description"]]
        check("QFX: grocery expense negative and categorized",
              len(expense_txns) == 1 and expense_txns[0]["amount"] < 0
              and expense_txns[0]["category"] == "groceries",
              f"expense_txns={expense_txns}")

        transfer_txns = [t for t in txns if t.get("is_transfer")]
        check("QFX: transfer transaction flagged", len(transfer_txns) >= 1,
              f"count={len(transfer_txns)}")

        accounts = data.get("accounts", [])
        check("QFX: account produced with masked id (last 4 of 987654321000 = 1000)",
              len(accounts) == 1 and accounts[0]["mask"] == "1000",
              f"accounts={accounts}")
        check("QFX: full account number never present in output",
              "987654321000" not in json.dumps(data),
              "raw account number leaked into output")

        check("QFX: account balance parsed from LEDGERBAL",
              accounts[0]["balance"] == 1336.58, f"accounts={accounts}")


def test_projections() -> None:
    model_path = os.path.join(SAMPLE_DIR, "sample_plan_model.json")
    with open(model_path, "r", encoding="utf-8") as f:
        original_model_raw = f.read()

    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "model_out.json")
        proc = run_script("projections.py", [model_path, "--out", out_path])
        check("projections.py exits 0", proc.returncode == 0, f"stderr={proc.stderr}")

        if proc.returncode != 0:
            return

        # Ensure the original fixture file was never mutated on disk.
        with open(model_path, "r", encoding="utf-8") as f:
            after_raw = f.read()
        check("projections.py did not mutate the input file on disk",
              original_model_raw == after_raw, "input file content changed")

        with open(out_path, "r", encoding="utf-8") as f:
            out_model = json.load(f)

        analysis = out_model.get("analysis", {})

        # Inputs preserved untouched
        with open(model_path, "r", encoding="utf-8") as f:
            original_model = json.load(f)
        check("projections.py preserves accounts array unchanged",
              out_model.get("accounts") == original_model.get("accounts"),
              "accounts array was mutated")
        check("projections.py preserves transactions array unchanged",
              out_model.get("transactions") == original_model.get("transactions"),
              "transactions array was mutated")
        check("projections.py preserves assumptions unchanged",
              out_model.get("assumptions") == original_model.get("assumptions"),
              "assumptions were mutated")

        debt = analysis.get("debt", {})
        avalanche = debt.get("avalanche", {})
        snowball = debt.get("snowball", {})

        check("debt: total > 0", (debt.get("total") or 0) > 0, f"debt={debt}")
        check("debt: avalanche months_to_free is a positive int",
              isinstance(avalanche.get("months_to_free"), int) and avalanche["months_to_free"] > 0,
              f"avalanche={avalanche}")
        check("debt: avalanche order starts with highest-APR debt (credit card a5, 23.99%)",
              avalanche.get("order", [None])[0] == "a5",
              f"avalanche order={avalanche.get('order')}")
        check("debt: snowball order starts with smallest-balance debt (student loan a6, $2000)",
              snowball.get("order", [None])[0] == "a6",
              f"snowball order={snowball.get('order')}")
        check("debt: avalanche total_interest < snowball total_interest (avalanche beats snowball on this fixture)",
              (avalanche.get("total_interest") or 0) < (snowball.get("total_interest") or 0),
              f"avalanche_interest={avalanche.get('total_interest')} snowball_interest={snowball.get('total_interest')}")

        ef = analysis.get("emergency_fund", {})
        check("emergency_fund: runway_months > 0",
              (ef.get("runway_months") or 0) > 0, f"ef={ef}")

        cash_flow = analysis.get("cash_flow", {})
        check("cash_flow: monthly_income_avg > 0",
              (cash_flow.get("monthly_income_avg") or 0) > 0, f"cash_flow={cash_flow}")
        check("cash_flow: monthly_expenses_avg > 0",
              (cash_flow.get("monthly_expenses_avg") or 0) > 0, f"cash_flow={cash_flow}")
        check("cash_flow: by_category excludes transfer category",
              "transfer" not in (cash_flow.get("by_category") or {}),
              f"by_category={cash_flow.get('by_category')}")

        nw = analysis.get("net_worth", {})
        check("net_worth: assets > 0", (nw.get("assets") or 0) > 0, f"nw={nw}")
        check("net_worth: liabilities > 0", (nw.get("liabilities") or 0) > 0, f"nw={nw}")
        expected_net = (nw.get("assets") or 0) - (nw.get("liabilities") or 0)
        check("net_worth: net == assets - liabilities",
              abs((nw.get("net") or 0) - expected_net) < 0.01, f"nw={nw}")

        retirement = analysis.get("retirement", {})
        scenarios = retirement.get("scenarios", {})
        best = scenarios.get("best", {}).get("value_at_retirement")
        base = scenarios.get("base", {}).get("value_at_retirement")
        worst = scenarios.get("worst", {}).get("value_at_retirement")
        check("retirement: best > base > worst",
              best is not None and base is not None and worst is not None and best > base > worst,
              f"best={best} base={base} worst={worst}")
        check("retirement: projection_series is non-empty",
              len(retirement.get("projection_series", [])) > 0,
              f"projection_series len={len(retirement.get('projection_series', []))}")


def test_projections_empty_input_degrades_gracefully() -> None:
    """Guard-rail check: empty/near-empty model should never crash, should produce nulls."""
    empty_model = {
        "schema_version": 1, "generated_at": "2026-07-04", "currency": "USD",
        "profile": {}, "accounts": [], "transactions": [], "holdings": [],
        "market_context": {}, "assumptions": {},
        "analysis": {}, "source_manifest": [], "disclaimer": ""
    }
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "empty_model.json")
        out_path = os.path.join(td, "empty_out.json")
        with open(in_path, "w", encoding="utf-8") as f:
            json.dump(empty_model, f)

        proc = run_script("projections.py", [in_path, "--out", out_path])
        check("projections.py handles empty model without crashing",
              proc.returncode == 0, f"stderr={proc.stderr}")

        if proc.returncode == 0:
            with open(out_path, "r", encoding="utf-8") as f:
                out = json.load(f)
            analysis = out.get("analysis", {})
            check("empty model: cash_flow degrades to nulls",
                  analysis.get("cash_flow", {}).get("monthly_income_avg") is None,
                  f"cash_flow={analysis.get('cash_flow')}")
            check("empty model: debt degrades to zeroed/empty structure",
                  analysis.get("debt", {}).get("total") == 0.0,
                  f"debt={analysis.get('debt')}")


def main() -> int:
    print("=== financial-plan-architect test suite ===\n")

    print("--- parse_statements.py: CSV fixture ---")
    test_parse_csv()
    print("\n--- parse_statements.py: QFX fixture ---")
    test_parse_qfx()
    print("\n--- projections.py: sample_plan_model.json ---")
    test_projections()
    print("\n--- projections.py: empty-input guard rail ---")
    test_projections_empty_input_degrades_gracefully()

    print(f"\n=== {len(passed)} passed, {len(failures)} failed ===")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
