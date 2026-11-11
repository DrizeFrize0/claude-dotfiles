// Lennox Expressive: the login screen (SDDM, Qt 6).
//
// After end-4's illogical-impulse: Material You colors from your wallpaper, a big clock,
// a glass card with your picture, and motion on Material 3's "emphasized" curves.
// Opening: the wallpaper settles in from a slight zoom while the blur rises, then the
// clock and the card float up one after the other. A wrong password shakes the field.
// Logging in: the card shrinks away and the screen fades to black while the desktop loads.
// More than one user on the laptop: their pictures sit above the card (profiles).

import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "black"

    // ------------------------------------------------------------ colors
    // theme.conf has safe defaults; backgrounds/colors.json (written by lennox-wallpaper,
    // needs QML_XHR_ALLOW_FILE_READ=1 from /etc/sddm.conf.d/10-lennox.conf) has the wallpaper's.
    property color primary: config.primary || "#81d5cd"
    property color onPrimary: config.onPrimary || "#003734"
    property color surface: config.surface || "#0e1514"
    property color onSurface: config.onSurface || "#dde4e2"
    property color surfaceContainer: config.surfaceContainer || "#1a2120"
    property color outline: config.outline || "#899391"
    property color errorColor: config.error || "#ffb4ab"
    property bool clock24: String(config.clock24) !== "false"

    function loadColors() {
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || !xhr.responseText)
                return
            try {
                var c = JSON.parse(xhr.responseText)
                if (c.primary) primary = c.primary
                if (c.on_primary) onPrimary = c.on_primary
                if (c.surface) surface = c.surface
                if (c.on_surface) onSurface = c.on_surface
                if (c.surface_container) surfaceContainer = c.surface_container
                if (c.outline) outline = c.outline
                if (c.error) errorColor = c.error
            } catch (e) {}
        }
        xhr.open("GET", Qt.resolvedUrl(config.colors || "backgrounds/colors.json"))
        xhr.send()
    }

    // Material 3 motion
    readonly property var emphasizedDecel: [0.05, 0.7, 0.1, 1.0, 1.0, 1.0]
    readonly property var emphasizedAccel: [0.3, 0.0, 0.8, 0.15, 1.0, 1.0]
    readonly property var standard: [0.2, 0.0, 0.0, 1.0, 1.0, 1.0]

    // ------------------------------------------------------------ users and sessions
    property int userIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property bool busy: false

    Repeater { id: users; model: userModel
        delegate: Item { property string uName: model.name; property string uReal: model.realName || ""
                         property string uIcon: model.icon || "" } }
    Repeater { id: sessions; model: sessionModel
        delegate: Item { property string sName: model.name || "" } }

    function user(i) { return users.count > i && users.itemAt(i) ? users.itemAt(i) : null }
    function userName() { var u = user(userIndex); return u ? u.uName : "" }
    function shownName() {
        var u = user(userIndex)
        if (!u) return ""
        var n = u.uReal.length ? u.uReal : u.uName
        return n.charAt(0).toUpperCase() + n.slice(1)
    }
    function hello() {
        var h = new Date().getHours()
        return h < 5 ? "Up late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
    }
    function login() {
        if (busy) return
        busy = true
        error.text = ""
        sddm.login(userName(), password.text, sessionIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            busy = false
            password.text = ""
            error.text = "Wrong password. Try again."
            shake.restart()
            password.forceActiveFocus()
        }
        function onLoginSucceeded() { leaving.start() }
    }

    // ------------------------------------------------------------ the wallpaper
    Item {
        id: backdrop
        anchors.fill: parent
        opacity: 0
        scale: 1.08

        Image {
            id: wallpaper
            anchors.fill: parent
            source: config.background || "backgrounds/lennox.jpg"
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            visible: false
        }
        MultiEffect {
            id: blurred
            anchors.fill: parent
            source: wallpaper
            blurEnabled: true
            blurMax: 64
            blur: 0.0
            saturation: 0.1
        }
        // A gentle darkening toward the bottom, so the words stay readable on any picture
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.15) }
                GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.55) }
            }
        }
    }

    // ------------------------------------------------------------ the clock
    Column {
        id: clockBox
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.12 + 30
        opacity: 0
        spacing: 2

        Text {
            id: clock
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.onSurface
            font.family: "Inter"
            font.pixelSize: Math.round(root.height * 0.12)
            font.weight: Font.DemiBold
            font.letterSpacing: -2
            text: Qt.formatTime(new Date(), root.clock24 ? "HH:mm" : "h:mm")
        }
        Text {
            id: date
            anchors.horizontalCenter: parent.horizontalCenter
            color: Qt.rgba(root.onSurface.r, root.onSurface.g, root.onSurface.b, 0.8)
            font.family: "Inter"
            font.pixelSize: Math.round(root.height * 0.024)
            font.weight: Font.Medium
            text: Qt.formatDate(new Date(), "dddd d MMMM")
        }
        Timer {
            interval: 1000; running: true; repeat: true
            onTriggered: {
                clock.text = Qt.formatTime(new Date(), root.clock24 ? "HH:mm" : "h:mm")
                date.text = Qt.formatDate(new Date(), "dddd d MMMM")
            }
        }
    }

    // ------------------------------------------------------------ profiles (more than one user)
    Row {
        id: profiles
        visible: users.count > 1
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: card.top
        anchors.bottomMargin: 22
        spacing: 14
        opacity: card.opacity
        Repeater {
            model: users.count
            delegate: Item {
                width: 52; height: 52
                property bool current: index === root.userIndex
                Avatar {
                    anchors.centerIn: parent
                    size: parent.current ? 52 : 40
                    source: root.user(index) ? root.user(index).uIcon : ""
                    letter: root.user(index) ? root.user(index).uName.charAt(0).toUpperCase() : "?"
                    ring: parent.current ? root.primary : "transparent"
                    tint: root.primary
                    ink: root.onPrimary
                    opacity: parent.current ? 1.0 : 0.6
                    Behavior on size { NumberAnimation { duration: 300; easing.type: Easing.BezierSpline; easing.bezierCurve: root.emphasizedDecel } }
                }
                MouseArea { anchors.fill: parent; onClicked: { root.userIndex = index; password.forceActiveFocus() } }
            }
        }
    }

    // ------------------------------------------------------------ the card
    Rectangle {
        id: card
        width: Math.min(420, root.width - 48)
        height: content.implicitHeight + 56
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.46 + 40
        radius: 32
        color: Qt.rgba(root.surfaceContainer.r, root.surfaceContainer.g, root.surfaceContainer.b, 0.72)
        border.color: Qt.rgba(root.outline.r, root.outline.g, root.outline.b, 0.35)
        border.width: 1
        opacity: 0
        transformOrigin: Item.Center

        Column {
            id: content
            anchors.centerIn: parent
            width: parent.width - 56
            spacing: 14

            Avatar {
                id: avatar
                anchors.horizontalCenter: parent.horizontalCenter
                size: 112
                source: root.user(root.userIndex) ? root.user(root.userIndex).uIcon : ""
                letter: root.shownName().charAt(0)
                ring: root.primary
                tint: root.primary
                ink: root.onPrimary
                scale: 0.6
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: Qt.rgba(root.onSurface.r, root.onSurface.g, root.onSurface.b, 0.7)
                font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium
                text: root.hello() + ","
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: root.onSurface
                font.family: "Inter"; font.pixelSize: 30; font.weight: Font.Bold
                text: root.shownName()
            }

            // The password pill
            Item {
                id: field
                width: parent.width
                height: 54
                Rectangle {
                    id: pill
                    anchors.fill: parent
                    radius: height / 2
                    color: Qt.rgba(root.surface.r, root.surface.g, root.surface.b, 0.55)
                    border.width: password.activeFocus ? 2 : 1
                    border.color: error.text.length ? root.errorColor
                                  : password.activeFocus ? root.primary
                                  : Qt.rgba(root.outline.r, root.outline.g, root.outline.b, 0.6)
                    Behavior on border.color { ColorAnimation { duration: 200 } }
                }
                TextField {
                    id: password
                    objectName: "password"
                    anchors.left: parent.left
                    anchors.right: go.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 22
                    anchors.rightMargin: 8
                    echoMode: TextInput.Password
                    passwordCharacter: "●"
                    placeholderText: keyboard.capsLock ? "Password (Caps Lock is on)" : "Password"
                    placeholderTextColor: keyboard.capsLock ? root.errorColor
                                          : Qt.rgba(root.onSurface.r, root.onSurface.g, root.onSurface.b, 0.5)
                    color: root.onSurface
                    font.family: "Inter"; font.pixelSize: 17
                    background: Item {}
                    focus: true
                    enabled: !root.busy
                    onAccepted: root.login()
                    Keys.onEscapePressed: text = ""
                }
                // The round "go" button: an arrow, or a spinner while checking
                Rectangle {
                    id: go
                    width: 42; height: 42; radius: 21
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.primary
                    scale: goArea.pressed ? 0.9 : 1.0
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        visible: !root.busy
                        text: "→"
                        color: root.onPrimary
                        font.pixelSize: 22; font.weight: Font.Bold
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        visible: root.busy
                        width: 20; height: 20; radius: 10
                        color: "transparent"
                        border.width: 3
                        border.color: Qt.rgba(root.onPrimary.r, root.onPrimary.g, root.onPrimary.b, 0.3)
                        Rectangle { width: 6; height: 6; radius: 3; color: root.onPrimary; x: 7; y: -1.5 }
                        RotationAnimation on rotation { from: 0; to: 360; duration: 800; loops: Animation.Infinite; running: root.busy }
                    }
                    MouseArea { id: goArea; anchors.fill: parent; onClicked: root.login() }
                }
                SequentialAnimation {
                    id: shake
                    property real d: 10
                    NumberAnimation { target: field; property: "x"; to: -shake.d; duration: 55 }
                    NumberAnimation { target: field; property: "x"; to: shake.d; duration: 70 }
                    NumberAnimation { target: field; property: "x"; to: -shake.d * 0.6; duration: 70 }
                    NumberAnimation { target: field; property: "x"; to: shake.d * 0.4; duration: 70 }
                    NumberAnimation { target: field; property: "x"; to: 0; duration: 60 }
                }
            }
            Text {
                id: error
                anchors.horizontalCenter: parent.horizontalCenter
                color: root.errorColor
                font.family: "Inter"; font.pixelSize: 13; font.weight: Font.Medium
                text: ""
                visible: text.length > 0
            }
        }
    }

    // ------------------------------------------------------------ bottom: session + power
    Row {
        id: bottom
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 10
        opacity: 0

        Chip {
            id: sessionChip
            label: sessions.count > root.sessionIndex && sessions.itemAt(root.sessionIndex)
                   ? sessions.itemAt(root.sessionIndex).sName : "Session"
            icon: "▦"
            tip: "Desktop session (click to change)"
            onClicked: root.sessionIndex = sessions.count ? (root.sessionIndex + 1) % sessions.count : 0
        }
        Chip { visible: sddm.canSuspend; icon: "☾"; label: "Sleep"; onClicked: sddm.suspend() }
        Chip { visible: sddm.canReboot; icon: "↻"; label: "Restart"; onClicked: sddm.reboot() }
        Chip { visible: sddm.canPowerOff; icon: "⏻"; label: "Shut down"; onClicked: sddm.powerOff() }
    }

    component Chip: Rectangle {
        id: chip
        property string label: ""
        property string icon: ""
        property string tip: ""
        signal clicked()
        height: 40
        width: chipRow.implicitWidth + 28
        radius: 20
        color: chipArea.containsMouse ? Qt.rgba(root.primary.r, root.primary.g, root.primary.b, 0.22)
                                      : Qt.rgba(root.surfaceContainer.r, root.surfaceContainer.g, root.surfaceContainer.b, 0.6)
        border.color: Qt.rgba(root.outline.r, root.outline.g, root.outline.b, 0.3)
        Behavior on color { ColorAnimation { duration: 150 } }
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 8
            Text { text: chip.icon; color: root.primary; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter }
            Text { text: chip.label; color: root.onSurface; font.family: "Inter"; font.pixelSize: 14
                   font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: chipArea; anchors.fill: parent; hoverEnabled: true; onClicked: chip.clicked() }
    }

    // A round picture with a colored ring; your initial when there is no picture
    component Avatar: Item {
        id: av
        property real size: 96
        property string source: ""
        property string letter: "?"
        property color ring: "white"
        property color tint: "teal"
        property color ink: "black"
        width: size; height: size
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: av.tint
            Text { anchors.centerIn: parent; text: av.letter; color: av.ink
                   font.family: "Inter"; font.pixelSize: av.size * 0.42; font.weight: Font.Bold
                   visible: face.status !== Image.Ready }
        }
        Image {
            id: face
            anchors.fill: parent
            source: av.source.length ? (av.source.indexOf("/") === 0 ? "file://" + av.source : av.source) : ""
            fillMode: Image.PreserveAspectCrop
            sourceSize: Qt.size(256, 256)
            visible: false
            asynchronous: true
        }
        Rectangle { id: mask; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
        MultiEffect {
            anchors.fill: parent
            source: face
            maskEnabled: true
            maskSource: mask
            visible: face.status === Image.Ready
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: width / 2
            color: "transparent"
            border.color: av.ring
            border.width: 3
        }
    }

    // ------------------------------------------------------------ motion
    ParallelAnimation {
        id: opening
        running: true
        NumberAnimation { target: backdrop; property: "opacity"; to: 1; duration: 700; easing.type: Easing.OutCubic }
        NumberAnimation { target: backdrop; property: "scale"; to: 1.0; duration: 1400
                          easing.type: Easing.BezierSpline; easing.bezierCurve: root.emphasizedDecel }
        NumberAnimation { target: blurred; property: "blur"; to: 1.0; duration: 1200; easing.type: Easing.OutCubic }
        SequentialAnimation {
            PauseAnimation { duration: 250 }
            ParallelAnimation {
                NumberAnimation { target: clockBox; property: "opacity"; to: 1; duration: 600; easing.type: Easing.OutCubic }
                NumberAnimation { target: clockBox; property: "y"; to: root.height * 0.12; duration: 900
                                  easing.type: Easing.BezierSpline; easing.bezierCurve: root.emphasizedDecel }
            }
        }
        SequentialAnimation {
            PauseAnimation { duration: 420 }
            ParallelAnimation {
                NumberAnimation { target: card; property: "opacity"; to: 1; duration: 600; easing.type: Easing.OutCubic }
                NumberAnimation { target: card; property: "y"; to: root.height * 0.46; duration: 900
                                  easing.type: Easing.BezierSpline; easing.bezierCurve: root.emphasizedDecel }
                NumberAnimation { target: avatar; property: "scale"; to: 1.0; duration: 900; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
            }
        }
        SequentialAnimation {
            PauseAnimation { duration: 700 }
            NumberAnimation { target: bottom; property: "opacity"; to: 1; duration: 600 }
        }
    }

    // Logged in: the card shrinks away and the screen fades to black while the desktop loads
    Rectangle { id: curtain; anchors.fill: parent; color: "black"; opacity: 0 }
    ParallelAnimation {
        id: leaving
        NumberAnimation { target: card; property: "scale"; to: 0.88; duration: 450
                          easing.type: Easing.BezierSpline; easing.bezierCurve: root.emphasizedAccel }
        NumberAnimation { targets: [card, clockBox, bottom, profiles]; property: "opacity"; to: 0; duration: 350 }
        NumberAnimation { target: curtain; property: "opacity"; to: 1; duration: 650; easing.type: Easing.InCubic }
    }

    Component.onCompleted: {
        loadColors()
        password.forceActiveFocus()
    }
    Keys.onLeftPressed: if (users.count > 1) userIndex = (userIndex + users.count - 1) % users.count
    Keys.onRightPressed: if (users.count > 1) userIndex = (userIndex + 1) % users.count
}
