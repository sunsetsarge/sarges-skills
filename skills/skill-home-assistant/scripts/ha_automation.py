#!/usr/bin/env python3
"""
ha_automation.py - Create / read / edit / delete automations via the
Home Assistant automation config API (POST/GET/DELETE
/api/config/automation/config/<id>).

This endpoint is real but UNDOCUMENTED and version-coupled (see
references/automations-cookbook.md §2). Every subcommand therefore probes
it first with a GET on a definitely-nonexistent id and checks for the
known 404 signature ({"message": "Resource not found"}) before doing
anything else. If the signature doesn't match, the endpoint has moved or
changed shape on this HA version -- stop and report it (there is no
sanctioned fallback; editing automations.yaml directly is out of scope).

Connection config resolution: same order as ha_control.py (env ->
~/.ha-skill/secrets.json -> C:\\Claude\\.credentials\\homeassistant.json).

Usage:
  python ha_automation.py create --file automation.yaml [--id ID] [--overwrite]
  python ha_automation.py get ID [--json]
  python ha_automation.py edit ID --file automation.yaml
  python ha_automation.py delete ID

Every create/edit validates the YAML first via validate_yaml.py's
lint_automation() (imported from the same directory) -- placeholder
tokens (PLACEHOLDER, REPLACE) and structural errors are hard failures.

Exit codes:
  0 = success
  1 = configuration / validation error
  2 = connection error
  3 = auth error
  6 = automation config API did not match the expected probe signature
      (Fork F2 -- endpoint moved; capability is DEGRADED, not silently
      pretended-to-work)
  7 = create/edit/delete did not converge (entity never appeared/vanished
      after a reasonable poll + reload attempt)
"""

import argparse
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_yaml  # noqa: E402  (local module, same directory)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None

SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".ha-skill", "secrets.json")
LEGACY_CRED_PATH = r"C:\Claude\.credentials\homeassistant.json"


