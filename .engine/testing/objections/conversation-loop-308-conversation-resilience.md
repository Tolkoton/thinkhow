# Objection package — conversation-loop tests, under slice conversation-resilience (task 308, S2b)

Filed under `conversation-resilience` because `conversation-loop` is PARKED (ledger 2026-10-27T12:38:47Z) and
`testing.py request conversation-loop --tester objection` answers «parked already». The owner answered the parked
question (task 308, question 1, and board 718): «А — так, тести застаріли: свіжий tester переписує ці три тести під
нове правило, решту їхніх перевірок (текст помилки, закритий звук, без перезавантаження, кнопки знову доступні)
лишає». Owner's words, 2026-10-27: «Режим розмови. Так, я згоден, що А хай буде.»

The S2a contract itself names the rule as temporary: `.engine/slices/conversation-loop.md` line 31–32 «Правила
помилок режиму (сигнал і знову слухати, автоматичний retry, пропуск речення) … — S2b. У S2a будь-яка помилка циклу
вимикає режим» and Q7 «помилка в S2a вимикає режим. Чому: найтонший tracer; правила стійкості — S2b на тих самих
станах».

The sealed S2b contract `.engine/slices/conversation-resilience.md` replaces it (lines 59–69):
- `/voice` not 200, network or empty text → `earcons.error()` and `listening` again, no stop; `ui.error` shows the
  fragment's text; three in a row (no successful recognition between) → the mode stops (`ui.error` with the last
  text, `earcons.error()`).
- `/reply` `failed`, network, not 200 (except 409) → one automatic `controller.retry({ spoken: "1" })`; the retry
  fails too → `ui.error(…)`, `earcons.error()`, the mode stops. 409 → error, signal, stop.
- `/speak` not 200, network, `decodeAudioData` fails → the sentence is skipped (no signal), the next one is taken;
  the mode does not stop.
- I3 (line 163–167): «Поки режим не вимкнено, жодна помилка розпізнавання чи голосу (крім трьох поспіль невдалих
  розпізнавань і відмови мікрофона) не переводить його в `off`» — Broken by: «S2a-поведінка «будь-яка помилка
  вимикає режим», що лишилася на якомусь шляху».

Asked: carry each test over to the S2b rule, keeping every other check it makes (the error text in `#error`, the
microphone track stopped, the AudioContext closed, the intervals cleared, no reload, `#mic`/`#send`/the field
enabled again) on a path where the mode really stops under S2b.

Failing now (`uv run pytest -q <test>`):
- `tests/contract/conversation_loop/test_cl_talk.py::test_error_with_a_fragment_shows_its_text_and_stops`
  (`cl_talk.test.mjs` «an error with a fragment (/voice or /speak not 200)…»): one `/voice` 502 now means signal and
  listen again, not a stop; `/speak` 409 now skips the sentence. A stop with a fragment's text under S2b: three
  `/voice` failures in a row (contract line 60–61).
- `tests/contract/conversation_loop/test_cl_talk.py::test_error_without_a_fragment_shows_the_stop_text_and_stops`
  (`cl_talk.test.mjs` «an error without a fragment (failed, decodeAudioData, network)…»): one `failed` now gets one
  automatic `/retry`; `decodeAudioData` failing and `/speak` network failure now skip the sentence. A stop without a
  fragment under S2b: `failed` on the first attempt and on the retry (line 62–65).
- `tests/contract/conversation_loop/test_cl_disputed_q4_enable.py::test_controls_enabled_again_after_an_error_stop`
  (`cl_disputed_q4_enable.test.mjs`): its stop is one `/voice` 502, which no longer stops the mode. The Q4 reading
  («once the mode is off without a reload, #mic, #send, the field are enabled again») stands; only the way to the
  stop changes.
