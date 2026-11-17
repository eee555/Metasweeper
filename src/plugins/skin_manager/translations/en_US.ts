<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US" sourcelanguage="zh_CN">
    <context>
        <name>SkinManagerPlugin</name>
        <message>
            <location filename="../config.py" line="32" />
            <location filename="../plugin.py" line="126" />
            <source>默认皮肤</source>
            <translation>Default skin</translation>
        </message>
        <message>
            <location filename="../config.py" line="76" />
            <location filename="../config.py" line="97" />
            <source>当前皮肤</source>
            <translation>Current skin&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="77" />
            <location filename="../config.py" line="134" />
            <source>当前音效包</source>
            <translation>Current sound pack&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="78" />
            <location filename="../config.py" line="99" />
            <source>选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原</source>
            <translation>Applies immediately (in-memory, no restart); choose default to restore&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="80" />
            <location filename="../config.py" line="136" />
            <source>选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原</source>
            <translation>Applies immediately (in-memory, no restart); choose default to restore&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="89" />
            <source>启动时自动应用</source>
            <translation>Auto-apply on startup&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="90" />
            <source>插件启动并连接主进程后，自动应用上次选择的皮肤与音效设置</source>
            <translation>Reapply the last skin and sound settings after the plugin connects&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="106" />
            <source>导入皮肤包</source>
            <translation>Import skin pack&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="108" />
            <source>导入皮肤 zip</source>
            <translation>Import skin zip&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="109" />
            <source>选择 zip 自动解压到本插件数据目录 skins/，随后即可在下拉框选择</source>
            <translation>Extract the zip into skins/; the pack then appears in the dropdown&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="117" />
            <source>启用游戏音效</source>
            <translation>Enable game sounds&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="118" />
            <source>通过 SetSoundCommand 独立控制；不影响主程序设置页里的开关</source>
            <translation>Controlled independently via SetSoundCommand; separate from game settings&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="125" />
            <source>音效音量</source>
            <translation>Sound volume&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="129" />
            <source>0~100，选择后立即生效</source>
            <translation>0–100, applies immediately&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="135" />
            <location filename="../sound.py" line="81" />
            <source>默认音效</source>
            <translation>Default sounds</translation>
        </message>
        <message>
            <location filename="../config.py" line="143" />
            <source>导入音效包</source>
            <translation>Import sound pack&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="145" />
            <source>导入音效 zip</source>
            <translation>Import sound zip&gt;</translation>
        </message>
        <message>
            <location filename="../config.py" line="146" />
            <source>选择 zip 自动解压到本插件数据目录 sounds/，随后即可在下拉框选择</source>
            <translation>Extract the zip into sounds/; the pack then appears in the dropdown&gt;</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="67" />
            <source>皮肤与音效</source>
            <translation>Skins and sounds</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="69" />
            <source>设置页分别选择皮肤与音效包，运行时热替换（纯内存、不重启）；两者为相互独立的功能与授权</source>
            <translation>Select skins and sound packs separately in settings; apply in memory without restarting, with independent features and permissions</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="131" />
            <source>皮肤目录不存在：{name}</source>
            <translation>Skin directory does not exist: {name}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="133" />
            <source>{name}（格子 {cells}、LED {leds}、笑脸 {faces}）</source>
            <translation>{name} (cells {cells}, LEDs {leds}, faces {faces})</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="138" />
            <source>主进程未响应（可能尚未连接或未授权）</source>
            <translation>Main process did not respond (possibly disconnected or unauthorized)</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="142" />
            <source>应用失败：{error}</source>
            <translation>Failed to apply: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="148" />
            <location filename="../plugin.py" line="211" />
            <source>已应用：{detail}</source>
            <translation>Applied: {detail}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="193" />
            <source>音效参数无效：{error}</source>
            <translation>Invalid sound parameters: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="198" />
            <source>主进程未响应（可能尚未连接或未授权 SetSoundCommand）</source>
            <translation>Main process did not respond (possibly disconnected or SetSoundCommand not authorized)</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="202" />
            <source>音效应用失败：{error}</source>
            <translation>Failed to apply sounds: {error}</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="207" />
            <source>音效（{state}，音量 {volume}，包 {pack}）</source>
            <translation>Sounds ({state}, volume {volume}, pack {pack})</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="208" />
            <source>开</source>
            <translation>On</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="208" />
            <source>关</source>
            <translation>Off</translation>
        </message>
        <message>
            <location filename="../plugin.py" line="209" />
            <source>默认</source>
            <translation>Default</translation>
        </message>
        <message>
            <location filename="../sound.py" line="96" />
            <source>未知音效事件: {event}</source>
            <translation>Unknown sound event: {event}</translation>
        </message>
        <message>
            <location filename="../sound.py" line="98" />
            <source>音量超出范围: {volume}</source>
            <translation>Volume out of range: {volume}</translation>
        </message>
        <message>
            <location filename="../sound.py" line="100" />
            <source>非法音效包名: {pack}</source>
            <translation>Invalid sound pack name: {pack}</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="30" />
            <source>就绪</source>
            <translation>Ready&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="31" />
            <source>开局</source>
            <translation>Start&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="32" />
            <source>开格</source>
            <translation>Open&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="33" />
            <source>双击</source>
            <translation>Chord&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="34" />
            <source>插旗</source>
            <translation>Flag on&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="35" />
            <source>拔旗</source>
            <translation>Flag off&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="36" />
            <source>胜利</source>
            <translation>Win&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="37" />
            <source>失败</source>
            <translation>Lose&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="53" />
            <source>皮肤管理</source>
            <translation>Skin manager&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="57" />
            <source>在插件列表里右键本插件 →「设置...」，从「当前皮肤」下拉框选择，选择后立即生效，无需重启。
