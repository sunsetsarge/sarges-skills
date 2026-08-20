# Verification — proving the asset actually works

The recurring failure in asset work is not a bad asset; it is a bad asset that
everyone believed was good. Three habits prevent almost all of it.

## 1. Look at your own output

You are vision-capable. Generate the contact sheet and **read the image**. Do not
infer correctness from frame counts, file sizes, or the absence of an exception —
none of them can see a halo, a turntable, or a character facing backwards.

Look at the right artefact at the right stage:

| Question | Artefact |
|---|---|
| Is this row an animation or a camera turntable? | every frame of the row, with indices |
| Which way does the source art face? | one big labelled crop per character |
| Did packing introduce halos / baseline drift? | the **packed** output, zoomed, on a dark checkerboard, ground line drawn |
| Does the camera angle match the motion? | a montage of 3–4 candidate angles side by side |

## 2. Prove it in the engine, at real size

A validator page that plays **every animation in the manifest over HTTP through the
real loader** catches what a contact sheet cannot: bad paths, failed decodes, empty
animations. Expose a machine-readable result so a headless run can gate on it:

```js
window.__ANIM_RESULT__ = { sheets, animations, missing: [], empty: 0 };
```

Then screenshot the running game at the true device resolution — 390×844 at DPR 2 for
a portrait phone — not a desktop window. Density and legibility problems only appear
at real size.

**Watch for stale frames.** If you stop the game loop to take deterministic
screenshots, nothing is calling `render()` any more, so every shot after the first
silently captures the same frame. This happened on the reference project: the
screenshots looked entirely plausible and were worthless. Drive `render()` explicitly
after stepping, and sanity-check that shots differ.

## 3. Have a different model judge it

Self-review misses defects, and a subagent's prose claim that something worked is not
evidence — subagents will report detailed, confident, wrong findings. The loop that
works:

1. Save the running game's canvas to a PNG on disk.
2. Spawn an agent on a **different model** with explicit acceptance criteria.
3. Require PASS/FAIL plus specific defects with coordinates.

Make the critic harsh — tell it "acceptable" is a failing grade and the bar is "a
player would screenshot this". A polite critic is useless.

**Triage what comes back.** Harsh critics generate real findings *and* confident
misreads. On the reference project one critic flagged "reward cards bleeding off the
right edge" that were actually gate sprites scrolling into view, and "the HUD lagging
the sprite" that was a state word being mistaken for a form name. Fix the real ones,
discard the misreads, and note which is which so the next round does not re-litigate.
Cap iterations (about 6 per item); a logged known-issue beats an infinite polish loop.

## What to hand back

- Contact sheets you have personally looked at.
- A validator result with a pass/fail exit code.
- Screenshots at true device size.
- A short note of what you decided without asking, and why.
