# Authenticity and IP

Practical guardrails, not legal theory — enough to build confidently without accidentally shipping something that gets pulled down.

## What's safe to copy: mechanics and systems

**Game mechanics and systems are not copyrightable.** The dash, wall-jump, coyote time, jump buffering, charge-buster tiers, a weakness chart structured as a directed cycle, the boss-intro ritual (door shutter, name splash, health-bar fill), stage-select structure, heart tanks, sub-tanks, ride armor — all of these are *systems*, and modeling them after the Mega Man X mold is exactly the point of this skill. Analyzing a specific existing game's systems as a reference model and reimplementing that system design in an original game is standard, legal, and how the genre itself has always evolved (every SNES-era action-platformer borrowed structurally from the ones before it).

This is true regardless of how closely the *system* resembles the source of inspiration — a weakness chart with 8 nodes in a directed cycle is a structure, not an expression, and structures aren't protected.

## What's never safe to copy: expression

Copyright protects the specific creative *expression* — the actual art, character designs, music, names, and text — not the underlying system. Every game built from this skill must use entirely original:

- **Character and boss names** — never reuse names from any existing game (including any example archetype names used for illustration in this skill's own docs, such as the Frost/Flame/Storm/Volt/Stone/Toxin/Blade/Gravity template in `mechanics.md` — those exist to demonstrate the *cycle structure*, not as a name set to ship).
- **Sprites and character art** — draw/generate original art. Never trace, edit, or repackage sprite rips from an existing game, and never generate art through a process that reproduces a specific existing character's design.
- **Music** — compose or generate original music (see `snes-authenticity.md` for the target SPC-style sound). Never reuse, sample, or closely imitate a specific existing game's actual compositions.
- **Story and text** — original story, dialogue, and flavor text throughout.

## Marketing

Don't market a project built from this skill using another company's trademarks — most notably, never put "Mega Man" (or any other existing franchise name this genre draws from) in a title, subtitle, store page, tags, or marketing copy, even as a comparison ("Mega Man X clone," "in the style of Mega Man"). Describe the game by its own original genre positioning instead ("classic-style run-and-gun action platformer," "8-boss select action game") rather than by naming the trademark it was modeled on.

## Pre-ship checklist

Run through this before publishing/releasing a game built from this skill:

1. **Names**: every character, boss, weapon, and location name is original — none reused from any existing franchise, including this skill's own illustrative examples.
2. **Art**: every sprite, background, and UI asset is original creation (drawn, generated, or licensed-original) — none traced, ripped, or derived from existing game assets.
3. **Music**: every track and jingle is original composition — none sampled, reused, or closely imitative of a specific existing soundtrack.
4. **Store page / marketing copy**: no competing franchise's trademarked names appear anywhere in the title, description, tags, or promotional material.
5. **Systems check (informational, not a blocker)**: confirm the *systems* borrowed (dash-jump, weakness cycle, etc.) are implemented as this skill's original-content versions (e.g., the project's own themed weakness cycle, not a reskinned copy of any specific existing game's actual chart) — this isn't a legal requirement since systems aren't protectable, but keeping systems reskinned rather than 1:1 named-copies is good practice for the project reading as its own game rather than a reskin.
6. **Final gut check**: could a screenshot of this game, with names/art/music as shipped, be mistaken for a screenshot of a specific existing game? If yes, revisit whichever asset category is causing that impression before shipping.
