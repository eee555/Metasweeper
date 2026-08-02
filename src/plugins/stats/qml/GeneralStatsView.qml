import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtCharts 2.3

/**
 * 综合统计视图
 *
 * 布局：
 * ┌─────────────────────────────────────────────────────────────┐
 * │  [筛选栏]                                                    │
 * │  模式:[CB] 难度:[CB] [开始]~[结束] [本日][本周][本月][本年]  │
 * ├──────────────┬──────────────────────────────────────────────┤
 * │  汇总卡片    │   趋势折线图                                  │
 * └──────────────┴──────────────────────────────────────────────┘
 */

Rectangle {
    id: root
    color: "#f5f5f5"

    // ── 筛选状态 ──
    property int currentLevel: -1   // -1 = 全部
    property int currentMode: -1    // -1 = 全部
    property real startUs: 0         // 毫秒时间戳，0 = 不限
    property real endUs: 0           // 毫秒时间戳，0 = 不限
    property int topN: 0             // 前N名平均，0=全部平均

    property var levelNames: ({})
    property var modeNames: ({})
    property var summaryData: ({})
    property var enums: ({})

    // ── 延迟首次刷新 ──
    Timer {
        id: initTimer
        interval: 500
        running: true
        repeat: false
        onTriggered: {
            loadEnums();
            root.topN = bridge.getTopN();
            // 默认：标准模式 + 初级难度 + 本日
            modeCombo.currentIndex = 0;
            if (modeCombo.modeValues && modeCombo.modeValues.length > 0) {
                root.currentMode = modeCombo.modeValues[0]; // Standard=0
            }
            levelCombo.currentIndex = 0; // "初级"
            root.currentLevel = 3; // BEGINNER=3
            setTodayRange();
            refreshAll();
        }
    }

    // ── 监听 bridge 数据变化 ──
    Connections {
        target: bridge
        function onDataChanged() {
            refreshAll();
        }
        function onTopNChanged() {
            root.topN = bridge.getTopN();
        }
    }

    // ── 辅助函数 ──

    function loadEnums() {
        try {
            root.enums = JSON.parse(bridge.getEnumValues());
            root.levelNames = JSON.parse(bridge.getLevelNames());
            root.modeNames = JSON.parse(bridge.getModeNames());
        } catch (e) {
            console.warn("loadEnums error:", e);
        }
    }

    // 日期 → 毫秒时间戳（当天 00:00:00 本地时间）
    function dateToMs(date) {
        if (!date || isNaN(date.getTime()))
            return 0;
        var d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        return Math.floor(d.getTime());
    }

    // 日期 → 毫秒时间戳（当天 23:59:59 本地时间）
    function dateToEndMs(date) {
        if (!date || isNaN(date.getTime()))
            return 0;
        var d = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
        return Math.floor(d.getTime());
    }

    function setTodayRange() {
        var now = new Date();
        startDatePicker.setDate(now);
        endDatePicker.setDate(now);
        root.startUs = dateToMs(now);
        root.endUs = dateToEndMs(now);
    }

    function setYesterdayRange() {
        var now = new Date();
        var yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
        startDatePicker.setDate(yesterday);
        endDatePicker.setDate(yesterday);
        root.startUs = dateToMs(yesterday);
        root.endUs = dateToEndMs(yesterday);
    }

    function setThisWeekRange() {
        var now = new Date();
        var day = now.getDay(); // 0=周日
        var diff = day === 0 ? 6 : day - 1; // 周一为起点
        var monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diff);
        startDatePicker.setDate(monday);
        endDatePicker.setDate(now);
        root.startUs = dateToMs(monday);
        root.endUs = dateToEndMs(now);
    }

    function setThisMonthRange() {
        var now = new Date();
        var m1 = new Date(now.getFullYear(), now.getMonth(), 1);
        startDatePicker.setDate(m1);
        endDatePicker.setDate(now);
        root.startUs = dateToMs(m1);
        root.endUs = dateToEndMs(now);
    }

    function setThisYearRange() {
        var now = new Date();
        var y1 = new Date(now.getFullYear(), 0, 1);
        startDatePicker.setDate(y1);
        endDatePicker.setDate(now);
        root.startUs = dateToMs(y1);
        root.endUs = dateToEndMs(now);
    }

    function setAllRange() {
        startDatePicker.setDate(null);
        endDatePicker.setDate(null);
        root.startUs = 0;
        root.endUs = 0;
    }

    function pad2(n) {
        return n < 10 ? "0" + n : "" + n;
    }

    function fmtDate(d) {
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
    }

    function refreshAll() {
        try {
            var summary = JSON.parse(bridge.getSummary(root.currentLevel, root.currentMode, root.startUs, root.endUs));
            root.summaryData = summary || {};
            // 获取 topN 平均值并合并
            if (root.topN > 0 && root.summaryData) {
                var metrics = ["rtime", "3bvs", "ioe", "thrp", "corr", "ces", "cls"];
                for (var i = 0; i < metrics.length; i++) {
                    try {
                        var topnResult = JSON.parse(bridge.getTopNAvg(metrics[i], root.currentLevel, root.currentMode, root.startUs, root.endUs));
                        if (topnResult && topnResult.topn_avg != null) {
                            var key = metrics[i] === "rtime" ? "avg_win_time" : "avg_" + metrics[i];
                            root.summaryData[key] = topnResult.topn_avg;
                        }
                    } catch (e2) { /* ignore */ }
                }
            }
            trendChart.refresh();
        } catch (e) {
            console.warn("refreshAll error:", e);
        }
    }

    // ── 主布局 ──

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // ── 筛选栏（单行） ──
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            spacing: 6

            Label {
                text: "模式:"
                color: "#333333"
                font.pixelSize: 12
            }

            ComboBox {
                id: modeCombo
                model: ["全部"]
                currentIndex: 0
                Layout.preferredWidth: 100
                background: Rectangle {
                    color: "#ffffff"
                    radius: 4
                    border.color: "#cccccc"
                    implicitHeight: 28
                }
                contentItem: Text {
                    text: modeCombo.displayText
                    color: "#333333"
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 6
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
                popup: Popup {
                    y: modeCombo.height
                    width: modeCombo.width
                    padding: 1
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: modeCombo.popup.visible ? modeCombo.delegateModel : null
                        currentIndex: modeCombo.highlightedIndex
                    }
                    background: Rectangle {
                        color: "#ffffff"
                        border.color: "#cccccc"
                        radius: 4
                    }
                }
                property var modeValues: []
                onActivated: {
                    root.currentMode = modeValues[currentIndex];
                    refreshAll();
                }
                Component.onCompleted: {
                    try {
                        var names = JSON.parse(bridge.getModeNames());
                        var items = [];
                        var values = [];
                        var keys = Object.keys(names).map(Number).sort(function (a, b) {
                            return a - b;
                        });
                        for (var i = 0; i < keys.length; i++) {
                            items.push(names[keys[i]]);
                            values.push(keys[i]);
                        }
                        model = items;
                        modeValues = values;
                    } catch (e) {
                        console.warn("modeCombo init error:", e);
                    }
                }
            }

            Label {
                text: "难度:"
                color: "#333333"
                font.pixelSize: 12
            }

            ComboBox {
                id: levelCombo
                model: ["初级", "中级", "高级", "自定义"]
                currentIndex: 0
                Layout.preferredWidth: 90
                background: Rectangle {
                    color: "#ffffff"
                    radius: 4
                    border.color: "#cccccc"
                    implicitHeight: 28
                }
                contentItem: Text {
                    text: levelCombo.displayText
                    color: "#333333"
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 6
                }
                delegate: ItemDelegate {
                    width: levelCombo.width
                    contentItem: Text {
                        text: modelData
                        color: "#333333"
                        font.pixelSize: 12
                    }
                    background: Rectangle {
                        color: highlighted ? "#e3f2fd" : "#ffffff"
                    }
                    highlighted: levelCombo.highlightedIndex === index
                }
                popup: Popup {
                    y: levelCombo.height
                    width: levelCombo.width
                    padding: 1
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: levelCombo.popup.visible ? levelCombo.delegateModel : null
                        currentIndex: levelCombo.highlightedIndex
                    }
                    background: Rectangle {
                        color: "#ffffff"
                        border.color: "#cccccc"
                        radius: 4
                    }
                }
                onActivated: {
                    var lv = [root.enums.level.beginner, root.enums.level.intermediate, root.enums.level.expert, root.enums.level.custom];
                    root.currentLevel = lv[currentIndex];
                    refreshAll();
                }
            }

            Rectangle {
                width: 1
                height: 20
                color: "#e0e0e0"
            }

            CalendarPicker {
                id: startDatePicker
                onDateSelected: function (d) {
                    if (d) {
                        root.startUs = dateToMs(d);
                    } else {
                        root.startUs = 0;
                    }
                    refreshAll();
                }
            }

            Label {
                text: "~"
                color: "#999999"
                font.pixelSize: 13
            }

            CalendarPicker {
                id: endDatePicker
                onDateSelected: function (d) {
                    if (d) {
                        root.endUs = dateToEndMs(d);
                    } else {
                        root.endUs = 0;
                    }
                    refreshAll();
                }
            }

            Rectangle {
                width: 1
                height: 20
                color: "#e0e0e0"
            }

            Button {
                id: btnToday
                text: "本日"
                background: Rectangle {
                    color: btnToday.pressed ? "#e3f2fd" : "#ffffff"
                    radius: 4
                    border.color: "#90caf9"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#1565c0"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setTodayRange();
                    refreshAll();
                }
            }
            Button {
                id: btnYesterday
                text: "昨日"
                background: Rectangle {
                    color: btnYesterday.pressed ? "#e3f2fd" : "#ffffff"
                    radius: 4
                    border.color: "#90caf9"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#1565c0"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setYesterdayRange();
                    refreshAll();
                }
            }
            Button {
                id: btnWeek
                text: "本周"
                background: Rectangle {
                    color: btnWeek.pressed ? "#e8f5e9" : "#ffffff"
                    radius: 4
                    border.color: "#a5d6a7"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#2e7d32"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setThisWeekRange();
                    refreshAll();
                }
            }
            Button {
                id: btnMonth
                text: "本月"
                background: Rectangle {
                    color: btnMonth.pressed ? "#fff3e0" : "#ffffff"
                    radius: 4
                    border.color: "#ffcc80"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#e65100"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setThisMonthRange();
                    refreshAll();
                }
            }
            Button {
                id: btnYear
                text: "本年"
                background: Rectangle {
                    color: btnYear.pressed ? "#f3e5f5" : "#ffffff"
                    radius: 4
                    border.color: "#ce93d8"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#7b1fa2"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setThisYearRange();
                    refreshAll();
                }
            }
            Button {
                id: btnAll
                text: "全部"
                background: Rectangle {
                    color: btnAll.pressed ? "#eceff1" : "#ffffff"
                    radius: 4
                    border.color: "#b0bec5"
                    implicitHeight: 26
                    implicitWidth: 44
                }
                contentItem: Text {
                    text: parent.text
                    color: "#546e7a"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    setAllRange();
                    refreshAll();
                }
            }

            Item {
                Layout.fillWidth: true
            }
        }

        // ── 上半区：汇总卡片 + 进步历程图 ──
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 180
            spacing: 12
            clip: true

            ColumnLayout {
                Layout.minimumWidth: 85
                Layout.maximumWidth: 102
                Layout.fillHeight: true
                spacing: 4

                SummaryCard {
                    Layout.fillWidth: true
                    title: "总局数"
                    value: (root.summaryData && root.summaryData.total) || 0
                    icon: "\u{1F3AE}"
                }
                SummaryCard {
                    Layout.fillWidth: true
                    title: "胜局"
                    value: (root.summaryData && root.summaryData.wins) || 0
                    icon: "\u{1F3C6}"
                }
                SummaryCard {
                    Layout.fillWidth: true
                    title: "胜率"
                    value: root.summaryData && root.summaryData.total > 0 ? ((root.summaryData.wins || 0) / root.summaryData.total * 100).toFixed(1) + "%" : "0%"
                    icon: "\u{1F4C8}"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "用时"
                    icon: "\u{23F1}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_time ? root.summaryData.best_time.toFixed(2) + "s" : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_time ? root.summaryData.worst_time.toFixed(2) + "s" : "-"
                    avgValue: root.summaryData && root.summaryData.avg_win_time ? root.summaryData.avg_win_time.toFixed(2) + "s" : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "3BV/s"
                    icon: "\u{26A1}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_3bvs ? root.summaryData.best_3bvs.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_3bvs ? root.summaryData.worst_3bvs.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_3bvs ? root.summaryData.avg_3bvs.toFixed(2) : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "IOE"
                    icon: "\u{1F4CA}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_ioe ? root.summaryData.best_ioe.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_ioe ? root.summaryData.worst_ioe.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_ioe ? root.summaryData.avg_ioe.toFixed(2) : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "thrp"
                    icon: "\u{1F680}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_thrp ? root.summaryData.best_thrp.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_thrp ? root.summaryData.worst_thrp.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_thrp ? root.summaryData.avg_thrp.toFixed(2) : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "corr"
                    icon: "\u{1F3AF}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_corr ? root.summaryData.best_corr.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_corr ? root.summaryData.worst_corr.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_corr ? root.summaryData.avg_corr.toFixed(2) : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "ces"
                    icon: "\u{1F525}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_ces ? root.summaryData.best_ces.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_ces ? root.summaryData.worst_ces.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_ces ? root.summaryData.avg_ces.toFixed(2) : "-"
                }
                MetricCard {
                    Layout.fillWidth: true
                    title: "cls"
                    icon: "\u{1F4A6}"
                    bestLabel: "最佳"
                    bestValue: root.summaryData && root.summaryData.best_cls ? root.summaryData.best_cls.toFixed(2) : "-"
                    worstLabel: "最差"
                    worstValue: root.summaryData && root.summaryData.worst_cls ? root.summaryData.worst_cls.toFixed(2) : "-"
                    avgValue: root.summaryData && root.summaryData.avg_cls ? root.summaryData.avg_cls.toFixed(2) : "-"
                }
            }

            TrendChart {
                id: trendChart
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 300
            }
        }
    }

    // ── 简单卡片组件（单值） ──
    component SummaryCard: Rectangle {
        property string title: ""
        property var value: 0
        property string icon: ""
        color: "#ffffff"
        radius: 8
        implicitHeight: 36
        Row {
            anchors.fill: parent
            anchors.margins: 6
            spacing: 6
            Item {
                width: 20
                height: parent.height
                Text {
                    anchors.centerIn: parent
                    text: icon
                    font.pixelSize: 14
                }
            }
            Column {
                width: parent.width - 32
                spacing: 0
                Text {
                    text: title
                    color: "#999999"
                    font.pixelSize: 9
                }
                Text {
                    text: String(value)
                    color: "#333333"
                    font.pixelSize: 13
                    font.bold: true
                }
            }
        }
    }

    // ── 指标卡片组件（最佳/最差/平均） ──
    component MetricCard: Rectangle {
        property string title: ""
        property string icon: ""
        property string bestLabel: ""
        property string bestValue: "-"
        property string worstLabel: ""
        property string worstValue: ""
        property string avgValue: "-"
        color: "#ffffff"
        radius: 8
        implicitHeight: worstLabel ? 56 : 44
        Row {
            anchors.fill: parent
            anchors.margins: 5
            spacing: 5
            Item {
                width: 20
                height: parent.height
                Text {
                    anchors.centerIn: parent
                    text: icon
                    font.pixelSize: 14
                }
            }
            Column {
                width: parent.width - 28
                spacing: 0
                Text {
                    text: title
                    color: "#999999"
                    font.pixelSize: 9
                }
                Row {
                    spacing: 4
                    Text {
                        text: bestLabel
                        color: "#4CAF50"
                        font.pixelSize: 9
                    }
                    Text {
                        text: bestValue
                        color: "#333333"
                        font.pixelSize: 10
                        font.bold: true
                    }
                }
                Row {
                    spacing: 4
                    visible: worstLabel !== ""
                    Text {
                        text: worstLabel
                        color: "#F44336"
                        font.pixelSize: 9
                    }
                    Text {
                        text: worstValue
                        color: "#333333"
                        font.pixelSize: 10
                        font.bold: true
                    }
                }
                Row {
                    spacing: 4
                    Text {
                        text: root.topN > 0 ? "前" + root.topN + "平均" : "平均"
                        color: "#1976D2"
                        font.pixelSize: 9
                    }
                    Text {
                        text: avgValue
                        color: "#333333"
                        font.pixelSize: 10
                        font.bold: true
                    }
                }
            }
        }
    }
}
