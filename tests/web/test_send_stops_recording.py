"""Tasks 206 and 207: «Надіслати» while the microphone is busy stops the recording, sends nothing;
the mic shows its state without words (`node --test`)."""

import os
import shutil
import subprocess
from pathlib import Path

FILE = Path(__file__).with_name("send_stops_recording.test.mjs")


def test_send_while_the_microphone_is_busy_sends_nothing() -> None:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    assert node, "node not found on PATH nor in THINKHOW_NODE"
    proc = subprocess.run([node, "--test", str(FILE)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
