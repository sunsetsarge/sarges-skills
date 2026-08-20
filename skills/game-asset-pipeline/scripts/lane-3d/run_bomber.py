import requests, time, os, sys, json
API_KEY = os.environ.get("MESHY_API_KEY","")
BASE = "https://api.meshy.ai"; HEADERS = {"Authorization": f"Bearer {API_KEY}"}
S = requests.Session(); S.trust_env = False
OUT = os.path.dirname(os.path.abspath(__file__))

def create(ep, p):
    for a in range(3):
        r = S.post(f"{BASE}{ep}", headers=HEADERS, json=p, timeout=30)
        if r.status_code == 429: time.sleep(10); continue
        if r.status_code >= 400: sys.exit(f"ERR {r.status_code}: {r.text}")
        return r.json()["result"]
    sys.exit("rate limited")

def poll(ep, tid, timeout=1200):
    e, d = 0, 5
    while e < timeout:
        r = S.get(f"{BASE}{ep}/{tid}", headers=HEADERS, timeout=30); r.raise_for_status()
        t = r.json()
        if t["status"] == "SUCCEEDED": return t
        if t["status"] in ("FAILED","CANCELED"): sys.exit(f"FAIL {tid}: {t.get('task_error')}")
        w = 15 if t.get("progress",0) >= 95 else d; time.sleep(w); e += w; d = min(d*1.5,30)
    sys.exit("timeout")

def dl(url, path):
    r = S.get(url, timeout=300, stream=True); r.raise_for_status()
    open(path,"wb").write(r.content)
    print("DOWNLOADED:", path, flush=True)

STYLE = ", detailed, menacing, stylized proportions, bold shapes, clean silhouette, retro arcade game asset, symmetric"

def gen(name, prompt):
    print("=== generating", name, "===", flush=True)
    pid = create("/openapi/v2/text-to-3d", {"mode":"preview","prompt":prompt,"ai_model":"latest","symmetry_mode":"on"})
    poll("/openapi/v2/text-to-3d", pid)
    rid = create("/openapi/v2/text-to-3d", {"mode":"refine","preview_task_id":pid,"enable_pbr":True,"ai_model":"latest"})
    t = poll("/openapi/v2/text-to-3d", rid)
    dl(t["model_urls"]["glb"], os.path.join(OUT, name+".glb"))
    if t.get("thumbnail_url"): dl(t["thumbnail_url"], os.path.join(OUT, name+"_thumb.png"))
    print(name, "DONE", flush=True)

# Heavy four-engine bomber — read from the front/below as it bears down on the player.
gen("bomber",
    "a large heavy four-engine WW2 bomber aircraft, broad straight wings with four propeller engines, "
    "long fuselage with a rounded glass nose and a bomb bay underneath, twin tail fins, dark military grey-green, "
    "gun turrets, wide menacing wingspan, viewed as a complete symmetric aircraft" + STYLE)

# Fighter escort — small single-engine prop fighter.
gen("bomber_escort",
    "a small single-engine WW2 fighter plane, sleek pointed fuselage, one propeller at the nose, "
    "straight tapered wings, bubble canopy, dark military grey, agile aggressive silhouette, complete symmetric aircraft" + STYLE)

print("ALL DONE. balance:", S.get(f"{BASE}/openapi/v1/balance", headers=HEADERS, timeout=10).json(), flush=True)
