pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "KeychronStatus.js" as Status

Singleton {
    id: root
    property real clock: Date.now() / 1000
    property string keyboardJson: ""
    property string mouseJson: ""
    readonly property var keyboard: Status.decodeNow(keyboardJson, clock, "keyboard")
    readonly property var mouse: Status.decodeNow(mouseJson, clock, "mouse")
    readonly property bool lowBattery: Status.isLow(keyboard) || Status.isLow(mouse)
    readonly property string runtime: Quickshell.env("XDG_RUNTIME_DIR") + "/keychron-battery/"

    FileView {
        id: keyboardFile
        path: root.runtime + "keyboard-status.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.keyboardJson = text()
        // Retain the snapshot through transient reload errors; normal expiry applies.
    }
    FileView {
        id: mouseFile
        path: root.runtime + "status.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.mouseJson = text()
    }
    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: {
            root.clock = Date.now() / 1000;
            keyboardFile.reload();
            mouseFile.reload();
        }
    }
}
