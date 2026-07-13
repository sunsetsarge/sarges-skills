# Audio & Visual Style Reference

Fully synthesized chiptune audio (Web Audio API) and palette-limited pixel
rendering. Nothing is loaded from disk or network — no soundfonts, no sampled
files, no image assets. Everything is owned outright.

## AUDIO

### 1. Synth voice architecture

One `AudioContext`, created lazily on first user input (browsers block
autoplay — wire `resume()` to the title-screen keypress). Master chain:

```
voice osc(s) -> per-voice gain (ADSR) -> channel gain -> master gain -> destination
```

Four channel roles, mirroring the SNES-era feel:

| channel | waveform | role |
|---|---|---|
| lead | `square` | melody |
| harmony | `triangle` | counter-melody / chords (arpeggiated) |
| bass | `triangle` or `sawtooth` at −1/−2 octaves | bassline |
| noise | buffer of `Math.random()*2-1` samples | percussion / hits |

### 2. ADSR envelope

```js
function adsr(gain, t, {a=0.01, d=0.06, s=0.5, r=0.12, peak=0.4}) {
  const g = gain.gain;
  g.setValueAtTime(0, t);
  g.linearRampToValueAtTime(peak, t + a);
  g.linearRampToValueAtTime(peak * s, t + a + d);
  return (stopT) => { g.setValueAtTime(peak * s, stopT);
                      g.linearRampToValueAtTime(0, stopT + r); };
}
```

Always release-ramp to 0 before calling `osc.stop()` — hard stops click.
Plucky lead: a=0.005, d=0.08, s=0.2. Pad/harmony: a=0.05, s=0.7.

### 3. Sequencer

Notes as data: `[midiNote, startBeat, lengthBeats]` per channel, looped
per-track with `bpm` and `loopBeats`. Schedule ahead with the standard
two-clock pattern: a `setInterval(25ms)` lookahead that schedules every note
falling in the next 100ms window at exact `audioContext.currentTime`-based
times. Never schedule note-by-note with `setTimeout` — it drifts audibly.

`freq = 440 * 2 ** ((midi - 69) / 12)`.

### 4. Required tracks (write original melodies — never transcribe existing game music)

| track | character | tips |
|---|---|---|
| `bgm_title` | stately, slow (72–84 bpm) | long pad notes, sparse lead, major key |
| `bgm_overworld` | striding, hopeful (100–120 bpm) | 8–16 bar loop, walking bass on roots+fifths |
| `bgm_battle` | driving (140–160 bpm) | ostinato bass eighth-notes, minor key, short loop (8 bars) is fine |
| `bgm_victory` | fanfare, PLAYS ONCE | 2–3 s rising figure then resolution; field music resumes after |
| `bgm_dungeon1` | tense, sparse (80–100 bpm) | minor/diminished, noise-channel heartbeat |

Composition shortcut that reliably sounds "16-bit JRPG": pick a key, write a
4-note bass ostinato, put the lead on the pentatonic of that key with one
accidental for color, arpeggiate the harmony channel in triplets or eighths.

### 5. SFX recipes (each ≤ 0.3 s, fire-and-forget voices)

| sfx | recipe |
|---|---|
| menu blip | square 880 Hz, 40 ms, sharp ADSR |
| confirm | square 660→990 Hz two-step, 90 ms |
| cancel | square 440→330 Hz down-step, 90 ms |
| hit | noise burst 80 ms + triangle 110 Hz thump |
| miss | triangle 500→200 Hz slide (`exponentialRampToValueAtTime`), 120 ms |
| spell cast | saw 300→1200 Hz sweep, 200 ms, light detune (2 osc, ±4 cents) |
| heal | triangle arpeggio C-E-G-C upward, 60 ms per note |
| level up | square arpeggio 1-3-5-8-5-8, 300 ms total |
| encounter swirl | saw 200→800→200 Hz over 400 ms + noise swell |

### 6. Music director (one owner — SKILL.md rule 24)

Single module with `play(trackId)`, `stopAll()`, `duck(frac)`. It crossfades
(~300 ms via channel gains) on track change, refuses redundant `play` of the
already-playing track, and exposes `playOnce(trackId, onEnd)` for the victory
fanfare — the battle→field handoff calls `playOnce("bgm_victory", () =>
play(fieldTrack))`. Config menu volume sliders write the channel gains.

