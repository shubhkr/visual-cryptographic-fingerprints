// Visual-fingerprint comparison study (jsPsych 8).
// Before launch, set the three values in CONFIG. See study/README.md.
"use strict";

const CONFIG = {
  // ACTION: web-app URL of the Google Apps Script in study/save_to_drive.gs
  SAVE_URL: "https://script.google.com/macros/s/AKfycbxAk2yTh4d9gVA2rl1YlxDcnQlhpq0Mxjju-RhtK5OH1_gTSO1hrG6fU4nKO_NAeDsbrw/exec",
  PROLIFIC_COMPLETION_CODE: "C1L65YLF",
  // ACTION: researcher contact shown on the consent page
  CONTACT: "shubhambtps@live.in",
  DISPLAY_PX: 192,
  MIN_WINDOW_WIDTH: 900,
};

const jsPsych = initJsPsych({
  on_finish: () => {
    if (DEBUG) {
      jsPsych.data.displayData("csv");
    } else if (PROLIFIC_PID) {
      window.location = `https://app.prolific.com/submissions/complete?cc=${CONFIG.PROLIFIC_COMPLETION_CODE}`;
    }
  },
});

const url = (k) => jsPsych.data.getURLVariable(k);
const PROLIFIC_PID = url("PROLIFIC_PID") || "";
const STUDY_ID = url("STUDY_ID") || "";
const SESSION_ID = url("SESSION_ID") || "";
const DEBUG = url("debug") === "1";
const QUICK = url("quick") === "1"; // two trials per block, for testing only
// A local test server may receive the data instead of Google Drive. Allowed only
// when the page itself is served from this computer, so a crafted link cannot
// redirect real participants' data elsewhere.
const LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const SAVE_URL = LOCAL && url("save_url") ? url("save_url") : CONFIG.SAVE_URL;
const PARTICIPANT = PROLIFIC_PID || `anon-${jsPsych.randomization.randomID(10)}`;

const design = StudyDesign.buildDesign(window.STIMULI, PARTICIPANT);
if (QUICK) design.blocks.forEach((b) => (b.trials = b.trials.slice(0, 2)));

jsPsych.data.addProperties({
  participant: PARTICIPANT,
  study_id: STUDY_ID,
  session_id: SESSION_ID,
  stimulus_version: window.STIMULI.version,
  design_seed: design.seed,
  reference_side: design.reference_side,
  block_order: design.block_order.join(","),
  debug: DEBUG,
});

// ---------------------------------------------------------------- rendering

const REP_NAMES = {
  hex: "Hexadecimal",
  walk: "Pattern A",
  life_mirrored: "Pattern B",
  life_unmirrored: "Pattern C",
  voronoi: "Pattern D",
};

function hexHtml(digest) {
  const groups = digest.match(/.{4}/g);
  const lines = [];
  for (let i = 0; i < groups.length; i += 4) lines.push(groups.slice(i, i + 4).join(" "));
  return `<div class="hex">${lines.join("<br>")}</div>`;
}

function imgHtml(src) {
  const px = CONFIG.DISPLAY_PX;
  return `<img class="fp" src="${src}" width="${px}" height="${px}" alt="">`;
}

function stim(t, which) {
  if (t.kind === "hex") return hexHtml(which === "ref" ? t.target : t.candidate);
  return imgHtml(which === "ref" ? t.target_img : t.candidate_img);
}

function pairHtml(t, footer) {
  const ref = `<div class="side"><div class="label">Approved release</div>${stim(t, "ref")}</div>`;
  const cand = `<div class="side"><div class="label">Release to deploy</div>${stim(t, "cand")}</div>`;
  const sides = design.reference_side === "left" ? ref + cand : cand + ref;
  return `<div class="pair">${sides}</div>${footer}`;
}

const KEYS = `<p class="keys"><b>F</b> = same release &nbsp;&nbsp;&nbsp; <b>J</b> = different release</p>`;

