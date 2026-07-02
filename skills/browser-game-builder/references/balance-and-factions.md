# Balance & Faction Design

How to make combat feel tactical instead of a stat-ball, and how to make factions
genuinely different instead of palette swaps.

## Contents
1. Unit stat template
2. Damage-vs-armor matrix (the core of tactics)
3. Veterancy & upgrades
4. Asymmetric factions (advantage/disadvantage triangle)
5. Tuning process

## 1. Unit stat template
Every unit's `def` shares a shape:
```js
{ k:'crusader', n:'Crusader', cls:'veh', cost:900, build:12,
  hp:520, armor:'heavy', sp:52, sight:180, scale:1.0,
  w:{ type:'cannon', dmg:45, rng:150, cd:1.4, aoe:0, aa:false } }  // weapon, optional
```
`cls` (inf/veh/air/heli) drives draw + layer; `armor` and `w.type` drive the
matrix below. Keep costs and DPS in a spreadsheet mentally: **DPS = dmg/cd**, and
**cost-efficiency = effective-DPS×EHP / cost** should land in a similar band across
units of the same role, then get bent deliberately by faction identity (§4).

## 2. Damage-vs-armor matrix
The single most important tactical lever. A weapon type does different % damage to
each armor class, so unit choice is rock-paper-scissors, not "bigger number wins":

|          | inf | light | heavy | air | building |
|----------|-----|-------|-------|-----|----------|
| gun      | 100 |  70   |  25   |  0  |   15     |
| cannon   |  60 | 100   | 100   |  0  |   70     |
| rocket   |  50 |  90   | 110   | 40  |  120     |
| flame    | 120 |  80   |  40   |  0  |   60     |
| AA       |  10 |  20   |  10   | 130 |    5     |
| sniper   | 200 |   0   |   0   |  0  |    0     |
| artillery|  90 |  90   |  70   |  0  |  110     |

`finalDamage = w.dmg * matrix[w.type][target.armor]/100 * vetMul * upgradeMul`.
Air units are only hittable by weapons with `aa:true` (or the AA row). Tune the
numbers so every unit has a clear counter and a clear prey.

## 3. Veterancy & upgrades
Two orthogonal progression axes keep engagements dynamic:
- **Veterancy** (per-unit, earned by kills): rank 0→3 multiplies dmg/range/HP/sight.
  `VET_DMG=[1,1.20,1.45,1.75]`, `VET_HP=[1,1.25,1.55,1.90]`, etc. Promote at kill
  thresholds `[2,5,9]`. Veterans surviving is a reward for good micro.
- **Upgrades** (faction-wide, bought at a tech building): e.g. Weapons +12%/level,
  Armor +15%/level, Optics +sight/range, Drill +speed. Escalating price per level.

Effective stat = `base × vet × upgrade`. Buildings usually use base stats only.

## 4. Asymmetric factions — the part people skip
Three factions that are stat-swaps of each other are boring. Give each a distinct
**advantage** and a distinct **disadvantage** that form a complementary triangle,
so matchups play differently and there's a reason to pick one. A worked example
(the C&C-Generals archetype — reuse the *structure*, rename per ip-safety.md):

- **High-Tech faction** — *Advantage:* best air power, precise/tough units, strong
  late game. *Disadvantage:* everything costs more and builds slower; punished by
  early aggression and by attrition. Economy: fewer, more valuable units.
- **Mass faction** — *Advantage:* cheap, tough units and horde bonuses (units near
  each other fight better); dominant in a straight slugfest. *Disadvantage:* slow
  units and slow tech; weak air; out-maneuvered. Economy: overwhelm with numbers.
- **Guerrilla faction** — *Advantage:* cheapest units, stealth/ambush, salvages
  wreckage into upgrades, rebuilds fast, tunnels/relocation. *Disadvantage:*
  fragile units, no real air force, loses stand-up fights. Economy: raid, harass,
  never trade evenly.

The triangle: High-Tech beats Mass in the air and late; Mass beats Guerrilla in a
brawl; Guerrilla beats High-Tech by denying the slow expensive economy time to
come online. Express each identity as **concrete multipliers + one unique
mechanic**, not flavor text:
```js
FACTION_MODS = {
  hitech:    { costMul:1.20, buildMul:1.15, airBonus:1.15, unique:'spyDrone' },
  mass:      { costMul:0.85, hpMul:1.15, spMul:0.90, hordeBonus:0.15, unique:'hordeAura' },
  guerrilla: { costMul:0.70, hpMul:0.80, stealth:true, salvage:0.25, unique:'tunnelNet' },
};
```
Wire the mods into cost, build time, and the stat functions; implement each
`unique` as a small faction-only ability/building. Verify the triangle by playing
each matchup — if one faction wins every matchup at equal skill, adjust the mod
that most directly counters its win condition.

## 5. Tuning process
1. Set costs so same-role units across factions have comparable value, then apply
   faction mods.
2. Play (or sim) each of the 3 matchups; note who wins and why.
3. Adjust the *identity* mod, not random stats — if Mass loses to Guerrilla, the
   fix is horde/HP or Guerrilla fragility, not a global tweak.
4. Watch for degenerate strategies (one unit spammed). Give it a hard counter or
   raise its cost/pop.
5. Re-check after every new unit — units interact multiplicatively.
