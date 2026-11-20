// Checks the trial design for many simulated participants.
//   node study/test_design.js docs/stimuli.js
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const D = require(path.join(__dirname, "..", "docs", "design.js"));

const src = fs.readFileSync(process.argv[2] || path.join(__dirname, "..", "docs", "stimuli.js"), "utf8");
const window = {};
new Function("window", src)(window);
const S = window.STIMULI;

const counts = {};
for (let p = 0; p < 500; p++) {
  const d = D.buildDesign(S, `P${p}`);
  // same participant key, same design
  assert.deepStrictEqual(D.buildDesign(S, `P${p}`), d);
  assert.deepStrictEqual([...d.block_order].sort(), [...D.REPS].sort());
  assert.strictEqual(d.blocks.length, 5);
  assert.strictEqual(d.practice.length, 4);
  assert.strictEqual(d.attention_positions.length, 3);
  const used = new Set();
  for (const b of d.blocks) {
    assert.strictEqual(b.trials.length, 32);
    const types = {};
    for (const t of b.trials) types[t.pair_type] = (types[t.pair_type] || 0) + 1;
    if (b.kind === "hex") assert.deepStrictEqual(types, { same: 16, random: 4, hex_hard: 12 });
    else assert.deepStrictEqual(types, { same: 16, random: 4, phash_hard: 6, ssim_hard: 6 });
    // no target appears twice within a representation, including example and practice
    const items = b.trials.map((t) => t.item).concat([b.example.item]);
    assert.strictEqual(new Set(items).size, items.length);
    items.forEach((i) => used.add(`${b.rep}:${i}`));
    for (const t of b.trials) {
      assert.strictEqual(t.correct_response === "same", t.pair_type === "same");
      assert.strictEqual(t.candidate === t.target, t.pair_type === "same");
      if (b.kind === "image") {
        assert.ok(t.target_img && t.candidate_img);
        assert.ok(fs.existsSync(path.join(__dirname, "..", "docs", t.target_img)), t.target_img);
        assert.ok(fs.existsSync(path.join(__dirname, "..", "docs", t.candidate_img)), t.candidate_img);
      }
      counts[`${b.rep}:${t.pair_type}`] = (counts[`${b.rep}:${t.pair_type}`] || 0) + 1;
    }
  }
  for (const t of d.practice) assert.ok(!used.has(`${t.rep}:${t.item}`), "practice item reused");
  for (const a of d.attention_positions) assert.ok(a.after < d.blocks[a.block].trials.length);
}
const sides = new Set([...Array(200).keys()].map((p) => D.buildDesign(S, `Q${p}`).reference_side));
assert.strictEqual(sides.size, 2);
console.log("design OK for 500 simulated participants");
console.log(counts);
