# Progression — Metroidvania-Lite Upgrades

The genre's progression model is deliberately shallow compared to a full Metroidvania: a small, fixed set of armor upgrades plus two flat HP-economy systems (heart tanks, sub-tanks), layered over an otherwise stage-select structure rather than one fully open world map. The payoff is backtracking value without requiring a fully interconnected map — see `level-design.md` for how WorldFlags substitutes for true map interconnection.

## Armor upgrades

Four upgrade slots, one major capability each. Each is typically hidden in a specific stage, sometimes gated behind another upgrade (see gating graph below).

| Slot | Grants | Design intent |
|---|---|---|
| Leg | Ground dash (if not base-kit) and/or air dash | The traversal upgrade — biggest immediate feel change, so it's a strong early unlock to hand out. |
| Arm | Charged special-weapon shots (Lv2/Lv3 tiers applied to equipped special weapons, not just the buster) and L3 buster tier | Turns special weapons from single-use tools into scalable damage, rewarding weapon variety later in the run. |
| Body | 50% incoming damage reduction, and/or a "no knockback flinch" toggle | A survivability upgrade — matters most for late-game stages and superbosses where knockback into a hazard is the actual killer, not raw damage. |
| Head | Utility: reveal hidden passages on the map/minimap, or break specific reinforced blocks | The "backtracking key" upgrade — explicitly designed to make previously-seen dead ends make sense in hindsight. |

Design rule: each armor piece should be discoverable in a stage where the player does **not** yet need it to finish that stage — it's a bonus found via exploration, not a hard blocker for stage completion. Save hard blockers for hidden *paths* (below), not for main-route completion.

## Heart tanks

- Each heart tank found permanently adds **+2 max HP**.
- **8 heart tanks total**, one per Maverick-style stage (see `level-design.md`) is a clean 1:1 distribution that gives every stage exactly one exploration reward of this type.
- **Base HP 16 -> max HP 32** once all 8 are collected (16 + 8x2 = 32).
- Immediately applied on pickup (no menu confirmation needed) and always persists — never lost on death, only reset on an explicit new-game.

## Sub-tanks

- **2-4 sub-tanks** is the target range; more than 4 dilutes their usefulness as an emergency resource and starts to trivialize boss fights.
- **Fill mechanism**: a sub-tank does not fill on its own — it fills from **surplus HP pickups**, i.e., health drops the player collects while already at full HP overflow into an available sub-tank instead of being wasted. This rewards players who explore/farm before a boss fight rather than rushing in at exactly full HP.
- **Manual use**: activating a sub-tank is a deliberate player-initiated action (menu or dedicated button), instantly restoring HP up to the tank's stored amount. It is never automatic (e.g., never auto-triggers on near-death) — automatic use removes the player agency that makes sub-tanks a resource-management decision rather than a safety net.
- **Persistence**: a sub-tank's fill state (empty, partially full, full) is part of the save schema (see `architecture.md`'s save-schema section) and persists across sessions exactly as left — a sub-tank used mid-run stays empty until refilled, even after saving/reloading.

## Hidden paths and fair gating

Hidden paths are optional side-routes gated behind a specific weapon or armor piece, existing purely to reward backtracking with heart tanks, sub-tanks, ammo expansions, or armor pieces themselves.

### Gating graph — worked example

A minimal, concrete example of how gates can interlock without becoming a required order:

```
Stage 1 (Frost)   -- hidden path needs [Blade weapon] --> Sub-Tank #1
Stage 2 (Flame)   -- hidden path needs [Leg armor: air dash] --> Heart Tank
Stage 3 (Storm)   -- hidden path needs [Frost weapon] --> Head armor
Stage 4 (Volt)    -- hidden path needs [Head armor: block-break] --> Heart Tank
Stage 5 (Stone)   -- hidden path needs [Storm weapon] --> Sub-Tank #2
Stage 6 (Toxin)   -- hidden path needs [Arm armor: charge specials] --> Heart Tank
Stage 7 (Blade)   -- hidden path needs [Gravity weapon] --> Heart Tank
Stage 8 (Gravity) -- hidden path needs [Body armor] --> final Heart Tank
```

Reading this graph: no stage's hidden path requires beating that same stage's own boss weapon (avoids a trivial same-stage-only gate), and armor gates are spread so that a player who explores opportunistically will naturally unlock 2-3 hidden paths on a second pass through earlier stages once they've picked up a couple of armor pieces or weapons — this is what makes "backtrack once you have new toys" feel rewarding rather than like a forced checklist.

### Rules for fair hiding

A hidden path that feels like a cheap secret (invisible wall, pixel-hunt) breaks trust; a hidden path that's fairly telegraphed feels like a reward for paying attention. Use these signal types, and use at least one every time:

- **Cracked/textured walls**: a visibly distinct wall texture (cracks, discoloration) marks a breakable or weapon-vulnerable wall from the first time the player walks past it, even before they have the tool to open it. This lets a first playthrough notice-and-remember, then confirm on a later pass.
- **Off-screen ledges implied by camera framing**: a platform edge that visibly continues past the current camera deadzone (see `architecture.md`'s camera section) signals "there's more here" without requiring the player to already suspect a secret — good for dash-jump-only side routes that don't need a special weapon, just skill plus knowledge that the ledge exists.
- **Camera hints / establishing pans**: a brief scripted camera pan on stage entry or after a trigger, showing the hidden area from a distance, plants the idea early so the player isn't relying purely on random exploration to notice it at all.
- **Never** hide a path behind a wall with *zero* visual distinction from a normal solid wall — if it requires a wiki lookup to find on a first playthrough, it is not fairly hidden, it is simply hidden, and should be redesigned with one of the above cues.
