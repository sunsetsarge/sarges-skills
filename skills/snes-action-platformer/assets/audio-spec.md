# Audio Spec — SPC-Style Chiptune/Sampled Hybrid

The target character is **Super Nintendo's S-SMP/SPC700 sound**: a hybrid of synthesized chiptune waveforms and short, low-bitrate sampled instruments (plucked bass, brass stabs, gated drum hits), run through a shared hardware echo/reverb unit, with a **hard 8-voice polyphony ceiling**. This spec exists so music and SFX authored for the game sit in that sonic space rather than drifting into modern full-orchestra or generic synthwave territory, and so nothing gets built that can't actually be mixed live in Godot's audio bus system.

## Character discipline

- **~8 simultaneous voice budget.** The real SNES S-DSP has 8 hardware voices total, shared across music and every sound effect. You are not hard-limited to 8 tracks in a modern engine, but **compose and mix as if you were** — dense, cluttered layering (12+ simultaneous elements) reads as generically "epic" rather than SNES-authentic, and also risks the modern-equivalent problem of masking SFX under music (see Mixing rules below). A typical SNES-era stage theme uses ~4-6 voices for music (bass, chord/pad, lead melody, counter-melody or arpeggio, percussion, occasional stab), leaving 2-4 voices of headroom for SFX layering during combat.
- **Short, looped samples, not long one-shots.** Instrument samples (plucked bass pluck, brass stab, marimba pluck, drum hit) should be short (typically well under 1 second for one-shot instrument hits) with the SPC700's native looping used to sustain notes rather than recording a long natural sustain/decay. This is the specific technique that gives SNES music its slightly "clipped"/tight rhythmic character versus a modern sample-library sustain.
- **Characteristic echo, used sparingly and consistently.** The signature SPC700 echo is a short-delay, feedback-heavy, slightly lo-fi repeat (not a long ambient reverb tail). Apply one echo bus setting per music track (not per-instrument custom reverb), tuned once and reused, so the whole soundtrack shares a consistent "room."

## Music needed per scene

| Scene | Notes |
|---|---|
| Title screen | Establishes the game's melodic identity — the theme most likely to get reprised/remixed elsewhere (final boss, credits). |
| Stage select | Menu-loop, energetic but non-fatiguing since the player may sit on this screen deliberating for a while; typically a shorter, more percussion-forward loop than a stage theme. |
| Intro stage | Distinct from the 8 selectable stages — often more subdued/serious in tone since it establishes plot stakes before the player has any weapon options (buster-only). |
| 8 stage themes | One per selectable stage, **mood-matched to that stage's gimmick** (see `checklists/new-stage.md` for gimmick config) — e.g., an ice-gimmick stage skews toward sparse/crystalline instrumentation and a slower tempo feel, a fire-gimmick stage skews toward driving percussion and a brighter/hotter timbre, a storm/electric stage skews toward dissonant stabs and irregular rhythm accents. Mismatched mood-to-gimmick (upbeat music over a slow, methodical hazard stage) is a common and avoidable authenticity miss. |
| Boss theme | One shared theme for regular bosses (or per-boss if budget allows), higher tempo/intensity than any stage theme, built to loop cleanly since boss fights have variable length. |
| Final stage(s) / final boss themes | Distinct final-stretch identity, often referencing/remixing the title theme motif — this callback is a genre convention worth deliberately building toward, not accidental. |

## Required jingle set

Short, non-looping stingers. These are easy to under-scope — treat every one as required, not optional polish, since their absence is immediately felt (a boss defeat with no fanfare feels unfinished even if the gameplay is complete).

| Jingle | Target length | Notes |
|---|---|---|
| Stage-select confirm | ~2s | Plays on committing to a stage from the select screen; upbeat, forward-motion feel. |
| Get-weapon fanfare | 4-6s | Plays on boss defeat when the reward weapon is granted (see `checklists/new-boss.md`); this is one of the genre's most iconic jingle moments — give it real melodic weight, not a generic "success chime." |
| Boss-intro sting | ~3s | Plays as the boss door/arena intro sequence resolves into the fight starting (see `checklists/new-boss.md`); should land right as player control is handed back. |
| Checkpoint | ~1s | Very short, low-intrusion acknowledgment — this fires often, so it must not become annoying on repeat. |
| Death | ~2s | Distinct descending/negative motif, pairs with the death-burst sprite animation (see `assets/spritesheet-spec.md`). |
| Game-over | ~4s | Plays only after all lives/continues are exhausted (distinct from the per-death jingle above) — more final/somber than the per-death stinger. |
| Victory / stage-clear | ~5s | Plays after a stage's clear condition (typically boss defeat) resolves; celebratory, longer than the get-weapon fanfare since it can also carry a results/summary screen. |

