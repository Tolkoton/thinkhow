// Disputed (Q2): I3 «з точністю до пробілів» read word by word: the pieces joined by a space give the same
// sequence of words (split on whitespace) — no two words glued together when a delta ends right after a space.
// Not sealed until Q2.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { splitSentences } = require(path.resolve(here, "../../../src/thinkhow/web/static/conversation.js"));

const words = (s) => s.split(/\s+/).filter(Boolean);

function spoken(deltas) {
  const out = [];
  let tail = "";
  for (const d of deltas) {
    const r = splitSentences(tail + d, false);
    out.push(...r.sentences);
    tail = r.rest;
  }
  out.push(...splitSentences(tail, true).sentences);
  return out;
}

test("the pieces joined by a space keep every word apart, deltas cut right after a space", () => {
  const texts = [
    "Привіт. Як справи у тебе сьогодні? Добре… і далі без крапки",
    "Рядок один\n\nРядок два.\nТри слова тут",
    Array(150).fill("слово").join(" ") + ". Останнє речення тут",
  ];
  for (const text of texts) {
    const afterSpaces = text.split(/(?<=\s)/);
    const beforeSpaces = text.split(/(?=\s)/);
    for (const deltas of [afterSpaces, beforeSpaces, [text]]) {
      assert.deepEqual(words(spoken(deltas).join(" ")), words(text), JSON.stringify(text.slice(0, 30)));
    }
  }
});
