# Objection package — voice-synthesis sealed test vs. the interface language rule (task 208)

Why: the owner's decision in task 208 (`tasks/doing/208-interface-language.md`, «Рішення власника», 2026-10-27:
«Інтерфейс мовою людини точно так.» — to the proposal «усі написи, підказки, повідомлення про помилки … мовою, яку обрала
людина») changes one behaviour a sealed test was written against: an error fragment is now in the language the person
chose, not always in Ukrainian. The voice-synthesis contract line (`.engine/slices/voice-synthesis.md`, line 85:
«`NoVoice` → 409 фрагмент «Для вашої мови немає голосу.»») stays true for a person whose language is Ukrainian; for any
other person the same message comes from that language's catalog (`src/thinkhow/web/locales/<name>.json`, key
`err_no_voice`; the Ukrainian source `uk.json` holds exactly «Для вашої мови немає голосу.»).

The status (409), the fragment shape (`<p class="error">…</p>`) and «no synthesis call» are unchanged. Checked:
`uv run pytest tests/contract/voice_synthesis -q` → the one test below fails, every other test passes.

Items (test — contract line — why it fails now):
1. tests/contract/voice_synthesis/test_vs_web.py::test_seam5_language_without_voice_is_409_fragment — line 85 (NoVoice → 409
   fragment). The person chose kk-KZ, so the fragment is now Kazakh: `<p class="error">Сіздің тіліңізге арналған дауыс жоқ.</p>`; the test expects the
   Ukrainian words (`vs_fakes.NO_VOICE_TEXT`).

Asked: keep what the test proves — 409, an error fragment, the text of the no-voice message — and take the expected text in
the person's language: e.g. read `err_no_voice` from `src/thinkhow/web/locales/kk.json` (or `thinkhow.web.ui_text.texts("kk")`); keep kk-KZ (it has no voice).

