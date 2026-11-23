import assert from 'node:assert/strict';
import {requestMatches} from '../site/assets/request-guard.mjs';

for(const mode of ['detached','semi','contact'])assert.equal(requestMatches({revision:7,mode},7,mode),true);
for(const source of ['detached','semi','contact'])for(const target of ['detached','semi','contact'])if(source!==target)
  assert.equal(requestMatches({revision:7,mode:source},7,target),false,`late ${source} result must not enter ${target} mode`);
assert.equal(requestMatches({revision:7,mode:'semi'},8,'semi'),false,'revision mismatch fails within a mode');
console.log(JSON.stringify({status:'PASS',cross_mode_cases:7}));
