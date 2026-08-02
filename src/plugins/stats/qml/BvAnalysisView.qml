import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

/**
 * BV分析视图 - BV分布热力图
 *
 * 布局：
 * ┌─────────────────────────────────────────────────────────────┐
 * │  [全部/仅胜局]  [显示局数]                                    │
 * ├─────────────────────────────────────────────────────────────┤
 * │  初级                                                        │
 * │  [■][■][■][■][■][■]...                                      │
 * ├─────────────────────────────────────────────────────────────┤
 * │  中级                                                        │
 * │  [■][■][■][■][■][■]...                                      │
 * ├─────────────────────────────────────────────────────────────┤
 * │  高级                                                        │
 * │  [■][■][■][■][■][■]...                                      │
 * └─────────────────────────────────────────────────────────────┘
 */

Rectangle {
    id: root
    color: "#f5f5f5"

    // ── 状态 ──
    property int winsOnly: 1       // 0=全部, 1=仅胜局
    property int currentMode: 0    // -1=全部, 0=标准
    property bool showCount: false  // 是否显示局数文字
    property var beginnerData: ({})
    property var intermediateData: ({})
    property var expertData: ({})

    // ── 颜色档位 ──
    readonly property var colorLevels: ["#e0e0e0"   // 0次：灰色
        , "#c8e6c9"   // 1-9次：浅绿
        , "#66bb6a"   // 10-49次：中绿
        , "#2e7d32"   // 50-99次：深绿
        , "#1b5e20"    // ≥100次：极深绿
    ]

    function countToColorIndex(count) {
        if (count === 0)
            return 0;
        if (count < 10)
            return 1;
        if (count < 50)
            return 2;
        if (count < 100)
            return 3;
        return 4;
    }

    function textColorForIndex(idx) {
        return idx >= 3 ? "#ffffff" : "#333333";
    }

    // ── 数据加载 ──
    function loadData() {
        try {
            beginnerData = JSON.parse(bridge.getBvDistribution(3, currentMode, winsOnly));
            intermediateData = JSON.parse(bridge.getBvDistribution(4, currentMode, winsOnly));
            expertData = JSON.parse(bridge.getBvDistribution(5, currentMode, winsOnly));
        } catch (e) {
            console.warn("BvAnalysisView loadData error:", e);
        }
    }

    function getCount(data, bv) {
        var val = data[String(bv)];
        return val !== undefined ? val : 0;
    }

    // ── 延迟首次加载 ──
    Timer {
        id: initTimer
        interval: 600
        running: true
        repeat: false
        onTriggered: root.loadData()
    }

    Connections {
        target: bridge
        onDataChanged: root.loadData()
        onBvBeginnerMinChanged: root.loadData()
        onBvBeginnerMaxChanged: root.loadData()
        onBvIntermediateMinChanged: root.loadData()
        onBvIntermediateMaxChanged: root.loadData()
        onBvExpertMinChanged: root.loadData()
        onBvExpertMaxChanged: root.loadData()
    }

    // ── 主布局 ──
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ── 顶部工具栏 ──
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ComboBox {
                id: modeCombo
                property var modeValues: [-1]
                model: ["全部"]
                currentIndex: 1
                onActivated: {
                    root.currentMode = modeValues[currentIndex];
                    root.loadData();
                }

                background: Rectangle {
                    radius: 4
                    border.color: "#cccccc"
                    color: "#ffffff"
                    implicitWidth: 110
                    implicitHeight: 30
                }

                contentItem: Text {
                    text: modeCombo.displayText
                    color: "#333333"
                    font.pixelSize: 13
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                }

                delegate: ItemDelegate {
                    width: modeCombo.width
                    contentItem: Text {
                        text: modelData
                        color: "#333333"
                        font.pixelSize: 12
                    }
                    background: Rectangle {
                        color: highlighted ? "#e3f2fd" : "#ffffff"
                    }
                    highlighted: modeCombo.highlightedIndex === index
                }

                Component.onCompleted: {
                    try {
                        var names = JSON.parse(bridge.getModeNames());
                        var items = ["全部"];
                        var values = [-1];
                        var keys = Object.keys(names).map(Number).sort(function (a, b) {
                            return a - b;
                        });
                        for (var i = 0; i < keys.length; i++) {
                            items.push(names[keys[i]]);
                            values.push(keys[i]);
                        }
                        model = items;
                        modeValues = values;
                        currentIndex = 1; // 默认标准模式
                        root.currentMode = 0;
                    } catch (e) {
                        console.warn("modeCombo init error:", e);
                    }
                }
            }

            ComboBox {
                id: filterCombo
                model: ["全部", "仅胜局"]
                currentIndex: 1
                onCurrentIndexChanged: {
                    root.winsOnly = currentIndex;
                    root.loadData();
                }

                background: Rectangle {
                    radius: 4
                    border.color: "#cccccc"
                    color: "#ffffff"
                    implicitWidth: 120
                    implicitHeight: 30
                }

                contentItem: Text {
                    text: filterCombo.displayText
                    color: "#333333"
                    font.pixelSize: 13
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                }
            }

            Label {
                text: "显示局数"
                color: "#333333"
                font.pixelSize: 13
            }

            Switch {
                id: showCountSwitch
                checked: root.showCount
                onCheckedChanged: root.showCount = checked
            }

            Item {
                Layout.fillWidth: true
            }

            // ── 图例 ──
            RowLayout {
                spacing: 4
                Layout.alignment: Qt.AlignRight

                Repeater {
                    model: [
                        {
                            label: "0",
                            color: root.colorLevels[0]
                        },
                        {
                            label: "1-9",
                            color: root.colorLevels[1]
                        },
                        {
                            label: "10-49",
                            color: root.colorLevels[2]
                        },
                        {
                            label: "50-99",
                            color: root.colorLevels[3]
                        },
                        {
                            label: "≥100",
                            color: root.colorLevels[4]
                        }
                    ]

                    delegate: RowLayout {
                        spacing: 2
                        Rectangle {
                            width: 14
                            height: 14
                            radius: 2
                            color: modelData.color
                            border.color: "#bdbdbd"
                            border.width: 0.5
                        }
                        Text {
                            text: modelData.label
                            font.pixelSize: 10
                            color: "#666666"
                        }
                    }
                }
            }
        }

        // ── 三个板块 ──
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: sectionsCol.implicitHeight + 20
            clip: true

            ColumnLayout {
                id: sectionsCol
                width: parent.width
                spacing: 16

                BvSection {
                    id: beginnerSection
                    Layout.fillWidth: true
                    title: "初级"
                    bvMin: bridge.bvBeginnerMin
                    bvMax: bridge.bvBeginnerMax
                    dataMap: root.beginnerData
                    showCount: root.showCount
                    colorLevels: root.colorLevels
                }

                BvSection {
                    id: intermediateSection
                    Layout.fillWidth: true
                    title: "中级"
                    bvMin: bridge.bvIntermediateMin
                    bvMax: bridge.bvIntermediateMax
                    dataMap: root.intermediateData
                    showCount: root.showCount
                    colorLevels: root.colorLevels
                }

                BvSection {
                    id: expertSection
                    Layout.fillWidth: true
                    title: "高级"
                    bvMin: bridge.bvExpertMin
                    bvMax: bridge.bvExpertMax
                    dataMap: root.expertData
                    showCount: root.showCount
                    colorLevels: root.colorLevels
                }
            }
        }
    }

    // ── BV 板块组件 ──
    component BvSection: Rectangle {
        id: section
        color: "#ffffff"
        radius: 8
        border.color: "#e0e0e0"
        border.width: 1

        property string title: ""
        property int bvMin: 0
        property int bvMax: 0
        property var dataMap: ({})
        property bool showCount: false
        property var colorLevels: []

        implicitHeight: sectionLayout.implicitHeight + 24

        ColumnLayout {
            id: sectionLayout
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Text {
                text: section.title
                font.pixelSize: 14
                font.bold: true
                color: "#333333"
            }

            Flow {
                id: flow
                Layout.fillWidth: true
                spacing: 2

                Repeater {
                    model: section.bvMax > section.bvMin ? (section.bvMax - section.bvMin + 1) : 0

                    delegate: Rectangle {
                        property int bvValue: section.bvMin + model.index
                        property int count: section.dataMap[String(bvValue)] || 0
                        property int colorIdx: {
                            if (count === 0)
                                return 0;
                            if (count < 10)
                                return 1;
                            if (count < 50)
                                return 2;
                            if (count < 100)
                                return 3;
                            return 4;
                        }

                        width: 28
                        height: section.showCount ? 38 : 28
                        radius: 3
                        color: section.colorLevels[colorIdx]

                        ToolTip.visible: mouseArea.containsMouse
                        ToolTip.text: "BV: " + bvValue + "  局数: " + count
                        ToolTip.delay: 300

                        Column {
                            anchors.centerIn: parent
                            spacing: 0

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bvValue
                                font.pixelSize: 9
                                color: colorIdx >= 3 ? "#ffffff" : "#555555"
                                visible: !section.showCount
                            }

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bvValue
                                font.pixelSize: 8
                                color: colorIdx >= 3 ? "#ffffff" : "#555555"
                                visible: section.showCount
                            }

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: count
                                font.pixelSize: 8
                                color: colorIdx >= 3 ? "#e0e0e0" : "#888888"
                                visible: section.showCount
                            }
                        }

                        MouseArea {
                            id: mouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                        }
                    }
                }
            }
        }
    }
}
