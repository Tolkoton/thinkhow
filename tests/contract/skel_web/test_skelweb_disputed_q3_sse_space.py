"""Disputed (Q3): the SSE parser accepts `event:x` and `data:{…}` with no space. Not sealed until Q3."""

from pathlib import Path

from skelweb_fakes import run_node_test

HERE = Path(__file__).parent


def test_sse_parser_fields_without_a_space_after_the_colon() -> None:
    run_node_test(
        HERE / "skelweb_disputed_q3_sse_space.test.mjs", "sse parser: fields without a space after the colon"
    )
