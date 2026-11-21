// Exercise the real result-delivery functions extracted from index.html.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(here, '..', 'src-tauri', 'resources', 'atlas', 'index.html'), 'utf8');
const a = html.indexOf('let swarmRun = null; const swarmTimers = {}; const swarmSummaryBusy = new Set();');
const b = html.indexOf('function startSwarmChats(run, originId){', a);
assert.ok(a >= 0 && b > a, 'delivery implementation present');
const code = html.slice(a, b);
const delay = ms => new Promise(r => setTimeout(r, ms));
function setup(chats, results, failures = {}) {
  const calls = [];
  const S = { chats, bots: [{id:'b1',name:'10x: CTO'},{id:'b2',name:'10x: QA'},{id:'lead',name:'Swarm Lead'}] };
  const ctx = {
    S, save(){}, renderLog(){}, chat(){return null;}, setInterval(){return 1;}, clearInterval(){}, Date,
    setTimeout, Promise, encodeURIComponent, console, document: { hidden: true },   // swarmSync auto-start returns early
    fetch: async url => {
      calls.push(url);
      const id = new URL(url, 'http://atlas.local').searchParams.get('conversation_id');
      if (failures[id]) return {ok:false,status:503,json:async()=>({})};
      return {ok:true,status:200,json:async()=>results[id] || {ok:false,error:'not found'}};
    }
  };
  vm.createContext(ctx); vm.runInContext(code + '\nthis.finish = swarmFinishCheck;', ctx);
  return {ctx,S,calls};
}
const origin = () => ({id:'origin',messages:[],swarmSummaries:[]});
const bot = (id, botId, status='completed') => ({id,botId,swarmRun:'run1',swarmOrigin:'origin',swarmStatus:status,swarmError:status==='failed'?'model failed':''});
const results = {
  'run1-1': {ok:true,status:'completed',result:{answer:'CTO ACTUAL ANSWER'}},
  'run1-2': {ok:true,status:'completed',result:{answer:'QA ACTUAL ANSWER'}},
  'run1-final': {ok:true,status:'completed',result:{plan:{CTO:'Implement'},combined:'Combined deliverable',tests:{text:'3 tests passed'},review:'Review complete',where:{plan:'cloud',combine:'cloud',review:'cloud'}}}
};

// No pipeline: both real bot answers are delivered to the originating chat.
{
  const o=origin(), {ctx,S,calls}=setup([o,bot('run1-1','b1'),bot('run1-2','b2')],results);
  await ctx.finish(S.chats[1]);
  const m=o.messages.find(x=>x.swarmDeliveryRun==='run1');
  assert.ok(m); assert.match(m.content,/CTO ACTUAL ANSWER/); assert.match(m.content,/QA ACTUAL ANSWER/);
  assert.deepEqual([...o.swarmSummaries],['run1']); assert.equal(calls.length,2);
  await ctx.finish(S.chats[2]);
  assert.equal(o.messages.filter(x=>x.swarmDeliveryRun==='run1').length,1,'duplicate finish callback updates same message');
}

// Pipeline: bot answers AND the lead's combined result, tests and review are delivered.
{
  const o=origin(), {ctx,S}=setup([o,bot('run1-1','b1'),bot('run1-2','b2'),{...bot('run1-final','lead'),swarmFinal:true}],results);
  await ctx.finish(S.chats[1]);
  const m=o.messages.find(x=>x.swarmDeliveryRun==='run1');
  for (const value of ['CTO ACTUAL ANSWER','QA ACTUAL ANSWER','Combined deliverable','3 tests passed','Review complete']) assert.match(m.content,new RegExp(value));
  assert.deepEqual([...o.swarmSummaries],['run1']);
}

// Missing result: visible warning, not falsely marked delivered; next startup retries in place.
{
  const o=origin(), chats=[o,bot('run1-1','b1'),bot('run1-2','b2')];
  const {ctx,S,calls}=setup(chats,results,{'run1-2':true});
  await ctx.finish(chats[1]);
  let m=o.messages.find(x=>x.swarmDeliveryRun==='run1');
  assert.match(m.content,/RESULT DELIVERY INCOMPLETE/); assert.equal(o.swarmSummaries.includes('run1'),false);
  const retry=setup(chats,results);
  await retry.ctx.finish(chats[1]);
  m=o.messages.find(x=>x.swarmDeliveryRun==='run1');
  assert.match(m.content,/QA ACTUAL ANSWER/); assert.doesNotMatch(m.content,/RESULT DELIVERY INCOMPLETE/);
  assert.deepEqual([...o.swarmSummaries],['run1']);
}

// Failed bots remain visible in status; successful bot result is still delivered.
{
  const o=origin(), chats=[o,bot('run1-1','b1'),bot('run1-2','b2','failed')];
  const {ctx,S}=setup(chats,results); await ctx.finish(chats[1]);
  const m=o.messages.find(x=>x.swarmDeliveryRun==='run1');
  assert.match(m.content,/SWARM FINISHED WITH PROBLEMS/); assert.match(m.content,/CTO ACTUAL ANSWER/); assert.match(m.content,/model failed/);
  assert.deepEqual([...o.swarmSummaries],['run1']);
}
console.log('swarm result delivery: ok');
