<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP" sourcelanguage="zh_CN">
    <context>
        <name>MinesweeperMcp</name>
        <message>
            <location filename="../config.py" line="22" />
            <source>MCP 端口</source>
            <translation>MCPポート</translation>
        </message>
        <message>
            <location filename="../config.py" line="23" />
            <source>端口必须为 1024..65535 的整数</source>
            <translation>ポートは1024〜65535の整数で指定してください</translation>
        </message>
        <message>
            <location filename="../config.py" line="55" />
            <location filename="../plugin.py" line="90" />
            <source>旧配置清理失败，MCP 服务保持停止</source>
            <translation>旧設定のクリーンアップに失敗したため、MCPは停止したままです</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="54" />
            <source>元扫雷 MCP 服务</source>
            <translation>元マインスイーパーMCPサービス</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="56" />
            <source>通过本机 MCP 服务提供可见棋盘和经授权的辅助操作</source>
            <translation>ローカルMCPサービスで可視盤面と許可済みの補助操作を提供します</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="103" />
            <source>请在现有 agent 的 MCP 配置中添加一个 Streamable HTTP 服务，保留其他配置。
endpoint: {endpoint}
协议版本：2025-11-25。使用客户端已有的 HTTP MCP 支持，不安装任何包，若客户端不支持 Streamable HTTP，明确报告不支持，不能改用 stdio。不启动子进程或新游戏，不自动玩游戏。连接后等待用户明确指令。只读取可见棋盘，控制需用户重新授权并开启主进程相应开关。click_cell 支持 clicks 数组批量点击（最多128项），也兼容 row/col/button 单点。批量按顺序逐项确认，首个失败即停止；先检查 completed/results/stopped_index。动作超时意味着结果未知，不得自动重试。</source>
            <translation>既存のagentのMCP設定にStreamable HTTPサービスを追加し、他の設定は保持してください。
endpoint: {endpoint}
プロトコルバージョン: 2025-11-25。クライアントに備わるHTTP MCP機能を使用し、パッケージはインストールしないでください。Streamable HTTP非対応の場合は明示的に報告し、stdioへ変更しないでください。サブプロセスや新しいゲームを起動せず、自動プレイもしないでください。接続後はユーザーの明示的な指示を待ってください。可視盤面のみを読み取ってください。操作にはユーザーによる再許可とメインプロセスの対応する設定が必要です。click_cellはclicks配列（最大128項目）と単一のrow/col/buttonに対応します。バッチの結果を順番に確認し、最初の失敗で停止してください。まずcompleted/results/stopped_indexを確認してください。操作がタイムアウトした場合は結果不明なので、自動的に再試行しないでください。</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="126" />
            <source>服务已运行；更换端口前请先停止</source>
            <translation>サービスは実行中です。ポート変更前に停止してください</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="164" />
            <source>启动失败；请检查端口、SDK 连接及配置，不会自动重试</source>
            <translation>起動に失敗しました。ポート、SDK接続、設定を確認してください。自動再試行は行いません</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="183" />
            <source>私有通信线程尚未退出，禁止重启</source>
            <translation>専用通信スレッドが終了していないため、再起動できません</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="118" />
            <location filename="../widgets.py" line="119" />
            <source>监听端口</source>
            <translation>待受ポート</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="120" />
            <location filename="../widgets.py" line="121" />
            <source>配置提示词</source>
            <translation>設定用プロンプト</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="122" />
            <source>复制配置提示词</source>
            <translation>設定用プロンプトをコピー</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="165" />
            <source>停止MCP</source>
            <translation>MCPを停止</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="166" />
            <source>启动MCP</source>
            <translation>MCPを開始</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="175" />
            <source>已停止</source>
            <translation>停止済み</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="176" />
            <source>正在启动</source>
            <translation>起動中</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="177" />
            <source>运行中</source>
            <translation>実行中</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="178" />
            <source>正在停止</source>
            <translation>停止中</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="179" />
            <source>启动失败</source>
            <translation>起動に失敗</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="182" />
            <source>运行中：{endpoint}</source>
            <translation>実行中: {endpoint}</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="186" />
            <source>错误：{reason}</source>
            <translation>エラー: {reason}</translation>
        </message>
    </context>
</TS>
