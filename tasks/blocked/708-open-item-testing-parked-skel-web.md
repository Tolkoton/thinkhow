# 708 — slice skel-web: третя суперечка про contract tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: testing-parked-skel-web

## Що сталося
Два кола суперечки між builder-ом і tester-ом не розв'язали slice skel-web: round 1: tests/contract/skel_web/skelweb_fakes.py:170 (seed_topic helper) — test_wrong; tests/contract/skel_web/test_skelweb_routes.py:34 (url helper) — test_wrong | round 2: tests/contract/skel_web/test_skelweb_invariants.py::test_I1_the_person_is_only_who_identify_says — test_wrong; tests/contract/skel_web/test_skelweb_invariants.py::test_I2_texts_and_titles_are_shown_as_text — test_wrong; tests/contract/skel_web/test_skelweb_local.py::test_e2e_local_mode_build_deps_topic_reply_close_files — test_wrong; tests/contract/skel_web/test_skelweb_local.py::test_uvicorn_starts_the_app_in_local_mode_and_home_opens — test_wrong; tests/contract/skel_web/test_skelweb_logging.py::test_request_id_from_cloud_trace_header_or_a_new_uuid4_hex — test_wrong; tests/contract/skel_web/test_skelweb_logging.py::test_unexpected_exception_is_logged_as_http_request_status_500 — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_home_lists_my_topics_and_the_new_topic_form — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_owner_home_has_all_topics_with_title_and_uid — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_html_routes_are_text_html_utf8 — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_every_request_ensures_the_profile_of_the_person — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_topic_page_title_turn_anchors_roles_and_texts — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_own_topic_page_has_reply_form_send_and_close — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_topic_awaiting_answer_shows_try_again — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_owner_on_a_foreign_topic_sees_it_without_form_and_buttons — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_foreign_topic_page_is_404_fragment — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_value_error_on_another_route_is_400_request_not_accepted — test_wrong; tests/contract/skel_web/test_skelweb_routes.py::test_unexpected_exception_is_500_fragment_without_trace — test_wrong. Третє коло не проводиться: slice відкладено, робота йде далі з наступним. Обидва кола стоять у .engine/testing/ledger.md.

- Записано: 2026-10-23T22:29:39Z, hook testing.py

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Хто правий у суперечці про тести slice-а skel-web — тест, код чи slice contract слід уточнити?
   Відповідь:
