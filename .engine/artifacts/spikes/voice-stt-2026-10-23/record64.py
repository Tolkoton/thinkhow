"""Real Chromium MediaRecorder: feed a WAV as the fake microphone, record in each supported browser format."""
import base64, sys, pathlib, wave
import importlib
sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright  # not a project dependency
EXE = str(pathlib.Path.home() / ".cache/ms-playwright/chromium-1208/chrome-linux64/chrome")
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
JS = """async ([mime, ms]) => {
  if (!MediaRecorder.isTypeSupported(mime)) return null;
  const s = await navigator.mediaDevices.getUserMedia({audio: true});
  const r = new MediaRecorder(s, {mimeType: mime, audioBitsPerSecond: 64000}); const chunks = [];
  r.ondataavailable = e => chunks.push(e.data);
  const done = new Promise(res => r.onstop = res);
  r.start(); await new Promise(res => setTimeout(res, ms)); r.stop(); await done;
  s.getTracks().forEach(t => t.stop());
  const b = new Uint8Array(await new Blob(chunks, {type: r.mimeType}).arrayBuffer());
  let bin = ''; for (const x of b) bin += String.fromCharCode(x);
  return [r.mimeType, btoa(bin)];
}"""
MIMES = {"webm": "audio/webm;codecs=opus", "mp4": "audio/mp4"}
import http.server, threading, os
os.chdir("/tmp/f13spike/www")
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), http.server.SimpleHTTPRequestHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    for wav in sorted(src.glob("*.wav")):
        secs = wave.open(str(wav)).getnframes() / 24000
        for tag, mime in MIMES.items():
            b = p.chromium.launch(executable_path=EXE, args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={wav}%noloop"])
            page = b.new_context(permissions=["microphone"]).new_page(); page.goto("http://localhost:8765/")
            res = page.evaluate(JS, [mime, int(secs * 1000) + 600])
            b.close()
            if res is None: print(wav.stem, tag, "unsupported"); continue
            data = base64.b64decode(res[1]); (out / f"{wav.stem}.{tag}").write_bytes(data)
            print(wav.stem, tag, res[0], len(data))
