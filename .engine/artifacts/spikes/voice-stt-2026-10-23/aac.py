import sys, pathlib, av
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for wav in sorted(src.glob("*.wav")):
    dst = out / f"{wav.stem}.m4a"
    with av.open(str(wav)) as i, av.open(str(dst), "w", format="mp4") as o:
        s = o.add_stream("aac", rate=24000, layout="mono"); s.bit_rate = 64000
        for f in i.decode(audio=0):
            f.pts = None
            for pk in s.encode(f): o.mux(pk)
        for pk in s.encode(None): o.mux(pk)
    print(dst.name, dst.stat().st_size)
