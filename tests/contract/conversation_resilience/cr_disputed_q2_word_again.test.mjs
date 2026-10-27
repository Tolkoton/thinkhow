// Disputed (Q2): after the cut of a sources literal or of a whole sources line, does the word rule of stableText
// apply again to the word now standing at the end? The contract: «stableText застосовує свої зрізи по колу, доки
// текст не перестане коротшати» — this test takes that reading: «текст.» is then the unfinished word and goes too.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { SRC_PATH } from "./cr_page_fakes.mjs";

const require = createRequire(import.meta.url);
const { stableText } = require(SRC_PATH);

test("Q2: after a cut at the end the word rule applies again to the word now at the end", () => {
  assert.equal(stableText("Ось текст.\n"), "Ось ");
  assert.equal(stableText("Ось текст.\n\nДжерела: [a](https://a.ua)"), "Ось ");
});
