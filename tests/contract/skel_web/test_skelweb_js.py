"""Contract tests of skel-web, Seam 5: the SSE parser of conversation.js under `node --test`."""

from pathlib import Path

from skelweb_fakes import run_node_test

HERE = Path(__file__).parent


def test_sse_parser_same_events_at_every_byte_and_pair_of_bytes() -> None:
    run_node_test(
        HERE / "skelweb_parser.test.mjs", "sse parser: same events at every byte and every pair of bytes"
    )
