# Battle System Reference

ATB math, commands, damage, elements, statuses, enemy AI, and rewards.
All names below (spells, commands, statuses) are original placeholders —
rename freely per game, never to franchise names.

## 1. ATB core loop

### Gauge fill

```js
const READY = 100;
const ATB_RATE = 0.4;              // global pacing knob, tune 0.3–0.6

function tickATB(dt) {             // dt in ms
  if (battleState !== "TICKING") return;   // RULE 1: Wait mode pauses ALL fill
  for (const c of combatants) {
    if (!c.alive || c.ready || hasStatus(c, "stasis")) continue;
    const mult = hasStatus(c, "haste") ? 1.5 : hasStatus(c, "slow") ? 0.5 : 1;
    c.atb = Math.min(c.atb + c.stats.speed * ATB_RATE * mult * dt / 16.67, READY);
    if (c.atb >= READY) { c.ready = true; readyQueue.push(c); }
  }
}
```

- Speed 30–40 = sluggish tank, 50–60 = average, 70+ = speedster. A full bar
  from empty at speed 50 and rate 0.4 ≈ 5 seconds — that's genre-correct pacing.
- `battleState` values: `TICKING`, `MENU_OPEN`, `RESOLVING`, `VICTORY`,
  `DEFEAT`, `FLED`. Fill happens ONLY in `TICKING`. Enemies use the same gauges
  and the same queue — when an enemy comes ready, its AI picks an action and it
  enters the same FIFO.
- When an actor acts, reset `atb = 0, ready = false`. Some commands can
  set a partial refund (quick actions restart at 20–30) — data-drive it via a
  `recovery` field on the command/spell.

### Action queue discipline

1. Pop one entry from `readyQueue` (FIFO).
2. Player actor → `battleState = "MENU_OPEN"`, open its command menu. Enemy →
   run AI table, produce an action.
3. On action chosen → `battleState = "RESOLVING"` → validate actor alive/able
   and target alive (retarget or cancel — SKILL.md rule 2) → animate → apply
   damage/effects → death checks → counters/reactions → end-of-battle check.
4. Back to `TICKING`.

Never resolve two actions concurrently. Poison/regen/burn tick when the
afflicted unit's own gauge crosses ready (charge them a "virtual tick"), or on
a fixed 4-second timer — pick one, apply consistently, and run the
end-of-battle check after those ticks too.

## 2. Command menu

Per ready character: **Fight / [Signature] / Magic / Item / Defend**, plus
**Flee** on a party-level input (hold cancel).

- **Fight** — basic physical, front/back row modifiers apply.
- **Signature** — this character's unique command from `commands.json` (see
  §3). Position it second: it's the character's identity.
- **Magic** — submenu of spells learned (innate + Glyphstone-taught), shows MP
  cost, greys out unaffordable or silenced. Silence blocks the whole submenu.
- **Item** — party inventory, consumables only in battle.
- **Defend** — until next turn: physical damage ×0.5, small ATB recovery bonus.
- Row: back row = physical damage dealt and received ×0.5; spells and most
  signatures unaffected.

## 3. Signature commands (one per character)

Each roster character has exactly one, defined in `commands.json` with a
`behavior` key the engine implements once and data parameterizes. The eight
canonical behaviors (invent flavor names per game — examples given):

| behavior | example name | mechanic |
|---|---|---|
| `steal` | Pilfer | % chance to take from the enemy's `stealTable` (common/rare slots) |
| `throw` | Lob | consume an inventory item flagged `throwable`, big physical damage |
| `mimic` | Echo Fang | cast the last enemy skill observed this battle, no MP cost |
| `charge` | Overwind | skip N turns charging, then release multiplied damage (2×/4×/8×) |
| `gamble` | Fate Wheel | random effect from a weighted table (huge hit, heal, self-hurt, dud) |
| `shapeshift` | Feral Vow | transform: stat swap + new moveset until battle ends or HP threshold |
| `guard_ally` | Bulwark Oath | intercept physical attacks aimed at chosen ally this round |
| `scan` | Appraise | reveal enemy HP/weaknesses/steal table in the UI |

Rules of thumb: every behavior must be usable every battle (no dead commands);
`gamble` tables must weight duds ≥ jackpots; `charge` must show a visible
charging state; `mimic` needs a "nothing observed yet" fallback (weak flail).

## 4. Damage formulas

Keep them simple, integer, and tunable. `rand(0.9, 1.1)` variance on
everything; damage floors at 1 unless immune/absorb.

```
physical = max(1, floor( (ATK * 2 + LCK/4) * powerMod * rowMod * rand
                         - DEF * 1.5 ) * defendMod * elemMod )
magical  = max(1, floor( (MAG * 2 + spellPower) * rand - SPI * 1.5 ) * elemMod )
healing  = floor( (MAG + spellPower) * rand )       // no mitigation
```

