# Godot 4.3+ Project Setup for SNES-Style Action Platformers

Pixel-perfect, deterministic, MMX-feel project configuration. Every setting below has a concrete why, not just a where. Confirm exact menu paths and property names against your installed Godot version — the editor UI and some property names have shifted across 4.0 -> 4.3+ point releases.

## Table of Contents

- [Viewport vs Window Size](#viewport-vs-window-size)
- [Stretch Mode and Aspect](#stretch-mode-and-aspect)
- [Texture Filtering](#texture-filtering)
- [2D Pixel Snapping](#2d-pixel-snapping)
- [Physics Tick Rate and _physics_process](#physics-tick-rate-and-_physics_process)
- [InputMap Actions](#inputmap-actions)
- [Autoload Singletons](#autoload-singletons)
- [Collision Layers and Masks](#collision-layers-and-masks)
- [Windows Export Notes](#windows-export-notes)
- [Quickstart: Playable Core in One Sitting](#quickstart-playable-core-in-one-sitting)

## Viewport vs Window Size

Project Settings > Display > Window > Size > **Viewport Width/Height**: set to `256 x 224`. This is the SNES-authentic internal render resolution — every pixel-art asset you draw should be authored at this scale (1 sprite pixel = 1 viewport pixel).

Project Settings > Display > Window > Size > **Window Width/Height Override**: set to a clean integer multiple, e.g. `1024 x 896` (4x) or `1280 x 1120` (5x, closest to 1080p headroom). This is the actual OS window/monitor size the player sees.

Why two separate numbers: the viewport is the coordinate space your game logic and art live in (256x224 units). The window override is just the physical pixel size Godot scales that viewport up to for display. Confusing the two is the single most common cause of "why does my pixel art look wrong" — if you set the *window* to 256x224 you get a postage-stamp game on a modern monitor; if you draw art at window-native resolution you lose the SNES-authentic look and the integer-scaling benefits below.

## Stretch Mode and Aspect

Project Settings > Display > Window > Stretch:
- **Mode**: `viewport`
- **Aspect**: `integer`

Why `viewport` mode: it renders your whole scene at the 256x224 viewport resolution first, then scales that finished image up to fill the window. This is what lets low-res pixel art stay crisp — you are scaling a raster image by a whole number, not asking the 3D/2D renderer to draw individual sprites at fractional in-between sizes.

Why `integer` aspect specifically: `expand` or fractional stretching will scale the 256x224 image by a non-whole-number factor whenever the window size isn't an exact multiple (e.g. a user resizes to 1000x860). A 1.9x or 3.3x scale factor forces the GPU to interpolate between source pixels, which blurs hard pixel edges and produces visible shimmer/wobble as the camera or sprites move, because different source pixels contribute different amounts to each destination pixel from frame to frame. `integer` aspect clamps the scale factor to whole numbers (1x, 2x, 3x, 4x...) and pillarboxes/letterboxes any leftover space instead of stretching into it. Every destination pixel then maps to exactly one source pixel, at a fixed ratio, every frame — no shimmer, no sub-pixel blending.

## Texture Filtering

Project Settings > Rendering > Textures > Canvas Textures > **Default Texture Filter**: set to `Nearest`.

Why not `Linear` (the default): Linear filtering blends neighboring texel colors when a texture is displayed at a non-1:1 size, which is exactly what you want for photographic textures but actively destroys pixel art — it turns your crisp 1px black outline into a 2-3px gray gradient. Nearest filtering picks the single nearest source texel with no blending, preserving hard pixel edges at any integer scale.

If you ever import an individual texture that needs different behavior (e.g. a soft-edged particle or a UI blur effect), override it per-resource in the Import dock rather than changing the project default.

## 2D Pixel Snapping

Project Settings > Rendering > 2D > Snap:
- **Snap 2D Transforms to Pixel**: `On`
- **Snap 2D Vertices to Pixel**: `On`

What this fixes: without these, a Node2D's global position (and by extension anything parented under it, like sprites following a smoothly-interpolated camera or a physics body moving at sub-integer speeds) can end up sitting at a fractional pixel coordinate, e.g. `x = 142.37`. Combined with nearest-neighbor filtering, that fractional position causes the rendered sprite to visibly jitter/shimmer by a pixel as it crosses integer boundaries frame to frame, because the renderer has to decide which whole pixel to snap to and that decision flips as the fractional part crosses 0.5. Turning these two snaps on forces the renderer to round transforms and vertices to whole pixels before drawing, eliminating that jitter. This matters most for camera-followed sprites and anything with `position_smoothing_enabled` on a Camera2D, or physics-driven characters moving at non-integer px/s.

## Physics Tick Rate and _physics_process

Project Settings > Physics > Common > **Physics Ticks per Second**: set to `60` (this is Godot's default, but verify it — some templates change it). Equivalent to `Engine.physics_ticks_per_second = 60` if you ever need to read/set it from code.

**Hard rule: all game logic — movement, timers, state machine transitions, input polling for anything gameplay-affecting — lives in `_physics_process(delta)`, never in `_process(delta)`.**

Why: `_process(delta)` runs once per *rendered frame*, and frame rate varies with GPU load, vsync, monitor refresh rate, and background system load. If your jump arc, dash timer, or hitbox lifetime is computed in `_process`, the exact same input sequence produces different in-game results depending on how fast the machine happens to be rendering that session — a coyote-time window of "0.08 seconds" becomes "0.08 seconds, or is it 4 frames at 50fps vs 5 frames at 60fps" and replay/speedrun determinism breaks entirely. `_physics_process(delta)` runs at the fixed rate configured above (60 times per second, `delta` a constant ~0.01667), decoupled from render fps — the same inputs always produce the same physics outcome regardless of display performance. Only put rendering-only cosmetic work (particle emission timing that doesn't affect gameplay, purely visual camera shake juice) in `_process`.

## InputMap Actions

Project Settings > Input Map. Create these actions with the concrete bindings below. Pick one face-button convention and use it consistently across every doc/template in this skill (this skill uses **shoot = J / gamepad B/Circle**, matching classic run-and-gun face-button layout where the primary attack sits under the dominant thumb, not the jump button).

| Action | Keyboard | Gamepad |
|---|---|---|
| `move_left` | A, Left Arrow | D-pad Left, Left Stick Left |
| `move_right` | D, Right Arrow | D-pad Right, Left Stick Right |
| `move_up` | W, Up Arrow | D-pad Up, Left Stick Up |
| `move_down` | S, Down Arrow | D-pad Down, Left Stick Down |
| `jump` | Space | Gamepad A / Cross (bottom face button) |
| `dash` | Shift | Gamepad X / Square (left face button), or a shoulder button (L1/LB) if you want dash on a dedicated trigger finger |
| `shoot` | J | Gamepad B / Circle (right face button) |
| `weapon_next` | E | Right shoulder (R1/RB) |
| `weapon_prev` | Q | Left shoulder (L1/LB) — if `dash` also uses a shoulder, move dash to a face button instead; don't double-bind a physical button to two actions |
| `pause` | Escape | Start / Options |

`move_up`/`move_down` exist even in a game without ladders yet because menus, cutscene skips, and future ladder/crouch mechanics all want a vertical axis already wired — cheaper to define it now than retrofit every menu script later.

## Autoload Singletons

Project Settings > Autoload. Add these four as Autoload (singleton) scripts. This section describes each one's **role** — see `data-resources.md` for how StageData reads WorldFlags, and the templates directory for actual gameplay scripts (these four autoloads are project-specific glue, not shipped as templates here).

| Autoload | Role |
|---|---|
| **GameState** | Holds the player's live run-time state: current HP, current equipped weapon id, per-weapon ammo counts, lives remaining, current stage/checkpoint id. This is the "what's true right now" blackboard that HUD, player controller, and stage-transition code all read/write. Cleared/reset on new game, NOT the same as SaveManager's persisted data (GameState can hold transient combat state SaveManager never touches, like current i-frame flags). |
| **SaveManager** | Owns serialize/deserialize of the save file (JSON or Godot `ConfigFile`/binary resource, your call) — reads GameState + WorldFlags into a save-file shape on `save_game()`, and populates GameState + WorldFlags from a loaded file on `load_game()`. Also tracks which checkpoint the player last touched so a death/reload resumes there instead of stage start. |
| **AudioManager** | Owns all music/SFX playback: crossfades between stage background tracks (e.g. fade out stage theme over ~1s while fading in boss theme when a boss door triggers), manages SFX playback through a dedicated audio bus (separate from music bus so a settings menu can independently slider-control SFX vs music volume), and handles ducking (temporarily lowering music volume under an important SFX or boss roar). |
| **WorldFlags** | A persistent dictionary of boolean/string flags representing save-independent "world state" — which bosses are defeated, which stage gimmicks/shortcuts are unlocked, which one-time cutscenes have played. StageData resources read WorldFlags at load time to decide which spawn-table entries are active and which tile/door variants to show (see `data-resources.md` for the `world_flags_required` / `world_flag_variants` mechanism). WorldFlags is serialized by SaveManager but is logically distinct from GameState because it represents the *world's* memory, not the *player's* live stats. |

## Collision Layers and Masks

Set these names in Project Settings > Layer Names > 2D Physics so the Inspector shows readable labels instead of "Layer 3". Use exactly this table across every scene in the project — consistency here is what makes the Hitbox/Hurtbox pattern in `combat.md` work without per-scene special-casing.

| Layer # | Name | What's placed on it | What it collides with (mask) |
|---|---|---|---|
| 1 | `world` | Ground, walls, static level geometry (TileMapLayer collision) | Everything solid: player, enemy, projectiles |
| 2 | `player` | The player's CharacterBody2D / Hurtbox | world, enemy (contact damage), enemy_attack, one_way, triggers |
| 3 | `player_attack` | Player Hitboxes (buster shots, melee swings) | enemy |
| 4 | `enemy` | Enemy CharacterBody2D / Hurtbox | world, player (contact damage), player_attack, one_way |
| 5 | `enemy_attack` | Enemy Hitboxes (projectiles, contact-damage areas) | player |
| 6 | `one_way` | One-way platform tiles (`TileMapLayer` with one-way collision enabled per-tile, or a dedicated `StaticBody2D`) | player, enemy (both can stand on / drop through) |
| 7 | `triggers` | Area2D room-lock zones, camera triggers, cutscene triggers, checkpoint zones | player only (usually — triggers rarely care about enemies) |

Note the asymmetry: `player` and `enemy` masks include each other for **contact damage** (a body-to-body Area2D touch), while `player_attack`/`enemy_attack` are separate layers so a projectile doesn't also apply contact damage rules or get blocked by the same masks as the character it came from — see `combat.md` for how Hitbox/Hurtbox scripts use this table.

## Windows Export Notes

1. **Export template**: Editor > Manage Export Templates > download/install the version matching your Godot editor version exactly (mismatched versions cause silent export failures or missing-feature errors).
2. **Embed PCK vs separate .pck**: Export dialog has an "Embed PCK" checkbox.
   - **Embed PCK on** (single `.exe`): simplest distribution — one file to hand a playtester or upload to itch.io. Slightly larger single binary, slightly slower to re-export during iteration since the whole exe gets rewritten each time.
   - **Embed PCK off** (`game.exe` + `game.pck` side by side): faster iterative export during development (only the `.pck` changes most of the time), and lets you patch content (swap the `.pck`) without touching the exe — useful for content-only hotfixes post-release. Use this during active development; switch to embedded for the final distributed build if you want single-file simplicity.
3. **GPU driver quirk (black screen / driver crash)**: Godot 4 defaults to the Vulkan / Forward+ renderer on Windows. On older or integrated GPUs (common on secondhand laptops, some office/library machines) this can produce a black screen on launch or an outright driver crash, because Forward+ assumes a reasonably modern Vulkan driver. If a playtester reports this, have them (or you, pre-emptively for known-low-spec targets) switch Project Settings > Rendering > **Renderer** > Rendering Method to **Compatibility** (the GL Compatibility / GLES3-equivalent backend). Compatibility mode is plenty for 2D pixel art — you are not using Forward+'s advanced 3D lighting features — and is dramatically more compatible across old/integrated/mobile GPUs. Consider shipping Compatibility as the project default for a 2D pixel-art game unless you specifically need a Forward+-only feature.

## Quickstart: Playable Core in One Sitting

Numbered, concrete, aimed at "movement feels right" being testable before you stop for the day.

1. **Project settings pass.** Apply every setting above in order: viewport 256x224, window override 1024x896 (or 1280x1120), stretch mode `viewport` + aspect `integer`, default texture filter `Nearest`, both 2D pixel-snap options on, physics ticks 60, InputMap actions from the table. This is ~15 minutes of checkbox-clicking and it's the foundation everything else sits on — don't skip ahead without it, because retrofitting pixel-snapping after you've built levels means re-checking every camera-follow scene.
2. **Add the 4 autoloads as empty scripts first.** Create `game_state.gd`, `save_manager.gd`, `audio_manager.gd`, `world_flags.gd`, each just `extends Node` with a one-line comment describing its role (copy from the table above). Register all four in Project Settings > Autoload. Building them empty first means every later script that does `GameState.something` or `WorldFlags.has(...)` has a real target to call into instead of erroring on a missing singleton — you'll flesh out their internals as you need specific fields, not all at once up front.
3. **Build a test room with TileMapLayer.** Create a new scene, root node `Node2D` named `TestRoom`. Add a `TileMapLayer` child, assign it a `TileSet` with one ground tile (any placeholder 16x16 or 32x32 pixel-art tile works), paint a flat ground strip plus a couple of ledges at different heights so you can test jump arcs. Set the TileMapLayer's collision layer to `world` (layer 1) per the table above.
4. **Drop in the player.** Add a `CharacterBody2D` node named `Player` under `TestRoom`, set its collision layer to `player` (2) and collision mask to `world, enemy, enemy_attack, one_way, triggers` per the table. Attach `player_controller.gd` (from `templates/`) to it. Give it a placeholder `Sprite2D` or `AnimatedSprite2D` child (even a colored rectangle texture is fine at this stage) and a `CollisionShape2D` sized to the sprite. Add a `Camera2D` as a child of Player (or a sibling that follows it), attach `camera_controller.gd` to it, and set it Current.
5. **Wire up shoot with a projectile pool.** Add a `ProjectilePool` node (attach `projectile_pool.gd`), point its exported `PackedScene` field at a minimal projectile scene (an `Area2D` root with `projectile.gd` attached, a `CollisionShape2D`, and a `Hitbox` child using `hitbox.gd`). In `player_controller.gd`'s shoot-input handling, call `ProjectilePool.acquire()` and set the returned instance's velocity/team/damage. At this point you can run the scene, walk, jump (with variable jump height via early-release), dash, wall-slide/wall-jump off the test ledges, and shoot — the full locomotion + combat input loop is testable in one sitting, before a single piece of real art or level design exists.