function compareTrial(t, phase, blockIndex) {
  return {
    type: jsPsychHtmlKeyboardResponse,
    stimulus: pairHtml(t, KEYS),
    choices: ["f", "j"],
    data: {
      task: "compare",
      phase,
      block: blockIndex,
      rep: t.rep,
      pair_type: t.pair_type,
      item: t.item,
      target: t.target,
      candidate: t.candidate,
      correct_response: t.correct_response,
      phash: t.phash ?? null,
      ssim: t.ssim ?? null,
      edge_match: t.edge_match ?? null,
    },
    on_finish: (d) => {
      d.said_same = d.response === "f";
      d.correct = d.said_same === (d.correct_response === "same");
      d.false_accept = d.correct_response === "different" && d.said_same;
    },
  };
}

function feedbackTrial() {
  return {
    type: jsPsychHtmlKeyboardResponse,
    stimulus: () => {
      const last = jsPsych.data.get().last(1).values()[0];
      const truth = last.correct_response === "same" ? "the same release" : "different releases";
      return `<p class="${last.correct ? "ok" : "bad"}">${last.correct ? "Correct" : "Not quite"}: these were ${truth}.</p>`;
    },
    choices: "NO_KEYS",
    trial_duration: 1500,
    data: { task: "feedback" },
  };
}

// The required key alternates (J, F, J) so that pressing one key all the
// time cannot pass every check.
const ATTENTION_KEYS = ["j", "f", "j"];

function attentionTrial(n) {
  const key = ATTENTION_KEYS[n % ATTENTION_KEYS.length];
  return {
    type: jsPsychHtmlKeyboardResponse,
    stimulus: `<p class="attn">This is an attention check.<br>Please press <b>${key.toUpperCase()}</b> now.</p>`,
    choices: ["f", "j"],
    data: { task: "attention", attention_index: n, expected_key: key },
    on_finish: (d) => (d.passed = d.response === key),
  };
}

// ---------------------------------------------------------------- timeline

const timeline = [];

timeline.push({
  type: jsPsychPreload,
  images: [...new Set(design.blocks.flatMap((b) => [b.example, ...b.trials])
    .concat(design.practice)
    .flatMap((t) => (t.kind === "image" ? [t.target_img, t.candidate_img] : [])))],
  message: "<p>Loading images...</p>",
});

timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: () =>
    window.innerWidth >= CONFIG.MIN_WINDOW_WIDTH
      ? "<p>Your window is large enough. Please keep it at this size and do not zoom.</p>"
      : `<p>This study needs a window at least ${CONFIG.MIN_WINDOW_WIDTH} pixels wide.<br>Please use a laptop or desktop computer, or make the window larger, then reload the page.</p>`,
  choices: () => (window.innerWidth >= CONFIG.MIN_WINDOW_WIDTH ? ["Continue"] : []),
  data: { task: "window_check" },
  on_start: () => jsPsych.data.addProperties({ window_w: window.innerWidth, window_h: window.innerHeight }),
});

timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: `
    <div class="consent">
      <h2>Consent</h2>
      <p>This is a research study about how people compare digital fingerprints of software releases.
      It takes about 18 minutes. You will see pairs of codes or images and decide whether they match.</p>
      <p>We record your answers and response times and store them in a private Google Drive folder
      that only the researchers can open. We do not collect your name or contact details.
      Your Prolific ID is stored only to manage payment and is removed before the data are shared.
      You can stop at any time by closing the window.</p>
      <p>The study is run by an independent researcher with no institutional ethics board, so it was not
      reviewed by one. It involves minimal risk: you only look at images and codes on your screen.
      Taking part is voluntary, and stopping early has no penalty beyond the normal Prolific rules.</p>
      <p>Questions: ${CONFIG.CONTACT}</p>
      <p>Do you agree to take part?</p>
    </div>`,
  choices: ["I agree", "I do not agree"],
  data: { task: "consent" },
  on_finish: (d) => {
    d.consented = d.response === 0;
    if (!d.consented) jsPsych.abortExperiment("<p>Thank you. You have chosen not to take part. You can close this window.</p>");
  },
});

