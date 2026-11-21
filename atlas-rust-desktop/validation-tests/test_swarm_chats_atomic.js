// Swarm chats are atomic chats: linked to the chat where /swarm was typed. Runs the real functions from index.html.
import fs from "node:fs";
import assert from "node:assert/strict";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const html = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src-tauri", "resources", "atlas", "index.html"), "utf8");
const slice = (from, to) => { const a = html.indexOf(from), b = html.indexOf(to, a); assert.ok(a >= 0 && b > a, `missing ${from}`); return html.slice(a, b); };
const code = [
  slice("const ATOMIC_STOP =", "function atomicShiftAssessment"),
  slice("function atomicCapsule", "function atomicTransition"),
  slice("function swarmChatTitle", "function resumeSwarmWatchers"),
].join("\n");

const origin = { id: "o1", title: "main chat", botId: "b0", messages: [{ role: "user", content: "/swarm write a calculator" }] };
const S = { chats: [origin], bots: [{ id: "b1", name: "10x: SDE" }, { id: "b2", name: "10x: QA Engineer" }, { id: "b0", name: "Default" }] };
const watched = [];
const ctx = { S, save() {}, renderAll() {}, bot: () => S.bots[2], swarmWatch: c => watched.push(c.id), console };
vm.createContext(ctx);
vm.runInContext(code + "\nthis.startSwarmChats = startSwarmChats;", ctx);

ctx.startSwarmChats({ run_id: "sw1", goal: "write a calculator that is very long indeed", steps: [
  { conversation_id: "sw1-1", agent: "10x: SDE", task: "write it" },
  { conversation_id: "sw1-2", agent: "10x: QA Engineer", task: "test it" },
  { conversation_id: "sw1-final", agent: "Swarm Lead", task: "combine", final: true }] }, "o1");

const mine = id => S.chats.find(c => c.id === id);
for (const id of ["sw1-1", "sw1-2", "sw1-final"]) {
  const c = mine(id);
  assert.equal(c.atomic, true, id + " atomic");
  assert.equal(c.parentChatId, "o1");
  assert.equal(c.atomicGroupId, "o1");
  assert.match(c.contextCapsule, /ATLAS PROJECT CONTEXT CAPSULE/);
  assert.match(c.contextCapsule, /write a calculator/);
}
assert.equal(mine("sw1-1").title, "[SWARM] SDE: write a calculator that is…");
assert.ok(mine("sw1-1").title.length <= 40);
assert.match(mine("sw1-final").title, /^\[SWARM\] Lead: /);
assert.equal(mine("sw1-1").botId, "b1");           // each bot's chat lives inside that bot
assert.equal(mine("sw1-2").botId, "b2");
assert.equal(mine("sw1-final").swarmFinal, true);
assert.deepEqual([...origin.atomicChildren], ["sw1-1", "sw1-2", "sw1-final"]);
assert.deepEqual(watched.sort(), ["sw1-1", "sw1-2", "sw1-final"]);

// No origin chat (for example it was deleted): chats are still made, just not linked.
ctx.startSwarmChats({ run_id: "sw2", steps: [{ conversation_id: "sw2-1", agent: "10x: SDE", task: "x" }] }, "gone");
assert.equal(mine("sw2-1").atomic, undefined);
console.log("swarm atomic chats: ok");
