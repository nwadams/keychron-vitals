import QtQuick
import qs.Services
import qs.Common
import qs.DCommon.Widgets

DCard {
    id: root
    readonly property var keyboard: KeychronBatteryService.keyboard
    readonly property var mouse: KeychronBatteryService.mouse
    height: devices.implicitHeight + pad * 2
    restRadius: Theme.cornerRadiusL

    Column {
        id: devices
        width: parent.width
        spacing: Theme.spacingM

        StyledText {
            text: "Keychron batteries"
            color: Theme.primary
            font.pixelSize: Theme.fontSizeSmall
            font.weight: Theme.fontWeightMedium
        }

        DeviceRow { width: parent.width; deviceName: "Keychron K2 HE"; deviceIcon: "keyboard"; reading: root.keyboard }
        DeviceRow { width: parent.width; deviceName: "Keychron M3 Lite"; deviceIcon: "mouse"; reading: root.mouse }
    }

    component DeviceRow: Row {
        id: device
        property string deviceName
        property string deviceIcon
        property var reading
        readonly property bool low: reading.percent !== null && reading.percent < 20
        spacing: Theme.spacingM

        DIcon {
            id: icon
            name: device.reading.charging ? "bolt" : device.deviceIcon
            size: Theme.iconSize
            color: device.low ? Theme.error : Theme.primary
            anchors.verticalCenter: parent.verticalCenter
        }
        Column {
            width: parent.width - icon.width - level.implicitWidth - parent.spacing * 2
            spacing: Theme.spacingXXS
            StyledText { width: parent.width; text: device.deviceName; color: Theme.onSurface; wrapMode: Text.WordWrap }
            StyledText { width: parent.width; text: device.reading.detail; font.pixelSize: Theme.fontSizeSmall; color: Theme.onSurfaceVariant; wrapMode: Text.WordWrap }
        }
        StyledText {
            id: level
            anchors.verticalCenter: parent.verticalCenter
            text: device.reading.percent === null ? "N/A" : device.reading.percent + "%"
            font.pixelSize: Theme.fontSizeLarge
            font.weight: Theme.fontWeightMedium
            color: device.low ? Theme.error : Theme.onSurface
        }
    }
}
