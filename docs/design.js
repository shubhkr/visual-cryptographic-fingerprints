// Trial design for the visual-fingerprint comparison study.
// Pure functions only, so the design can be unit-tested in Node:
//   node study/test_design.js
(function (root) {
  "use strict";

  const REPS = ["hex", "walk", "life_mirrored", "life_unmirrored", "voronoi"];
  const PER_REP = { same: 16, random: 4, hard: 12 }; // 32 trials per representation
  const N_PRACTICE_REPS = 2;
  const N_ATTENTION = 3;

  // Small seeded PRNG (mulberry32) so a participant's design is reproducible.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function seedFrom(text) {
    let h = 2166136261 >>> 0; // FNV-1a
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h;
  }

  function shuffle(arr, rand) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function makeTrial(rep, kind, items, idx, pairType) {
    const it = items[idx];
    const cand = pairType === "same" ? null : it[pairType];
    const t = {
      rep,
      kind,
      item: idx,
      pair_type: pairType,
      target: it.target,
      candidate: cand ? cand.digest : it.target,
      correct_response: pairType === "same" ? "same" : "different",
    };
    if (kind === "image") {
      t.target_img = it.target_img;
      t.candidate_img = cand ? cand.img : it.target_img;
      t.phash = cand ? cand.phash : 0;
      t.ssim = cand ? cand.ssim : 1;
    } else {
      t.edge_match = cand ? cand.edge_match : 64;
    }
    return t;
  }

  // Returns { seed, reference_side, block_order, practice, blocks, attention_positions }
  function buildDesign(stimuli, participantKey) {
    const seed = seedFrom(String(participantKey));
    const rand = rng(seed);
    const blockOrder = shuffle(REPS, rand);
    const blocks = [];
    const leftovers = {};

    for (const rep of blockOrder) {
      const spec = stimuli.reps[rep];
      const kind = spec.kind;
      const order = shuffle([...Array(spec.items.length).keys()], rand);
      let k = 0;
      const take = (n) => order.slice(k, (k += n));
      const trials = [];
      for (const i of take(PER_REP.same)) trials.push(makeTrial(rep, kind, spec.items, i, "same"));
      for (const i of take(PER_REP.random)) trials.push(makeTrial(rep, kind, spec.items, i, "random"));
      const hard = take(PER_REP.hard);
      hard.forEach((i, n) => {
        const type = kind === "hex" ? "hex_hard" : n % 2 === 0 ? "phash_hard" : "ssim_hard";
        trials.push(makeTrial(rep, kind, spec.items, i, type));
      });
      leftovers[rep] = order.slice(k);
      blocks.push({ rep, kind, example: makeTrial(rep, kind, spec.items, leftovers[rep][0], "same"),
                    trials: shuffle(trials, rand) });
    }

    // Practice: one same and one random pair from two representations, using
    // items that do not appear in the main blocks.
    const practice = [];
    for (const rep of shuffle(REPS, rand).slice(0, N_PRACTICE_REPS)) {
      const spec = stimuli.reps[rep];
      const spare = leftovers[rep];
      practice.push(makeTrial(rep, spec.kind, spec.items, spare[1], "same"));
      practice.push(makeTrial(rep, spec.kind, spec.items, spare[2], "random"));
    }

    // Attention checks go after a random trial in blocks 2, 3 and 4.
    const attention = [];
    for (let b = 1; b <= N_ATTENTION; b++) {
      attention.push({ block: b, after: Math.floor(rand() * blocks[b].trials.length) });
    }

    return {
      seed,
      reference_side: rand() < 0.5 ? "left" : "right",
      block_order: blockOrder,
      practice: shuffle(practice, rand),
      blocks,
      attention_positions: attention,
    };
  }

  const api = { REPS, PER_REP, buildDesign, seedFrom, rng, shuffle };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.StudyDesign = api;
})(this);
