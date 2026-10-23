"""DISPUTED (Q2): after a 200 with text the held recording is forgotten — recognize() posts nothing.

Not sealed until the slice planner answers Q2.
"""

from vd_fakes import HERE, run_node_test


def test_q2_after_text_recognize_posts_nothing() -> None:
    run_node_test(
        HERE / "vd_disputed_q2_forget.test.mjs",
        "Q2: after a 200 with text the recording is forgotten — recognize() posts nothing",
    )
