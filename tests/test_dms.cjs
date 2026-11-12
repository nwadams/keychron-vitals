const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(`${__dirname}/../dms/Status.js`, 'utf8'), context);
const decode = (s, now = 1000) => context.decode(JSON.stringify(s), now, 'keyboard');
const status = {version: 1, updated_at: 990, observed_at: 990, reading: {battery_percent: 36, charging: false, voltage_mv: 3627, connection: '2.4GHz receiver'}};
assert.equal(decode(status).percent, 36);
assert.match(decode(status).detail, /3627 mV/);
assert.equal(decode({...status, reading: {...status.reading, battery_percent: 0}}).percent, 0);
assert.match(decode({...status, updated_at: 995}).detail, /last known/);
assert.match(decode({...status, reading: {...status.reading, charging: true}}).detail, /Charging/);
assert.match(decode({...status, reading: {...status.reading, charging: true, charging_state: 2}}).detail, /Full/);
for (const invalid of [null, {}, {...status, version: 2}, {...status, observed_at: 820}, {...status, updated_at: 820}, {...status, updated_at: 1001}, {...status, observed_at: 1001}, {...status, reading: null}, {...status, reading: {...status.reading, battery_percent: 101}}, {...status, reading: {...status.reading, battery_percent: 1.5}}, {...status, reading: {...status.reading, charging: 'false'}}])
    assert.equal(decode(invalid).percent, null);
assert.equal(context.decode('broken', 1000, 'mouse').percent, null);
console.log('DMS status validation passed');
// Regression: a new reading arrives between timer ticks. Fresh data must stay valid.
vm.runInContext('Date.now = () => 1000000', context);
const newReading = {...status, updated_at: 999.9, observed_at: 999.9};
assert.equal(context.decodeNow(JSON.stringify(newReading), 995, 'keyboard').percent, 36);
assert.equal(context.decodeNow(JSON.stringify({...newReading, updated_at: 1001}), 995, 'keyboard').percent, null);
for (const [percent, expected] of [[0, true], [19, true], [20, false], [21, false], [null, false]])
    assert.equal(context.isLow({percent}), expected);
console.log('Between-tick refresh and strict below-20% warning checks passed');
