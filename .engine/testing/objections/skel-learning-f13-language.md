# Objection package — skel-learning sealed test vs. the F13 language rule (task 106)

Why: a later sealed contract, `.engine/slices/voice-language.md` (feature `voice-and-language`, S1; owner's words in
task 106: «людина обирає свою мову при першому вході»), changes one behaviour this test was written against:
«`GET /` і `GET /topics/{uid}/{topic_id}` викликають `workspace.language(...)`» and «Один обробник `NoLanguage`:
запит `GET` → 303 на `/language`». It names this test among those to update: «Зміна в них — лише додати вибір
мови; перевірки не послаблюються.» The same change was ruled `test_wrong` for 17 skel-web tests (round 2 of
skel-web, `.engine/testing/ledger.md`).

Asked: choose a language for the local person before the GET of the topic page (e.g. `POST /language` with
`code=uk-UA`) and keep every other check as written.

Items:
1. tests/contract/skel_learning/test_skell_chain.py::test_seam4_local_chain_ends_in_an_observation_whose_link_opens_an_existing_turn — Seam 4 of skel-learning («the observation's link opens an existing turn»); the final GET of the topic page answers 303 to `/language` for a person without a language, so the anchor is not found.