## SFX list

| SFX | Notes |
|---|---|
| Jump | Short, bright, un-pitched-percussive or brief upward pitch-bend blip — this fires constantly, keep it cheap and non-fatiguing. |
| Dash | Distinct "whoosh"/burst character, ideally layered with the dash-dust sprite cue (see spritesheet spec) for a combined audio-visual read. |
| Land | Subtle thud, must not compete with jump/dash SFX volume since all three can cluster in rapid platforming sequences. |
| Buster shot x3 (per charge tier) | Uncharged: small/quick pop. Lv2 charge: fuller, slightly longer tone. Lv3 charge: biggest, most distinct timbre — the charge-tier SFX ladder should be audibly distinguishable with eyes closed, since charge tier changes gameplay risk (see `game-feel.md`) and players rely on the audio cue as much as the visual aura. |
| Charge loop | Rising-pitch or building-texture loop that plays while the charge button is held, distinct from the release-shot SFX; must loop seamlessly since hold duration is player-controlled (see charge tiers: tap/0.55s/1.1s). |
| Hits (player-taken, enemy-taken) | Two distinct hit SFX — player-taken hit should read as more alarming/negative than enemy-taken hit, reinforcing which side just took damage without needing to look at HP bars. |
| Enemy pops/deaths | Small enemies: quick, satisfying pop-and-gone. Larger enemies/mini-bosses: more substantial destruction SFX layered with their death animation. |
| Menu (move/confirm/cancel/error) | Standard menu-navigation SFX set — cheap to author, but missing "error" (e.g., trying to select a locked stage) is a common gap; include it explicitly. |

## Tooling suggestions

- **Trackers**: Furnace or OpenMPT are the practical modern tools for authoring genuinely SPC700-flavored music — Furnace has a native SNES/S-DSP emulation chip mode, which is the most direct path to authentic echo/sample-based sound without hand-simulating it in a DAW.
- **Synthesized alternative**: free SNES-style soundfonts (SF2 packs modeled on SNES instrument samples) loaded into a standard DAW or a soundfont player are a viable lower-effort path if a tracker workflow isn't practical — the key requirement is still short/looped samples and the 8-voice discipline above, not the specific tool.
- Either path: **export stems as short loop-pointed audio, not one long rendered pass**, so the loop point survives into the engine import step below.

## Godot import settings

- **SFX -> WAV.** Uncompressed, short one-shots; WAV avoids compression-artifact smearing on percussive transients and decoding overhead is negligible for short files.
- **Music -> OGG Vorbis with explicit loop points.** Set the loop start/end sample markers on import (Godot's `AudioStreamOggVorbis` supports loop metadata) so stage themes and the title loop seamlessly rather than hard-cutting and restarting — a hard restart every loop is one of the fastest ways to make a soundtrack feel cheap. Verify the loop point lands on a musically clean bar boundary, not just "wherever the render happened to end."
- Keep jingles as **non-looping OGG or WAV** (short enough that compression savings from OGG are marginal; WAV is fine too) — do not accidentally mark a one-shot jingle as looping in the import settings, or it will replay itself.

## Mixing rules

- **Music sits ~6dB under SFX** in the default mix (music bus gain reduced relative to SFX bus, or SFX bus boosted relative to music — same effect, pick one convention and hold it). This ensures combat feedback (hits, shots, charge state) always reads clearly over the music bed, which matters more for gameplay-critical audio (e.g., hearing your own hit-taken SFX to register damage) than for pure ambiance.
- **No sidechain ducking, keep it simple.** Do not build a dynamic sidechain/ducking system where SFX triggers automatically attenuate music — this is unnecessary complexity for the genre and can introduce audible pumping artifacts. A static, pre-balanced gain relationship (the -6dB rule above) achieves the same practical goal (SFX audibility) with zero runtime signal-processing risk and is period-authentic (the SNES itself has no such dynamic mixing).
- Route all music through **one shared bus** and all SFX through a **second shared bus**, each with independent volume sliders exposed in the options menu — this is both a mixing-rules matter and a baseline accessibility/user-preference requirement.
