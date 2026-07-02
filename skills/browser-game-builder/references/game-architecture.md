# Game Architecture (single-file Canvas)

Skeleton and systems for a 2D top-down/RTS game in one HTML file. Copy the shapes,
not the specifics.

## Contents
1. Page + loop
2. Entity model
3. Camera & input
4. Pathfinding
5. Fog of war
6. Animation (code motion over static sprites)
7. Terrain + the no-wall-in reachability guarantee

## 1. Page + loop
One `<canvas>`, one requestAnimationFrame loop with a **fixed-timestep update** and
a separate render (so simulation is deterministic and frame-rate independent):
```js
let last=performance.now(), acc=0; const DT=1/60;
function frame(now){ acc += Math.min(0.25,(now-last)/1000); last=now;
  while(acc>=DT){ update(DT); acc-=DT; }
  render(); requestAnimationFrame(frame); }
requestAnimationFrame(frame);
```
Global `G` holds all state (`G.units, G.buildings, G.parts, G.cam, G.time, G.state`).
`G.state` is a tiny FSM: `menu | play | win | lose`.

## 2. Entity model
Plain objects in flat arrays, not class hierarchies — easier for an agent to edit
and for you to serialize (save game). A unit:
```js
{ id, owner, x,y, face, def,           // def = shared stat template (see balance doc)
  hp, maxHp, vet, kills, target, path, // combat + orders
  moving, _px,_py, recoil,             // animation state
  air }                                // layer flag
```
`def` is looked up from a per-faction roster table; instances carry only what
varies. Draw order: terrain → decor → shadows → ground units → buildings → air →
particles → fog → UI.

## 3. Camera & input
`G.cam={x,y,zoom}`; world→screen is `(wx-cam.x)*zoom, (wy-cam.y)*zoom`. Support
edge-scroll + drag-pan + wheel-zoom on desktop and one-finger pan / pinch-zoom /
tap-select on touch (branch on `pointer` events; test on a phone early — mobile is
half your audience for a browser game). Box-select drags a rect and selects units
whose centers fall inside.

## 4. Pathfinding
A* on the tile grid with a **binary heap** open-set (an array `.sort()` per pop is
the classic thing that tanks your frame-rate with 100 units). Cost grid marks
building footprints and `solid` terrain as blocked. Smooth the returned path
(drop waypoints with line-of-sight to the next) so units don't stair-step. Cache
paths and recompute lazily. For big maps, cap A* iterations and fall back to
"move toward" so a blocked unit never freezes the loop.

## 5. Fog of war
Two bitfields over the tile grid per player: `explored` (ever seen) and `visible`
(seen now). Each frame, clear `visible`, then for each owned unit/building stamp a
sight radius. Render as a dark overlay: unexplored = black, explored-not-visible =
dimmed, visible = clear. Keep it on an offscreen canvas updated a few times a
second, not every frame.

## 6. Animation — code motion over static sprites
Cheap life. All of this rides on top of the directional sprite with no extra art.

**Moving flag** (drives everything): at the top of `updateUnit`,
```js
u.moving = Math.hypot(u.x-(u._px||u.x), u.y-(u._py||u.y)) > 0.5;
u._px=u.x; u._py=u.y;
```

**Recoil** on fire; decay each frame; translate sprite back along facing:
```js
// on fire:  u.recoil = (heavyCannon?3 : rocket?1.6 : 1);
// update:   u.recoil = Math.max(0,(u.recoil||0) - dt*20);
// draw:     if(u.recoil) c.translate(-Math.cos(u.face)*u.recoil, -Math.sin(u.face)*u.recoil);
```

**Infantry legs** — a single top-down sprite can't show a gait, so split at the
waist and shear the lower half as a pendulum while the torso holds:
```js
// draw upper body normally, then for the legs region:
const shear = Math.sin(G.time*11 + u.id*2.1) * 0.32;   // when u.moving
c.transform(1,0, shear,1, 0,0);                         // skew lower slice
```
(Or vector-draw a two-leg cycle *under* the body sprite — legs swing from the hip
with `sin(phase)` / `sin(phase+π)`.)

**Rotors** — draw crossed blades spinning above helicopter bodies:
```js
c.save(); c.rotate((G.time*26+u.id)%TAU); /* draw two thin blades */ c.restore();
```

**Dust / downwash** — spawn short-lived tinted particles under moving tracked
units (`#b8a878`) and hovering aircraft (`#cfc4a0`); fade alpha over ~0.4s.

Keep every animation a pure function of `G.time` + `u.id` (phase offset) so units
don't march in lockstep and nothing needs stored per-frame animation state.

## 7. Terrain + the no-wall-in guarantee
**Look:** procedural biome ground — a couple of base colours dithered/perlin-
blended per tile, subtle noise, edge blending between biomes. Scatter decor
(trees, rocks, water) as sprites/shapes; mark some as `solid` (block movement +
pathing). This reads as "real terrain" without any texture files.

**The guarantee:** static objects must never fully enclose a start position. After
generating the map + placing decor, run a **flood-fill reachability check** and
repair before the match starts:
```
1. Build the passability grid (solid terrain + decor + water = blocked).
2. Flood-fill from base A. If any other base / key resource is not reached:
3. Carve the thinnest blocker path: clear solid tiles along the straight line
   between the disconnected bases (or run a cost-based path that's allowed to
   remove decor) until the flood-fill connects them.
4. Repeat until every base-pair and every base→its-nearest-resource is connected.
```
Do this at generation time, not runtime — a player who spawns walled in quits and
never comes back. Also guarantee each base has open build space and a path to at
least one expansion/resource. Log if you had to carve a lot (it means the decor
density is too high).
