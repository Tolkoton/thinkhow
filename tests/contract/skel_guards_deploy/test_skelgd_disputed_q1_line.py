"""Disputed contract test of skel-guards-deploy (Q1): `StorageCall.line` is the 1-based line
where the call starts.

Not sealed until the slice planner answers Q1: the contract names `line` and does not say how it is counted.
"""

from skelgd_files import guards_module


def test_q1_storage_call_line_is_the_one_based_line_where_the_call_starts() -> None:
    source = (
        "import x\n"
        "\n"
        "def f(storage):\n"
        "    storage.write(\n"
        '        "users",\n'
        '        "p",\n'
        '        b"",\n'
        '        "t",\n'
        "    )\n"
        '    storage.read("system", "q")\n'
    )
    calls = guards_module().storage_calls(source)
    assert sorted((c.method, c.line) for c in calls) == [("read", 10), ("write", 4)]
