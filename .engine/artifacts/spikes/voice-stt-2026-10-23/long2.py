import sys, wave, pathlib, av
a = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); order = [int(x) for x in sys.argv[3].split(",")]; name = sys.argv[4]
frames = b""; pause = b"\x00\x00" * 16800
for k in order:
    w = wave.open(str(a / f"uk{k}.wav")); frames += w.readframes(w.getnframes()) + pause
with wave.open(str(out / f"{name}.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(frames)
with av.open(str(out / f"{name}.wav")) as i, av.open(str(out / f"{name}.webm"), "w", format="webm") as o:
    s = o.add_stream("libopus", rate=48000, layout="mono"); rs = av.AudioResampler(format="s16", layout="mono", rate=48000)
    for f in i.decode(audio=0):
        for g in rs.resample(f):
            g.pts = None
            for pk in s.encode(g): o.mux(pk)
    for pk in s.encode(None): o.mux(pk)
print(name, "secs", round(len(frames) / 48000, 1))
