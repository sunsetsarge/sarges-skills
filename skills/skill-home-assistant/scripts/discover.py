#!/usr/bin/env python3
"""
discover.py - Full read-only inventory of a Home Assistant instance.

Combines REST (alive check + config) with WebSocket (states, registries,
dashboards, supervisor add-ons) to produce a single JSON inventory that an
agent can reason over before making changes.

Connection config resolution order:
  1. Environment variables HA_URL and HA_TOKEN
  2. JSON secrets file at %USERPROFILE%\\.ha-skill\\secrets.json
     ({"ha_url": "...", "ha_token": "..."})

Usage:
  python discover.py [--json] [--out FILE] [--timeout SECONDS]

Exit codes:
  0 = success
  1 = configuration error (missing URL/token)
  2 = connection error (refused, timeout, DNS, etc.)
  3 = auth error (401 / bad token)
  4 = unexpected runtime error
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# --------------------------------------------------------------------------
# websocket-client is an optional dependency. Give an actionable hint if
# it's missing rather than letting the user see a bare ImportError.
# --------------------------------------------------------------------------
try:
    import websocket  # from the `websocket-client` PyPI package
except ImportError:
    websocket = None


# --------------------------------------------------------------------------
# Config / helpers
# --------------------------------------------------------------------------

SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".ha-skill", "secrets.json")


def mask(text):
    """Never print a real token. Always show *** instead."""
    return "***"


def load_config():
    """Resolve HA_URL / HA_TOKEN from env, falling back to secrets file."""
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if not ha_url or not ha_token:
        if os.path.isfile(SECRETS_PATH):
            try:
                with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                    secrets = json.load(f)
                ha_url = ha_url or secrets.get("ha_url")
                ha_token = ha_token or secrets.get("ha_token")
            except (OSError, json.JSONDecodeError) as e:
                print(
                    f"ERROR: could not read secrets file at {SECRETS_PATH}: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

    if not ha_url or not ha_token:
        print(
            "ERROR: Home Assistant connection not configured.\n"
            "Set environment variables HA_URL and HA_TOKEN, or create a JSON\n"
            f"secrets file at {SECRETS_PATH} with:\n"
            '  {"ha_url": "http://homeassistant.local:8123", "ha_token": "<long-lived token>"}',
            file=sys.stderr,
        )
        sys.exit(1)

    ha_url = ha_url.rstrip("/")
    return ha_url, ha_token


def rest_get(ha_url, ha_token, path, timeout=15):
    """Perform a REST GET against the HA API. Raises on error, with masked messages."""
    url = f"{ha_url}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(
                "ERROR: 401 Unauthorized. The HA_TOKEN (***) was rejected.\n"
                "Check that the long-lived access token is valid and not expired.",
                file=sys.stderr,
            )
            sys.exit(3)
        raise
    except urllib.error.URLError as e:
        print(
            f"ERROR: could not reach Home Assistant at {ha_url}{path}: {e.reason}\n"
            "Check HA_URL, that HA is running, and network/firewall access.",
            file=sys.stderr,
        )
        sys.exit(2)
    except TimeoutError:
        print(
            f"ERROR: timed out connecting to {ha_url}{path}.",
            file=sys.stderr,
        )
        sys.exit(2)


class HAWebSocket:
    """
    Thin wrapper around a Home Assistant WebSocket API session.

    Handles the auth handshake and id-sequenced request/response commands.
    Each script that needs WS access re-implements this small helper so the
    script can run standalone (per project spec).
    """

    def __init__(self, ha_url, ha_token, timeout=15):
        if websocket is None:
            print(
                "ERROR: the 'websocket-client' package is required for WebSocket\n"
                "access (states, registries, dashboards, supervisor). Install it with:\n"
                "  pip install websocket-client",
                file=sys.stderr,
            )
            sys.exit(1)

        ws_url = ha_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/api/websocket"
        self.ha_token = ha_token
        self._id = 0

        try:
            self.ws = websocket.create_connection(ws_url, timeout=timeout)
        except ConnectionRefusedError:
            print(
                f"ERROR: connection refused when opening WebSocket to {ws_url}.",
                file=sys.stderr,
            )
            sys.exit(2)
        except Exception as e:
            print(
                f"ERROR: could not open WebSocket to {ws_url}: {e}",
                file=sys.stderr,
            )
            sys.exit(2)

        self._authenticate()

    def _recv_json(self):
        raw = self.ws.recv()
        return json.loads(raw)

    def _authenticate(self):
        # HA sends {"type": "auth_required", ...} immediately on connect.
        first = self._recv_json()
        if first.get("type") != "auth_required":
            print(
                f"ERROR: unexpected first WebSocket message (expected auth_required): {first.get('type')}",
                file=sys.stderr,
            )
            sys.exit(2)

        self.ws.send(json.dumps({"type": "auth", "access_token": self.ha_token}))
        auth_result = self._recv_json()

        if auth_result.get("type") == "auth_invalid":
            print(
                "ERROR: WebSocket auth_invalid - the HA_TOKEN (***) was rejected.",
                file=sys.stderr,
            )
            sys.exit(3)
        if auth_result.get("type") != "auth_ok":
            print(
                f"ERROR: unexpected WebSocket auth response: {auth_result}",
                file=sys.stderr,
            )
            sys.exit(2)

    def command(self, payload, tolerate_failure=False):
        """
        Send an id-sequenced command and return the 'result' field.

        If tolerate_failure is True, returns None instead of raising/exiting
        when the command fails (used for optional things like Supervisor).
        """
        self._id += 1
        msg = dict(payload)
        msg["id"] = self._id
        try:
            self.ws.send(json.dumps(msg))
            resp = self._recv_json()
        except Exception as e:
            if tolerate_failure:
                return None
            print(f"ERROR: WebSocket command failed: {e}", file=sys.stderr)
            sys.exit(2)

        if not resp.get("success", False):
            if tolerate_failure:
                return None
            print(
                f"ERROR: WebSocket command {payload.get('type')} failed: {resp.get('error')}",
                file=sys.stderr,
            )
            sys.exit(2)
        return resp.get("result")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Discovery logic
# --------------------------------------------------------------------------

def build_entities_by_area(entity_registry, device_registry, states):
    """
    Group entities by area_id, falling back to the owning device's area_id
    when the entity itself has no area assigned.
    """
    device_area = {d["id"]: d.get("area_id") for d in device_registry}

    by_area = {}
    entity_area_map = {}

    for ent in entity_registry:
        entity_id = ent.get("entity_id")
        area_id = ent.get("area_id")
        if not area_id:
            device_id = ent.get("device_id")
            if device_id:
                area_id = device_area.get(device_id)
        area_key = area_id or "unassigned"
        by_area.setdefault(area_key, []).append(entity_id)
        entity_area_map[entity_id] = area_key

    # Entities that exist in states but not in the registry (e.g. some
    # helpers/template entities) get bucketed as unassigned too.
    known = set(entity_area_map.keys())
    for st in states:
        eid = st.get("entity_id")
        if eid not in known:
            by_area.setdefault("unassigned", []).append(eid)

    return by_area


def build_entities_by_domain(states):
    by_domain = {}
    for st in states:
        eid = st.get("entity_id", "")
        domain = eid.split(".", 1)[0] if "." in eid else "unknown"
        by_domain.setdefault(domain, []).append(eid)
    return by_domain


def detect_hacs(states, entity_registry):
    for st in states:
        eid = st.get("entity_id", "")
        if eid.startswith("sensor.hacs") or eid == "update.hacs":
            return True
    for ent in entity_registry:
        if ent.get("platform") == "hacs":
            return True
    return False


def unique_integrations(entity_registry, device_registry):
    platforms = set()
    for ent in entity_registry:
        p = ent.get("platform")
        if p:
            platforms.add(p)
    manufacturers = set()
    for dev in device_registry:
        m = dev.get("manufacturer")
        if m:
            manufacturers.add(m)
    return sorted(platforms), sorted(manufacturers)


def find_unavailable(states):
    return sorted(
        st["entity_id"]
        for st in states
        if st.get("state") in ("unavailable", "unknown")
    )


def run_discovery(ha_url, ha_token, timeout):
    result = {}

    # --- REST: alive check + config ---
    rest_get(ha_url, ha_token, "/api/", timeout=timeout)  # alive check, discard body
    config = rest_get(ha_url, ha_token, "/api/config", timeout=timeout) or {}

    result["version"] = config.get("version")
    result["location_name"] = config.get("location_name")
    installation_type = config.get("installation_type", "unknown")
    result["installation_type"] = installation_type

    # --- WebSocket: states + registries + dashboards ---
    ws = HAWebSocket(ha_url, ha_token, timeout=timeout)
    try:
        states = ws.command({"type": "get_states"}) or []
        areas = ws.command({"type": "config/area_registry/list"}) or []
        devices = ws.command({"type": "config/device_registry/list"}) or []
        entities = ws.command({"type": "config/entity_registry/list"}) or []
        dashboards = ws.command(
            {"type": "lovelace/dashboards/list"}, tolerate_failure=True
        ) or []

        # Supervisor (HA OS / Supervised only). HARD-WON GOTCHA: do NOT call
        # REST /api/hassio/* - it 401s even with a valid core long-lived
        # token. The WS supervisor/api passthrough is the reliable path.
        addons_result = ws.command(
            {
                "type": "supervisor/api",
                "endpoint": "/addons",
                "method": "get",
            },
            tolerate_failure=True,
        )
        supervisor_available = addons_result is not None
        addons = []
        if supervisor_available:
            addons_data = addons_result.get("data", addons_result) if isinstance(addons_result, dict) else addons_result
            raw_addons = addons_data.get("addons", []) if isinstance(addons_data, dict) else []
            for a in raw_addons:
                addons.append(
                    {
                        "name": a.get("name"),
                        "slug": a.get("slug"),
                        "version": a.get("version"),
                        "state": a.get("state"),
                        "update_available": a.get("update_available"),
                    }
                )

    finally:
        ws.close()

    result["supervisor"] = supervisor_available
    result["areas"] = [
        {"area_id": a.get("area_id"), "name": a.get("name")} for a in areas
    ]

    result["devices"] = {
        "count": len(devices),
        "list": [
            {
                "id": d.get("id"),
                "name": d.get("name_by_user") or d.get("name"),
                "manufacturer": d.get("manufacturer"),
                "model": d.get("model"),
                "area_id": d.get("area_id"),
            }
            for d in devices
        ],
    }

    result["entities"] = {
        "by_domain": build_entities_by_domain(states),
        "by_area": build_entities_by_area(entities, devices, states),
        "total_count": len(states),
    }

    platforms, manufacturers = unique_integrations(entities, devices)
    result["integrations"] = {
        "platforms": platforms,
        "device_manufacturers": manufacturers,
    }

    result["addons"] = addons
    result["hacs"] = detect_hacs(states, entities)
    result["dashboards"] = [
        {
            "url_path": d.get("url_path"),
            "title": d.get("title"),
            "mode": d.get("mode"),
        }
        for d in dashboards
    ]
    result["unavailable_entities"] = find_unavailable(states)

    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def print_human_summary(result):
    print("Home Assistant Discovery Summary")
    print("=================================")
    print(f"Version:            {result.get('version')}")
    print(f"Location:           {result.get('location_name')}")
    print(f"Installation type:  {result.get('installation_type')}")
    print(f"Supervisor:         {result.get('supervisor')}")
    print(f"HACS installed:     {result.get('hacs')}")
    print(f"Areas:              {len(result.get('areas', []))}")
    print(f"Devices:            {result.get('devices', {}).get('count', 0)}")
    print(f"Entities (total):   {result.get('entities', {}).get('total_count', 0)}")

    by_domain = result.get("entities", {}).get("by_domain", {})
    print(f"Domains ({len(by_domain)}):")
    for domain in sorted(by_domain, key=lambda d: -len(by_domain[d]))[:15]:
        print(f"  - {domain}: {len(by_domain[domain])}")

    print(f"Integrations (platforms): {len(result.get('integrations', {}).get('platforms', []))}")
    print(f"Add-ons: {len(result.get('addons', []))}")
    print(f"Dashboards: {len(result.get('dashboards', []))}")

    unavailable = result.get("unavailable_entities", [])
    print(f"Unavailable/unknown entities: {len(unavailable)}")
    if unavailable:
        for eid in unavailable[:20]:
            print(f"  - {eid}")
        if len(unavailable) > 20:
            print(f"  ... and {len(unavailable) - 20} more")


def main():
    parser = argparse.ArgumentParser(description="Full read-only Home Assistant inventory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout.")
    parser.add_argument("--out", metavar="FILE", help="Also write JSON output to this file.")
    parser.add_argument("--timeout", type=float, default=15, help="Network timeout in seconds (default 15).")
    args = parser.parse_args()

    ha_url, ha_token = load_config()

    try:
        result = run_discovery(ha_url, ha_token, args.timeout)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: unexpected failure during discovery: {e}", file=sys.stderr)
        sys.exit(4)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except OSError as e:
            print(f"ERROR: could not write output file {args.out}: {e}", file=sys.stderr)
            sys.exit(4)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human_summary(result)

    sys.exit(0)


if __name__ == "__main__":
    main()
