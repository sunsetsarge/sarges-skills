"""
engine.py -- stdlib-only reference engine for the text-adventure skill.

Loads a world JSON document (rooms, objects, vocabulary, rules, meta) and
runs a Zork-style parser game loop. ZERO game content is hard-coded here:
every room, object, verb synonym, and puzzle rule comes from the world file
passed in at load time. This file only implements the *mechanics*:

    - world model (rooms / objects / flags)
    - command parser (tokenizing, vocabulary, scope, disambiguation)
    - default verb handlers (look, take, open, ...)
    - the declarative rules evaluator (triggers -> conditions -> effects)
    - meta systems: score, turns, save/load, undo, rank

Two runtimes share this same rules contract: this Python engine, and the
browser runtime in engine/web/template.html (which reimplements the same
world-model + rules semantics in JavaScript so a single world JSON drives
both). Python-only extension point: an optional hooks.py next to the world
JSON (see load_hooks()) -- it does NOT run in the browser export.

Deterministic: no randomness, no wall-clock dependence, no network/file
access beyond the explicit world/save paths the caller supplies.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Vocabulary defaults (used when the world JSON does not override them)
# ---------------------------------------------------------------------------

# Canonical verb -> list of surface-form synonyms (world "vocabulary.verbs"
# may extend or override any entry; see world-schema.md / standard-verbs.md).
DEFAULT_VERB_SYNONYMS: Dict[str, List[str]] = {
    "look": ["look", "l"],
    "examine": ["examine", "x", "inspect", "describe"],
    "inventory": ["inventory", "i", "inv"],
    "take": ["take", "get", "grab", "pick"],
    "drop": ["drop"],
    "go": ["go", "walk", "run", "move"],
    "open": ["open"],
    "close": ["close", "shut"],
    "lock": ["lock"],
    "unlock": ["unlock"],
    "read": ["read"],
    "push": ["push"],
    "pull": ["pull"],
    "turn": ["turn"],
    "put": ["put", "place", "insert"],
    "wear": ["wear", "don"],
    "remove": ["remove", "unwear", "doff"],
    "eat": ["eat"],
    "drink": ["drink"],
    "search": ["search"],
    "enter": ["enter"],
    "exit": ["exit"],
    "wait": ["wait", "z"],
    "again": ["again", "g"],
    "attack": ["attack", "hit", "kill", "fight"],
    "talk": ["talk", "speak"],
    "ask": ["ask"],
    "tell": ["tell"],
    "give": ["give"],
    "save": ["save"],
    "load": ["load", "restore"],
    "undo": ["undo"],
    "restart": ["restart"],
    "quit": ["quit", "q"],
    "score": ["score"],
    "help": ["help", "?"],
    "verbose": ["verbose"],
    "brief": ["brief"],
}

# Direction canonical name -> synonyms (abbreviations included).
DIRECTIONS: Dict[str, List[str]] = {
    "north": ["north", "n"],
    "south": ["south", "s"],
    "east": ["east", "e"],
    "west": ["west", "w"],
    "up": ["up", "u"],
    "down": ["down", "d"],
    "in": ["in", "enter"],
    "out": ["out", "exit"],
    "northeast": ["northeast", "ne"],
    "northwest": ["northwest", "nw"],
    "southeast": ["southeast", "se"],
    "southwest": ["southwest", "sw"],
}

# Prepositions the parser recognizes for verb [noun] [prep noun] forms.
PREPOSITIONS = ["with", "using", "in", "into", "on", "onto", "to", "at", "from", "under"]

# Words that terminate scanning a noun phrase / are ignored as noise.
ARTICLES = {"a", "an", "the"}
CHAIN_WORDS = {"then"}

FLAG_KEYS = [
    "portable", "fixed", "container", "open", "openable", "lockable",
    "locked", "key", "supporter", "light_source", "on", "edible",
    "drinkable", "readable", "wearable", "worn",
]

GRUE_MESSAGE = "It is pitch black. You are likely to be eaten by a grue."


# ---------------------------------------------------------------------------
# World model
# ---------------------------------------------------------------------------


class GameOver(Exception):
    """Raised internally to unwind the loop cleanly on quit/restart."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind  # "quit" | "restart"


