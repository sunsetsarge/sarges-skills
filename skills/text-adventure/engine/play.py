#!/usr/bin/env python
"""
play.py -- thin CLI runtime for the text-adventure engine.

Usage:
    python play.py <world.json> [--save <savefile.json>]

All game logic lives in engine.py; this file only wires stdin/stdout to the
Engine, and adds two Python-only conveniences: `save <path>` / `load <path>`
write/read a JSON snapshot to disk (the browser runtime uses localStorage
instead, see engine/web/template.html).

Never lets an exception surface as a raw traceback to the player -- any
unexpected error is caught and reported as a friendly, generic message so
malformed input can never crash a session.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as eng


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Play a text-adventure world file.")
    parser.add_argument("world_path", help="Path to a world JSON file.")
    parser.add_argument("--save", dest="save_path", default=None,
                         help="Default save/load path used by bare 'save'/'load' commands.")
    args = parser.parse_args(argv)

    world_path = args.world_path
    if not os.path.exists(world_path):
        print(f"World file not found: {world_path}")
        return 1

    default_save = args.save_path or (os.path.splitext(world_path)[0] + ".save.json")

    while True:
        try:
            world = eng.load_world(world_path)
        except Exception as e:  # malformed world JSON must not crash the CLI
            print(f"Could not load world file: {e}")
            return 1

        hooks = None
        try:
            hooks = eng.load_hooks(world_path)
        except Exception:
            hooks = None  # hooks.py is optional; a broken one is ignored, not fatal

        game = eng.Engine(world, hooks=hooks)
        print(game.start_message())

        try:
            restart = run_loop(game, default_save)
        except eng.GameOver as go:
            restart = (go.kind == "restart")
            if go.kind == "quit":
                print("Goodbye.")
                return 0

        if not restart:
            return 0
        print("\nRestarting...\n")


def run_loop(game: "eng.Engine", default_save: str) -> bool:
    """Returns True if the player asked to restart (raised via GameOver),
    otherwise loops until quit/EOF. Never lets a random exception escape to
    a raw traceback -- unexpected errors are shown as a friendly message and
    play continues."""
    while True:
        try:
            line = input("\n> ")
        except EOFError:
            print("\nGoodbye.")
            raise eng.GameOver("quit")
        except KeyboardInterrupt:
            print("\nGoodbye.")
            raise eng.GameOver("quit")

        low = line.strip().lower()

        # Python-only file save/load conveniences (not part of engine.py's
        # in-memory undo/meta-verb handling, since file I/O is host-specific).
        if low == "save" or low.startswith("save "):
            parts = line.strip().split(maxsplit=1)
            path = parts[1] if len(parts) > 1 else default_save
            try:
                eng.save_game(game.world, path)
                print(f"Saved to {path}.")
            except Exception as e:
                print(f"Could not save: {e}")
            continue

        if low == "load" or low.startswith("load "):
            parts = line.strip().split(maxsplit=1)
            path = parts[1] if len(parts) > 1 else default_save
            try:
                eng.load_game(game.world, path)
                print(f"Loaded from {path}.")
                print(eng.room_full_description(game.world))
            except Exception as e:
                print(f"Could not load: {e}")
            continue

        try:
            output = game.execute_line(line)
        except eng.GameOver:
            raise
        except Exception as e:  # last-resort safety net -- never show a traceback
            output = f"Something went wrong processing that command ({e}). Try something else."

        if output:
            print(output)

        if game.world.game_over:
            print("\nType 'restart' to play again, or 'quit' to exit.")


if __name__ == "__main__":
    sys.exit(main())
