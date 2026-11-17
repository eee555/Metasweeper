<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US" sourcelanguage="zh_CN">
    <context>
        <name>MinesweeperMcp</name>
        <message>
            <location filename="../config.py" line="22" />
            <source>MCP 端口</source>
            <translation>MCP port</translation>
        </message>
        <message>
            <location filename="../config.py" line="23" />
            <source>端口必须为 1024..65535 的整数</source>
            <translation>Port must be an integer from 1024 to 65535</translation>
        </message>
        <message>
            <location filename="../config.py" line="55" />
            <location filename="../plugin.py" line="90" />
            <source>旧配置清理失败，MCP 服务保持停止</source>
            <translation>Legacy configuration cleanup failed; MCP remains stopped</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="54" />
            <source>元扫雷 MCP 服务</source>
            <translation>MetaSweeper MCP service</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="56" />
            <source>通过本机 MCP 服务提供可见棋盘和经授权的辅助操作</source>
            <translation>Expose the visible board and authorized assistance through a local MCP service</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="103" />
            <source>请在现有 agent 的 MCP 配置中添加一个 Streamable HTTP 服务，保留其他配置。
endpoint: {endpoint}
协议版本：2025-11-25。使用客户端已有的 HTTP MCP 支持，不安装任何包，若客户端不支持 Streamable HTTP，明确报告不支持，不能改用 stdio。不启动子进程或新游戏，不自动玩游戏。连接后等待用户明确指令。只读取可见棋盘，控制需用户重新授权并开启主进程相应开关。click_cell 支持 clicks 数组批量点击（最多128项），也兼容 row/col/button 单点。批量按顺序逐项确认，首个失败即停止；先检查 completed/results/stopped_index。动作超时意味着结果未知，不得自动重试。</source>
            <translation>Add a Streamable HTTP service to the existing agent MCP configuration, preserving other settings.
endpoint: {endpoint}
Protocol version: 2025-11-25. Use the client’s existing HTTP MCP support; do not install packages. If Streamable HTTP is unsupported, report that explicitly; do not switch to stdio. Do not launch subprocesses or a new game, and do not play automatically. After connecting, wait for explicit user instructions. Read only the visible board. Control requires renewed user authorization and the corresponding switches in the main process. click_cell accepts a clicks array (up to 128 clicks) and also single row/col/button arguments. Confirm batch results in order and stop at the first failure; check completed/results/stopped_index first. A timed-out action has an unknown result and must not be retried automatically.</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="126" />
            <source>服务已运行；更换端口前请先停止</source>
            <translation>Service is running; stop it before changing ports</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="164" />
            <source>启动失败；请检查端口、SDK 连接及配置，不会自动重试</source>
            <translation>Start failed; check the port, SDK connection and configuration. No automatic retry.</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="183" />
            <source>私有通信线程尚未退出，禁止重启</source>
            <translation>Private communication thread has not exited; restart is blocked</translation>
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
            <translation>Configuration prompt</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="122" />
            <source>复制配置提示词</source>
            <translation>Copy configuration prompt</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="165" />
            <source>停止MCP</source>
            <translation>Stop MCP</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="166" />
            <source>启动MCP</source>
            <translation>Start MCP</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="175" />
            <source>已停止</source>
            <translation>Stopped</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="176" />
            <source>正在启动</source>
            <translation>Starting</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="177" />
            <source>运行中</source>
            <translation>Running</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="178" />
            <source>正在停止</source>
            <translation>Stopping</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="179" />
            <source>启动失败</source>
            <translation>Failed to start</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="182" />
            <source>运行中：{endpoint}</source>
            <translation>Running: {endpoint}</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="186" />
            <source>错误：{reason}</source>
            <translation>Error: {reason}</translation>
        </message>
    </context>
</TS>