timeline.push({
  type: jsPsychInstructions,
  pages: [
    `<h2>Your task</h2>
     <p>Imagine you review AI model releases before they are deployed.</p>
     <p>On each screen you will see two fingerprints. One belongs to the <b>approved release</b>.
     The other belongs to the <b>release about to be deployed</b>.</p>
     <p>Decide whether they are the <b>same release</b>.</p>`,
    `<p>Fingerprints come in five styles: one is a code made of letters and digits, and four are patterns.</p>
     <p>Different releases can look similar. Work as you would at your job: carefully, but without unusual effort.</p>
     <p>Press <b>F</b> if they are the same release and <b>J</b> if they are different.</p>
     <p>Please do not zoom, take screenshots or use other tools.</p>`,
    `<p>First you will do ${design.practice.length} practice trials with feedback.</p>`,
  ],
  show_clickable_nav: true,
  data: { task: "instructions" },
});

design.practice.forEach((t) => timeline.push(compareTrial(t, "practice", -1), feedbackTrial()));

timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: "<p>Practice is over. From now on there is no feedback.</p><p>There are 5 parts with a short break between them.</p>",
  choices: ["Start"],
  data: { task: "transition" },
});

design.blocks.forEach((block, bi) => {
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `<p><b>Part ${bi + 1} of ${design.blocks.length}: ${REP_NAMES[block.rep]}</b></p>
               <p>Here is an example of two fingerprints of the <b>same</b> release in this style.</p>
               ${pairHtml(block.example, "")}`,
    choices: ["Start this part"],
    data: { task: "block_intro", block: bi, rep: block.rep },
  });
  const checks = design.attention_positions.filter((a) => a.block === bi);
  block.trials.forEach((t, ti) => {
    timeline.push(compareTrial(t, "main", bi));
    checks.filter((a) => a.after === ti).forEach((a) => timeline.push(attentionTrial(design.attention_positions.indexOf(a))));
  });
  if (bi < design.blocks.length - 1) {
    timeline.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<p>Part ${bi + 1} done. Take a short break if you like.</p>`,
      choices: ["Continue"],
      data: { task: "break" },
    });
  }
});

timeline.push({
  type: jsPsychSurveyText,
  questions: [
    { prompt: "Which fingerprint style was easiest to compare, and why? (optional)", name: "easiest", rows: 2 },
    { prompt: "Did you use any tools such as zoom or screenshots? (optional)", name: "tools", rows: 1 },
    { prompt: "Any other comments? (optional)", name: "comments", rows: 2 },
  ],
  data: { task: "debrief" },
});

// Send the data to Google Drive. Text/plain avoids a CORS preflight, which
// Apps Script does not answer. Retries three times before giving up.
async function saveData() {
  const body = JSON.stringify({
    filename: `${PARTICIPANT}_${SESSION_ID || Date.now()}.csv`,
    data: jsPsych.data.get().csv(),
  });
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const r = await fetch(SAVE_URL, { method: "POST", headers: { "Content-Type": "text/plain" }, body });
      const reply = await r.json();
      if (reply.ok) return "saved";
    } catch (e) {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500 * attempt));
  }
  return "failed";
}

let SAVE_STATUS = DEBUG ? "debug" : "pending";
if (!DEBUG) {
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: "<p>Saving your answers. Please do not close this window.</p>",
    choices: "NO_KEYS",
    trial_duration: 300,
    data: { task: "saving_notice" },
  });
  timeline.push({
    type: jsPsychCallFunction,
    async: true,
    func: (done) => saveData().then((status) => { SAVE_STATUS = status; done(status); }),
    data: { task: "save" },
  });
}

timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: () => {
    if (SAVE_STATUS === "debug") return "<p>Test run finished. Nothing was saved.</p>";
    const saved = SAVE_STATUS === "saved"
      ? "<p>Thank you. Your answers are saved.</p>"
      : "<p>Thank you. Your answers could not be saved automatically.<br>Please send a message to the researcher through Prolific so you are still paid.</p>";
    return saved + (PROLIFIC_PID ? "<p>Click below to return to Prolific.</p>" : "");
  },
  choices: [PROLIFIC_PID ? "Return to Prolific" : "Finish"],
  data: { task: "end" },
});

jsPsych.run(timeline);
