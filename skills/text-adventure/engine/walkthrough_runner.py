#!/usr/bin/env python
"""
walkthrough_runner.py -- automated win-state verifier for a world + a
walkthrough command list. This is the mandatory proof step referenced by
authoring-workflow.md: a game must not be delivered until its walkthrough
passes here.

Usage:
    python walkthrough_runner.py <world.json> <walkthrough.txt>

walkthrough.txt format:
    - one command per line
    - blank lines ignored
    - lines starting with '#' are comments, ignored

Exit code 0 + "PASS" line on success (engine reached world.win == True with
no unexpected errors). Exit code 1 + "FAIL" + a full transcript of every
command/response pair on failure, so a human/agent can see exactly where it
diverged.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as eng


def load_walkthrough(path: str) -> list:
    commands = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            commands.append(stripped)
    return commands


def run(world_path: str, walkthrough_path: str) -> int:
    transcript = []

    try:
        world = eng.load_world(world_path)
    except Exception as e:
        print(f"FAIL: could not load world file: {e}")
        return 1

    try:
        hooks = eng.load_hooks(world_path)
    except Exception as e:
        print(f"FAIL: hooks.py present but failed to import: {e}")
        return 1

    try:
        commands = load_walkthrough(walkthrough_path)
    except Exception as e:
        print(f"FAIL: could not load walkthrough file: {e}")
        return 1

    if not commands:
        print("FAIL: walkthrough file contained no commands.")
        return 1

    game = eng.Engine(world, hooks=hooks)
    transcript.append(("<start>", game.start_message()))

    for cmd in commands:
        try:
            output = game.execute_line(cmd)
        except eng.GameOver as go:
            transcript.append((cmd, f"<GameOver: {go.kind}>"))
            print("FAIL: walkthrough issued quit/restart before reaching a win state.")
            _print_transcript(transcript)
            return 1
        except Exception as e:
            transcript.append((cmd, f"<EXCEPTION: {e}>"))
            print(f"FAIL: unhandled exception on command {cmd!r}: {e}")
            _print_transcript(transcript)
            return 1
        transcript.append((cmd, output))

    if world.game_over and world.win:
        print(f"PASS: walkthrough completed in {world.turns} turns, "
              f"score {world.score}/{world.max_score}.")
        print(f"End message: {world.end_message}")
        return 0

    if world.game_over and not world.win:
        print("FAIL: game ended in a LOSS state, not a win.")
        _print_transcript(transcript)
        return 1

    print("FAIL: walkthrough completed all commands but the game never reached a win state.")
    _print_transcript(transcript)
    return 1


def _print_transcript(transcript) -> None:
    print("\n----- TRANSCRIPT -----")
    for cmd, output in transcript:
        print(f"> {cmd}")
        print(output)
        print()
    print("----- END TRANSCRIPT -----")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python walkthrough_runner.py <world.json> <walkthrough.txt>")
        sys.exit(1)
    sys.exit(run(sys.argv[1], sys.argv[2]))
