"""WAV → webm/opus 64 kbit/s, the type the app's recorder sends in Chromium.

Run outside the project: `uv run --no-project --with av python webm.py <dir>` (PyAV is not a project dependency,
so it is imported by name).
"""
import importlib, sys, pathlib
av = importlib.import_module("av")
d = pathlib.Path(sys.argv[1])
for wav in sorted(d.glob("*.wav")):
    dst = wav.with_suffix(".webm")
    with av.open(str(wav)) as i, av.open(str(dst), "w", format="webm") as o:
        s = o.add_stream("libopus", rate=48000, layout="mono"); s.bit_rate = 64000
        for f in i.decode(audio=0):
            f.pts = None
            for pk in s.encode(f): o.mux(pk)
        for pk in s.encode(None): o.mux(pk)
    print(dst.name, dst.stat().st_size)
