# REGEN_TODO template

Copy into the target project as `docs/REGEN_TODO.md`. The point is that unusable
source art never blocks the pipeline and never gets silently forgotten.

Two things make an entry useful: **evidence** (so nobody re-litigates whether the art
is really broken) and a **concrete regeneration spec** (so the fix is a paste, not a
design session).

---

```markdown
# REGEN_TODO — source art that cannot be used as-is

Established by reading contact sheets, not by guessing. Evidence in `docs/audit/`.
Nothing here blocks a shipping feature; each is designed around.

## Blocking <feature / level / chapter>

### `<asset_key>` — <Display Name>
`<source path>`. <What is measurably wrong — sizes, frame counts, what the contact
sheet shows. Be specific enough that someone can confirm it in one look.>

**Needs:** <exact regeneration spec. For 2D: uniform grid, one subject per cell,
solid white background, rows IDLE / WALK / ATTACK / HURT / DEATH, N frames per row,
facing LEFT, no baked captions, min cell height Npx. For 3D: what shape failed and
whether to build it from primitives instead.>

## Not blocking, but degraded

| Asset | Problem | Current handling |
|---|---|---|
| `<key>` | <turntable / 1-frame anim / low native res> | <single angle + procedural motion / fades instead of animating> |

## Notes for the next generation run

- Do **not** ask for labelled sheets — baked caption text has to be filtered back out,
  and captions have been wrong about facing.
- State the facing convention explicitly in the prompt.
- Specify cell size: source at 2–3× the on-screen height, never below it.
```

---

## While the gap is open

Substitute a loud, obviously-wrong placeholder — magenta checkerboard, not a grey box.
A silent fallback gets shipped; a magenta one gets noticed. Exclude the asset from any
roster or spawn table rather than shipping it broken, and note in the handoff which
features are affected.
