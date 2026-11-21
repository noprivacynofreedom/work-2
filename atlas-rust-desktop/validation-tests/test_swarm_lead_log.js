// The Swarm Lead chat must collect every bot's live lines, in one message, without duplicates.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(here, '..', 'src-tauri', 'resources', 'atlas', 'index.html'), 'utf8');
const a = html.indexOf('function swarmWatch(c){');
const b = html.indexOf('// Retrieve a finished task', a);
assert.ok(a >= 0 && b > a, 'swarmWatch present');
const code = html.slice(a, b);

const lead = { id: 'r1-final', botId: 'lead', messages: [], swarmRun: 'r1', swarmFinal: true };
const bot1 = { id: 'r1-1', botId: 'b1', messages: [], swarmRun: 'r1' };
const bot2 = { id: 'r1-2', botId: 'b2', messages: [], swarmRun: 'r1' };
const other = { id: 'r2-1', botId: 'b1', messages: [], swarmRun: 'r2' };   // a different run
const S = { chats: [lead, bot1, bot2, other], bots: [{ id: 'b1', name: '10x: CTO' }, { id: 'b2', name: '10x: QA' }, { id: 'lead', name: 'Swarm Lead' }] };
const logs = {
  'r1-1': { lines: [{ ts: 1, level: 'info', message: 'CTO is thinking' }], next: 1, done: false },
  'r1-2': { lines: [{ ts: 2, level: 'error', message: 'QA model offline' }], next: 1, done: false },
  'r1-final': { lines: [{ ts: 3, level: 'info', message: 'Lead plans' }], next: 1, done: false, status: 'running', phase: 'plan' },
  'r2-1': { lines: [{ ts: 4, level: 'info', message: 'other run line' }], next: 1, done: false },
};
let timer;
let chatRenders = 0;
const ctx = { S, save() {}, renderLog() {}, renderChats() { chatRenders++; }, chat: () => null, setInterval: fn => { timer = fn; return 1; }, clearInterval() {},
  swarmFinishCheck() {}, swarmTimers: {}, Date, encodeURIComponent, console,
  setTimeout() { return 1; }, document: { hidden: true },   // swarmSync auto-start stays off in the test
  fetch: async url => ({ ok: true, json: async () => logs[new URL(url, 'http://x').searchParams.get('conversation_id')] }) };
vm.createContext(ctx);
vm.runInContext(code + '\nthis.swarmWatch = swarmWatch;', ctx);

for (const c of [bot1, bot2, lead, other]) ctx.swarmWatch(c);
await new Promise(r => setTimeout(r, 50));

const lm = lead.messages.filter(m => m.swarmLog);
assert.equal(lm.length, 1, 'one live-log message in the Lead chat');
assert.match(lm[0].content, /\[10x: CTO\] CTO is thinking/);
assert.match(lm[0].content, /\[10x: QA\] \(problem\) QA model offline/);
assert.match(lm[0].content, /Lead plans/);
assert.doesNotMatch(lm[0].content, /other run line/, 'other runs stay out');
assert.doesNotMatch(lm[0].content, /\[Swarm Lead\]/, 'the Lead own lines are not tagged twice');
assert.equal(lead.messages.filter(m => m.swarmLog).length, 1);
assert.match(bot1.messages[0].content, /CTO is thinking/, 'bot chat still has its own log');
assert.equal(lead.swarmPhase, 'plan', 'the Lead chat keeps the phase the server reports');
assert.ok(chatRenders > 0, 'a status or phase change redraws the chat list');
console.log('swarm lead live log: ok');
