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

def poll(ep, tid, timeout=900):
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

STYLE = ", detailed, menacing, stylized proportions, bold shapes, clean silhouette, retro arcade game asset"
prompt = ("WW2 battleship dreadnought warship seen in full broadside side profile: very long dark battleship-gray steel hull, "
          "three large twin-barrel main gun turrets on the deck (two forward, one aft), tall central bridge superstructure "
          "tower with a tripod mast and rangefinder, two funnels, rows of smaller secondary guns along the hull, "
          "long low aggressive silhouette sitting in the water" + STYLE)
pid = create("/openapi/v2/text-to-3d", {"mode":"preview","prompt":prompt,"ai_model":"latest","symmetry_mode":"off"})
poll("/openapi/v2/text-to-3d", pid)
rid = create("/openapi/v2/text-to-3d", {"mode":"refine","preview_task_id":pid,"enable_pbr":True,"ai_model":"latest"})
t = poll("/openapi/v2/text-to-3d", rid)
dl(t["model_urls"]["glb"], os.path.join(OUT,"battleship.glb"))
if t.get("thumbnail_url"): dl(t["thumbnail_url"], os.path.join(OUT,"battleship_thumb.png"))
print("BATTLESHIP DONE. balance:", S.get(f"{BASE}/openapi/v1/balance", headers=HEADERS, timeout=10).json(), flush=True)