## VISUALS

### 7. Resolution & scaling

Logical canvas 240×160 up to 480×270; scale up integer-multiple to fit the
window (`canvas.style.imageRendering = "pixelated"`, and set
`ctx.imageSmoothingEnabled = false`). Draw everything at logical resolution;
never draw at display resolution — subpixel positions destroy the aesthetic.
Snap camera and sprite positions to integers at draw time.

### 8. Palette discipline (SKILL.md rule 25)

Define 16–32 named colors ONCE, grouped in banks:

```js
const PAL = {
  ui:      ["#10141f", "#2a2f4e", "#5b6ee1", "#f0f0e8"],
  field_v: ["#1a3b2a", "#2e6e41", "#7fb069", "#d8e3c3", "..."],   // verdant epoch
  field_s: ["#3b2a1a", "#6e412e", "#b0697f", "#e3c3d8", "..."],   // sundered epoch
  sprites: ["#000000", "#f4d6b0", "#8a4b2d", "#3866c8", "..."]
};
```

Every draw call indexes PAL — zero ad-hoc hex literals in rendering code. The
epoch flip (SKILL.md rule 17) swaps `field_v` → `field_s` and instantly makes
the whole world read as changed, nearly for free.

Classic 16-bit color tricks: shade with hue-shift (shadows toward blue/purple,
not just darker); 3–4 shades per material; pure black outlines on sprites but
NOT on tiles.

### 9. Sprites without image files

This skill's default is hand-coded, not generated — small enough sprites
(16×24-ish) that a human-editable, diffable, zero-dependency palette-index
string beats a PNG pipeline for this genre's normal scope. If the design
calls for something outside that scope (richer battle/dialogue portraits,
a title screen, box art — real illustrated pixel art rather than tiny
in-engine sprites), the `pixel-art-studio` skill is the tool: it owns
ComfyUI's pixel-art generation lanes plus a grid-snap/quantize verification
pass. Its PNG output doesn't auto-convert into the palette-index-string
format below — that'd need a manual extract-palette-and-re-index pass —
so reach for it for standalone art assets, not as a drop-in replacement for
this section's sprite-authoring approach.

Encode sprites as palette-index strings, one char per pixel, exactly like map
layouts — human-editable and diffable:

```js
const SPRITES = {
  brannic_d0: [   // 16x24, facing down, frame 0; "." = transparent
    "......0000......",
    ".....011110.....",
    // ... 24 rows
  ]
};
```

Blit each sprite once to an offscreen canvas at load, then `drawImage` from
the cache — never per-pixel `fillRect` in the frame loop.

- Character sheets: 4 directions × 2-frame walk cycle minimum (mirror left
  from right to halve authoring); 3–4 frames if budget allows. Battle poses:
  idle / act / hurt / KO — 4 more frames.
- Alternate palettes (recolored enemies, epoch variants) come free: re-blit
  the same index data against a different bank.
- Vector-drawn fallback first (colored rounded rects with a facing tick) so
  the game is playable before any pixel art exists — art is a polish phase.

### 10. Tiles & layers

16×16 tiles blitted from the same offscreen-cache approach. Draw order:
ground layer → objects/NPC/party sprites sorted by Y (painter's algorithm) →
overhang layer (tree tops, arch tops) → weather/fx → UI. A 2–4 frame global
animation ticker (~250 ms) drives water/lava tile cycling.

### 11. Battle scene layout

Side-view: enemies on the left third, party in a right-side column, each
member's row position offset by front/back row. Bottom: the command window +
a party status strip (name, HP, MP, ATB bar). ATB bars fill left→right and
flash when ready. Damage numbers float up from the target and fade (white
physical, colored by element for magic, green for heals).

### 12. UI chrome

One window-frame routine used EVERYWHERE (menus, dialogue, shops): dark
gradient fill from `PAL.ui`, 2 px light border, 1 px inner shadow line,
rounded corners optional. Cursor is a small pointing chevron that steps (not
slides) between entries, with the menu-blip SFX on every move (rule 19
debounce keeps this from machine-gunning). Text: 8 px monospace bitmap-style
font — `ctx.fillText` with a web-safe monospace at integer positions is
acceptable; a hand-drawn 5×7 pixel font from index strings is the deluxe
option.
