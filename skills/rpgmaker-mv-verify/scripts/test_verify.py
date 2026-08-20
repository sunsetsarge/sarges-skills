"""Prove rpgmv_verify.py catches each defect class by injecting them one at a time."""
import json, os, shutil, subprocess, sys, tempfile

SRC = r"D:\Documents\Games\Stormlight"
VERIFY = r"C:\Claude\Scripts\rpgmv_verify.py"
PY = r"C:\AI-Shared\python.exe"


_seq = [0]


def build_fixture(dest):
    # a fresh directory per case: Windows keeps handles on just-copied trees,
    # so deleting and recreating the same path races with the indexer
    _seq[0] += 1
    dest = f"{dest}_{os.getpid()}_{_seq[0]}"   # pid keeps reruns from colliding
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    shutil.copytree(os.path.join(SRC, "data"), os.path.join(dest, "data"))
    # empty files suffice: the asset check tests existence only
    for folder in ("tilesets", "characters", "faces", "sv_actors"):
        s = os.path.join(SRC, "img", folder)
        d = os.path.join(dest, "img", folder)
        os.makedirs(d, exist_ok=True)
        if os.path.isdir(s):
            for f in os.listdir(s):
                if f.endswith(".png"):
                    open(os.path.join(d, f), "wb").close()
    return dest


def run(path):
    r = subprocess.run([PY, VERIFY, path], capture_output=True, text=True)
    return r.stdout


def load(path, name):
    with open(os.path.join(path, "data", name), encoding="utf-8-sig") as fh:
        return json.load(fh)


def save(path, name, obj):
    with open(os.path.join(path, "data", name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)


# --------------------------------------------------------------- injectors
def inj_assets(p):
    os.remove(os.path.join(p, "img", "tilesets", "Outside_A1.png"))
    return "ASSETS"


def inj_autotile(p):
    m = load(p, "Map002.json")
    m["data"][0] = 2496          # kind9 (waterfall) shape16 -> illegal
    save(p, "Map002.json", m)
    return "AUTOTILE"


def inj_placement(p):
    m = load(p, "Map004.json")
    for ev in m["events"]:
        if ev and ev["name"] == "Shopkeeper":
            ev["x"], ev["y"] = 10, 3     # back into the wall
    save(p, "Map004.json", m)
    return "PLACEMENT"


def inj_eventcmd(p):
    m = load(p, "Map004.json")
    for ev in m["events"]:
        if ev and ev["name"] == "Shopkeeper":
            for c in ev["pages"][0]["list"]:
                if c["code"] == 302:
                    c["parameters"] = [0, 0]
    save(p, "Map004.json", m)
    return "EVENTCMD"


def inj_geometry(p):
    m = load(p, "Map003.json")
    m["tilesetId"] = 99
    save(p, "Map003.json", m)
    return "GEOMETRY"


def inj_transfer(p):
    m = load(p, "Map002.json")
    for ev in m["events"]:
        if not ev:
            continue
        for pg in ev["pages"]:
            for c in pg["list"]:
                if c["code"] == 201:
                    c["parameters"] = [0, 77, 5, 5, 0, 0]   # map 77 does not exist
                    save(p, "Map002.json", m)
                    return "TRANSFER"
    return "TRANSFER"


def inj_start(p):
    sysd = load(p, "System.json")
    m = load(p, "Map002.json")
    sx, sy = sysd["startX"], sysd["startY"]
    m["events"].append({
        "id": 999, "name": "Bad Warp", "note": "", "x": sx, "y": sy,
        "pages": [{
            "conditions": {"actorId": 1, "actorValid": False, "itemId": 1, "itemValid": False,
                           "selfSwitchCh": "A", "selfSwitchValid": False, "switch1Id": 1,
                           "switch1Valid": False, "switch2Id": 1, "switch2Valid": False,
                           "variableId": 1, "variableValid": False, "variableValue": 0},
            "directionFix": False, "image": {"characterIndex": 0, "characterName": "",
                                             "direction": 2, "pattern": 1, "tileId": 0},
            "list": [{"code": 201, "indent": 0, "parameters": [0, 1, 5, 5, 0, 0]},
                     {"code": 0, "indent": 0, "parameters": []}],
            "moveFrequency": 3, "moveRoute": {"list": [{"code": 0, "parameters": []}],
                                              "repeat": True, "skippable": False, "wait": False},
            "moveSpeed": 2, "moveType": 0, "priorityType": 0, "stepAnime": False,
            "through": True, "trigger": 1, "walkAnime": False}]})
    save(p, "Map002.json", m)
    return "START"


def inj_stacked(p):
    m = load(p, "Map002.json")
    live = [e for e in m["events"] if e]
    a, b = live[0], live[1]
    b["x"], b["y"] = a["x"], a["y"]
    save(p, "Map002.json", m)
    return "PLACEMENT/stacked"


CASES = [inj_assets, inj_autotile, inj_placement, inj_eventcmd,
         inj_geometry, inj_transfer, inj_start, inj_stacked]

base = os.path.join(tempfile.gettempdir(), "rpgmv_fixture")
out = run(build_fixture(base))   # use the returned path, not the stem
print("BASELINE (expect CLEAN):", out.strip().splitlines()[-1] if out.strip() else "(no output)")
print()

passed = failed = 0
for inj in CASES:
    p = build_fixture(base)
    label = inj(p)
    out = run(p)
    key = label.split("/")[0]
    detected = f"## {key}" in out
    # for the stacked case, look for the specific message instead
    if label.endswith("stacked"):
        detected = "stacked events" in out
    if label == "START":
        detected = "warps out immediately" in out or "## START" in out
    status = "PASS" if detected else "FAIL"
    passed += detected
    failed += not detected
    first = next((l.strip() for l in out.splitlines()
                  if l.strip().startswith(("FATAL", "WARN"))), "(nothing reported)")
    print(f"{status}  inject {label:20} -> {first[:110]}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