class World:
    """
    Wraps the raw world JSON dict and the live mutable game state.

    `data` holds the immutable-ish authored content (room templates, object
    templates, rules, vocabulary, meta). Mutable fields below (rooms,
    objects, flags, score, turns, ...) are exactly what save/load/undo
    serialize.
    """

    def __init__(self, world_json: Dict[str, Any]):
        self.data = world_json
        self.meta = world_json.get("meta", {})
        self.title = self.meta.get("title", "Untitled Adventure")
        self.max_score = self.meta.get("max_score", 0)
        self.ranks = self.meta.get("ranks", [])  # list of [threshold, title]

        self.rooms: Dict[str, Dict[str, Any]] = {}
        for rid, r in world_json.get("rooms", {}).items():
            self.rooms[rid] = copy.deepcopy(r)

        self.objects: Dict[str, Dict[str, Any]] = {}
        for oid, o in world_json.get("objects", {}).items():
            obj = copy.deepcopy(o)
            # normalize flags dict so every known flag key exists (False default)
            flags = obj.get("flags", {})
            norm = {k: bool(flags.get(k, False)) for k in FLAG_KEYS}
            obj["flags"] = norm
            self.objects[oid] = obj

        # global boolean/value flags
        self.flags: Dict[str, Any] = dict(world_json.get("flags", {}))

        # vocabulary: merge defaults with world overrides/additions
        self.verb_synonyms: Dict[str, List[str]] = {
            k: list(v) for k, v in DEFAULT_VERB_SYNONYMS.items()
        }
        vocab = world_json.get("vocabulary", {}) or {}
        for verb, syns in (vocab.get("verbs") or {}).items():
            existing = set(self.verb_synonyms.get(verb, []))
            existing.update(syns)
            existing.add(verb)
            self.verb_synonyms[verb] = sorted(existing)

        # rules: list of rule dicts, evaluated in file order
        self.rules: List[Dict[str, Any]] = list(world_json.get("rules", []))

        # meta/game state
        self.current_room = self.meta.get("start_room")
        self.score = 0
        self.turns = 0
        self.game_over = False
        self.win = False
        self.end_message: Optional[str] = None
        self.visited_rooms: set = set()
        self.pronoun_it: Optional[str] = None
        self.verbose = True
        self.last_command: Optional[str] = None

        # undo: stack of prior serialized states (bounded)
        self.undo_stack: List[Dict[str, Any]] = []
        self.max_undo = 10

    # -- serialization ------------------------------------------------------

    def serialize(self) -> Dict[str, Any]:
        return {
            "rooms": copy.deepcopy(self.rooms),
            "objects": copy.deepcopy(self.objects),
            "flags": copy.deepcopy(self.flags),
            "current_room": self.current_room,
            "score": self.score,
            "turns": self.turns,
            "game_over": self.game_over,
            "win": self.win,
            "end_message": self.end_message,
            "visited_rooms": list(self.visited_rooms),
            "pronoun_it": self.pronoun_it,
            "verbose": self.verbose,
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        self.rooms = copy.deepcopy(snap["rooms"])
        self.objects = copy.deepcopy(snap["objects"])
        self.flags = copy.deepcopy(snap["flags"])
        self.current_room = snap["current_room"]
        self.score = snap["score"]
        self.turns = snap["turns"]
        self.game_over = snap["game_over"]
        self.win = snap["win"]
        self.end_message = snap["end_message"]
        self.visited_rooms = set(snap["visited_rooms"])
        self.pronoun_it = snap["pronoun_it"]
        self.verbose = snap["verbose"]

    def push_undo(self) -> None:
        self.undo_stack.append(self.serialize())
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

    def pop_undo(self) -> bool:
        if not self.undo_stack:
            return False
        snap = self.undo_stack.pop()
        self.restore(snap)
        return True

    # -- object/location helpers --------------------------------------------

    def obj_location(self, oid: str) -> Any:
        return self.objects[oid].get("location", "nowhere")

    def set_obj_location(self, oid: str, location: Any) -> None:
        self.objects[oid]["location"] = location

    def objects_in_room(self, room_id: str) -> List[str]:
        return [oid for oid, o in self.objects.items() if o.get("location") == room_id]

    def objects_in_inventory(self) -> List[str]:
        return [oid for oid, o in self.objects.items() if o.get("location") == "inventory"]

    def objects_in_container(self, container_id: str) -> List[str]:
        out = []
        for oid, o in self.objects.items():
            loc = o.get("location")
            if isinstance(loc, dict) and loc.get("in") == container_id:
                out.append(oid)
        return out

    def objects_on_supporter(self, supporter_id: str) -> List[str]:
        out = []
        for oid, o in self.objects.items():
            loc = o.get("location")
            if isinstance(loc, dict) and loc.get("on") == supporter_id:
                out.append(oid)
        return out

    def objects_holding(self, holder_id: str) -> List[str]:
        """Objects directly in or on a given container/supporter object."""
        return self.objects_in_container(holder_id) + self.objects_on_supporter(holder_id)

    def is_lit(self) -> bool:
        """True if the current room has light: not dark, or a lit light_source in scope."""
        room = self.rooms.get(self.current_room, {})
        if not room.get("dark"):
            return True
        for oid in self.scope_object_ids(include_dark_check=False):
            o = self.objects[oid]
            if o["flags"].get("light_source") and o["flags"].get("on"):
                return True
        return False

    def scope_object_ids(self, include_dark_check: bool = True) -> List[str]:
        """
        Objects the player can currently interact with: room contents +
        contents of any open containers/supporters in the room + inventory +
        contents of open containers carried. If the room is dark and unlit,
        scope collapses to just the inventory (and what's inside open
        carried containers) so darkness-tolerant actions like "turn on lamp"
        still resolve nouns.
        """
        if include_dark_check and not self.is_lit():
            ids = list(self.objects_in_inventory())
            for oid in list(ids):
                o = self.objects[oid]
                if o["flags"].get("container") and o["flags"].get("open"):
                    ids.extend(self.objects_holding(oid))
            return ids

        ids: List[str] = []
        room_objs = self.objects_in_room(self.current_room)
        ids.extend(room_objs)
        for oid in room_objs:
            o = self.objects[oid]
            if o["flags"].get("container") and o["flags"].get("open"):
                ids.extend(self.objects_holding(oid))
            if o["flags"].get("supporter"):
                ids.extend(self.objects_holding(oid))
        inv = self.objects_in_inventory()
        ids.extend(inv)
        for oid in inv:
            o = self.objects[oid]
            if o["flags"].get("container") and o["flags"].get("open"):
                ids.extend(self.objects_holding(oid))
        seen = set()
        out = []
        for oid in ids:
            if oid not in seen:
                seen.add(oid)
                out.append(oid)
        return out

    def describe_object_short(self, oid: str) -> str:
        o = self.objects[oid]
        name = o.get("name", oid)
        suffix = ""
        if o["flags"].get("container"):
            suffix = " (open)" if o["flags"].get("open") else " (closed)"
        if o["flags"].get("worn"):
            suffix += " (worn)"
        if o["flags"].get("light_source") and o["flags"].get("on"):
            suffix += " (on)"
        return f"{name}{suffix}"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_world(path: str) -> World:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return World(data)


def load_hooks(world_path: str):
    """
    Optional Python-only escape hatch. If a file named `hooks.py` sits next
    to the world JSON, it is imported and returned. hooks.py is NEVER
    required -- the bundled example (the-cellar) does not use one -- and it
    does not carry into the browser/HTML export (Python-only).
    Expected optional callables inside hooks.py:
        on_command(world, verb, noun, target) -> Optional[str]
        on_turn(world) -> Optional[str]
    """
    base_dir = os.path.dirname(os.path.abspath(world_path))
    hooks_path = os.path.join(base_dir, "hooks.py")
    if not os.path.exists(hooks_path):
        return None
    spec = importlib.util.spec_from_file_location("world_hooks", hooks_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class ParseResult:
    def __init__(self):
        self.raw = ""
        self.verb: Optional[str] = None
        self.verb_word: Optional[str] = None
        self.noun_words: List[str] = []
        self.prep: Optional[str] = None
        self.target_words: List[str] = []
        self.error: Optional[str] = None
        self.is_direction = False


def _canonical_verb(word: str, world: World) -> Optional[str]:
    word = word.lower()
    for canon, syns in world.verb_synonyms.items():
        if word == canon or word in syns:
            return canon
    return None


def _canonical_direction(word: str) -> Optional[str]:
    word = word.lower()
    for canon, syns in DIRECTIONS.items():
        if word == canon or word in syns:
            return canon
    return None


def tokenize(line: str) -> List[str]:
    return [w for w in line.strip().lower().split() if w]


def split_chained_commands(line: str) -> List[str]:
    """Split on '.' or the word 'then' into separate command strings."""
    line = line.replace(".", " . ")
    tokens = line.split()
    commands: List[List[str]] = [[]]
    for tok in tokens:
        low = tok.lower()
        if tok == "." or low in CHAIN_WORDS:
            commands.append([])
        else:
            commands[-1].append(tok)
    return [" ".join(c) for c in commands if c]


def parse_command(line: str, world: World) -> ParseResult:
    res = ParseResult()
    res.raw = line
    tokens = tokenize(line)
    tokens = [t for t in tokens if t not in ARTICLES]
    if not tokens:
        res.error = "EMPTY"
        return res

    first = tokens[0]

    # bare direction shortcut: "north" == "go north"
    direction = _canonical_direction(first)
    if direction and len(tokens) == 1:
        res.verb = "go"
        res.verb_word = first
        res.is_direction = True
        res.noun_words = [direction]
        return res

    verb = _canonical_verb(first, world)
    if verb is None:
        res.error = f"I don't know how to '{first}'."
        return res
    res.verb = verb
    res.verb_word = first

    rest = tokens[1:]
    if verb == "go" and rest:
        d = _canonical_direction(rest[0])
        if d:
            res.noun_words = [d]
            res.is_direction = True
            return res

    # split rest into noun phrase [prep noun phrase]
    prep_idx = None
    for i, tok in enumerate(rest):
        if tok in PREPOSITIONS:
            prep_idx = i
            break

    if prep_idx is None:
        res.noun_words = rest
    else:
        res.noun_words = rest[:prep_idx]
        res.prep = rest[prep_idx]
        res.target_words = rest[prep_idx + 1:]

    return res


def _matches_object(oid: str, words: List[str], world: World) -> bool:
    """Does this object match a noun phrase (name/synonyms/adjectives)?"""
    if not words:
        return False
    o = world.objects[oid]
    names = {o.get("name", "").lower()}
    for s in o.get("synonyms", []):
        names.add(s.lower())
    adjectives = {a.lower() for a in o.get("adjectives", [])}

    remaining = list(words)
    head = remaining[-1]
    if head not in names:
        joined = " ".join(remaining)
        if joined in names:
            return True
        return False
    for w in remaining[:-1]:
        if w not in adjectives and w not in names:
            return False
    return True


def resolve_noun(words: List[str], world: World, pronoun_ok: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a noun-phrase word list to an object id within current scope.
    Returns (object_id, error_message). On ambiguity, error_message asks the
    disambiguation question. On no match, error is the "can't see" message.
    """
    if not words:
        return None, None

    if pronoun_ok and words == ["it"]:
        if world.pronoun_it and world.pronoun_it in world.scope_object_ids():
            return world.pronoun_it, None
        return None, "You'll have to be more specific -- I don't know what 'it' refers to."

    scope = world.scope_object_ids()
    candidates = [oid for oid in scope if _matches_object(oid, words, world)]

    if not candidates:
        return None, "You can't see any such thing."
    if len(candidates) == 1:
        return candidates[0], None

    names = [world.objects[c].get("name", c) for c in candidates]
    if len(names) == 2:
        question = f"Which do you mean, the {names[0]} or the {names[1]}?"
    else:
        listed = ", the ".join(names[:-1])
        question = f"Which do you mean, the {listed}, or the {names[-1]}?"
    return None, question


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------


def _flag_get(world: World, key: str) -> Any:
    return world.flags.get(key)


def _obj_loc_matches(loc: Any, target: str) -> bool:
    """Check whether an object's location value matches a target spec used
    in rule conditions: 'inventory', 'nowhere', a room id, 'in:<id>', 'on:<id>'."""
    if isinstance(target, str):
        if target.startswith("in:"):
            return isinstance(loc, dict) and loc.get("in") == target[3:]
        if target.startswith("on:"):
            return isinstance(loc, dict) and loc.get("on") == target[3:]
        return loc == target
    return False


def condition_met(world: World, cond: Dict[str, Any]) -> bool:
    """
    Supported condition shapes (all ANDed together in a rule's "conditions" list):
      {"flag": "name", "equals": value}
      {"object": "id", "location": "<room|inventory|nowhere|in:X|on:X>"}
      {"object": "id", "property": "flagname", "equals": true/false}
      {"score_at_least": N}  / {"score_at_most": N}
    """
    if "flag" in cond:
        val = _flag_get(world, cond["flag"])
        return val == cond.get("equals", True)
    if "object" in cond and "location" in cond:
        oid = cond["object"]
        if oid not in world.objects:
            return False
        return _obj_loc_matches(world.obj_location(oid), cond["location"])
    if "object" in cond and "property" in cond:
        oid = cond["object"]
        if oid not in world.objects:
            return False
        want = cond.get("equals", True)
        return bool(world.objects[oid]["flags"].get(cond["property"])) == bool(want)
    if "score_at_least" in cond:
        return world.score >= cond["score_at_least"]
    if "score_at_most" in cond:
        return world.score <= cond["score_at_most"]
    return False


def conditions_met(world: World, conditions: List[Dict[str, Any]]) -> bool:
    return all(condition_met(world, c) for c in conditions)


def apply_effect(world: World, effect: Dict[str, Any], output: List[str]) -> None:
    """
    Effects, applied in list order:
      {"set_flag": "name", "value": true}
      {"move": "object_id", "to": "<room|inventory|nowhere|in:X|on:X>"}
      {"reveal_exit": {"room": "id", "direction": "n", "to": "id"}}
      {"lock_exit": {"room": "id", "direction": "n"}}   # removes/blocks an exit
      {"unlock": "object_id"}                            # sets locked flag False
      {"lock": "object_id"}                              # sets locked flag True
      {"print": "message text"}
      {"score": delta}
      {"win": "message"}
      {"lose": "message"}

    Any effect that changes a global flag's value (currently just "set_flag")
    triggers on_flag rules for that flag name -- see apply_effects_with_flag_cascade().
    """
    if "set_flag" in effect:
        world.flags[effect["set_flag"]] = effect.get("value", True)
        return
    if "move" in effect:
        oid = effect["move"]
        to = effect["to"]
        if isinstance(to, str) and to.startswith("in:"):
            world.set_obj_location(oid, {"in": to[3:]})
        elif isinstance(to, str) and to.startswith("on:"):
            world.set_obj_location(oid, {"on": to[3:]})
        else:
            world.set_obj_location(oid, to)
        return
    if "reveal_exit" in effect:
        spec = effect["reveal_exit"]
        room = world.rooms.get(spec["room"])
        if room is not None:
            room.setdefault("exits", {})[spec["direction"]] = spec["to"]
        return
    if "lock_exit" in effect:
        spec = effect["lock_exit"]
        room = world.rooms.get(spec["room"])
        if room is not None and "exits" in room:
            room["exits"].pop(spec["direction"], None)
        return
    if "unlock" in effect:
        oid = effect["unlock"]
        if oid in world.objects:
            world.objects[oid]["flags"]["locked"] = False
        return
    if "lock" in effect:
        oid = effect["lock"]
        if oid in world.objects:
            world.objects[oid]["flags"]["locked"] = True
        return
    if "print" in effect:
        output.append(effect["print"])
        return
    if "score" in effect:
        world.score += effect["score"]
        return
    if "win" in effect:
        world.game_over = True
        world.win = True
        world.end_message = effect["win"]
        return
    if "lose" in effect:
        world.game_over = True
        world.win = False
        world.end_message = effect["lose"]
        return


def apply_effects(world: World, effects: List[Dict[str, Any]], output: List[str]) -> None:
    """
    Applies effects in order, then fires any matching on_flag rules for each
    flag whose VALUE actually changed as a result (compares before/after for
    every "set_flag" effect in this list). Cascades: an on_flag rule's own
    effects can change further flags, which fire further on_flag rules -- but
    depth is capped (MAX_FLAG_CASCADE_DEPTH) to guard against infinite loops
    (e.g. two on_flag rules that flip each other back and forth).
    """
    changed_flags: List[str] = []
    for e in effects:
        if "set_flag" in e:
            name = e["set_flag"]
            before = world.flags.get(name)
            apply_effect(world, e, output)
            after = world.flags.get(name)
            if before != after:
                changed_flags.append(name)
        else:
            apply_effect(world, e, output)
    for name in changed_flags:
        _fire_on_flag(world, name, output, depth=1)


MAX_FLAG_CASCADE_DEPTH = 10


def _fire_on_flag(world: World, flag_name: str, output: List[str], depth: int) -> None:
    if depth > MAX_FLAG_CASCADE_DEPTH:
        return
    for rule in world.rules:
        if not _rule_trigger_matches(rule, None, None, None, "on_flag", extra=flag_name):
            continue
        conds = rule.get("conditions", [])
        if not conditions_met(world, conds):
            continue
        _apply_effects_cascade(world, rule.get("effects", []), output, depth + 1)


def _apply_effects_cascade(world: World, effects: List[Dict[str, Any]], output: List[str], depth: int) -> None:
    """Same as apply_effects but threads the cascade depth counter through,
    so nested on_flag firings triggered by a rule's own set_flag effects are
    still capped by MAX_FLAG_CASCADE_DEPTH."""
    changed_flags: List[str] = []
    for e in effects:
        if "set_flag" in e:
            name = e["set_flag"]
            before = world.flags.get(name)
            apply_effect(world, e, output)
            after = world.flags.get(name)
            if before != after:
                changed_flags.append(name)
        else:
            apply_effect(world, e, output)
    for name in changed_flags:
        _fire_on_flag(world, name, output, depth)


def _rule_trigger_matches(rule: Dict[str, Any], verb: Optional[str], noun: Optional[str],
                           target: Optional[str], kind: str, extra: Optional[str] = None) -> bool:
    trig = rule.get("trigger", {})
    if kind == "command":
        if "on_enter" in trig or "on_turn" in trig or "on_flag" in trig:
            return False
        if "verb" in trig and trig["verb"] != verb:
            return False
        if "object" in trig and trig["object"] != noun:
            return False
        if "target" in trig and trig["target"] != target:
            return False
        return "verb" in trig
    if kind == "on_enter":
        return trig.get("on_enter") == extra
    if kind == "on_turn":
        return "on_turn" in trig
    if kind == "on_flag":
        # Reachable via _fire_on_flag()'s direct iteration (not through
        # run_rules), but kept here so the shape check stays in one place.
        return trig.get("on_flag") == extra
    return False


def run_rules(world: World, kind: str, verb: Optional[str] = None, noun: Optional[str] = None,
              target: Optional[str] = None, extra: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Evaluate all rules matching (kind, ...). Returns (consumed, messages).
    `consumed` is True if any matching rule's conditions were met (for
    command-kind rules this means "do not run the default handler").
    """
    consumed = False
    output: List[str] = []
    for rule in world.rules:
        if not _rule_trigger_matches(rule, verb, noun, target, kind, extra):
            continue
        conds = rule.get("conditions", [])
        if not conditions_met(world, conds):
            continue
        apply_effects(world, rule.get("effects", []), output)
        consumed = True
        if kind == "command" and rule.get("stop", True):
            break
    return consumed, output


# ---------------------------------------------------------------------------
# Default verb handlers
# ---------------------------------------------------------------------------


def room_full_description(world: World) -> str:
    room = world.rooms[world.current_room]
    lines = [room.get("name", world.current_room)]
    if not world.is_lit():
        lines.append(GRUE_MESSAGE)
        return "\n".join(lines)
    lines.append(room.get("description", ""))
    objs = world.objects_in_room(world.current_room)
    visible = [o for o in objs if not world.objects[o]["flags"].get("worn")]
    if visible:
        lines.append("You can see: " + ", ".join(world.describe_object_short(o) for o in visible) + ".")
    exits = sorted((room.get("exits") or {}).keys())
    if exits:
        lines.append("Exits: " + ", ".join(exits) + ".")
    return "\n".join(lines)


def room_brief(world: World) -> str:
    room = world.rooms[world.current_room]
    if not world.is_lit():
        return f"{room.get('name', world.current_room)}\n{GRUE_MESSAGE}"
    return room.get("name", world.current_room)


def do_look(world: World, res: ParseResult) -> str:
    if world.current_room not in world.visited_rooms or world.verbose:
        return room_full_description(world)
    return room_brief(world)


def do_inventory(world: World) -> str:
    items = world.objects_in_inventory()
    if not items:
        return "You are carrying nothing."
    return "You are carrying: " + ", ".join(world.describe_object_short(o) for o in items) + "."


def do_examine(world: World, oid: str) -> str:
    o = world.objects[oid]
    desc = o.get("description", f"You see nothing special about the {o.get('name', oid)}.")
    extra = []
    if o["flags"].get("readable") and o.get("text"):
        extra.append(f'It reads: "{o["text"]}"')
    if o["flags"].get("container"):
        if o["flags"].get("open"):
            contents = world.objects_holding(oid)
            if contents:
                extra.append("It contains: " + ", ".join(world.describe_object_short(c) for c in contents) + ".")
            else:
                extra.append("It is empty.")
        else:
            extra.append("It is closed.")
    if extra:
        desc = desc + " " + " ".join(extra)
    return desc


def do_take(world: World, oid: str) -> str:
    o = world.objects[oid]
    if world.obj_location(oid) == "inventory":
        return f"You already have the {o.get('name', oid)}."
    if not o["flags"].get("portable", True) or o["flags"].get("fixed"):
        return f"You can't take the {o.get('name', oid)}."
    world.set_obj_location(oid, "inventory")
    return "Taken."


def do_drop(world: World, oid: str) -> str:
    if world.obj_location(oid) != "inventory":
        return "You aren't carrying that."
    world.set_obj_location(oid, world.current_room)
    return "Dropped."


def _exit_target(exit_val: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return (room_id, door_object_id_or_None) for an exits[] entry."""
    if isinstance(exit_val, str):
        return exit_val, None
    if isinstance(exit_val, dict):
        return exit_val.get("to"), exit_val.get("door")
    return None, None


def do_go(world: World, direction: str) -> Optional[str]:
    """Returns an error string on failure, or None on success (room changed)."""
    room = world.rooms[world.current_room]
    exits = room.get("exits") or {}
    if direction not in exits:
        return "You can't go that way."
    target, door = _exit_target(exits[direction])
    if door:
        door_obj = world.objects.get(door)
        if door_obj and door_obj["flags"].get("lockable") and door_obj["flags"].get("locked"):
            return f"The {door_obj.get('name', door)} is locked."
        if door_obj and door_obj["flags"].get("openable") and not door_obj["flags"].get("open"):
            return f"The {door_obj.get('name', door)} is closed."
    if target is None or target not in world.rooms:
        return "You can't go that way."
    world.current_room = target
    return None


def do_open(world: World, oid: str) -> str:
    o = world.objects[oid]
    if o["flags"].get("locked"):
        return f"The {o.get('name', oid)} is locked."
    if not o["flags"].get("openable") and not o["flags"].get("container"):
        return f"You can't open the {o.get('name', oid)}."
    if o["flags"].get("open"):
        return f"The {o.get('name', oid)} is already open."
    o["flags"]["open"] = True
    return f"You open the {o.get('name', oid)}."


def do_close(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("open"):
        return f"The {o.get('name', oid)} is already closed."
    o["flags"]["open"] = False
    return f"You close the {o.get('name', oid)}."


def do_lock(world: World, oid: str, key_id: Optional[str]) -> str:
    o = world.objects[oid]
    if not o["flags"].get("lockable"):
        return f"You can't lock the {o.get('name', oid)}."
    required_key = o.get("key")
    if key_id is None:
        return "Lock it with what?"
    if key_id != required_key:
        return f"The {world.objects[key_id].get('name', key_id)} doesn't fit."
    o["flags"]["locked"] = True
    return f"You lock the {o.get('name', oid)}."


def do_unlock(world: World, oid: str, key_id: Optional[str]) -> str:
    o = world.objects[oid]
    if not o["flags"].get("lockable"):
        return f"You can't unlock the {o.get('name', oid)}."
    if not o["flags"].get("locked"):
        return f"The {o.get('name', oid)} is already unlocked."
    required_key = o.get("key")
    if key_id is None:
        return "Unlock it with what?"
    if key_id != required_key:
        return f"The {world.objects[key_id].get('name', key_id)} doesn't fit."
    o["flags"]["locked"] = False
    return f"You unlock the {o.get('name', oid)}."


def do_read(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("readable"):
        return f"There's nothing to read on the {o.get('name', oid)}."
    return o.get("text", "It's blank.")


def do_put(world: World, oid: str, prep: str, target_id: str) -> str:
    obj = world.objects[oid]
    tgt = world.objects[target_id]
    if world.obj_location(oid) != "inventory":
        return f"You aren't holding the {obj.get('name', oid)}."
    if prep in ("in", "into"):
        if not tgt["flags"].get("container"):
            return f"You can't put things in the {tgt.get('name', target_id)}."
        if not tgt["flags"].get("open"):
            return f"The {tgt.get('name', target_id)} is closed."
        world.set_obj_location(oid, {"in": target_id})
        return f"You put the {obj.get('name', oid)} in the {tgt.get('name', target_id)}."
    else:  # on / onto
        if not tgt["flags"].get("supporter"):
            return f"You can't put things on the {tgt.get('name', target_id)}."
        world.set_obj_location(oid, {"on": target_id})
        return f"You put the {obj.get('name', oid)} on the {tgt.get('name', target_id)}."


def do_wear(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("wearable"):
        return f"You can't wear the {o.get('name', oid)}."
    if world.obj_location(oid) != "inventory":
        return f"You aren't carrying the {o.get('name', oid)}."
    o["flags"]["worn"] = True
    return f"You put on the {o.get('name', oid)}."


def do_remove(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("worn"):
        return f"You aren't wearing the {o.get('name', oid)}."
    o["flags"]["worn"] = False
    return f"You take off the {o.get('name', oid)}."


def do_eat(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("edible"):
        return f"You can't eat the {o.get('name', oid)}."
    world.set_obj_location(oid, "nowhere")
    return f"You eat the {o.get('name', oid)}. Delicious."


def do_drink(world: World, oid: str) -> str:
    o = world.objects[oid]
    if not o["flags"].get("drinkable"):
        return f"You can't drink the {o.get('name', oid)}."
    return f"You drink the {o.get('name', oid)}."


def do_search(world: World, oid: str) -> str:
    o = world.objects[oid]
    if o["flags"].get("container"):
        if not o["flags"].get("open"):
            return f"The {o.get('name', oid)} is closed."
        contents = world.objects_holding(oid)
        if contents:
            return "You find: " + ", ".join(world.describe_object_short(c) for c in contents) + "."
        return "You find nothing."
    return f"You find nothing special in the {o.get('name', oid)}."


def do_turn_on_off(world: World, oid: str, on: bool) -> str:
    o = world.objects[oid]
    if not o["flags"].get("light_source"):
        return "Nothing happens."
    o["flags"]["on"] = on
    state = "on" if on else "off"
    return f"You turn the {o.get('name', oid)} {state}."


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------


class Engine:
    """Owns a World and executes one command at a time; used by play.py,
    walkthrough_runner.py, and tests. Keeping execution here (rather than in
    play.py) means every runtime that embeds this engine gets identical
    behavior."""

    def __init__(self, world: World, hooks=None):
        self.world = world
        self.hooks = hooks

    def start_message(self) -> str:
        w = self.world
        w.visited_rooms.add(w.current_room)
        title = w.title
        header = f"{title}\n{'=' * len(title)}\n"
        _, msgs = run_rules(w, "on_enter", extra=w.current_room)
        body = room_full_description(w)
        extra = ("\n" + "\n".join(msgs)) if msgs else ""
        return header + "\n" + body + extra

    def execute_line(self, line: str) -> str:
        """Execute a raw input line (possibly chained); returns full output text."""
        parts = split_chained_commands(line)
        if not parts:
            return "I beg your pardon?"
        outputs = []
        for single in parts:
            outputs.append(self._execute_single(single))
        return "\n".join(o for o in outputs if o)

    def _execute_single(self, line: str) -> str:
        w = self.world
        stripped = line.strip()

        if not stripped:
            return "I beg your pardon?"

        if stripped.lower() in ("again", "g"):
            if w.last_command is None:
                return "There's nothing to repeat."
            line = w.last_command
        else:
            w.last_command = line

        res = parse_command(line, w)

        if res.error == "EMPTY":
            return "I beg your pardon?"
        if res.error:
            return res.error

        verb = res.verb

        meta_result = self._handle_meta(verb, res)
        if meta_result is not None:
            return meta_result

        if w.game_over:
            return "The game has ended. Type 'restart' to play again, or 'quit' to exit."

        w.push_undo()

        noun_id: Optional[str] = None
        target_id: Optional[str] = None
        direction: Optional[str] = None

        if verb == "go":
            direction = res.noun_words[0] if res.noun_words else None
        else:
            if res.noun_words:
                low_words = [x.lower() for x in res.noun_words]
                if low_words in (["all"], ["everything"]):
                    return self._handle_all(verb)
                noun_id, err = resolve_noun(res.noun_words, w)
                if err:
                    return err
            if res.target_words:
                target_id, err2 = resolve_noun(res.target_words, w)
                if err2:
                    return err2

        if noun_id:
            w.pronoun_it = noun_id
        if target_id:
            w.pronoun_it = target_id

        # darkness gate: most actions fail in the dark except a short allow-list
        allowed_in_dark = {"go", "turn", "inventory", "wait", "look", "drop"}
        if not w.is_lit() and verb not in allowed_in_dark:
            return GRUE_MESSAGE

        # 1) hooks.py on_command (python-only escape hatch), highest priority
        if self.hooks and hasattr(self.hooks, "on_command"):
            hook_msg = self.hooks.on_command(w, verb, noun_id, target_id)
            if hook_msg is not None:
                after = self._end_of_turn()
                return (hook_msg + ("\n" + after if after else "")).strip()

        # 2) world rules for this command
        consumed, msgs = run_rules(w, "command", verb=verb, noun=noun_id, target=target_id)
        if consumed:
            out = "\n".join(msgs) if msgs else ""
            after = self._end_of_turn()
            return (out + ("\n" + after if after else "")).strip()

        # 3) default handler
        out = self._default_action(verb, res, noun_id, target_id, direction)
        after = self._end_of_turn()
        combined = out or ""
        if after:
            combined = (combined + "\n" + after).strip() if combined else after
        return combined

    def _handle_all(self, verb: str) -> str:
        w = self.world
        if verb == "take":
            targets = [oid for oid in w.objects_in_room(w.current_room)
                       if w.objects[oid]["flags"].get("portable", True) and not w.objects[oid]["flags"].get("fixed")]
            if not targets:
                return "There is nothing here to take."
            lines = []
            for oid in targets:
                w.push_undo()
                lines.append(do_take(w, oid))
            after = self._end_of_turn()
            if after:
                lines.append(after)
            return "\n".join(lines)
        if verb == "drop":
            targets = w.objects_in_inventory()
            if not targets:
                return "You aren't carrying anything."
            lines = []
            for oid in targets:
                w.push_undo()
                lines.append(do_drop(w, oid))
            after = self._end_of_turn()
            if after:
                lines.append(after)
            return "\n".join(lines)
        return "You can't do that with 'all'."

    def _handle_meta(self, verb: str, res: ParseResult) -> Optional[str]:
        w = self.world
        if verb == "quit":
            raise GameOver("quit")
        if verb == "restart":
            raise GameOver("restart")
        if verb == "help":
            return ("Standard commands: look, examine <obj>, inventory, take/drop <obj>, "
                    "go <direction> (n/s/e/w/u/d/ne/nw/se/sw/in/out), open/close/lock/unlock <obj>, "
                    "read <obj>, put <obj> in/on <obj>, wear/remove <obj>, eat/drink <obj>, search <obj>, "
                    "turn on/off <obj>, wait, again, save/load, undo, score, restart, quit, verbose/brief.")
        if verb == "score":
            return f"You have scored {w.score} out of {w.max_score} points in {w.turns} turns."
        if verb == "verbose":
            w.verbose = True
            return "Verbose mode: room descriptions will always be shown."
        if verb == "brief":
            w.verbose = False
            return "Brief mode: full descriptions only on first visit."
        if verb == "undo":
            if w.pop_undo():
                return "Undone."
            return "Nothing to undo."
        return None

    def _default_action(self, verb: str, res: ParseResult, noun_id: Optional[str],
                         target_id: Optional[str], direction: Optional[str]) -> str:
        w = self.world
        if verb == "look":
            return do_look(w, res)
        if verb == "inventory":
            return do_inventory(w)
        if verb == "go":
            if direction is None:
                return "Go where?"
            err = do_go(w, direction)
            if err is not None:
                return err
            first_visit = w.current_room not in w.visited_rooms
            w.visited_rooms.add(w.current_room)
            _, enter_msgs = run_rules(w, "on_enter", extra=w.current_room)
            base = room_full_description(w) if (w.verbose or first_visit) else room_brief(w)
            if enter_msgs:
                base = base + "\n" + "\n".join(enter_msgs)
            return base
        if verb == "wait":
            return "Time passes."
        if noun_id is None and verb not in ("look", "inventory", "wait", "turn"):
            return f"{verb.capitalize()} what?"
        if verb == "examine":
            return do_examine(w, noun_id)
        if verb == "take":
            return do_take(w, noun_id)
        if verb == "drop":
            return do_drop(w, noun_id)
        if verb == "open":
            return do_open(w, noun_id)
        if verb == "close":
            return do_close(w, noun_id)
        if verb == "lock":
            return do_lock(w, noun_id, target_id)
        if verb == "unlock":
            return do_unlock(w, noun_id, target_id)
        if verb == "read":
            return do_read(w, noun_id)
        if verb == "put":
            if target_id is None:
                return "Put it where?"
            prep = res.prep or "in"
            return do_put(w, noun_id, prep, target_id)
        if verb == "wear":
            return do_wear(w, noun_id)
        if verb == "remove":
            return do_remove(w, noun_id)
        if verb == "eat":
            return do_eat(w, noun_id)
        if verb == "drink":
            return do_drink(w, noun_id)
        if verb == "search":
            return do_search(w, noun_id)
        if verb == "turn":
            # Supports three phrasings: "turn on lamp" (prep=on, target=lamp),
            # "turn lamp on" (noun_words=[lamp, on]), and plain "turn lamp".
            words = [x.lower() for x in res.noun_words]
            on = "on" in words or (res.prep == "on")
            off = "off" in words or (res.prep == "off")
            words_wo = [x for x in words if x not in ("on", "off")]
            if words_wo:
                oid, err = resolve_noun(words_wo, w)
                if err:
                    return err
            elif res.target_words:
                oid, err = resolve_noun(res.target_words, w)
                if err:
                    return err
            else:
                oid = noun_id
            if oid is None:
                return "Turn what?"
            if on:
                return do_turn_on_off(w, oid, True)
            if off:
                return do_turn_on_off(w, oid, False)
            return f"You turn the {w.objects[oid].get('name', oid)}, but nothing happens."
        if verb == "push":
            return f"You push the {w.objects[noun_id].get('name', noun_id)}, but nothing happens."
        if verb == "pull":
            return f"You pull the {w.objects[noun_id].get('name', noun_id)}, but nothing happens."
        if verb == "enter":
            return f"You can't enter the {w.objects[noun_id].get('name', noun_id)}."
        if verb == "exit":
            return "You can't exit that."
        if verb == "attack":
            return "Violence isn't the answer here."
        if verb in ("talk", "ask", "tell"):
            return "There's no reply."
        if verb == "give":
            return "There's no one here to give that to."
        return "You can't do that."

    def _end_of_turn(self) -> str:
        w = self.world
        w.turns += 1
        msgs: List[str] = []
        if self.hooks and hasattr(self.hooks, "on_turn"):
            hook_msg = self.hooks.on_turn(w)
            if hook_msg:
                msgs.append(hook_msg)
        _, rule_msgs = run_rules(w, "on_turn")
        msgs.extend(rule_msgs)
        if w.game_over and w.end_message:
            rank = self._rank_line()
            msgs.append(w.end_message)
            msgs.append(rank)
        return "\n".join(msgs)

    def _rank_line(self) -> str:
        w = self.world
        title = "Adventurer"
        for threshold, name in sorted(w.ranks, key=lambda t: -t[0]):
            if w.score >= threshold:
                title = name
                break
        return f"You scored {w.score} of {w.max_score} points in {w.turns} turns, earning the rank of {title}."


# ---------------------------------------------------------------------------
# Save / load (file-based, for the Python CLI runtime)
# ---------------------------------------------------------------------------


def save_game(world: World, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(world.serialize(), f, indent=2)


def load_game(world: World, path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    world.restore(snap)


if __name__ == "__main__":
    print("engine.py is a library module. Run play.py <world.json> to play.")
    sys.exit(0)
