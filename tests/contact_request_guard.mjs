import assert from 'node:assert/strict';
import {requestMatches} from '../site/assets/request-guard.mjs';

const detached={revision:7,contact:false};
assert.equal(requestMatches(detached,7,false),true);
assert.equal(requestMatches(detached,8,true),false, 'late detached result must not enter contact mode');
const contact={revision:11,contact:true};
assert.equal(requestMatches(contact,11,true),true);
assert.equal(requestMatches(contact,12,false),false, 'late contact result must not enter detached mode');
assert.equal(requestMatches(contact,11,false),false, 'mode mismatch fails even if a revision were reused');
console.log(JSON.stringify({status:'PASS',cross_mode_cases:3}));
