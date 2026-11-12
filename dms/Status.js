// Shared by QML and the hardware-free Node tests. Never query HID from the bar.
function decode(contents, now, kind) {
    const unavailable = {percent: null, charging: false, detail: "Unavailable — wake " + kind + " or check service"};
    try {
        const status = JSON.parse(contents);
        const r = status.reading;
        if (status.version !== 1 || !Number.isFinite(status.updated_at) ||
            !Number.isFinite(status.observed_at) ||
            now - status.updated_at < 0 || now - status.updated_at >= 180 ||
            now - status.observed_at < 0 || now - status.observed_at >= 180 ||
            !r || !Number.isInteger(r.battery_percent) || r.battery_percent < 0 ||
            r.battery_percent > 100 || typeof r.charging !== "boolean")
            return unavailable;
        let detail = r.charging_state === 2 ? "Full" : r.charging ? "Charging" : "Discharging";
        if (typeof r.connection === "string") detail += " · " + r.connection;
        if (kind === "keyboard" && Number.isFinite(r.voltage_mv)) detail += " · " + r.voltage_mv + " mV";
        if (status.updated_at > status.observed_at) detail += " · last known";
        return {percent: r.battery_percent, charging: r.charging, detail: detail};
    } catch (_) {
        return unavailable;
    }
}

// tick is a binding dependency for expiration; wall time is sampled on every file update.
function decodeNow(contents, tick, kind) {
    return decode(contents, Math.max(tick, Date.now() / 1000), kind);
}

function isLow(reading) {
    return reading.percent !== null && reading.percent < 20;
}
