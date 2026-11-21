// SWARM tab: Lead is the parent row of each run, chips show live state, Lead shows failed tests. Runs the real functions from index.html.
import fs from "node:fs";
import assert from "node:assert/strict";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const html = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src-tauri", "resources", "atlas", "index.html"), "utf8");
const slice = (from, to) => { const a = html.indexOf(from), b = html.indexOf(to, a); assert.ok(a >= 0 && b > a, `missing ${from}`); return html.slice(a, b); };
const code = slice("const SWARM_LEAD_PHASE", "const SWARM_LEAD_STEPS") + slice("function swarmGroups", "function renderSwarmTree");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const S = { chats: [
  { id: "a-final", swarmRun: "a", swarmFinal: true, swarmLive: true, swarmPhase: "bots", title: "[SWARM] Lead: write a calc" },
  { id: "a-1", swarmRun: "a", swarmLive: true, swarmTaskStatus: "claimed", title: "[SWARM] SDE: write a calc", swarmTask: "code it" },
  { id: "a-2", swarmRun: "a", swarmLive: false, swarmStatus: "failed", title: "[SWARM] QA Engineer: write a calc" },
  { id: "b-final", swarmRun: "b", swarmFinal: true, swarmLive: false, swarmStatus: "completed", swarmTestsStatus: "failed", title: "[SWARM] Lead: x" },
  { id: "plain", title: "normal chat" },
] };
// The sliced code also holds the Uplink rail state (7e4a1cb), which reads matchMedia at load.
const ctx = { S, esc, matchMedia: () => ({ matches: false }) };
vm.createContext(ctx);
vm.runInContext(code + "\nthis.f = { swarmBadge, swarmState, swarmParts, swarmChip, swarmGroups };", ctx);
const { swarmBadge, swarmState, swarmParts, swarmChip, swarmGroups } = ctx.f;
const c = id => S.chats.find(x => x.id === id);

// Groups: one per run, Lead is the parent, normal chats stay out.
const g = swarmGroups();
assert.equal(g.length, 2);
assert.equal(g[0].lead.id, "a-final");
assert.deepEqual([...g[0].bots.map(x => x.id)], ["a-1", "a-2"]);

// Live state per bot.
assert.deepEqual([...swarmState(c("a-1"))], ["●", "RUNNING", "busy"]);
assert.deepEqual([...swarmState(c("a-2"))], ["✕", "FAILED", "err"]);
assert.deepEqual([...swarmState(c("a-final"))], ["●", "BOTS WORKING", "busy"]);

// Role and goal come from old titles too.
assert.equal(swarmParts(c("a-2")).role, "QA ENGINEER");
assert.equal(swarmParts(c("a-2")).goal, "write a calc");
assert.equal(swarmParts(c("a-final")).role, "SWARM LEAD");
assert.equal(swarmParts(c("a-1")).task, "code it");
assert.match(swarmChip(c("a-1")), /class="chip busy"/);

// Lead with failed tests does not say plain DONE.
assert.equal(swarmBadge(c("b-final"))[0], "SWARM LEAD · DONE, TESTS FAILED");
assert.equal(swarmState(c("b-final"))[1], "TESTS FAILED");
c("b-final").swarmTestsStatus = "passed";
assert.equal(swarmBadge(c("b-final"))[0], "SWARM LEAD · DONE");
console.log("swarm tree: OK");
