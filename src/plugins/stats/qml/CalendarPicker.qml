import QtQuick
import QtQuick.Controls

/**
 * 日历弹出式日期选择器
 *
 * 用法：
 *   CalendarPicker {
 *       id: startDate
 *       onDateSelected: (date) => { ... }
 *   }
 */
Item {
    id: root
    width: 120
    height: 30

    signal dateSelected(var date)

    property alias text: dateField.text
    property var selectedDate: undefined
    property string placeholder: "YYYY-MM-DD"

    function setDate(d) {
        if (d && !isNaN(d.getTime())) {
            selectedDate = d;
            dateField.text = pad2(d.getFullYear()) + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
        } else {
            selectedDate = undefined;
            dateField.text = "";
        }
    }

    function pad2(n) {
        return n < 10 ? "0" + n : "" + n;
    }

    TextField {
        id: dateField
        anchors.fill: parent
        placeholderText: root.placeholder
        color: "#333333"
        font.pixelSize: 13
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        readOnly: true
        background: Rectangle {
            color: "#ffffff"
            radius: 4
            border.color: dateField.activeFocus ? "#42a5f5" : "#cccccc"
            implicitWidth: 120
            implicitHeight: 30
        }
        onAccepted: applyText()
        onEditingFinished: applyText()

        function applyText() {
            if (text.length === 10) {
                var p = text.split("-");
                if (p.length === 3) {
                    var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
                    if (!isNaN(d.getTime())) {
                        root.selectedDate = d;
                        root.dateSelected(d);
                        calendarPopup.close();
                        return;
                    }
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                dateField.forceActiveFocus();
                calendarPopup.open();
            }
        }
    }

    Popup {
        id: calendarPopup
        x: 0
        y: parent.height + 2
        width: 280
        height: 300
        padding: 8
        modal: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#ffffff"
            border.color: "#cccccc"
            radius: 8
        }

        contentItem: Item {
            // 月份导航
            Row {
                id: navRow
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 36
                spacing: 4

                Button {
                    id: btnPrev
                    width: 36
                    height: 36
                    text: "<"
                    font.pixelSize: 16
                    background: Rectangle {
                        color: btnPrev.pressed ? "#e0e0e0" : "transparent"
                        radius: 4
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#333333"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 16
                    }
                    onClicked: {
                        calMonth = calMonth - 1;
                        if (calMonth < 0) {
                            calMonth = 11;
                            calYear = calYear - 1;
                        }
                    }
                }

                Text {
                    width: navRow.width - 76
                    height: 36
                    text: calYear + "年" + (calMonth + 1) + "月"
                    color: "#333333"
                    font.pixelSize: 14
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                Button {
                    id: btnNext
                    width: 36
                    height: 36
                    text: ">"
                    font.pixelSize: 16
                    background: Rectangle {
                        color: btnNext.pressed ? "#e0e0e0" : "transparent"
                        radius: 4
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#333333"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 16
                    }
                    onClicked: {
                        calMonth = calMonth + 1;
                        if (calMonth > 11) {
                            calMonth = 0;
                            calYear = calYear + 1;
                        }
                    }
                }
            }

            // 星期标题
            Row {
                id: weekRow
                anchors.top: navRow.bottom
                anchors.topMargin: 4
                anchors.left: parent.left
                anchors.right: parent.right
                height: 24

                Repeater {
                    model: ["一", "二", "三", "四", "五", "六", "日"]
                    Text {
                        width: weekRow.width / 7
                        height: 24
                        text: modelData
                        color: index >= 5 ? "#e53935" : "#999999"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            // 日历网格
            MonthGrid {
                id: monthGrid
                anchors.top: weekRow.bottom
                anchors.topMargin: 4
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: todayRow.top
                anchors.bottomMargin: 4

                month: calMonth
                year: calYear
                locale: Qt.locale("zh_CN")

                delegate: Item {
                    width: monthGrid.width / 7
                    height: 28

                    Rectangle {
                        id: dayBg
                        anchors.fill: parent
                        anchors.margins: 2
                        radius: width / 2
                        color: {
                            if (model.day <= 0)
                                return "transparent";
                            if (root.selectedDate && model.day === root.selectedDate.getDate() && calMonth === root.selectedDate.getMonth() && calYear === root.selectedDate.getFullYear())
                                return "#42a5f5";
                            return "transparent";
                        }
                    }

                    Text {
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 13
                        text: model.day > 0 ? model.day : ""
                        color: {
                            if (model.day <= 0)
                                return "transparent";
                            if (root.selectedDate && model.day === root.selectedDate.getDate() && calMonth === root.selectedDate.getMonth() && calYear === root.selectedDate.getFullYear())
                                return "#ffffff";
                            var today = new Date();
                            if (model.day === today.getDate() && calMonth === today.getMonth() && calYear === today.getFullYear())
                                return "#1565c0";
                            if (model.date && (model.date.getDay() === 0 || model.date.getDay() === 6))
                                return "#e53935";
                            return "#333333";
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: model.day > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (model.day > 0) {
                                var d = new Date(calYear, calMonth, model.day);
                                root.setDate(d);
                                root.dateSelected(d);
                                calendarPopup.close();
                            }
                        }
                    }
                }
            }

            // 今天按钮
            Row {
                id: todayRow
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                height: 32

                Button {
                    id: btnToday
                    text: "今天"
                    background: Rectangle {
                        color: btnToday.pressed ? "#e3f2fd" : "#f5f5f5"
                        radius: 4
                        border.color: "#90caf9"
                        implicitHeight: 28
                        implicitWidth: 60
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#1565c0"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        var now = new Date();
                        calYear = now.getFullYear();
                        calMonth = now.getMonth();
                        root.setDate(now);
                        root.dateSelected(now);
                        calendarPopup.close();
                    }
                }

                Button {
                    id: btnClear
                    text: "清除"
                    background: Rectangle {
                        color: btnClear.pressed ? "#ffebee" : "#f5f5f5"
                        radius: 4
                        border.color: "#ef9a9a"
                        implicitHeight: 28
                        implicitWidth: 60
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#c62828"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.selectedDate = undefined;
                        root.text = "";
                        root.dateSelected(null);
                        calendarPopup.close();
                    }
                }
            }
        }
    }

    // 日历当前显示的年月
    property int calYear: new Date().getFullYear()
    property int calMonth: new Date().getMonth()
}
