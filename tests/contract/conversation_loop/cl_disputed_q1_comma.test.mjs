// Disputed (Q1): on a cut «по останній коми» the comma stays at the end of the left piece. Not sealed until Q1.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { splitSentences } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

test("a piece cut at a comma ends with that comma", () => {
  const clause = "ж".repeat(48) + ",";
  const text = Array(25).fill(clause).join(" ").slice(0, -1) + ".";
  const r = splitSentences(text, true);
  assert.ok(r.sentences.length >= 3, `${r.sentences.length} pieces`);
  for (const s of r.sentences.slice(0, -1)) assert.ok(s.endsWith(","), JSON.stringify(s.slice(-10)));
  for (const s of r.sentences.slice(1)) assert.ok(!s.startsWith(","), JSON.stringify(s.slice(0, 10)));
});
