# Design principles

Craft guidance for writing the game itself, independent of engine mechanics. These are the rules
that separate a fair, enjoyable parser game from a frustrating one.

## Voice and tense

Write in **second person present tense**: "You are standing in a dim kitchen." / "The lamp
casts a warm glow." Never first person, never past tense narration. Room and object text should
read as if the player is there right now.

## Examinability

**Everything a description mentions must be examinable.** If a room description says "A heavy
wooden table sits in the middle of the room," a `table` object must exist with its own
`examine` text -- not just a phrase in the room's prose that the parser can't resolve as a
noun. The-cellar's kitchen mentions the table, rug, and barrel, and all three exist as real
objects. A player typing `examine table` after reading about one should never get "You can't
see any such thing."

The same applies transitively: if an object's `description` or `text` mentions another item by
name, that item should exist too, or the mention should be removed/reworded.

## Fair puzzles

- **Clue every puzzle in-world.** The solution should be discoverable from descriptions,
  examine text, or things the player has already picked up -- never from outside knowledge or a
  walkthrough.
- **Generous synonyms.** List every reasonable noun/verb synonym a player might type (`barrel`
  vs `flour barrel`, `key` vs `brass key`, `get`/`grab`/`take`). A puzzle should never fail
  because the player used a plausible word the author didn't anticipate.
- **No guess-the-verb.** If a puzzle requires an unusual verb, either make it work through the
  standard verb set (a rule keyed to `push`/`pull`/`turn`/`put` etc.) or clue the exact verb
  needed directly in the prose ("The lever looks like it wants to be pulled.").
- **No outside knowledge required.** Real-world trivia, prior genre knowledge, or meta-puzzles
  the player couldn't infer from the game itself are unfair.

## No unwarned softlocks

Never let the game reach a state where the win condition becomes impossible without a clear
in-world warning first, or an alternate path. Concretely:

- Don't let a required item be permanently destroyed/lost/sealed away unless the player is
  warned before it happens ("The floor gives way beneath the key -- grab it now or lose it
  forever!").
- Don't let an exit seal permanently mid-puzzle without either a warning or a way to still win
  (or at least still not be *stuck* -- reaching an unwinnable-but-quittable state is far less bad
  than reaching an unwinnable state the player doesn't realize is unwinnable).
- Any lose condition should have a **legible cause** -- the player should understand exactly why
  they lost from the message shown, not have to guess.
- This is exactly what `walkthrough_runner.py` exists to catch: a documented winning path proves
  at least one route through the game is always completable by construction, and fuzz-testing
  nonsense input proves it can't be broken by mistyping.

## Zarfian cruelty scale

Aim for **Polite** or at most **Tough**, never **Cruel** or worse. In practice:
- *Polite*: the game can be lost, but only through a clearly signaled action, and it's obvious
  in advance which actions are risky.
- *Tough*: it's possible to make the game unwinnable through carelessness, but the player
  realizes it fairly soon (not hours of dead play before finding out).
- Avoid designs where a wrong move early on (that seems perfectly reasonable at the time)
  silently dooms a run that isn't discovered as unwinnable until much later.

## Consistent mapping

Room connections should be spatially consistent and (usually) reversible: if going north from
room A reaches room B, going south from B should return to A, unless there's a deliberate,
clued exception (a one-way slide, a trapdoor that seals behind you -- and even then, warn the
player or make sure it doesn't strand them).

## Pacing and cluing

- Introduce mechanics gradually: don't require the player to juggle darkness, a locked door, and
  a multi-step inventory puzzle all in the first two rooms.
- Red herrings should be rare and clearly herrings on reflection, not indistinguishable from real
  clues -- a game that's mostly padding erodes trust in every future clue.
- Give a sense of progress: score increments, rank changes, or simply new areas opening up should
  land often enough that the player feels the game moving.

## Darkness / the grue convention

Dark rooms and the "eaten by a grue" message are an homage to Zork's darkness mechanic and
should be used as **atmospheric hazard**, not a random-death trap:
- A dark room should always have an obtainable light source reachable *before* the player is
  forced to enter it blind, or the darkness itself should be survivable (most actions simply
  fail with the grue warning rather than actually killing the player -- consult
  `rules-system.md`/`parser-design.md`: by default, entering the dark doesn't kill you, it just
  blocks most actions until you have a working light source in scope).
- Don't add a rule that actually kills the player in the dark unless it's clearly telegraphed
  ("something skitters closer in the blackness...") well before it happens, consistent with the
  no-unwarned-softlocks principle above.
