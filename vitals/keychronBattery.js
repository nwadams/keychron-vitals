// Local M3 Lite and K2 HE integration. Hardware polling runs outside GNOME Shell.
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

export function sensorValues(status, now = Date.now() / 1000, device = 'mouse') {
    const reading = status?.reading;
    const age = now - status?.observed_at;
    const valid = status?.version === 1 && Number.isFinite(status.observed_at) &&
        Number.isFinite(status.updated_at) && now - status.updated_at >= 0 &&
        now - status.updated_at < 180 && age >= 0 && age < 180 &&
        Number.isInteger(reading?.battery_percent) && reading.battery_percent >= 0 &&
        reading.battery_percent <= 100 && typeof reading.charging === 'boolean';
    if (!valid)
        return [null, `Unavailable — wake ${device} or check service`];
    const state = reading.charging_state === 2 ? 'Full' : reading.charging ? 'Charging' : 'Discharging';
    const voltage = device === 'keyboard' && Number.isFinite(reading.voltage_mv) ? ` · ${reading.voltage_mv} mV` : '';
    const cached = status.updated_at > status.observed_at ? ' · last known' : '';
    return [reading.battery_percent / 100, `${state} · ${reading.connection}${voltage}${cached}`];
}

export function queryKeychronBattery(callback, displaySummary = false) {
    // The boolean form remains compatible with the earlier mouse-only hook.
    const selected = displaySummary === true ? 8 : displaySummary;
    const devices = [
        {label: 'Keychron M3 Lite', file: 'status.json', slot: 8, kind: 'mouse'},
        {label: 'Keychron K2 HE', file: 'keyboard-status.json', slot: 9, kind: 'keyboard'},
    ];
    return Promise.all(devices.map(device => {
        const path = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'keychron-battery', device.file]);
        const emit = status => {
            const [percentage, state] = sensorValues(status, Date.now() / 1000, device.kind);
            callback(device.label, percentage, 'battery', 'percent');
            callback(device.label + ' State', state, 'battery', 'string');
            if (selected === device.slot)
                callback('battery', percentage, 'battery-group', 'percent');
        };
        return readStatus(path).then(contents => emit(JSON.parse(contents))).catch(() => emit(null));
    }));
}
