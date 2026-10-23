# Objection package — skel-web sealed tests vs. the F13 language rule (task 106)

Why: a later sealed contract, `.engine/slices/voice-language.md` (feature `voice-and-language`, S1; owner's words in
task 106: «людина обирає свою мову при першому вході»), changes one behaviour these tests were written against:
«`GET /` і `GET /topics/{uid}/{topic_id}` викликають `workspace.language(...)`» and «Один обробник `NoLanguage`:
запит `GET` → 303 на `/language`». A person with a fresh profile (only `email`) now gets 303 on `/` and on a topic
page instead of 200. The voice-language contract names these files as ones to update: «Зміна в них — лише додати
вибір мови; перевірки не послаблюються.»

The skel-web contract (`.engine/slices/skel-web.md`) is unchanged otherwise; every failing test below fails only at
a GET of `/` or a topic page that now answers 303 (checked: `uv run pytest tests/contract/skel_web -q`).

Asked: for each test, choose a language for the person(s) of the test before the GET of a page (e.g.
`POST /language` with `code=uk-UA` and the same identity headers, or `workspace.set_language(storage, user, "uk-UA")`)
and keep every other check as written. Where a test's subject is the profile itself
(`test_every_request_ensures_the_profile_of_the_person`), please keep what it proves — that every request creates the
profile with the person's email — e.g. by a request that does not need a language (`GET /` still runs the login
layer and answers 303; `GET /language` answers 200).

Items (test — contract line of skel-web it checks — why it fails now):
1. tests/contract/skel_web/test_skelweb_invariants.py::test_I1_the_person_is_only_who_identify_says — I1; GET / → 303 for a person without a language.
2. tests/contract/skel_web/test_skelweb_invariants.py::test_I2_texts_and_titles_are_shown_as_text — I2; GET of the topic page → 303.
3. tests/contract/skel_web/test_skelweb_local.py::test_e2e_local_mode_build_deps_topic_reply_close_files — local mode chain; GET page → 303.
4. tests/contract/skel_web/test_skelweb_local.py::test_uvicorn_starts_the_app_in_local_mode_and_home_opens — «home opens»: GET / → 303 now; the page after choosing a language is 200.
5. tests/contract/skel_web/test_skelweb_logging.py::test_request_id_from_cloud_trace_header_or_a_new_uuid4_hex — logs a GET / that now is 303 (the request id part is unaffected; a status assertion of 200 fails).
6. tests/contract/skel_web/test_skelweb_logging.py::test_unexpected_exception_is_logged_as_http_request_status_500 — the GET reaches the 303 before the planted failure.
7. tests/contract/skel_web/test_skelweb_routes.py::test_home_lists_my_topics_and_the_new_topic_form — GET / → 303.
8. tests/contract/skel_web/test_skelweb_routes.py::test_owner_home_has_all_topics_with_title_and_uid — GET / → 303.
9. tests/contract/skel_web/test_skelweb_routes.py::test_html_routes_are_text_html_utf8 — GET / and topic → 303.
10. tests/contract/skel_web/test_skelweb_routes.py::test_every_request_ensures_the_profile_of_the_person — asserts GET / == 200 before reading the profile.
11. tests/contract/skel_web/test_skelweb_routes.py::test_topic_page_title_turn_anchors_roles_and_texts — topic page → 303.
12. tests/contract/skel_web/test_skelweb_routes.py::test_own_topic_page_has_reply_form_send_and_close — topic page → 303.
13. tests/contract/skel_web/test_skelweb_routes.py::test_topic_awaiting_answer_shows_try_again — topic page → 303.
14. tests/contract/skel_web/test_skelweb_routes.py::test_owner_on_a_foreign_topic_sees_it_without_form_and_buttons — topic page → 303 (the owner has no language).
15. tests/contract/skel_web/test_skelweb_routes.py::test_foreign_topic_page_is_404_fragment — the language check runs before the topic is opened, so 303 instead of 404 for a person without a language; with a language chosen it is 404 as before.
16. tests/contract/skel_web/test_skelweb_routes.py::test_value_error_on_another_route_is_400_request_not_accepted — reaches a GET page → 303.
17. tests/contract/skel_web/test_skelweb_routes.py::test_unexpected_exception_is_500_fragment_without_trace — the planted failure sits behind a GET page → 303.