选「默认皮肤」即可还原。</source>
            <translation>Right-click this plugin → Settings, choose a skin. Applies immediately, no restart.
Choose the default to restore.&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="65" />
            <source>尚未应用皮肤</source>
            <translation>No skin applied yet&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="68" />
            <source>重新应用</source>
            <translation>Reapply&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="69" />
            <source>强制把当前选中的皮肤重新发送到主进程</source>
            <translation>Force-resend the selected skin to the game process&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="75" />
            <source>在插件「设置...」里用「导入皮肤包」按钮安装 zip，或把资源放到插件目录 skins/&lt;名称&gt;/ 下，导入后即自动出现在下拉框里。</source>
            <translation>Use the Import skin pack button in Settings, or put resources under skins/&lt;name&gt;/. Imported packs appear in the dropdown.&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="85" />
            <source>音效</source>
            <translation>Sounds&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="88" />
            <source>在插件「设置...」里分别设置「启用游戏音效」「音效音量」「当前音效包」，与皮肤设置相互独立，互不影响。授权也是独立的 SetSoundCommand。</source>
            <translation>Configure sound enable, volume and pack independently in Settings. Authorization uses a separate SetSoundCommand.&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="96" />
            <source>试听：</source>
            <translation>Preview:&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="105" />
            <source>播放</source>
            <translation>Play&gt;</translation>
        </message>
        <message>
            <location filename="../widgets.py" line="106" />
            <source>按当前音效设置发送试听请求（需已授权 SetSoundCommand）</source>
            <translation>Send a preview request with current settings (requires SetSoundCommand authorization)&gt;</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="91" />
            <source>压缩包为空</source>
            <translation>Archive is empty</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="93" />
            <source>文件数超过上限 {limit}</source>
            <translation>File count exceeds the limit of {limit}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="106" />
            <source>压缩包包含不安全的路径或符号链接</source>
            <translation>Archive contains unsafe paths or symbolic links</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="110" />
            <source>不允许的文件类型: {path}</source>
            <translation>Disallowed file type: {path}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="113" />
            <source>单文件过大（上限 {limit} KB）: {path}</source>
            <translation>File too large (limit {limit} KB): {path}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="117" />
            <source>解压后总大小超过上限 {limit} MB</source>
            <translation>Uncompressed size exceeds the limit of {limit} MB</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="158" />
            <source>找不到文件: {path}</source>
            <translation>File not found: {path}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="173" />
            <source>包名无效（不能为空、下划线开头或保留设备名）</source>
            <translation>Invalid pack name (empty, starts with an underscore, or a reserved device name)</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="211" />
            <source>压缩包内没有找到任何皮肤/音效资源（可能需要检查目录结构）</source>
            <translation>No skin or sound resources found in the archive; check its directory structure</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="235" />
            <source>写入资源包失败: {error}</source>
            <translation>Failed to write resource pack: {error}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="262" />
            <source>导入 zip 包</source>
            <translation>Import ZIP pack</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="281" />
            <location filename="../zip_import.py" line="340" />
            <source>尚未导入</source>
            <translation>Not imported</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="297" />
            <source>选择 zip 包</source>
            <translation>Select ZIP pack</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="297" />
            <source>Zip 文件 (*.zip);;所有文件 (*)</source>
            <translation>ZIP files (*.zip);;All files (*)</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="304" />
            <location filename="../zip_import.py" line="308" />
            <source>导入失败：{error}</source>
            <translation>Import failed: {error}</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="314" />
            <location filename="../zip_import.py" line="336" />
            <source>已导入「{name}」({count} 个文件)</source>
            <translation>Imported “{name}” ({count} files)</translation>
        </message>
        <message>
            <location filename="../zip_import.py" line="329" />
            <location filename="../zip_import.py" line="338" />
            <source>已导入</source>
            <translation>Imported</translation>
        </message>
    </context>
</TS>
