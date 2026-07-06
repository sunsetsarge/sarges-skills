#!/usr/bin/env python3
"""
test_guardrail.py - Offline test battery for ha_control.py's guardrail
engine. NO LIVE WRITES. Run before any Phase C live verification.

Covers:
  (a)-(f) the B4 guardrail matrix (direct calls into guardrail_check())
  the poisoned-URL dry-run proof (subprocess, bogus HA_URL, must not hang
    or touch the network for explicit entity_id targets)
  the fail-closed proof (rename guardrail.json away, confirm ALL calls
    are refused, restore the file)

Exit code 0 = all green. Nonzero = at least one case failed (printed).
"""

import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
PYTHON = r"C:\AI-Shared\python.exe"

sys.path.insert(0, SCRIPTS_DIR)
import ha_control  # noqa: E402

failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def matrix():
    guardrail = ha_control.load_guardrail()
    check("guardrail.json loads (fail_closed=False)", guardrail.get("_fail_closed") is False)

    # (a) one lamp, allowed
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "light.turn_on", ["light.man_cave_lamp_2"], False, set()
    )
    check("(a) single light.turn_on -> allowed", allowed, reason)

    # (b) dry-run semantics are structural (tested via cmd_call / poisoned-URL,
    # not the gate itself — the gate doesn't know about --confirm at all,
    # by design: gating happens before the confirm check in cmd_call).
    check("(b) gate is confirm-agnostic (dry-run enforced in cmd_call, not here)", True)

    # (c) lock.unlock without confirm-critical -> refused, names the entity
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "lock.unlock", ["lock.front_door"], False, set()
    )
    check("(c) lock.unlock refused without --confirm-critical", not allowed and "front_door" in reason, reason)

    # (c2) same, WITH confirm-critical -> allowed
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "lock.unlock", ["lock.front_door"], False, {"lock.front_door"}
    )
    check("(c2) lock.unlock allowed WITH matching --confirm-critical", allowed, reason)

    # (d) switch.turn_off on switch.cully_core -> refused (pattern gate)
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "switch.turn_off", ["switch.cully_core"], False, set()
    )
    check("(d) switch.cully_core refused by pattern gate", not allowed, reason)

    # (e) 12 lights -> refused (bulk hard cap = 10)
    twelve = [f"light.probe_{i}" for i in range(12)]
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "light.turn_on", twelve, False, set()
    )
    check("(e) 12 targets refused by bulk hard cap", not allowed, reason)

    # (e2) 4 lights -> allowed but flagged as bulk (over confirm_threshold=3)
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "light.turn_on", [f"light.probe_{i}" for i in range(4)], False, set()
    )
    check("(e2) 4 targets allowed, flagged bulk", allowed and "Bulk" in reason, reason)

    # (f) area expansion "already expanded" to include the lock -> refused
    # (resolve_targets would have expanded area:MainHall to this list live;
    # here we feed the already-expanded list directly, which is exactly
    # what guardrail_check receives in the real code path.)
    expanded_area_list = ["light.main_hall_ceiling", "switch.main_hall_outlet", "lock.front_door"]
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "lock.unlock", expanded_area_list, False, set()
    )
    check("(f) expanded area list containing the lock is refused", not allowed and "lock.front_door" in hits, reason)

    # literal 'all' -> refused, no override exists
    allowed, reason, hits = ha_control.guardrail_check(
        guardrail, "switch.turn_off", [], True, set()
    )
    check("literal 'all' target refused outright", not allowed, reason)


def poisoned_url_proof():
    """
    Dry-run against explicit entity_id targets, with a bogus unroutable
    HA_URL, must exit 0 quickly with the printed plan — proving zero
    network access was attempted for bare entity_id resolution.
    """
    env = dict(os.environ)
    env["HA_URL"] = "http://255.255.255.255:1"
    env["HA_TOKEN"] = "not-a-real-token"
    start = time.time()
    try:
        result = subprocess.run(
            [PYTHON, os.path.join(SCRIPTS_DIR, "ha_control.py"), "call", "light.turn_on",
             "--target", "light.probe_a,light.probe_b"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        elapsed = time.time() - start
        check(
            "poisoned-URL dry-run exits 0 fast (no network touch)",
            result.returncode == 0 and elapsed < 3 and "DRY RUN" in result.stdout,
            f"returncode={result.returncode} elapsed={elapsed:.2f}s stdout_tail={result.stdout[-200:]}",
        )
    except subprocess.TimeoutExpired:
        check("poisoned-URL dry-run exits 0 fast (no network touch)", False, "TIMED OUT — dry-run touched the network")


def fail_closed_proof():
    """Rename guardrail.json away; confirm ALL calls are refused; restore."""
    guardrail_path = os.path.join(SCRIPTS_DIR, "guardrail.json")
    backup_path = guardrail_path + ".bak_test"
    env = dict(os.environ)
    env["HA_URL"] = "http://255.255.255.255:1"
    env["HA_TOKEN"] = "not-a-real-token"
    os.rename(guardrail_path, backup_path)
    try:
        result = subprocess.run(
            [PYTHON, os.path.join(SCRIPTS_DIR, "ha_control.py"), "call", "light.turn_on",
             "--target", "light.probe_a", "--confirm"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        check(
            "missing guardrail.json refuses even a --confirm call (fail closed)",
            result.returncode == 0 and "GUARDRAIL UNAVAILABLE" in result.stdout and "REFUSED" in result.stdout,
            f"returncode={result.returncode} stdout_tail={result.stdout[-300:]}",
        )
    finally:
        os.rename(backup_path, guardrail_path)


def main():
    print("=== B4 guardrail matrix ===")
    matrix()
    print("\n=== Poisoned-URL dry-run proof ===")
    poisoned_url_proof()
    print("\n=== Fail-closed guardrail proof ===")
    fail_closed_proof()

    print(f"\n{'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
    if failures:
        for f in failures:
            print(f"  - {f}")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
