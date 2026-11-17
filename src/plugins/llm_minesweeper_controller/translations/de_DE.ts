<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="de_DE" sourcelanguage="zh_CN">
    <context>
        <name>MinesweeperMcp</name>
        <message>
            <location filename="../config.py" line="22" />
            <source>MCP 端口</source>
            <translation>MCP-Port</translation>
        </message>
        <message>
            <location filename="../config.py" line="23" />
            <source>端口必须为 1024..65535 的整数</source>
            <translation>Port muss eine ganze Zahl zwischen 1024 und 65535 sein</translation>
        </message>
        <message>
            <location filename="../config.py" line="55" />
            <location filename="../plugin.py" line="90" />
            <source>旧配置清理失败，MCP 服务保持停止</source>
            <translation>Bereinigung der alten Konfiguration fehlgeschlagen; MCP bleibt gestoppt</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="54" />
            <source>元扫雷 MCP 服务</source>
            <translation>MetaSweeper-MCP-Dienst</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="56" />
            <source>通过本机 MCP 服务提供可见棋盘和经授权的辅助操作</source>
            <translation>Sichtbares Spielfeld und genehmigte Hilfsaktionen über einen lokalen MCP-Dienst bereitstellen</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="103" />
            <source>请在现有 agent 的 MCP 配置中添加一个 Streamable HTTP 服务，保留其他配置。
endpoint: {endpoint}
协议版本：2025-11-25。使用客户端已有的 HTTP MCP 支持，不安装任何包，若客户端不支持 Streamable HTTP，明确报告不支持，不能改用 stdio。不启动子进程或新游戏，不自动玩游戏。连接后等待用户明确指令。只读取可见棋盘，控制需用户重新授权并开启主进程相应开关。click_cell 支持 clicks 数组批量点击（最多128项），也兼容 row/col/button 单点。批量按顺序逐项确认，首个失败即停止；先检查 completed/results/stopped_index。动作超时意味着结果未知，不得自动重试。</source>
            <translation>Füge der vorhandenen MCP-Konfiguration des Agenten einen Streamable-HTTP-Dienst hinzu; andere Einstellungen beibehalten.
endpoint: {endpoint}
Protokollversion: 2025-11-25. Vorhandene HTTP-MCP-Unterstützung des Clients verwenden, keine Pakete installieren. Falls Streamable HTTP nicht unterstützt wird, dies ausdrücklich melden; nicht auf stdio wechseln. Keine Unterprozesse oder neue Spiele starten und nicht automatisch spielen. Nach der Verbindung auf ausdrückliche Benutzeranweisungen warten. Nur das sichtbare Spielfeld lesen. Steuerung erfordert erneute Benutzerautorisierung und die entsprechenden Schalter im Hauptprozess. click_cell akzeptiert ein clicks-Array (höchstens 128 Klicks) sowie einzelne row/col/button-Argumente. Stapelergebnisse der Reihe nach bestätigen und beim ersten Fehler stoppen; zuerst completed/results/stopped_index prüfen. Nach einem Aktionszeitlimit ist das Ergebnis unbekannt; nicht automatisch wiederholen.</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="126" />
            <source>服务已运行；更换端口前请先停止</source>
            <translation>Dienst läuft; vor einem Portwechsel stoppen</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="164" />
            <source>启动失败；请检查端口、SDK 连接及配置，不会自动重试</source>
            <translation>Start fehlgeschlagen; Port, SDK-Verbindung und Konfiguration prüfen. Kein automatischer Neuversuch.</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="183" />
            <source>私有通信线程尚未退出，禁止重启</source>
            <translation>Privater Kommunikationsthread läuft noch; Neustart gesperrt</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="118" />
            <location filename="../widgets.py" line="119" />
            <source>监听端口</source>
            <translation>Port</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="120" />
            <location filename="../widgets.py" line="121" />
            <source>配置提示词</source>
            <translation>Konfigurationshinweis</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="122" />
            <source>复制配置提示词</source>
            <translation>Konfigurationshinweis kopieren</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="165" />
            <source>停止MCP</source>
            <translation>MCP stoppen</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="166" />
            <source>启动MCP</source>
            <translation>MCP starten</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="175" />
            <source>已停止</source>
            <translation>Gestoppt</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="176" />
            <source>正在启动</source>
            <translation>Wird gestartet</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="177" />
            <source>运行中</source>
            <translation>Läuft</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="178" />
            <source>正在停止</source>
            <translation>Wird gestoppt</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="179" />
            <source>启动失败</source>
            <translation>Start fehlgeschlagen</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="182" />
            <source>运行中：{endpoint}</source>
            <translation>Läuft: {endpoint}</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="186" />
            <source>错误：{reason}</source>
            <translation>Fehler: {reason}</translation>
        </message>
    </context>
</TS>
