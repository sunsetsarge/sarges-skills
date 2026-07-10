#!/usr/bin/env python3
"""
discord_post.py - post a message to any channel in Blaine's Discord using the C1-10P bot.

Self-contained (stdlib only). Token from DISCORD_BOT_TOKEN env or ~/.discord-mcp/config.json.
json.dumps sends non-ASCII as \\uXXXX escapes, so emoji/em-dashes render correctly (no
PowerShell-style mojibake). Resolves the target channel by NAME (or id), auto-chunks messages
over 2000 chars, optional checkmark reaction, and a --dry-run preview.

Commands:
  whoami                                             verify the bot + server count
  channels [--guild G]                               list postable channels (id  #name)
  send --channel NAME|id (--text T | --file F)       post a message
       [--react] [--dry-run] [--guild G]
"""
import argparse, json, os, sys, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path

# Windows consoles default to cp1252; make stdout/stderr UTF-8 so printing emoji doesn't crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API   = "https://discord.com/api/v10"
UA    = "DiscordBot (sarges-skills discord-post, 1.0)"
CHECK = "✅"


def load_token():
    t = os.environ.get("DISCORD_BOT_TOKEN")
    if t:
        return t.strip()
    cfg = Path(os.path.expanduser("~")) / ".discord-mcp" / "config.json"
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
            if d.get("discordToken"):
                return d["discordToken"].strip()
        except Exception as e:
            sys.exit(f"could not read {cfg}: {e}")
    sys.exit("No token: set DISCORD_BOT_TOKEN or create ~/.discord-mcp/config.json with a 'discordToken'.")


def _req(method, path, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", f"Bot {token}")
    req.add_header("User-Agent", UA)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited
                retry = 2.0
                try:
                    retry = float(json.loads(e.read().decode()).get("retry_after", 2))
                except Exception:
                    pass
                time.sleep(max(1.0, retry))
                continue
            sys.exit(f"HTTP {e.code} on {method} {path}: {e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            if attempt == 4:
                sys.exit(f"network error on {method} {path}: {e}")
            time.sleep(1.5)
    return None


def all_guilds(token):
    return _req("GET", "/users/@me/guilds", token) or []


def resolve_guild(token, want):
    gs = all_guilds(token)
    if not gs:
        sys.exit("the bot is in no servers.")
    if want:
        for g in gs:
            if g["id"] == want or g["name"].lower() == want.lower():
                return g["id"]
        sys.exit(f"server '{want}' not found; bot is in: " + ", ".join(g["name"] for g in gs))
    if len(gs) == 1:
        return gs[0]["id"]
    sys.exit("bot is in multiple servers - pass --guild <name>: " + ", ".join(g["name"] for g in gs))


def postable_channels(token, gid):
    chans = _req("GET", f"/guilds/{gid}/channels", token) or []
    return [c for c in chans if c.get("type") in (0, 5)]  # text + announcement


def resolve_channel(token, gid, want):
    if want.isdigit():
        return want
    w = want.lstrip("#").lower()
    chans = postable_channels(token, gid)
    exact = [c for c in chans if c["name"].lower() == w]
    if exact:
        return exact[0]["id"]
    partial = [c for c in chans if w in c["name"].lower()]
    if len(partial) == 1:
        return partial[0]["id"]
    if len(partial) > 1:
        sys.exit(f"'{want}' is ambiguous: " + ", ".join("#" + c["name"] for c in partial))
    sys.exit(f"channel '{want}' not found. Run:  discord_post.py channels")


def chunk(text, n=1990):
    text = text.rstrip()
    out = []
    while text:
        if len(text) <= n:
            out.append(text)
            break
        cut = text.rfind("\n", 0, n)
        if cut < n // 2:
            cut = n
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return out or [""]


def cmd_whoami(token, a):
    me = _req("GET", "/users/@me", token)
    print(f'OK bot: {me.get("username")} (id {me.get("id")}) in {len(all_guilds(token))} server(s)')


def cmd_channels(token, a):
    gid = resolve_guild(token, a.guild)
    for c in sorted(postable_channels(token, gid), key=lambda x: x["name"].lower()):
        print(f'{c["id"]}  #{c["name"]}')


def cmd_send(token, a):
    if a.file:
        text = Path(a.file).read_text(encoding="utf-8")
    elif a.text is not None:
        text = a.text
    else:
        sys.exit("send requires --text or --file")
    gid = resolve_guild(token, a.guild)
    cid = resolve_channel(token, gid, a.channel)
    parts = chunk(text)
    print(f"{len(parts)} message(s) -> channel {cid}" + (" [DRY RUN]" if a.dry_run else ""))
    last = None
    for i, c in enumerate(parts, 1):
        if a.dry_run:
            print(f"  --- chunk {i} ({len(c)} chars) ---\n{c}\n")
            continue
        res = _req("POST", f"/channels/{cid}/messages", token, {"content": c})
        last = res.get("id")
        print(f"  sent {i}/{len(parts)} -> msg {last}")
        time.sleep(0.7)
    if a.react and last and not a.dry_run:
        _req("PUT", f"/channels/{cid}/messages/{last}/reactions/{urllib.parse.quote(CHECK)}/@me", token)
        print("  reacted " + CHECK)


def main():
    p = argparse.ArgumentParser(description="Post to Discord via the bot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    sc = sub.add_parser("channels"); sc.add_argument("--guild"); sc.set_defaults(fn=cmd_channels)
    ss = sub.add_parser("send")
    ss.add_argument("--channel", required=True, help="channel name (e.g. ideas or #ideas) or numeric id")
    ss.add_argument("--text", help="message text")
    ss.add_argument("--file", help="read message body from a UTF-8 file")
    ss.add_argument("--guild", help="server name/id (only needed if the bot is in more than one)")
    ss.add_argument("--react", action="store_true", help="add a checkmark reaction to the last message")
    ss.add_argument("--dry-run", action="store_true", help="preview, do not post")
    ss.set_defaults(fn=cmd_send)
    a = p.parse_args()
    a.fn(load_token(), a)


if __name__ == "__main__":
    main()