def load_config():
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if (not ha_url or not ha_token) and os.path.isfile(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = json.load(f)
            ha_url = ha_url or secrets.get("ha_url")
            ha_token = ha_token or secrets.get("ha_token")
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read secrets file: {e}", file=sys.stderr)
            sys.exit(1)

    if (not ha_url or not ha_token) and os.path.isfile(LEGACY_CRED_PATH):
        try:
            with open(LEGACY_CRED_PATH, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            ha_url = ha_url or legacy.get("url")
            ha_token = ha_token or legacy.get("token")
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read credential file: {e}", file=sys.stderr)
            sys.exit(1)

    if not ha_url or not ha_token:
        print(
            "ERROR: Home Assistant connection not configured. Set HA_URL/HA_TOKEN,\n"
            f"or {SECRETS_PATH}, or {LEGACY_CRED_PATH}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return ha_url.rstrip("/"), ha_token


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


def resolve_entity_id(ha_url, ha_token, automation_id, timeout=15):
    """
    HA's automation entity_id is slugified from `alias`, NOT from the config
    `id` -- the `id` only becomes the entity registry's `unique_id`. So
    `automation.<id>` is NOT a safe assumption (discovered live during
    wargame 09 C4: a create with id="wargame_debug_probe_2" and
    alias="[skill] WARGAME DEBUG PROBE" materialized as
    entity_id="automation.skill_wargame_debug_probe", unique_id
    "wargame_debug_probe_2"). Always resolve the real entity_id via the
    entity registry, matching on unique_id. Returns None if not found.
    """
    if websocket is None:
        print(
            "ERROR: resolving the automation's real entity_id requires the\n"
            "'websocket-client' package. Install it with: pip install websocket-client",
            file=sys.stderr,
        )
        sys.exit(5)
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        hello = json.loads(ws.recv())
        if hello.get("type") != "auth_required":
            return None
        ws.send(json.dumps({"type": "auth", "access_token": ha_token}))
        if json.loads(ws.recv()).get("type") != "auth_ok":
            print("ERROR: 401 on WebSocket auth.", file=sys.stderr)
            sys.exit(3)
        ws.send(json.dumps({"type": "config/entity_registry/list", "id": 1}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                break
        for e in m.get("result", []):
            if e.get("platform") == "automation" and e.get("unique_id") == automation_id:
                return e["entity_id"]
        return None
    finally:
        ws.close()


def probe(ha_url, ha_token):
    """
    Fork F2 tripwire. GET a definitely-nonexistent automation id and check
    for the known 404 signature. If it doesn't match, the endpoint has
    drifted on this HA version -- refuse to proceed rather than guess.
    """
    bogus_id = "zz_probe_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    status, body = rest_request(ha_url, ha_token, f"/api/config/automation/config/{bogus_id}")
    if status == 401:
        print("ERROR: 401 on probe -- token invalid/expired.", file=sys.stderr)
        sys.exit(3)
    if status == 404 and isinstance(body, dict) and body.get("message") == "Resource not found":
        return True
    print(
        "FORK F2: the automation config API did not return the expected 404 signature.\n"
        f"  status={status} body={body}\n"
        "This endpoint is undocumented and version-coupled. Its behavior has drifted\n"
        "on this HA version. Automation create/edit/delete is DEGRADED -- do not proceed.\n"
        "Sanctioned fallbacks: none (editing automations.yaml directly is out of scope).\n"
        "Report this in the handoff and flag the capability as DEGRADED in SKILL.md.",
        file=sys.stderr,
    )
    return False


def load_and_validate(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"ERROR: {path} is not valid YAML: {e}", file=sys.stderr)
        sys.exit(1)

    findings = validate_yaml.lint_automation(doc, 0)
    errors = [f for f in findings if f.level == "error"]
    if errors:
        print(f"ERROR: {path} failed validation:", file=sys.stderr)
        for f in errors:
            print(f"  [{f.path}] {f.message}", file=sys.stderr)
        sys.exit(1)
    for f in findings:
        if f.level == "warning":
            print(f"WARN: [{f.path}] {f.message}", file=sys.stderr)
    return doc


def poll_entity(ha_url, ha_token, entity_id, expect_present, timeout_s=15, interval_s=2):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, _ = rest_request(ha_url, ha_token, f"/api/states/{entity_id}")
        present = status == 200
        if present == expect_present:
            return True
        time.sleep(interval_s)
    return False


def cmd_create(args, ha_url, ha_token):
    if not probe(ha_url, ha_token):
        sys.exit(6)

    doc = load_and_validate(args.file)
    automation_id = args.id or (
        "wargame_probe_" + time.strftime("%Y%m%dt%H%M%Sz", time.gmtime())
    )

    status, existing = rest_request(ha_url, ha_token, f"/api/config/automation/config/{automation_id}")
    if status == 200 and not args.overwrite:
        print(
            f"ERROR: automation '{automation_id}' already exists. "
            "Pass --overwrite to replace it, or choose a different --id.",
            file=sys.stderr,
        )
        sys.exit(1)

    # id is in the URL, not the body
    body = {k: v for k, v in doc.items() if k not in ("id",)}
    status, result = rest_request(
        ha_url, ha_token, f"/api/config/automation/config/{automation_id}",
        method="POST", data=body,
    )
    if status not in (200, 201):
        print(f"ERROR: create failed, HTTP {status}: {result}", file=sys.stderr)
        sys.exit(1)

    # entity_id is slugified from `alias`, NOT the config id -- resolve it
    # via the entity registry (unique_id == automation_id), don't assume.
    entity_id = None
    deadline = time.time() + 15
    while time.time() < deadline:
        entity_id = resolve_entity_id(ha_url, ha_token, automation_id)
        if entity_id:
            break
        time.sleep(2)

    if not entity_id:
        print("Entity did not register after 15s; forcing automation.reload...", file=sys.stderr)
        rest_request(ha_url, ha_token, "/api/services/automation/reload", method="POST", data={})
        deadline = time.time() + 15
        while time.time() < deadline:
            entity_id = resolve_entity_id(ha_url, ha_token, automation_id)
            if entity_id:
                break
            time.sleep(2)
        if not entity_id:
            print(f"ERROR: automation '{automation_id}' still absent after reload+poll. Attempting cleanup delete.", file=sys.stderr)
            rest_request(ha_url, ha_token, f"/api/config/automation/config/{automation_id}", method="DELETE")
            sys.exit(7)

    if not poll_entity(ha_url, ha_token, entity_id, expect_present=True, timeout_s=10):
        print(f"ERROR: {entity_id} registered but has no state after 10s.", file=sys.stderr)
        sys.exit(7)

    print(f"CREATED: id={automation_id} entity={entity_id}")
    print(f"{automation_id} {entity_id}")
    return 0


def cmd_get(args, ha_url, ha_token):
    if not probe(ha_url, ha_token):
        sys.exit(6)
    status, body = rest_request(ha_url, ha_token, f"/api/config/automation/config/{args.id}")
    if status == 404:
        print(f"NOT FOUND: {args.id}")
        sys.exit(1)
    print(json.dumps(body, indent=2) if args.json else body)
    return 0


def cmd_edit(args, ha_url, ha_token):
    if not probe(ha_url, ha_token):
        sys.exit(6)
    status, _ = rest_request(ha_url, ha_token, f"/api/config/automation/config/{args.id}")
    if status != 200:
        print(f"ERROR: automation '{args.id}' does not exist (HTTP {status}). Use create instead.", file=sys.stderr)
        sys.exit(1)
    doc = load_and_validate(args.file)
    body = {k: v for k, v in doc.items() if k not in ("id",)}
    status, result = rest_request(
        ha_url, ha_token, f"/api/config/automation/config/{args.id}", method="POST", data=body,
    )
    if status not in (200, 201):
        print(f"ERROR: edit failed, HTTP {status}: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"EDITED: {args.id}")
    return 0


def cmd_delete(args, ha_url, ha_token):
    if not probe(ha_url, ha_token):
        sys.exit(6)

    # Resolve the real entity_id BEFORE deleting -- once the config entry
    # is gone the registry lookup by unique_id has nothing to match.
    entity_id = resolve_entity_id(ha_url, ha_token, args.id) or f"automation.{args.id}"

    status, result = rest_request(ha_url, ha_token, f"/api/config/automation/config/{args.id}", method="DELETE")
    if status not in (200, 201):
        print(f"ERROR: delete failed, HTTP {status}: {result}", file=sys.stderr)
        sys.exit(1)

    if not poll_entity(ha_url, ha_token, entity_id, expect_present=False, timeout_s=15):
        print(f"Entity {entity_id} still present after 15s; forcing automation.reload...", file=sys.stderr)
        rest_request(ha_url, ha_token, "/api/services/automation/reload", method="POST", data={})
        if not poll_entity(ha_url, ha_token, entity_id, expect_present=False, timeout_s=15):
            print(f"ERROR: {entity_id} still present after reload+poll (registry ghost). Flag in handoff.", file=sys.stderr)
            sys.exit(7)

    config_status, _ = rest_request(ha_url, ha_token, f"/api/config/automation/config/{args.id}")
    if config_status != 404:
        print(f"WARNING: config API still returns {config_status} for deleted id {args.id}.", file=sys.stderr)

    print(f"DELETED: {args.id}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Create/read/edit/delete HA automations via the config API.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--file", required=True)
    p_create.add_argument("--id")
    p_create.add_argument("--overwrite", action="store_true")

    p_get = sub.add_parser("get")
    p_get.add_argument("id")
    p_get.add_argument("--json", action="store_true")

    p_edit = sub.add_parser("edit")
    p_edit.add_argument("id")
    p_edit.add_argument("--file", required=True)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("id")

    args = p.parse_args()
    ha_url, ha_token = load_config()

    if args.cmd == "create":
        sys.exit(cmd_create(args, ha_url, ha_token))
    elif args.cmd == "get":
        sys.exit(cmd_get(args, ha_url, ha_token))
    elif args.cmd == "edit":
        sys.exit(cmd_edit(args, ha_url, ha_token))
    elif args.cmd == "delete":
        sys.exit(cmd_delete(args, ha_url, ha_token))


if __name__ == "__main__":
    main()
