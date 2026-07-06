#!/usr/bin/env python3
"""
ha_control.py - Read states and call services against a Home Assistant
instance, with dry-run-by-default semantics and a fail-closed guardrail.

Connection config resolution order (matches discover.py, extended per
project ledger P3 to also accept the ha_api.py credential file):
  1. Environment variables HA_URL and HA_TOKEN
  2. JSON secrets file at %USERPROFILE%\\.ha-skill\\secrets.json
     ({"ha_url": "...", "ha_token": "..."})
  3. JSON credential file at C:\\Claude\\.credentials\\homeassistant.json
     ({"url": "...", "token": "..."})

Usage:
  python ha_control.py states [--domain D] [--area A] [--json]
  python ha_control.py get ENTITY_ID [--json]
  python ha_control.py call DOMAIN.SERVICE --target T1,T2,... [--data JSON] [--confirm]
                              [--confirm-critical ENTITY_ID ...]

Dry-run is the default for `call`. Nothing is mutated unless --confirm is
given. Explicit entity_id targets require ZERO network access to resolve
(pure string handling) so a dry-run against explicit targets never touches
the network at all, even with a bogus HA_URL. area:/group:/label: targets
require one read (registry/state lookup) to expand into entity_ids, in
either mode -- this is a read, never a mutation.

The guardrail (guardrail.json, resolved relative to this file, never cwd)
is FAIL CLOSED: if it is missing or does not parse, ALL service calls are
refused. Reads (states/get) are unaffected.

Exit codes:
  0 = success (including a clean dry-run or a clean refusal)
  1 = configuration error (missing URL/token, missing guardrail file)
  2 = connection error
  3 = auth error (401)
  4 = refused by guardrail (only used with --json for machine callers;
      human-facing runs still exit 0 on a refusal, since "the guardrail
      worked as intended" is not a script failure)
  5 = unexpected runtime error
"""

import argparse
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.request

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None

SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".ha-skill", "secrets.json")
LEGACY_CRED_PATH = r"C:\Claude\.credentials\homeassistant.json"
GUARDRAIL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardrail.json")


def mask(_text):
    return "***"


