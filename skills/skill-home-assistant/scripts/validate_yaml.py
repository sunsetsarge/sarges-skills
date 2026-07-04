#!/usr/bin/env python3
"""
validate_yaml.py - Validate automation/dashboard YAML before applying it to
Home Assistant.

Usage:
  python validate_yaml.py FILE [FILE ...] --kind automation|dashboard|generic [--json] [--live-check]
  cat automation.yaml | python validate_yaml.py - --kind automation

Exit codes:
  0 = pass (no error-level findings)
  1 = fail (one or more error-level findings, or a parse error)
  2 = usage / config error
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    print(
        "ERROR: the 'PyYAML' package is required for YAML validation. Install it with:\n"
        "  pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".ha-skill", "secrets.json")

VALID_MODES = {"single", "restart", "queued", "parallel"}
PLACEHOLDER_MARKERS = ("PLACEHOLDER", "REPLACE")


def mask(text):
    return "***"


def load_config_optional():
    """
    Load HA_URL / HA_TOKEN the same way discover.py does, but do not fail if
    missing - live-check is optional and only needed if requested.
    """
    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")
    if not ha_url or not ha_token:
        if os.path.isfile(SECRETS_PATH):
            try:
                with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                    secrets = json.load(f)
                ha_url = ha_url or secrets.get("ha_url")
                ha_token = ha_token or secrets.get("ha_token")
            except (OSError, json.JSONDecodeError):
                pass
    if ha_url:
        ha_url = ha_url.rstrip("/")
    return ha_url, ha_token


class Finding:
    def __init__(self, level, message, path=None):
        self.level = level  # "error" or "warning"
        self.message = message
        self.path = path

    def to_dict(self):
        d = {"level": self.level, "message": self.message}
        if self.path:
            d["path"] = self.path
        return d


def contains_placeholder(value):
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(marker in upper for marker in PLACEHOLDER_MARKERS)


def find_placeholders(obj, path="root"):
    """Recursively walk a structure looking for obviously-fake entity_ids/values."""
    findings = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{path}.{k}"
            if k == "entity_id" and contains_placeholder(v):
                findings.append(
                    Finding("error", f"Placeholder entity_id found: {v!r}", child_path)
                )
            elif contains_placeholder(v) and isinstance(v, str):
                findings.append(
                    Finding("warning", f"Placeholder-looking value found: {v!r}", child_path)
                )
            findings.extend(find_placeholders(v, child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            findings.extend(find_placeholders(item, f"{path}[{i}]"))
    return findings


def parse_yaml(text):
    """Parse YAML, supporting multi-doc streams. Returns list of docs."""
    docs = list(yaml.safe_load_all(text))
    # Filter out fully empty docs (e.g. trailing '---')
    return [d for d in docs if d is not None]


def lint_automation(doc, doc_index):
    """
    Structural lint for the modern automation schema:
      triggers: [...]   (accept legacy singular 'trigger' with a warning)
      conditions: [...] (optional)
      actions: [...]    (accept legacy singular 'action' with a warning)
      mode: single|restart|queued|parallel
    """
    findings = []
    prefix = f"doc[{doc_index}]"

    # automations.yaml is a LIST of automations; a single automation is a mapping.
    if isinstance(doc, list):
        for j, item in enumerate(doc):
            sub = lint_automation(item, doc_index)
            findings.extend(
                Finding(f.level, f.message, f"{prefix}[{j}]" + (f.path or prefix)[len(prefix):])
                for f in sub
            )
        return findings

    if not isinstance(doc, dict):
        return [Finding("error", "Automation document is not a mapping or list of mappings.", prefix)]

    # alias
    if not doc.get("alias"):
        findings.append(Finding("error", "Missing 'alias' (required for a readable automation name).", prefix))

    # id / unique_id
    if not doc.get("id") and not doc.get("unique_id"):
        findings.append(
            Finding(
                "warning",
                "Missing 'id' (or 'unique_id'). Without it, the automation won't be "
                "editable in the UI and can't be safely deduplicated on reload.",
                prefix,
            )
        )

    # triggers / trigger
    has_triggers = "triggers" in doc
    has_legacy_trigger = "trigger" in doc
    if has_triggers:
        triggers = doc["triggers"]
    elif has_legacy_trigger:
        triggers = doc["trigger"]
        findings.append(
            Finding(
                "warning",
                "Using legacy singular 'trigger:' key. Modern schema prefers 'triggers:'.",
                prefix,
            )
        )
    else:
        triggers = None
        findings.append(Finding("error", "Missing 'triggers' (or legacy 'trigger').", prefix))

    if triggers is not None:
        trigger_list = triggers if isinstance(triggers, list) else [triggers]
        for i, trig in enumerate(trigger_list):
            if isinstance(trig, dict) and "platform" in trig:
                findings.append(
                    Finding(
                        "warning",
                        "Trigger uses legacy 'platform:' key; modern schema uses 'trigger:' "
                        "inside each trigger item (e.g. 'trigger: state').",
                        f"{prefix}.triggers[{i}]",
                    )
                )

    # actions / action
    has_actions = "actions" in doc
    has_legacy_action = "action" in doc
    if not has_actions and not has_legacy_action:
        findings.append(Finding("error", "Missing 'actions' (or legacy 'action').", prefix))
    elif has_legacy_action and not has_actions:
        findings.append(
            Finding(
                "warning",
                "Using legacy singular 'action:' key. Modern schema prefers 'actions:'.",
                prefix,
            )
        )

    # mode
    mode = doc.get("mode")
    if mode is not None and mode not in VALID_MODES:
        findings.append(
            Finding(
                "error",
                f"Invalid 'mode': {mode!r}. Must be one of {sorted(VALID_MODES)}.",
                prefix,
            )
        )

    # placeholders anywhere in the doc
    findings.extend(find_placeholders(doc, prefix))

    return findings


def lint_dashboard(doc, doc_index):
    """
    Structural lint for a Lovelace dashboard config:
      views: list, each with a type/title
    """
    findings = []
    prefix = f"doc[{doc_index}]"

    if not isinstance(doc, dict):
        return [Finding("error", "Dashboard document is not a mapping.", prefix)]

    views = doc.get("views")
    if not isinstance(views, list):
        findings.append(Finding("error", "Missing or invalid 'views' (expected a list).", prefix))
        views = []

    for i, view in enumerate(views):
        view_prefix = f"{prefix}.views[{i}]"
        if not isinstance(view, dict):
            findings.append(Finding("error", "View entry is not a mapping.", view_prefix))
            continue
        if not view.get("type") and not view.get("title"):
            findings.append(
                Finding(
                    "warning",
                    "View has neither 'type' nor 'title' set.",
                    view_prefix,
                )
            )

    findings.extend(find_placeholders(doc, prefix))
    return findings


def lint_generic(doc, doc_index):
    """Generic YAML: parse succeeded is the only check, plus placeholder scan."""
    prefix = f"doc[{doc_index}]"
    return find_placeholders(doc, prefix)


def live_check_config(ha_url, ha_token, timeout=30):
    """
    Call HA's built-in config checker: POST /api/config/core/check_config.
    Returns (ok: bool, message: str).
    """
    if not ha_url or not ha_token:
        return False, "HA_URL/HA_TOKEN not configured; cannot run --live-check."

    url = f"{ha_url}/api/config/core/check_config"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        },
        method="POST",
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            ok = body.get("result") == "valid"
            msg = body.get("errors") or "valid"
            return ok, msg
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "401 Unauthorized (token ***) during live-check."
        return False, f"HTTP error {e.code} during live-check."
    except urllib.error.URLError as e:
        return False, f"Could not reach Home Assistant for live-check: {e.reason}"


def validate_file(path, kind):
    """Returns (findings: list[Finding], parsed_ok: bool)."""
    if path == "-":
        text = sys.stdin.read()
        label = "<stdin>"
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            label = path
        except OSError as e:
            return [Finding("error", f"Could not read file: {e}", path)], False

    try:
        docs = parse_yaml(text)
    except yaml.YAMLError as e:
        return [Finding("error", f"YAML parse error in {label}: {e}", label)], False

    if not docs:
        return [Finding("error", f"No YAML documents found in {label}.", label)], False

    all_findings = []
    for i, doc in enumerate(docs):
        if kind == "automation":
            all_findings.extend(lint_automation(doc, i))
        elif kind == "dashboard":
            all_findings.extend(lint_dashboard(doc, i))
        else:
            all_findings.extend(lint_generic(doc, i))

    return all_findings, True


def main():
    parser = argparse.ArgumentParser(description="Validate HA automation/dashboard YAML before applying.")
    parser.add_argument("files", nargs="+", help="File path(s) to validate, or '-' for stdin.")
    parser.add_argument(
        "--kind", choices=["automation", "dashboard", "generic"], default="generic",
        help="Type of YAML being validated (default: generic).",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    parser.add_argument(
        "--live-check", action="store_true",
        help="Additionally call HA's /api/config/core/check_config (requires HA reachable).",
    )
    args = parser.parse_args()

    report = {"kind": args.kind, "files": []}
    overall_ok = True

    for path in args.files:
        findings, parsed_ok = validate_file(path, args.kind)
        errors = [f for f in findings if f.level == "error"]
        warnings = [f for f in findings if f.level == "warning"]
        file_ok = parsed_ok and not errors
        if not file_ok:
            overall_ok = False

        report["files"].append(
            {
                "file": path,
                "parsed_ok": parsed_ok,
                "pass": file_ok,
                "errors": [f.to_dict() for f in errors],
                "warnings": [f.to_dict() for f in warnings],
            }
        )

    if args.live_check:
        ha_url, ha_token = load_config_optional()
        live_ok, live_msg = live_check_config(ha_url, ha_token)
        report["live_check"] = {"ok": live_ok, "message": live_msg}
        if not live_ok:
            overall_ok = False

    report["overall_pass"] = overall_ok

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Validation kind: {args.kind}")
        print("=" * 40)
        for f in report["files"]:
            status = "PASS" if f["pass"] else "FAIL"
            print(f"[{status}] {f['file']} (parsed_ok={f['parsed_ok']})")
            for e in f["errors"]:
                loc = f" ({e['path']})" if e.get("path") else ""
                print(f"    ERROR: {e['message']}{loc}")
            for w in f["warnings"]:
                loc = f" ({w['path']})" if w.get("path") else ""
                print(f"    WARN:  {w['message']}{loc}")
        if "live_check" in report:
            lc = report["live_check"]
            print(f"\nLive check: {'OK' if lc['ok'] else 'FAILED'} - {lc['message']}")
        print("=" * 40)
        print(f"Overall: {'PASS' if overall_ok else 'FAIL'}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
