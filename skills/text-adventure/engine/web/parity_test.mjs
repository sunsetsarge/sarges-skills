// parity_test.mjs -- cross-runtime regression test for the text-adventure skill.
//
// Proves engine/web/template.html's JavaScript engine reaches the SAME
// outcome as engine/engine.py (the authoritative Python runtime) when fed
// the exact same world JSON and the exact same walkthrough command list.
//
// How it works:
//   1. Reads template.html as plain text.
//   2. Extracts the inline JS between the ENGINE-CORE-START / ENGINE-CORE-END
//      markers (the pure engine logic -- no DOM references), plus the
//      `if (typeof module !== "undefined" ...) { module.exports = {...} }`
//      export block that immediately follows it.
//   3. Runs that extracted source in a real Node CommonJS module (via
//      `Module._compile`, stdlib-only, no npm deps) so `module`/`exports`
//      resolve exactly like a required .js file would.
//   4. Loads examples/the-cellar.json and feeds it the same commands as
//      examples/the-cellar.walkthrough.txt.
//   5. Asserts: win reached, final score == 10, turn count == 11 (matching
///     the Python walkthrough_runner.py result for the same world+walkthrough).
//
// This file SHIPS with the skill as the permanent cross-runtime regression
// test -- run it any time template.html or a world's rules change:
//     node engine/web/parity_test.mjs
//
// stdlib-only: no npm install required (uses only Node's built-in `fs`,
// `path`, `module`, and `url`).

import fs from "node:fs";
import path from "node:path";
import Module from "node:module";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE_PATH = path.join(__dirname, "template.html");
const WORLD_PATH = path.join(__dirname, "..", "..", "examples", "the-cellar.json");
const WALKTHROUGH_PATH = path.join(__dirname, "..", "..", "examples", "the-cellar.walkthrough.txt");

const START_MARKER = "// === ENGINE-CORE-START ===";
const END_MARKER = "// === ENGINE-CORE-END ===";
const EXPORT_END_MARKER = "return;\n  }";

function extractEngineCore(html) {
  const startIdx = html.indexOf(START_MARKER);
  if (startIdx === -1) throw new Error("ENGINE-CORE-START marker not found in template.html");
  const endIdx = html.indexOf(END_MARKER, startIdx);
  if (endIdx === -1) throw new Error("ENGINE-CORE-END marker not found in template.html");

  // Core engine logic (world model, parser, rules, default verbs, Engine class).
  const core = html.slice(startIdx, endIdx);

  // The module.exports block sits immediately after ENGINE-CORE-END, inside
  // the same enclosing IIFE, ending at the first "return;\n  }" after it.
  const afterEnd = html.slice(endIdx);
  const exportBlockStart = afterEnd.indexOf("if (typeof module");
  if (exportBlockStart === -1) throw new Error("module.exports guard block not found after ENGINE-CORE-END");
  const exportBlockRelEnd = afterEnd.indexOf(EXPORT_END_MARKER, exportBlockStart);
  if (exportBlockRelEnd === -1) throw new Error("Could not find end of module.exports guard block");
  const exportBlock = afterEnd.slice(exportBlockStart, exportBlockRelEnd + EXPORT_END_MARKER.length);

  return core + "\n" + exportBlock + "\n";
}

function loadEngineCoreAsModule(source) {
  const m = new Module(TEMPLATE_PATH + ".engine-core.js", null);
  m.filename = TEMPLATE_PATH + ".engine-core.js";
  m.paths = Module._nodeModulePaths(__dirname);
  m._compile(source, m.filename);
  return m.exports;
}

function loadWalkthrough(p) {
  const lines = fs.readFileSync(p, "utf-8").split(/\r?\n/);
  const commands = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    commands.push(line);
  }
  return commands;
}

function main() {
  const html = fs.readFileSync(TEMPLATE_PATH, "utf-8");
  const engineSource = extractEngineCore(html);
  const engineCore = loadEngineCoreAsModule(engineSource);
  const { World, Engine, GameOverSignal } = engineCore;

  if (!World || !Engine) {
    console.log("FAIL: extracted engine-core did not export World/Engine.");
    process.exit(1);
  }

  const worldJson = JSON.parse(fs.readFileSync(WORLD_PATH, "utf-8"));
  const commands = loadWalkthrough(WALKTHROUGH_PATH);

  const world = new World(worldJson);
  const engine = new Engine(world);

  const transcript = [];
  transcript.push(["<start>", engine.startMessage()]);

  for (const cmd of commands) {
    try {
      const out = engine.executeLine(cmd);
      transcript.push([cmd, out]);
    } catch (e) {
      if (e instanceof GameOverSignal) {
        transcript.push([cmd, `<GameOver: ${e.kind}>`]);
        console.log("FAIL: walkthrough issued quit/restart before reaching a win state.");
        printTranscript(transcript);
        process.exit(1);
      }
      transcript.push([cmd, `<EXCEPTION: ${e && e.message}>`]);
      console.log(`FAIL: unhandled exception on command ${JSON.stringify(cmd)}: ${e && e.stack}`);
      printTranscript(transcript);
      process.exit(1);
    }
  }

  const EXPECTED_SCORE = 10;
  const EXPECTED_TURNS = 11;

  if (!world.gameOver || !world.win) {
    console.log("FAIL: game did not reach a win state.");
    printTranscript(transcript);
    process.exit(1);
  }
  if (world.score !== EXPECTED_SCORE) {
    console.log(`FAIL: expected score ${EXPECTED_SCORE}, got ${world.score}.`);
    printTranscript(transcript);
    process.exit(1);
  }
  if (world.turns !== EXPECTED_TURNS) {
    console.log(`FAIL: expected ${EXPECTED_TURNS} turns, got ${world.turns}.`);
    printTranscript(transcript);
    process.exit(1);
  }

  console.log(`PASS: browser-runtime walkthrough completed in ${world.turns} turns, score ${world.score}/${world.maxScore}.`);
  console.log(`End message: ${world.endMessage}`);
  process.exit(0);
}

function printTranscript(transcript) {
  console.log("\n----- TRANSCRIPT -----");
  for (const [cmd, output] of transcript) {
    console.log(`> ${cmd}`);
    console.log(output);
    console.log("");
  }
  console.log("----- END TRANSCRIPT -----");
}

main();