def load_config():
    """Resolve HA_URL / HA_TOKEN: env -> ~/.ha-skill/secrets.json -> legacy homeassistant.json."""
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if (not ha_url or not ha_token) and os.path.isfile(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = json.load(f)
            ha_url = ha_url or secrets.get("ha_url")
            ha_token = ha_token or secrets.get("ha_token")
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read secrets file at {SECRETS_PATH}: {e}", file=sys.stderr)
            sys.exit(1)

    if (not ha_url or not ha_token) and os.path.isfile(LEGACY_CRED_PATH):
        try:
            with open(LEGACY_CRED_PATH, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            ha_url = ha_url or legacy.get("url")
            ha_token = ha_token or legacy.get("token")
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read credential file at {LEGACY_CRED_PATH}: {e}", file=sys.stderr)
            sys.exit(1)

    if not ha_url or not ha_token:
        print(
            "ERROR: Home Assistant connection not configured.\n"
            "Set environment variables HA_URL and HA_TOKEN, or create a JSON\n"
            f"secrets file at {SECRETS_PATH}, or use {LEGACY_CRED_PATH}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return ha_url.rstrip("/"), ha_token


def load_guardrail():
    """
    FAIL CLOSED: missing or unparseable guardrail.json means every service
    call is refused. Returns a dict with '_fail_closed': True in that case
    so callers can distinguish "empty allow-everything list" (never valid)
    from "guardrail unavailable, deny everything."
    """
    if not os.path.isfile(GUARDRAIL_PATH):
        return {"_fail_closed": True, "_reason": f"guardrail file not found at {GUARDRAIL_PATH}"}
    try:
        with open(GUARDRAIL_PATH, "r", encoding="utf-8") as f:
            g = json.load(f)
        g.setdefault("critical_entity_patterns", [])
        g.setdefault("critical_service_patterns", [])
        g.setdefault("bulk_confirm_threshold", 3)
        g.setdefault("bulk_hard_cap", 10)
        g["_fail_closed"] = False
        return g
    except (OSError, json.JSONDecodeError) as e:
        return {"_fail_closed": True, "_reason": f"guardrail file at {GUARDRAIL_PATH} is unreadable/invalid: {e}"}


# --------------------------------------------------------------------------
# REST helpers
# --------------------------------------------------------------------------

def rest_request(ha_url, ha_token, path, method="GET", data=None, timeout=15):
    url = f"{ha_url}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach Home Assistant: {e.reason}", file=sys.stderr)
        sys.exit(2)


# --------------------------------------------------------------------------
# WebSocket helper (only used for area:/label:/group: expansion — a read)
# --------------------------------------------------------------------------

def ws_expand(ha_url, ha_token, kind, value, timeout=15):
    """
    Expand an area/label into a list of entity_ids via the entity + device
    registries. This is a READ; it never mutates anything. Requires the
    websocket-client package.
    """
    if websocket is None:
        print(
            "ERROR: expanding area:/label: targets requires the 'websocket-client'\n"
            "package. Install it with: pip install websocket-client\n"
            "(Bare entity_id targets do not need this.)",
            file=sys.stderr,
        )
        sys.exit(5)

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        hello = json.loads(ws.recv())
        if hello.get("type") != "auth_required":
            print("ERROR: unexpected WebSocket handshake.", file=sys.stderr)
            sys.exit(5)
        ws.send(json.dumps({"type": "auth", "access_token": ha_token}))
        auth_result = json.loads(ws.recv())
        if auth_result.get("type") != "auth_ok":
            print("ERROR: WebSocket auth failed (401).", file=sys.stderr)
            sys.exit(3)

        msg_id = 1

        def cmd(payload):
            nonlocal msg_id
            payload["id"] = msg_id
            msg_id += 1
            ws.send(json.dumps(payload))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == payload["id"]:
                    return m

        entities = cmd({"type": "config/entity_registry/list"}).get("result", [])
        devices = cmd({"type": "config/device_registry/list"}).get("result", [])
        areas = cmd({"type": "config/area_registry/list"}).get("result", [])
    finally:
        ws.close()

    device_area = {d["id"]: d.get("area_id") for d in devices}

    if kind == "area":
        matches = [a for a in areas if a["name"].lower() == value.lower() or a.get("area_id") == value]
        if not matches:
            print(f"ERROR: no area matching '{value}' found in the area registry.", file=sys.stderr)
            sys.exit(5)
        area_id = matches[0]["area_id"]
        ids = []
        for e in entities:
            eff_area = e.get("area_id") or device_area.get(e.get("device_id"))
            if eff_area == area_id:
                ids.append(e["entity_id"])
        return ids

    if kind == "label":
        return [e["entity_id"] for e in entities if value in (e.get("labels") or [])]

    print(f"ERROR: unknown expansion kind '{kind}'.", file=sys.stderr)
    sys.exit(5)


def resolve_targets(ha_url, ha_token, spec):
    """
    Parse a comma-separated --target spec. Bare entity_ids (contain a dot,
    no prefix) resolve with ZERO network access. area:/label: prefixes
    require one read-only expansion call. 'all' is passed through literally
    (never expanded) so the bulk gate can refuse it outright.
    """
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    resolved = []
    literal_all = False
    for t in tokens:
        if t == "all":
            literal_all = True
            continue
        if t.startswith("area:"):
            resolved.extend(ws_expand(ha_url, ha_token, "area", t[len("area:"):]))
        elif t.startswith("label:"):
            resolved.extend(ws_expand(ha_url, ha_token, "label", t[len("label:"):]))
        elif t.startswith("group:"):
            group_id = t[len("group:"):]
            status, body = rest_request(ha_url, ha_token, f"/api/states/{group_id}")
            if status != 200:
                print(f"ERROR: could not read group '{group_id}' (HTTP {status}).", file=sys.stderr)
                sys.exit(5)
            resolved.extend(body.get("attributes", {}).get("entity_id", []))
        else:
            resolved.append(t)  # bare entity_id — no network needed
    # de-dupe, preserve order
    seen = set()
    ordered = []
    for e in resolved:
        if e not in seen:
            seen.add(e)
            ordered.append(e)
    return ordered, literal_all


# --------------------------------------------------------------------------
# Guardrail gates
# --------------------------------------------------------------------------

def guardrail_check(guardrail, service, targets, literal_all, confirm_critical):
    """
    Returns (allowed: bool, reason: str, critical_hits: list[str]).
    Three independent gates, ALL must pass for `allowed=True`:
      1. critical-entity pattern gate (per-entity --confirm-critical override)
      2. bulk-size gate (>hard_cap or literal 'all' -> hard refuse, no override)
      3. expansion gate is structural: this function only ever sees the
         ALREADY-EXPANDED target list (resolve_targets does the expansion
         before this is called), so a group/area hiding a critical entity
         cannot slip past gate 1.
    """
    if guardrail.get("_fail_closed"):
        return False, f"GUARDRAIL UNAVAILABLE - refusing all service calls: {guardrail.get('_reason')}", []

    hard_cap = guardrail["bulk_hard_cap"]
    confirm_threshold = guardrail["bulk_confirm_threshold"]

    if literal_all:
        return False, "Refused: literal 'all' target is never allowed. Loop over explicit entities instead.", []

    if len(targets) > hard_cap:
        return False, f"Refused: {len(targets)} targets exceeds the hard cap of {hard_cap}. No override.", []

    entity_patterns = guardrail["critical_entity_patterns"]
    service_patterns = guardrail["critical_service_patterns"]

    if any(fnmatch.fnmatch(service, p) for p in service_patterns):
        return False, f"Refused: service '{service}' matches a critical-service pattern. Not permitted via this tool.", []

    critical_hits = [e for e in targets if any(fnmatch.fnmatch(e, p) for p in entity_patterns)]
    if critical_hits:
        not_confirmed = [e for e in critical_hits if e not in confirm_critical]
        if not_confirmed:
            return (
                False,
                "Refused: critical entities in target list require --confirm-critical <entity_id> "
                f"named individually: {not_confirmed}",
                critical_hits,
            )

    if len(targets) > confirm_threshold:
        return True, f"Bulk call ({len(targets)} targets, over the {confirm_threshold}-target confirm threshold).", critical_hits

    return True, "OK", critical_hits


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------

def cmd_states(args, ha_url, ha_token):
    status, states = rest_request(ha_url, ha_token, "/api/states")
    if status != 200:
        print(f"ERROR: /api/states returned HTTP {status}", file=sys.stderr)
        sys.exit(5)
    if args.domain:
        states = [s for s in states if s["entity_id"].startswith(args.domain + ".")]
    if args.json:
        print(json.dumps(states, indent=2))
    else:
        for s in states:
            print(f"{s['entity_id']:55s} {s['state']}")
    return 0


def cmd_get(args, ha_url, ha_token):
    status, body = rest_request(ha_url, ha_token, f"/api/states/{args.entity_id}")
    if status == 404:
        print(f"ERROR: entity '{args.entity_id}' not found.", file=sys.stderr)
        sys.exit(5)
    if status != 200:
        print(f"ERROR: HTTP {status}: {body}", file=sys.stderr)
        sys.exit(5)
    print(json.dumps(body, indent=2) if args.json else f"{body['entity_id']}: {body['state']}")
    return 0


def cmd_call(args, ha_url, ha_token):
    domain, _, service = args.service.partition(".")
    if not domain or not service:
        print("ERROR: service must be DOMAIN.SERVICE, e.g. light.turn_on", file=sys.stderr)
        sys.exit(1)

    guardrail = load_guardrail()
    targets, literal_all = resolve_targets(ha_url, ha_token, args.target)
    confirm_critical = set(args.confirm_critical or [])

    allowed, reason, critical_hits = guardrail_check(
        guardrail, args.service, targets, literal_all, confirm_critical
    )

    data = json.loads(args.data) if args.data else {}

    print("=" * 60)
    print(f"PLAN: {args.service}")
    print(f"  targets ({len(targets)}): {targets if targets else '(none - literal all requested)' if literal_all else '(none)'}")
    print(f"  data: {data}")
    print(f"  guardrail verdict: {'ALLOW' if allowed else 'REFUSE'} - {reason}")
    if critical_hits:
        print(f"  critical entities in scope: {critical_hits}")
    print("=" * 60)

    if not allowed:
        print("REFUSED - no request was sent.")
        return 0  # a working refusal is a successful run, not a script failure

    if not args.confirm:
        print("DRY RUN - no request was sent. Re-run with --confirm to execute.")
        return 0

    # Only now, after the guardrail passed AND --confirm was given, do we
    # touch the network for the actual mutating call.
    before = {}
    for e in targets:
        _, b = rest_request(ha_url, ha_token, f"/api/states/{e}")
        before[e] = b.get("state") if isinstance(b, dict) else None

    status, result = rest_request(
        ha_url, ha_token, f"/api/services/{domain}/{service}", method="POST",
        data={"entity_id": targets, **data} if targets else data,
    )
    if status not in (200, 201):
        print(f"ERROR: service call failed, HTTP {status}: {result}", file=sys.stderr)
        sys.exit(5)

    print("EXECUTED. Before -> After:")
    for e in targets:
        _, a = rest_request(ha_url, ha_token, f"/api/states/{e}")
        after_state = a.get("state") if isinstance(a, dict) else None
        print(f"  {e}: {before[e]} -> {after_state}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Read states and call HA services with dry-run-by-default safety.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_states = sub.add_parser("states", help="List entity states")
    p_states.add_argument("--domain")
    p_states.add_argument("--area")
    p_states.add_argument("--json", action="store_true")

    p_get = sub.add_parser("get", help="Read one entity")
    p_get.add_argument("entity_id")
    p_get.add_argument("--json", action="store_true")

    p_call = sub.add_parser("call", help="Call a service (dry-run unless --confirm)")
    p_call.add_argument("service", help="DOMAIN.SERVICE, e.g. light.turn_on")
    p_call.add_argument("--target", required=True, help="Comma-separated entity_ids, or area:/label:/group: prefixed, or 'all'")
    p_call.add_argument("--data", help="JSON service-call data")
    p_call.add_argument("--confirm", action="store_true")
    p_call.add_argument("--confirm-critical", action="append", metavar="ENTITY_ID")

    args = p.parse_args()
    ha_url, ha_token = load_config()

    if args.cmd == "states":
        sys.exit(cmd_states(args, ha_url, ha_token))
    elif args.cmd == "get":
        sys.exit(cmd_get(args, ha_url, ha_token))
    elif args.cmd == "call":
        sys.exit(cmd_call(args, ha_url, ha_token))


if __name__ == "__main__":
    main()
