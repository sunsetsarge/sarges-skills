# Parser design

How `engine.py` turns a raw input line into a verb + resolved objects. This describes the
Python reference engine (`parse_command`, `resolve_noun`, `_matches_object` in `engine.py`).

## Tokenizing

`tokenize()` lowercases the line and splits on whitespace. `parse_command()` then strips
articles (`a`, `an`, `the`) from every token before anything else happens -- so `"take the
brass key"` and `"take brass key"` parse identically.

## Command shape

`verb [noun words...] [preposition noun words...]`

The first non-article token is looked up as a verb (or a bare direction, see below). Everything
after it is split at the first token that matches a recognized preposition:

```
PREPOSITIONS = with, using, in, into, on, onto, to, at, from, under
```

Everything before the preposition is the noun phrase; everything after is the target phrase.
Examples:

- `unlock iron door with key` -> verb `unlock`, noun `iron door`, prep `with`, target `key`.
- `put brass key in lock` -> verb `put`, noun `brass key`, prep `in`, target `lock`.
- `examine lamp` -> verb `examine`, noun `lamp`, no prep/target.

If no preposition token is found, the whole remainder is treated as the noun phrase.

## Bare directions

A single bare direction word (`north`, `n`, `up`, ...) is shorthand for `go <direction>` --
handled as a special case before verb lookup even runs. `go north` (or `go n`) works the same
way through the normal verb path: `go` is a real verb, and its noun phrase is checked against
`DIRECTIONS` for a canonical match.

## Vocabulary / verb synonyms

Every canonical verb has a built-in synonym list (`DEFAULT_VERB_SYNONYMS` in `engine.py`), e.g.
`take` <- `get`, `grab`, `pick`; `look` <- `l`; `inventory` <- `i`, `inv`. A world's
`vocabulary.verbs` map is merged in additively at load time (`World.__init__`): each entry's
synonym list gets extended (not replaced), and the canonical verb name itself is always kept as
a valid trigger word. `_canonical_verb()` does a flat scan over every canonical verb's synonym
set, matching the *first* input token only -- so verb phrases are always exactly one word in the
Python engine (multi-word verb phrases like "pick up" are NOT recognized; see
`standard-verbs.md`).

## Noun resolution and scope

Once noun/target word lists are known, `resolve_noun()` matches them against
`World.scope_object_ids()` -- the set of objects the player can currently refer to:

- every object directly in the current room,
- the contents of any *room* object that is `container` + `open`, or `supporter`,
- everything in the player's inventory,
- the contents of any *carried* container that is `open`.

If the room is dark and unlit (see "Darkness" below), scope collapses to just the inventory (and
open carried containers) -- so you can still `turn on lamp` in the dark, but can't reference
room objects you can't see.

### Matching a noun phrase to an object (`_matches_object`)

The **last word** of the noun phrase must be either the object's `name` or one of its
`synonyms` (case-insensitive). Every word *before* the last one must be either an adjective
(`adjectives`) or itself a name/synonym word. This means:
- `"key"` matches an object with `synonyms: ["key"]`.
- `"brass key"` matches if `"brass"` is in `adjectives` and `"key"` is the head noun.
- Word order flexibility: the check also accepts the whole phrase joined with spaces as a
  literal multi-word synonym (e.g. a synonym literally listed as `"flour barrel"`).

### Ambiguity

If more than one in-scope object matches, resolution fails with a disambiguation question:
`"Which do you mean, the red key or the brass key?"` (or a longer comma-joined list for 3+
matches). No match at all -> `"You can't see any such thing."` **Note:** the Python engine does
not have a follow-up disambiguation loop -- it returns the question as the command's result text
and the player must re-issue a more specific command. (The browser runtime in
`engine/web/template.html` does implement a stateful follow-up: it remembers the ambiguous
candidate list and resolves the *next* line typed against it.)

### Pronoun `it`

`resolve_noun(["it"], ...)` resolves to `World.pronoun_it` -- the last object id that was
successfully resolved as either a noun or a target in any prior command -- but only if that
object is still in scope. If nothing has been referenced yet, or the last referent has left
scope, the response is: `"You'll have to be more specific -- I don't know what 'it' refers to."`

### `all` / `everything`

If the noun phrase is exactly `all` or `everything` (for `take` or `drop` only), the engine runs
`_handle_all()`: for `take`, every portable, non-fixed object in the current room; for `drop`,
every object in inventory. Any other verb with `all`/`everything` returns `"You can't do that
with 'all'."`

## Chaining and repeats

`split_chained_commands()` splits a raw line on the literal word `then` or a `.` character into
multiple independent commands, executed in order, each producing its own output line(s) joined
with newlines. `again` / `g` alone re-executes `World.last_command` (the most recently *typed*
line, tracked before chaining/repeat substitution) -- if nothing has been typed yet, the response
is `"There's nothing to repeat."`

## Error messages

The parser never raises a raw exception to the player. Specific, friendly errors:

- Unrecognized verb word: `"I don't know how to '<word>'."`
- Noun/target not found in scope: `"You can't see any such thing."`
- Ambiguous noun: `"Which do you mean, the X or the Y?"`
- Empty input: `"I beg your pardon?"`
- Verb requiring a noun with none given: `"<Verb capitalized> what?"` (e.g. `"Take what?"`).
- Anything that fails for content reasons (locked door, closed container, non-portable object,
  etc.) returns a specific in-world reason from the relevant default handler -- never a generic
  failure and never a stack trace. `play.py` and `walkthrough_runner.py` both additionally
  wrap command execution in a catch-all so a bug in content or a rule can never crash the
  session; the player instead sees "Something went wrong processing that command (...). Try
  something else."
