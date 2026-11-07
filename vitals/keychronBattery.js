// Local M3 Lite integration. Hardware polling runs outside GNOME Shell.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

function readStatus(path) {
    return new Promise((resolve, reject) => {
        const file = Gio.File.new_for_path(path);
        file.load_contents_async(null, (source, result) => {
            try {
                const [, contents] = source.load_contents_finish(result);
                resolve(new TextDecoder().decode(contents));
            } catch (error) {
                reject(error);
            }
        });
    });
}

export function sensorValues(status, now = Date.now() / 1000) {
    const reading = status?.reading;
    const age = now - status?.observed_at;
    const valid = status?.version === 1 && Number.isFinite(status.observed_at) &&
        Number.isFinite(status.updated_at) && now - status.updated_at >= 0 &&
        now - status.updated_at < 180 && age >= 0 && age < 180 &&
        Number.isInteger(reading?.battery_percent) && reading.battery_percent >= 0 &&
        reading.battery_percent <= 100 && typeof reading.charging === 'boolean';
    if (!valid)
        return [null, 'Unavailable — wake mouse or check service'];
    const state = reading.charging ? 'Charging' : 'Discharging';
    const cached = status.updated_at > status.observed_at ? ' · last known' : '';
    return [reading.battery_percent / 100, `${state} · ${reading.connection}${cached}`];
}

export function queryKeychronBattery(callback, displaySummary = false) {
    const path = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'keychron-battery', 'status.json']);
    const emit = status => {
        const [percentage, state] = sensorValues(status);
        callback('Keychron M3 Lite', percentage, 'battery', 'percent');
        callback('Keychron M3 Lite State', state, 'battery', 'string');
        if (displaySummary)
            callback('battery', percentage, 'battery-group', 'percent');
    };
    readStatus(path).then(contents => {
        emit(JSON.parse(contents));
    }).catch(() => emit(null));
}
