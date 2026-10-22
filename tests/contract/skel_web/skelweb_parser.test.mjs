// Contract tests of skel-web, Seam 5: createSseParser of conversation.js (slice tester; from the contract).
// Run one test: node --test --test-name-pattern='^<name>$' tests/contract/skel_web/skelweb_parser.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createSseParser } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

// Ukrainian, emoji (4 bytes in UTF-8), a line break inside a delta (JSON-escaped in one data: line).
const BODY =
  'event: saved\ndata: {"turn": 1}\n\n' +
  'event: delta\ndata: {"text": "Привіт,\\nсвіте 🌍 — «так»"}\n\n' +
  'event: delta\ndata: {"text": "ще 😀"}\n\n' +
  'event: answered\ndata: {"turn": 2}\n\n';

const EXPECTED = [
  { event: "saved", data: { turn: 1 } },
  { event: "delta", data: { text: "Привіт,\nсвіте 🌍 — «так»" } },
  { event: "delta", data: { text: "ще 😀" } },
  { event: "answered", data: { turn: 2 } },
];

function parseChunks(chunks) {
  const parser = createSseParser();
  const out = [];
  for (const chunk of chunks) out.push(...parser.push(chunk));
  return out;
}

test("sse parser: same events at every byte and every pair of bytes", () => {
  const bytes = new TextEncoder().encode(BODY);
  const n = bytes.length;
  assert.deepStrictEqual(parseChunks([bytes.slice()]), EXPECTED, "one chunk");
  const single = [];
  for (let i = 0; i < n; i++) single.push(bytes.slice(i, i + 1));
  assert.deepStrictEqual(parseChunks(single), EXPECTED, "one byte per chunk");
  for (let i = 1; i < n; i++) {
    const got = parseChunks([bytes.slice(0, i), bytes.slice(i)]);
    assert.deepStrictEqual(got, EXPECTED, `cut at byte ${i}`);
  }
  for (let i = 1; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const got = parseChunks([bytes.slice(0, i), bytes.slice(i, j), bytes.slice(j)]);
      assert.deepStrictEqual(got, EXPECTED, `cut at bytes ${i} and ${j}`);
    }
  }
});
