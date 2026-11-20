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
import http.server
import os
import random
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"
# probability of answering "same" on a hard mismatch, per representation
P_ACCEPT_HARD = {"hex": 0.10, "walk": 0.25, "life_mirrored": 0.40, "life_unmirrored": 0.15, "voronoi": 0.20}


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(DOCS))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def play(page, base, pid, quick, rng, shots):
    q = f"?debug=1&PROLIFIC_PID={pid}&SESSION_ID=S{pid}" + ("&quick=1" if quick else "")
    page.goto(base + q)
    n_compare = 0
    for _ in range(2000):
        page.wait_for_timeout(15)
        if page.locator("#jspsych-data-display").count():
            break
        trial = page.evaluate("() => { const t = jsPsych.getCurrentTrial(); return t ? t.data : null; }") or {}
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
            page.keyboard.press("j")
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
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    shots_dir = os.path.join(a.out, "shots")
    os.makedirs(shots_dir, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=a.chrome, args=["--no-sandbox"])
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
