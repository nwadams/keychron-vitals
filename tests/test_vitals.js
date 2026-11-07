import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
const {sensorValues, queryKeychronBattery} = await import(GLib.filename_to_uri(GLib.getenv('TEST_MODULE'), null));
function equal(actual, expected) {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
        throw Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}
const sample = {version: 1, updated_at: 1000, observed_at: 1000,
    reading: {battery_percent: 8, charging: false, connection: '2.4GHz receiver'}};
equal(sensorValues(sample, 1001), [0.08, 'Discharging · 2.4GHz receiver']);
equal(sensorValues({...sample, updated_at: 1030}, 1031)[1], 'Discharging · 2.4GHz receiver · last known');
for (const bad of [null, {}, {...sample, observed_at: 1002}, {...sample, updated_at: 1180},
    {...sample, reading: {...sample.reading, battery_percent: 101}}])
    equal(sensorValues(bad, 1001)[0], null);
equal(sensorValues(sample, 1180)[0], null);
equal(sensorValues({...sample, reading: {...sample.reading, battery_percent: 0}}, 1001)[0], 0);

// Exercise asynchronous file IO and fallback, as used in GNOME Shell.
const path = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'keychron-battery', 'status.json']);
GLib.mkdir_with_parents(GLib.path_get_dirname(path), 0o700);
async function query(selected = false) {
    const values = [];
    await queryKeychronBattery((...args) => values.push(args), selected);
    return values;
}
function mouse(rows) { return rows.find(row => row[0] === 'Keychron M3 Lite'); }
function summary(rows) { return rows.find(row => row[2] === 'battery-group'); }
const current = {...sample, observed_at: Date.now()/1000, updated_at: Date.now()/1000};
GLib.file_set_contents(path, JSON.stringify(current));
equal(mouse(await query()), ['Keychron M3 Lite', 0.08, 'battery', 'percent']);
equal(summary(await query(8)), ['battery', 0.08, 'battery-group', 'percent']);
GLib.file_set_contents(path, '{broken');
equal(mouse(await query())[1], null);
equal(summary(await query(8)), ['battery', null, 'battery-group', 'percent']);
Gio.File.new_for_path(path).delete(null);
equal(mouse(await query())[1], null);
equal(summary(await query(8)), ['battery', null, 'battery-group', 'percent']);
print('GJS: valid, zero, stale, future, malformed and missing readings passed');

const keyboardPath = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'keychron-battery', 'keyboard-status.json']);
const keyboard = {...current, reading: {battery_percent: 84, charging: false, charging_state: 0, voltage_mv: 3987, connection: '2.4GHz receiver'}};
GLib.file_set_contents(keyboardPath, JSON.stringify(keyboard));
const rows = await query(9);
equal(rows.find(row => row[0] === 'Keychron K2 HE'), ['Keychron K2 HE', 0.84, 'battery', 'percent']);
equal(summary(rows), ['battery', 0.84, 'battery-group', 'percent']);
if (!rows.find(row => row[0] === 'Keychron K2 HE State')[1].includes('3987 mV')) throw Error('Missing keyboard voltage');
equal((await query(0)).filter(row => row[2] === 'battery-group'), []);
GLib.file_set_contents(keyboardPath, '{broken');
equal(summary(await query(9)), ['battery', null, 'battery-group', 'percent']);
Gio.File.new_for_path(keyboardPath).delete(null);
equal(summary(await query(9)), ['battery', null, 'battery-group', 'percent']);
print('GJS: keyboard selection, voltage, built-in selection and invalid data passed');
