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
function query() {
    return new Promise(resolve => {
        const values = [];
        queryKeychronBattery((...args) => {
            values.push(args);
            if (values.length === 2) resolve(values);
        });
    });
}
const current = {...sample, observed_at: Date.now()/1000, updated_at: Date.now()/1000};
GLib.file_set_contents(path, JSON.stringify(current));
equal((await query())[0], ['Keychron M3 Lite', 0.08, 'battery', 'percent']);
GLib.file_set_contents(path, '{broken');
equal((await query())[0][1], null);
Gio.File.new_for_path(path).delete(null);
equal((await query())[0][1], null);
print('GJS: valid, zero, stale, future, malformed and missing readings passed');
