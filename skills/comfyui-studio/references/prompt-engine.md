# The prompt-expansion engine

ChatGPT's image quality is only half model; the other half is that **an LLM rewrites the user's
rough ask into a rich, structured prompt before the image model ever sees it.** You (the calling
Claude session) are that LLM. Never pass a user's one-liner straight to the sampler.

## The expansion template

Take the user's request and expand it into full descriptive sentences covering, in roughly this order:

1. **Subject(s)** — who/what, with counts and distinguishing attributes bound explicitly to each
   subject ("the woman on the left wears a red apron", not "woman, red apron, left").
2. **Composition / layout** — where each element sits (left/center/right, foreground/background),
   camera framing (close-up / wide shot / bird's-eye).
3. **Lighting** — source, direction, temperature ("warm low golden-hour sun from the right, long shadows").
4. **Style / medium** — photograph, oil painting, screen-print poster, 3D render; era or artist-school if relevant.
5. **Camera / lens** (photo styles) — "shot on a 35mm lens, shallow depth of field". "Photograph"
   works better than "photorealistic".
6. **Mood / atmosphere** — one clause is enough.
7. **In-image text** — the exact string in double quotes, with placement:
   `Large bold red letters at the top read "GRAND OPENING".` Keep strings short; every extra word
   is another chance to garble.

Write it as 3–8 natural-language sentences. NOT tag-soup, NOT `(word:1.3)` weights, NOT a wall of
negatives — modern MMDiT/flow models (Qwen, Z-Image, FLUX) are trained on captions and follow prose.
Weight syntax and quality-tag spam are SDXL-era habits; on modern models they hurt.

## Worked example — lazy vs expanded

**User ask:** "make me a poster that says GRAND OPENING over a busy street market with three vendors"

**Lazy prompt (what NOT to send):**
> poster, GRAND OPENING, street market, three vendors, high quality, detailed, 8k

Typical result: wrong vendor count, garbled headline, generic clip-art look.

**Expanded prompt (what to send):**
> A vintage-style promotional poster for a street market. Large bold red block letters at the top
> read "GRAND OPENING". Below the headline, a bustling open-air market scene with exactly three
> vendor stalls under striped awnings: an older woman selling oranges on the left, a bearded man
> grilling skewers in the center, and a young woman selling flowers on the right. At the bottom,
> smaller dark text reads "SATURDAY 9 AM". Warm cream paper background, flat screen-print texture,
> limited retro color palette.

Same model, same settings — the expanded version binds attributes to the right vendor, renders the
headline legibly (on a Qwen-family model), and reads as a designed poster instead of a collage.

## Negative prompts — modern rules

- **Qwen / FLUX / Z-Image Turbo at CFG 1.0:** negatives are IGNORED (distilled guidance). Use
  `ConditioningZeroOut` and steer with the positive prompt instead ("clean anatomy, natural hands").
- **Z-Image Base / RedZimage at CFG ~4:** a short negative works: `3D render, CGI, illustration,
  blurry, low quality, watermark, text` (drop `text` if you WANT in-image text).
- **SDXL:** the old heavy-negative habit is still valid there — embeddings like `easynegative`,
  `ng_deepnegative` exist in the loras folder. Only cargo-cult negatives on SDXL, nowhere else.

## In-image text rules

1. Quote the literal string: `reads "OPEN 24 HOURS"`.
2. State the placement and typography: "large bold serif letters at the top".
3. Keep it under ~6 words per text block; split long copy across blocks.
4. Route to a **Qwen-Image** model — it is the open-weights leader for text. Z-Image handles short
   text; SDXL/SD1.5 cannot spell (compositing real type afterwards is the right answer there — see
   the `vintage-ad-generator` skill for that pipeline).
5. If text garbles: raise CFG toward 4–5 (non-lightning graph), simplify the string, or re-run —
   text has higher seed variance than composition.
