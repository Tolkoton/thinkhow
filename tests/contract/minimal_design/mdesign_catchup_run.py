"""Helper for the minimal-design catch-up tests of the screenshot script (slice tester), from the contract.

`run_script` runs `scripts/screenshots_minimal_design.py` the way the contract's «Exit criterion» does —
`uv run --with playwright==1.64.1 python scripts/screenshots_minimal_design.py --out <dir>` from the
repository root — with a folder of the test first on `PYTHONPATH`. Its `sitecustomize.py`:

- in every Python process that loads it, wraps `subprocess.Popen` so that a child process (the server, however
  the script launches it) gets the same folder first on its `PYTHONPATH`;
- patches `starlette.staticfiles.StaticFiles.lookup_path`, so that `/static/style.css` is served from a copy
  the test wrote: the real `style.css` with one breakage laid on it (or none, for the clean run). Every time
  that copy is served, a line is appended to a mark file, so a test knows the breakage really reached the
  browser.

The breakage is CSS only: the script's own checks (Seams 1-3) are judged by what the script does when the page
misbehaves in exactly one named way.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = "scripts/screenshots_minimal_design.py"
STYLE = REPO / "src" / "thinkhow" / "web" / "static" / "style.css"

SCREENS = {
    "home-desktop-light.png",
    "home-desktop-dark.png",
    "home-phone-light.png",
    "home-phone-dark.png",
    "topic-desktop-light.png",
    "topic-desktop-dark.png",
    "topic-phone-light.png",
    "topic-phone-dark.png",
    "topic-pending-phone-light.png",
}

SITECUSTOMIZE = """
import os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))

try:
    import subprocess as _sp

    _orig_init = _sp.Popen.__init__

    def _init(self, *args, **kwargs):
        env = kwargs.get("env")
        env = dict(_os.environ if env is None else env)
        parts = [p for p in env.get("PYTHONPATH", "").split(_os.pathsep) if p]
        if _HERE not in parts:
            env["PYTHONPATH"] = _os.pathsep.join([_HERE, *parts])
        env.setdefault("MDCU_CSS", _os.environ.get("MDCU_CSS", ""))
        env.setdefault("MDCU_MARK", _os.environ.get("MDCU_MARK", ""))
        kwargs["env"] = env
        _orig_init(self, *args, **kwargs)

    _sp.Popen.__init__ = _init
except Exception:
    pass

try:
    import starlette.staticfiles as _sf

    _orig_lookup = _sf.StaticFiles.lookup_path

    def _lookup(self, path):
        css = _os.environ.get("MDCU_CSS", "")
        if css and path.replace("\\\\", "/").rstrip("/").endswith("style.css"):
            with open(_os.environ["MDCU_MARK"], "a", encoding="utf-8") as f:
                f.write(str(_os.getpid()) + "\\n")
            return css, _os.stat(css)
        return _orig_lookup(self, path)

    _sf.StaticFiles.lookup_path = _lookup
except Exception:
    pass
"""

# Phone-only and the 360 px context only, as media queries laid over the real sheet.
PHONE = "@media (max-width: 400px)"
PHONE_360 = "@media (max-width: 370px)"
PHONE_DARK = "@media (max-width: 400px) and (prefers-color-scheme: dark)"
# Nothing on the way may clip an overflow the breakage causes.
NO_CLIP = "html, body, main, form, ul, ol, li, .actions, header { overflow: visible !important; }"


@dataclass
class Run:
    code: int
    out: str
    served: int  # how many times the test's copy of style.css was served
    screens: Path


def broken_css(breakage: str | None, *, drop_dark: bool = False) -> str:
    css = STYLE.read_text(encoding="utf-8")
    if drop_dark:
        pattern = re.compile(r"prefers-color-scheme\s*:\s*dark")
        assert pattern.search(css), "style.css has no prefers-color-scheme: dark block to switch off"
        css = pattern.sub("prefers-color-scheme: mdcu-never", css)
    if breakage:
        css += "\n/* --- the test's breakage --- */\n" + breakage + "\n"
    return css


def run_script(tmp_path: Path, breakage: str | None = None, *, drop_dark: bool = False) -> Run:
    hook = tmp_path / "hook"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    css = tmp_path / "style.css"
    css.write_text(broken_css(breakage, drop_dark=drop_dark), encoding="utf-8")
    mark = tmp_path / "served.txt"
    mark.write_text("", encoding="utf-8")
    screens = tmp_path / "screens"
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(hook), *[p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]]
    )
    env["MDCU_CSS"] = str(css)
    env["MDCU_MARK"] = str(mark)
    proc = subprocess.run(
        [uv, "run", "--with", "playwright==1.64.1", "python", SCRIPT, "--out", str(screens)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    served = len([line for line in mark.read_text(encoding="utf-8").splitlines() if line.strip()])
    return Run(proc.returncode, proc.stdout + "\n--- stderr ---\n" + proc.stderr[-6000:], served, screens)


def png(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
