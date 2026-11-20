"""
End-to-end test: play the experiment in headless Chrome as simulated
participants and collect the data jsPsych records.

  python study/browser_test.py --participants 6 --out /tmp/sim
  python study/analyze.py /tmp/sim/*.csv

The simulated participant answers from a fixed rule (it reads the trial's
pair type), so the test checks that the experiment runs, records what the
analysis needs, and that the analysis recovers known differences.
"""

import argparse
import functools
import json
import http.server
import os
import random
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"
# probability of answering "same" on a hard mismatch, per representation
P_ACCEPT_HARD = {"hex": 0.10, "walk": 0.25, "life_mirrored": 0.40, "life_unmirrored": 0.15, "voronoi": 0.20}


RECEIVED = []
TRACE = False


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            # stand-in for the Google Apps Script endpoint (study/save_to_drive.gs)
            body = self.rfile.read(int(self.headers["Content-Length"]))
            RECEIVED.append(json.loads(body))
            out = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    handler = functools.partial(Quiet, directory=str(DOCS))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def play(page, base, pid, quick, rng, shots, save_url=None):
    q = f"?PROLIFIC_PID={pid}&SESSION_ID=S{pid}" + ("&quick=1" if quick else "")
    q += f"&save_url={save_url}" if save_url else "&debug=1"
    page.goto(base + q)
    n_compare = 0
    for _ in range(2000):
        page.wait_for_timeout(15)
        if page.locator("#jspsych-data-display").count():
            break
        try:
            trial = page.evaluate("() => { const t = jsPsych.getCurrentTrial(); return t ? t.data : null; }") or {}
        except Exception as e:  # page still loading its scripts
            if "jsPsych is not defined" not in str(e):
                raise
            print("  (jsPsych not ready at", page.url[:60], ")") if TRACE else None
            page.wait_for_timeout(200)
            continue
        task = trial.get("task")

        if task == "compare":
            key = (trial["rep"], trial["pair_type"])
            if shots is not None and trial["pair_type"] in ("phash_hard", "hex_hard", "ssim_hard") and key not in shots:
                page.screenshot(path=f"{shots_dir}/{pid}_{trial['rep']}_{trial['pair_type']}.png")
                shots.add(key)
            n_compare += 1
            same = trial["pair_type"] == "same"
            p_same = 0.95 if same else (0.02 if trial["pair_type"] == "random" else P_ACCEPT_HARD[trial["rep"]])
            page.wait_for_timeout(rng.randint(250, 450))  # human-like response time
            page.keyboard.press("f" if rng.random() < p_same else "j")
        elif task == "attention":
            page.wait_for_timeout(300)
            page.keyboard.press(trial.get("expected_key", "j"))
        elif task == "end" and save_url:
            end_text = page.inner_text("#jspsych-content")
            if "Return to Prolific" in end_text or "Finish" in end_text:
                page.evaluate("() => { window.__noRedirect = true; }")
                return end_text, n_compare
        elif task == "feedback":
            page.wait_for_timeout(1600)
        elif page.locator("#jspsych-instructions-next").count():
            page.click("#jspsych-instructions-next")
        elif page.locator("#jspsych-survey-text-next").count():
            page.click("#jspsych-survey-text-next")
        elif page.locator("button.jspsych-btn").count():
            page.locator("button.jspsych-btn").first.click()
    else:
        raise RuntimeError("experiment did not finish")
    return page.evaluate("() => jsPsych.data.get().csv()"), n_compare


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--participants", type=int, default=3)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="/tmp/sim")
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    ap.add_argument("--save-test", action="store_true",
                    help="run one participant in normal mode and check the data reaches the save endpoint")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    shots_dir = os.path.join(a.out, "shots")
    os.makedirs(shots_dir, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=a.chrome, args=["--no-sandbox"])
        if a.save_test:
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("pageerror", lambda e: errors.append(str(e)))
            end_text, n = play(page, base, "SAVETEST", True, random.Random(0), None, save_url=base + "save")
            assert RECEIVED, "nothing was posted to the save endpoint"
            got = RECEIVED[-1]
            assert got["filename"] == "SAVETEST_SSAVETEST.csv", got["filename"]
            assert got["data"].count("\n") > 20 and "compare" in got["data"]
            assert "answers are saved" in end_text, end_text
            print(f"save test OK: {got['filename']}, {len(got['data'])} bytes, end screen: {end_text.splitlines()[0]}")
            page.close()
            a.participants = 0
        for i in range(a.participants):
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and "favicon" not in (m.location or {}).get("url", "")
                    and errors.append(m.text))
            csv, n = play(page, base, f"SIM{i:03d}", a.quick, random.Random(i), set() if i == 0 else None)
            Path(a.out, f"SIM{i:03d}.csv").write_text(csv)
            print(f"SIM{i:03d}: {n} comparison trials", flush=True)
            page.close()
        browser.close()
    httpd.shutdown()
    if errors:
        print("browser errors:", *sorted(set(errors)), sep="\n  ")
        raise SystemExit(1)
    print("no browser errors")
