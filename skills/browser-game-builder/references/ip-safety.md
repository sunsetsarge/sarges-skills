# Shipping Legally: Clones, Re-skins, Packaging

Building a clone of an existing game to learn the mechanics is fine. Selling or
store-listing it while it still wears another game's identity is not. This is the
difference between "inspired by" and "infringing," and it's very fixable.

> Not legal advice — general guidance. For a real commercial launch, have a
> lawyer glance at your final names/art.

## What's free vs protected
- **Free to use (not copyrightable):** game *mechanics, rules, systems* — RTS
  base-building, harvester economies, rock-paper-scissors armies, veterancy,
  fog of war, the tech tree structure. There are a hundred RTS games because the
  genre itself is open. Clone the systems freely.
- **Protected (do not copy):** the game's *name and logo*; *faction names*;
  *unit/character/building names*; *story, dialogue, voice lines*; and *art* that
  copies specific protected designs. Also watch **real-world trademarks** used as
  unit names (e.g. real military vehicle/manufacturer names) and real insignia/flags.

So: keep the gameplay identical, replace every proper noun and any art that's a
recognizable copy. The result is a legitimately original game.

## The re-skin workflow
Develop under familiar names (readable, easier to reason about), then apply an
original identity as a **mechanical find-replace late in the project** so it's a
one-shot pass and doesn't slow development.

1. **Invent an original identity:** a new game title, and 3 original faction names
   with their own flavor (keep the asymmetry roles from balance-and-factions.md —
   only the names/skin change). Rename every unit and building to original names.
2. **Write `RESKIN_MAP.md`:** an exhaustive old→new table — factions, every unit
   key/display-name, every building, and all title/branding strings. Include a
   grep-able acceptance gate: *"after the pass, `grep -iE '<old trademarks>'` over
   the source returns zero hits (outside code comments)."*
3. **Apply it:** rename display strings and, if you want cleanliness, the internal
   keys + sprite filenames too (or keep internal keys and only swap display names —
   less churn, still legally sufficient since keys aren't user-visible).
4. **Art check:** make sure no sprite is a trace/copy of a protected design and no
   real logo/flag appears. Generated-from-scratch art in a generic military style
   is fine.
5. **Audio check:** synth SFX are clean by construction; any sourced music must be
   royalty-free/CC0 with credit.
6. **Verify:** run the grep gate; play once to catch stray strings in UI/tooltips.

Keep the re-skin **optional and deferred** if the build is personal/portfolio only
— but it is **mandatory before taking any payment or submitting to a store.**

## Packaging for distribution
The single HTML file is already a website. To go further:

- **Web / PWA (do this first):** add a `manifest.json` + a service worker so it's
  installable and works offline; host on any static host. This is the whole
  product for a web launch and the base for the app wrappers.
- **Google Play:** wrap the PWA as a **TWA** (Trusted Web Activity) via Bubblewrap,
  or use Capacitor. Straightforward; Android is the friendlier first store.
- **iOS / App Store:** wrap with Capacitor/Cordova. Higher friction — needs a Mac +
  Xcode + paid Apple Developer account, and Apple guideline 4.2 ("minimum
  functionality") sometimes rejects thin web wrappers, so add native-feeling polish
  (proper icons/splash, no browser chrome, offline). Often worth deferring past the
  web + Play launch.

## Monetization models that fit a browser game
Cosmetic-only or non-pay-to-win to keep store review + players happy: one-time
unlock/premium version, non-intrusive ads (rewarded/interstitial between matches),
cosmetic skins, or a "supporter" tier. Decide this before store submission because
it affects the listing and the review.

## Honest expectation
A finishing pass gets you a **polished, original-IP, single-player skirmish RTS** —
genuinely shippable. It does **not** get you the original's full content breadth
(campaign, hero powers, online multiplayer). Put those in a clearly-labeled
"Parity Backlog (post-ship)" so the scope stays honest and the first release
actually ships instead of chasing parity forever.
