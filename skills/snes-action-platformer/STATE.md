# STATE — snes-action-platformer skill

Updated: 2026-07-07 (session-handoff wrap)
Status: SHIPPED (v1.0.0; eval loop pending)
Phase: no formal plan — single-session build complete

## NEXT ACTION
Run the skill-creator eval loop on `snes-action-platformer` (baseline vs with-skill, like clone-forge's eval-1), OR use it live: apply it to Bounty Hunter X's Phase 1.6 feel-review gate as its first real-world validation.

## BLAINE GATES
- [ ] None for the skill itself. First-game validation naturally waits on the Bounty Hunter X pause-tween decision / Phase 2 sprite-tool purchase (see that project's ledger).

## KEY PATHS & FACTS
- Skill: `C:\Claude\sarges-skills\skills\snes-action-platformer` (34 files, ~3,030 lines)
- Installed: junction `~\.claude\skills\snes-action-platformer` → repo folder (verified live-triggering 2026-07-07)
- Repo: github sunsetsarge/sarges-skills @3915cdb (pushed)
- Layering contract: `references/design/` is engine-agnostic — a future `references/html5/` layer must not touch it
- Canonical tunables (must stay in sync across all files): gravity 900, walk 90, dash 210/0.35s, jump −330, cut ×0.45, coyote 0.08s, buffer 0.10s, i-frames 1.0s, charge 0.55/1.1s

## DONE (verified this session, 2026-07-07)
- All 34 files exist on disk; every SKILL.md pointer resolves (scripted link check); SKILL.md = 149 lines
- Deep spot-checks passed: game-feel.md (tunables + dash-off-ledge rules), gotchas.md (16 entries), player_controller.gd (516-line typed FSM), mechanics.md weakness 8-cycle
- Committed @3915cdb + pushed; junction created and skill registered in the live session skill list
- Trigger sanity check: all 3 test prompts fire on the description

## UNVERIFIED
- GDScript templates reviewed by eye only — not yet parsed by an actual Godot 4.3 editor (do this on first use)

## DECISIONS
- 2026-07-07 Mover default = constrained CharacterBody2D (velocity set explicitly, floor snap, raycast wall checks), custom move_and_collide documented as the precision alternative — pragmatic default, honest tradeoff
- 2026-07-07 Dash-expires-mid-air rule = decay to walk speed over 2–4 ticks (not instant clamp, not permanent carry)
- 2026-07-07 Weakness cycle uses original archetypes Flame→Frost→Storm→Volt→Stone→Toxin→Blade→Gravity→Flame; games retheme, never copy a real chart

## Session log
| Date | Model | What happened (1 line) | Confluence ver |
|---|---|---|---|
| 2026-07-07 | Fable 5 (plan/judge) + Sonnet ×3 (author) | Built, validated, committed, pushed, junctioned the full skill; Godot subagent stalled twice on phantom delegation — fixed with blunt resume | v1 (new p.83558401) |
