<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US" sourcelanguage="zh_CN">
    <context>
        <name>ClipboardReplay</name>
        <message>
            <location filename="../config.py" line="20" />
            <source>监听剪贴板（总开关）</source>
            <translation>Monitor clipboard (master switch)</translation>
        </message>
        <message>
            <location filename="../config.py" line="21" />
            <source>关闭时停用所有处理器，但保留各处理器的开关设置。</source>
            <translation>Disable all handlers while retaining their individual settings.</translation>
        </message>
        <message>
            <location filename="../config.py" line="39" />
            <source>是否启用此处理器；仅在总开关打开时生效。</source>
            <translation>Enable this handler; requires the master switch.</translation>
        </message>
        <message>
            <location filename="../handlers/base.py" line="84" />
            <source>已启用</source>
            <translation>Enabled</translation>
        </message>
        <message>
            <location filename="../handlers/base.py" line="84" />
            <source>已停用</source>
            <translation>Disabled</translation>
        </message>
        <message>
            <location filename="../handlers/classic95/handler.py" line="28" />
            <source>95经典扫雷小程序</source>
            <translation>95 Classic Minesweeper mini app</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="43" />
            <source>识别到录像 {id}</source>
            <translation>Detected replay {id}</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="46" />
            <source>录像 {id} 已加入等待，保留最新请求</source>
            <translation>Replay {id} queued; keeping the latest request</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="70" />
            <source>正在下载录像 {id}</source>
            <translation>Downloading replay {id}</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="76" />
            <location filename="../handlers/download.py" line="85" />
            <source>录像超过 32 MiB 的下载限制</source>
            <translation>Replay exceeds the 32 MiB download limit</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="92" />
            <source>录像下载超时</source>
            <translation>Replay download timed out</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="110" />
            <source>已跳过旧录像，准备处理最新请求</source>
            <translation>Skipped the previous replay; processing the latest request</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="119" />
            <source>Unexpected HTTP status: {status}</source>
            <translation>Unexpected HTTP status: {status}</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="127" />
            <source>下载的录像为空</source>
            <translation>Downloaded replay is empty</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="135" />
            <source>录像下载完成，使用系统临时文件</source>
            <translation>Replay downloaded to a system temporary file</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="145" />
            <source>已提交录像播放，临时文件将在 10 秒后清理</source>
            <translation>Replay playback requested; temporary file will be removed in 10 seconds</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="151" />
            <source>录像处理失败：{error}</source>
            <translation>Replay processing failed: {error}</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="162" />
            <source>录像处理已取消</source>
            <translation>Replay handling cancelled</translation>
        </message>
        <message>
            <location filename="../handlers/download.py" line="164" />
            <source>已取消下载</source>
            <translation>Download cancelled</translation>
        </message>
        <message>
            <location filename="../handlers/openms/handler.py" line="29" />
            <source>开源扫雷网录像</source>
            <translation>OpenMS replays</translation>
        </message>
        <message>
            <location filename="../handlers/saolei/handler.py" line="28" />
            <source>扫雷网录像</source>
            <translation>Saolei.wang replays</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="22" />
            <source>剪贴板监听已启动</source>
            <translation>Clipboard monitoring started</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="23" />
            <source>剪贴板监听已暂停</source>
            <translation>Clipboard monitoring paused</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="68" />
            <source>剪贴板助手</source>
            <translation>Clipboard assistant</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="70" />
            <source>监听剪贴板内容，识别后交给对应处理器执行</source>
            <translation>Monitor the clipboard and dispatch recognized content to its handler</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="114" />
            <source>无法初始化 {handler}：{error}</source>
            <translation>Cannot initialize {handler}: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="161" />
            <source>处理失败：{error}</source>
            <translation>Processing failed: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="181" />
            <source>无法更新 {handler}：{error}</source>
            <translation>Cannot update {handler}: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="188" />
            <source>插件已停止</source>
            <translation>Plugin stopped</translation>
        </message>
        <message>
            <location filename="../replay.py" line="20" />
            <source>服务器返回的是网页或 API 错误，而不是录像</source>
            <translation>Server returned a page or API error instead of a replay</translation>
        </message>
        <message>
            <location filename="../replay.py" line="26" />
            <source>缺少录像文件名或格式不支持</source>
            <translation>Missing or unsupported replay filename</translation>
        </message>
        <message>
            <location filename="../replay.py" line="39" />
            <source>未找到 src/main.py、metasweeper.exe 或 metaminsweeper.exe</source>
            <translation>Cannot find src/main.py, metasweeper.exe or metaminsweeper.exe</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="28" />
            <location filename="../widgets.py" line="48" />
            <location filename="../widgets.py" line="56" />
            <location filename="../widgets.py" line="63" />
            <source>运行日志</source>
            <translation>Activity log</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="30" />
            <location filename="../widgets.py" line="59" />
            <location filename="../widgets.py" line="81" />
            <source>已暂停</source>
            <translation>Paused</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="38" />
            <location filename="../widgets.py" line="39" />
            <location filename="../widgets.py" line="60" />
            <location filename="../widgets.py" line="61" />
            <source>清空日志</source>
            <translation>Clear log</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="47" />
            <location filename="../widgets.py" line="62" />
            <source>暂无日志</source>
            <translation>No log entries</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="58" />
            <location filename="../widgets.py" line="80" />
            <source>监听中</source>
            <translation>Listening</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="83" />
            <source>系统</source>
            <translation>System</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="92" />
            <source>错误</source>
            <translation>Error</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="93" />
            <source>信息</source>
            <translation>Info</translation>
        </message>
    </context>
</TS>
