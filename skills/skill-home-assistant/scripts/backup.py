#!/usr/bin/env python3
"""
backup.py - Trigger a Home Assistant Supervisor full backup and confirm it
landed, before making risky changes (e.g. applying automations/dashboards).

HARD-WON GOTCHA: Supervisor operations must go through the WebSocket
'supervisor/api' passthrough command, NOT the REST /api/hassio/* endpoints
(those 401 even with a valid core long-lived token).

Usage:
  python backup.py [--json] [--wait-max SECONDS] [--name NAME]

Exit codes:
  0 = backup created and confirmed
  1 = configuration error (missing URL/token)
  2 = connection/auth error
  3 = no Supervisor available (not HA OS / Supervised) - back up manually
  4 = backup triggered but could not be confirmed within --wait-max
  5 = unexpected runtime error
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error

try:
    import websocket  # from the `websocket-client` PyPI package
except ImportError:
    websocket = None


SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".ha-skill", "secrets.json")
DEFAULT_WAIT_MAX = 900  # 15 minutes
POLL_INTERVAL = 10  # seconds


def mask(text):
    return "***"


def load_config():
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
                print(f"ERROR: could not read secrets file at {SECRETS_PATH}: {e}", file=sys.stderr)
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

    return ha_url.rstrip("/"), ha_token


class HAWebSocket:
    """Minimal standalone WS helper (auth handshake + id-sequenced commands)."""

    def __init__(self, ha_url, ha_token, timeout=15):
        if websocket is None:
            print(
                "ERROR: the 'websocket-client' package is required. Install it with:\n"
                "  pip install websocket-client",
                file=sys.stderr,
            )
            sys.exit(1)

        ws_url = ha_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/api/websocket"
        self.ha_token = ha_token
        self._id = 0
        self.default_timeout = timeout

        try:
            self.ws = websocket.create_connection(ws_url, timeout=timeout)
        except ConnectionRefusedError:
            print(f"ERROR: connection refused when opening WebSocket to {ws_url}.", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR: could not open WebSocket to {ws_url}: {e}", file=sys.stderr)
            sys.exit(2)

        self._authenticate()

    def _recv_json(self):
        raw = self.ws.recv()
        return json.loads(raw)

    def _authenticate(self):
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
            print("ERROR: WebSocket auth_invalid - the HA_TOKEN (***) was rejected.", file=sys.stderr)
            sys.exit(2)
        if auth_result.get("type") != "auth_ok":
            print(f"ERROR: unexpected WebSocket auth response: {auth_result}", file=sys.stderr)
            sys.exit(2)

    def command(self, payload, tolerate_failure=False, recv_timeout=None):
        """
        Send an id-sequenced command and return the 'result' field.

        recv_timeout temporarily overrides the socket timeout for this one
        call - used for the backup trigger, which can legitimately take
        several minutes.
        """
        self._id += 1
        msg = dict(payload)
        msg["id"] = self._id

        old_timeout = self.ws.gettimeout()
        if recv_timeout is not None:
            self.ws.settimeout(recv_timeout)

        try:
            self.ws.send(json.dumps(msg))
            resp = self._recv_json()
        except Exception as e:
            if tolerate_failure:
                return None
            print(f"ERROR: WebSocket command failed or timed out: {e}", file=sys.stderr)
            return None
        finally:
            if recv_timeout is not None:
                self.ws.settimeout(old_timeout)

        if not resp.get("success", False):
            if tolerate_failure:
                return None
            print(
                f"ERROR: WebSocket command {payload.get('type')} failed: {resp.get('error')}",
                file=sys.stderr,
            )
            return None
        return resp.get("result")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def supervisor_api(ws, endpoint, method="get", data=None, tolerate_failure=True, recv_timeout=None):
    """Wrapper for the supervisor/api WS passthrough command."""
    payload = {
        "type": "supervisor/api",
        "endpoint": endpoint,
        "method": method,
    }
    if data is not None:
        payload["data"] = data
    return ws.command(payload, tolerate_failure=tolerate_failure, recv_timeout=recv_timeout)


def unwrap(result):
    """Supervisor API responses are sometimes nested under a 'data' key."""
    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result


def list_backups(ws):
    result = supervisor_api(ws, "/backups", method="get", tolerate_failure=True)
    if result is None:
        return []
    data = unwrap(result)
    if isinstance(data, dict):
        return data.get("backups", [])
    return []


def check_supervisor_present(ws):
    """Probe /addons (cheap, always present if Supervisor exists)."""
    result = supervisor_api(ws, "/addons", method="get", tolerate_failure=True)
    return result is not None


def trigger_backup(ws, name, initial_timeout):
    """
    POST /backups/new/full. This call blocks until HA finishes the backup,
    so give it a generous timeout. If it times out client-side, the caller
    falls back to polling /backups.

    Returns the slug if the call itself returned one, else None.
    """
    result = supervisor_api(
        ws,
        "/backups/new/full",
        method="post",
        data={"name": name},
        tolerate_failure=True,
        recv_timeout=initial_timeout,
    )
    if result is None:
        return None
    data = unwrap(result)
    if isinstance(data, dict):
        return data.get("slug")
    return None


def poll_for_backup(ha_url, ha_token, name, wait_max):
    """
    Reconnect (the original WS call may have died) and poll /backups every
    POLL_INTERVAL seconds up to wait_max seconds, looking for a backup whose
    name matches.
    """
    deadline = time.time() + wait_max
    while time.time() < deadline:
        try:
            ws = HAWebSocket(ha_url, ha_token, timeout=15)
            backups = list_backups(ws)
            ws.close()
        except SystemExit:
            raise
        except Exception:
            backups = []

        for b in backups:
            if b.get("name") == name:
                return b

        time.sleep(POLL_INTERVAL)

    return None


def main():
    parser = argparse.ArgumentParser(description="Trigger a Supervisor full backup and confirm it completed.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    parser.add_argument(
        "--wait-max", type=int, default=DEFAULT_WAIT_MAX,
        help=f"Max seconds to wait/poll for backup confirmation (default {DEFAULT_WAIT_MAX}).",
    )
    parser.add_argument(
        "--name", default=None,
        help="Backup name override (default: 'pre-skill-change-<UTC timestamp>').",
    )
    args = parser.parse_args()

    ha_url, ha_token = load_config()

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = args.name or f"pre-skill-change-{timestamp}"

    report = {"name": backup_name, "supervisor": False}

    try:
        ws = HAWebSocket(ha_url, ha_token, timeout=15)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: unexpected failure connecting to Home Assistant: {e}", file=sys.stderr)
        sys.exit(5)

    try:
        if not check_supervisor_present(ws):
            ws.close()
            msg = (
                "No Supervisor detected on this Home Assistant instance (not HA OS / "
                "Supervised - likely Core or Container install). Automatic full backups "
                "are not available here. Back up manually (snapshot your config directory, "
                "database, and secrets) before making changes."
            )
            report["supervisor"] = False
            report["error"] = msg
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"ERROR: {msg}")
            sys.exit(3)

        report["supervisor"] = True

        # Initial attempt: let the WS call block for a good chunk of the
        # wait budget (it returns when the backup is actually done).
        initial_timeout = min(args.wait_max, 300)  # first leg: up to 5 min
        slug = trigger_backup(ws, backup_name, initial_timeout)
    finally:
        ws.close()

    backup_record = None

    if slug:
        # Confirm it's really listed.
        try:
            ws2 = HAWebSocket(ha_url, ha_token, timeout=15)
            backups = list_backups(ws2)
            ws2.close()
        except SystemExit:
            raise
        except Exception:
            backups = []
        for b in backups:
            if b.get("slug") == slug:
                backup_record = b
                break

    if backup_record is None:
        # Either the trigger call timed out client-side, or slug lookup
        # failed - fall back to polling /backups by name.
        remaining = max(args.wait_max - POLL_INTERVAL, POLL_INTERVAL)
        backup_record = poll_for_backup(ha_url, ha_token, backup_name, remaining)

    if backup_record is None:
        msg = (
            f"Backup '{backup_name}' was triggered but could not be confirmed within "
            f"{args.wait_max} seconds. It may still be running - check the HA Backups "
            "page manually before proceeding."
        )
        report["confirmed"] = False
        report["error"] = msg
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"ERROR: {msg}")
        sys.exit(4)

    report["confirmed"] = True
    report["backup"] = {
        "slug": backup_record.get("slug"),
        "name": backup_record.get("name"),
        "size": backup_record.get("size"),
        "date": backup_record.get("date"),
        "type": backup_record.get("type"),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Home Assistant Backup Confirmation")
        print("===================================")
        b = report["backup"]
        print(f"Name:  {b['name']}")
        print(f"Slug:  {b['slug']}")
        print(f"Size:  {b['size']}")
        print(f"Date:  {b['date']}")
        print(f"Type:  {b['type']}")
        print("\nBackup confirmed. Safe to proceed with changes.")

    sys.exit(0)


if __name__ == "__main__":
    main()
