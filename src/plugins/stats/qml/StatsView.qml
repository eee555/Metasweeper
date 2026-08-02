import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

/**
 * 统计插件主视图 - 左右分割布局
 *
 * ┌──────────┬──────────────────────────────────────────────────┐
 * │ 导航列表  │  内容区（StackLayout 切换）                       │
 * │          │                                                  │
 * │ 综合统计  │  GeneralStatsView / BvAnalysisView / ...        │
 * │ BV分析   │                                                  │
 * └──────────┴──────────────────────────────────────────────────┘
 */

Rectangle {
    id: root
    color: "#f5f5f5"

    // ── 导航数据 ──
    ListModel {
        id: navModel
        ListElement {
            name: "综合统计"
            icon: "\u{1F4CA}"
        }
        ListElement {
            name: "BV分析"
            icon: "\u{26A1}"
        }
    }

    property int currentNavIndex: 0

    // ── 主布局：左右分割 ──
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── 左侧导航栏 ──
        Rectangle {
            Layout.preferredWidth: 130
            Layout.fillHeight: true
            color: "#ffffff"

            // 右侧分隔线
            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: "#e0e0e0"
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4

                // 标题
                Text {
                    text: "统计类别"
                    color: "#999999"
                    font.pixelSize: 11
                    Layout.fillWidth: true
                    leftPadding: 8
                    bottomPadding: 4
                }

                ListView {
                    id: navList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: navModel
                    currentIndex: root.currentNavIndex
                    clip: true
                    spacing: 2

                    delegate: ItemDelegate {
                        width: navList.width
                        height: 36

                        background: Rectangle {
                            radius: 6
                            color: model.index === root.currentNavIndex ? "#e3f2fd" : (mouseArea.containsMouse ? "#f5f5f5" : "transparent")
                        }

                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8

                            Text {
                                text: icon
                                font.pixelSize: 14
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: name
                                color: model.index === root.currentNavIndex ? "#1565c0" : "#333333"
                                font.pixelSize: 13
                                font.bold: model.index === root.currentNavIndex
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: mouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.currentNavIndex = model.index;
                            }
                        }
                    }
                }
            }
        }

        // ── 右侧内容区 ──
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentNavIndex

            GeneralStatsView {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }

            BvAnalysisView {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }
    }
}