- `powerMod`: weapon/skill multiplier (Fight = 1.0, heavy skills 1.5–3.0).
- `defendMod`: 0.5 if target is defending (physical only — SKILL.md rule 7).
- Crit: chance `= 4% + LCK/8`, damage ×2, ignores `defendMod`.
- Miss/evade: hit `= 92% + attackerLCK/4 − targetLCK/4`, clamp 60–99%. Magic
  never misses (statuses use save chances instead).

## 5. Elemental affinity

Elements are data (typical set: ember, frost, storm, stone, gale, tide,
radiance, gloom). Each enemy/equipment carries affinity lists.

**Precedence — ordered early-return, never additive (SKILL.md rule 6):**

```js
function elemMod(target, element) {
  if (!element) return 1;
  if (target.affinity.immune.includes(element))  return 0;
  if (target.affinity.absorb.includes(element))  return -1;  // heals instead
  if (target.affinity.resist.includes(element))  return 0.5;
  if (target.affinity.weak.includes(element))    return 2;
  return 1;
}
```

Absorb (−1) converts final damage to healing of the same magnitude. Equipment
can grant party members these affinities; when multiple equipment pieces
conflict, apply the same precedence to the merged sets.

## 6. Status ailments

| status | effect | wears off |
|---|---|---|
| venom | lose ~1/16 max HP per status tick | battle end / antidote |
| drowse | skip turns, gauge frozen | on taking damage, or 2–4 ticks |
| mute | Magic command disabled | timer / remedy |
| shackle | physical commands disabled, can still cast | timer / remedy |
| addle | acts randomly, may target allies | on taking physical damage |
| doom | instant KO on infliction | — (it IS the effect) |
| stonecurse | counts down 3 → petrified = removed from battle | cured before zero |
| haste / slow | ATB rate ×1.5 / ×0.5 | battle end |
| stasis | gauge frozen entirely | timer |

Infliction roll: `inflictChance × (1 − targetResist[status])`, resist from
race/equipment data, 0–1. Bosses list outright immunities in data (rule 9).
Every active status renders an icon or tint (rule 8). Party-wide petrify/KO =
defeat — include petrified members in the defeat check.

## 7. Enemy AI: scripted action tables

No utility AI — the genre is scripted tables with phases. Per enemy in
`enemies.json`:

```json
"ai": {
  "phases": [
    { "hpAbove": 0.5, "script": [
        { "act": "attack", "weight": 3 },
        { "act": "spell:ember_lash", "weight": 1 } ] },
    { "hpAbove": 0.0, "script": [
        { "act": "spell:ember_storm", "weight": 2 },
        { "act": "attack", "weight": 1 } ],
      "onEnter": { "message": "The husk's shell cracks!", "act": "spell:enrage_self" } }
  ],
  "counter": { "onElement": "frost", "act": "spell:ember_lash", "chance": 0.5 }
}
```

- Phase = first entry whose `hpAbove` the current HP fraction exceeds; crossing
  a threshold fires `onEnter` once (the telegraphed "boss transforms" beat).
- Weighted random pick within the active script; support `act` values
  `attack`, `spell:<id>`, `flee`, `summon:<enemyId>`, `nothing` (bosses that
  "gather strength").
- Targeting default: random living player, weighted 2× toward front row;
  scripts may override (`"target": "lowestHp"`).

## 8. Fleeing

- Player flee: hold cancel ≥ 1s. Success `= 50% + (partyAvgSpeed −
  enemyAvgSpeed) × 2%`, clamp 25–95%. Fail = the round passes, enemies act.
- `noFlee: true` on formations for bosses/story fights — show "Can't escape!".
- Enemies may flee via AI (`act: "flee"`) — they drop no EXP but battle can
  still be won if others remain.

## 9. Rewards & leveling

- Each enemy: `exp`, `coin` (invent currency name), `dropTable`
  (`[{itemId, chance}]`, roll each independently), `stealTable`, and `gp`
  (Glyph Points — fed to every equipped Glyphstone of living members).
- EXP split evenly among living members. EXP-to-next: `next = floor(50 *
  level^1.9)` — tune the exponent 1.8–2.1.
- On level-up: base stats grow from the character's `growth` block, PLUS the
  equipped Glyphstone's `levelBonus` (the passive hook — see data-schemas.md).
  Recompute derived stats (SKILL.md rule 16); heal nothing automatically.
- Spell learning: each Glyphstone lists `[{spellId, gpCost}]`; accumulated GP
  per (character, glyphstone) pair; on threshold, splash "Learned <spell>!"
  on the victory screen. Learned spells are permanent even after unequipping.

## 10. Victory / defeat sequence

Victory: freeze gauges → fanfare (let it finish — SKILL.md rule 24) → EXP/GP/
coin/drops screen → level-up and spell-learn splashes → return to field with
grace-period steps. Defeat: all members KO'd/petrified → defeat theme → title
or last save prompt. Fled: no rewards, field grace period still applies.
