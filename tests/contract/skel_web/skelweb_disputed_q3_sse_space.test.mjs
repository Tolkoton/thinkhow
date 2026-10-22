// Disputed (Q3): createSseParser accepts the field value with no space after the colon (SSE standard).
// Not sealed until the slice planner answers Q3.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { createSseParser } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

test("sse parser: fields without a space after the colon", () => {
  const body = 'event:saved\ndata:{"turn":1}\n\nevent:delta\ndata:{"text":"так 🌍"}\n\n';
  const bytes = new TextEncoder().encode(body);
  const parser = createSseParser();
  const out = [];
  for (let i = 0; i < bytes.length; i++) out.push(...parser.push(bytes.slice(i, i + 1)));
  assert.deepStrictEqual(out, [
    { event: "saved", data: { turn: 1 } },
    { event: "delta", data: { text: "так 🌍" } },
  ]);
});
