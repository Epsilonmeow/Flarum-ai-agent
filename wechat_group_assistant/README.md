# 学院微信群个人助手：本地自动化探测原型

这个目录是一个**独立原型**，用于验证当前电脑是否适合做“本地微信端自动采集 + AI 分类日报/周报”的个人版工具。

当前版本重点不是直接做完整产品，而是先安全确认：

1. 是否能检测到电脑端微信窗口。
2. 是否能识别目标微信群名称。
3. 是否能读取微信窗口中可见文本控件。
4. 是否能定位微信文件下载目录。
5. 在用户明确允许时，是否能复制当前可见聊天文本用于解析测试。

## 安全边界

本探测脚本默认是**只读模式**：

- 不发送消息。
- 不自动回复。
- 不自动提交小程序表单。
- 不删除聊天记录。
- 不修改微信设置。
- 不主动点击未知按钮。

只有在你显式使用 `--copy-visible` 参数，并且配置文件里开启 `allow_copy_probe: true` 时，脚本才会尝试对当前微信窗口发送 `Ctrl+A` / `Ctrl+C` 来复制当前可见内容。这个动作仍然不会发送任何消息。

## 文件说明

```text
wechat_group_assistant/
  README.md                    使用说明
  config.example.json           配置模板
  requirements-wechat.txt       探测脚本可选依赖
  run_probe.bat                 Windows 一键探测脚本
  probe_wechat.py               微信能力探测脚本
  data/                         探测输出目录，首次运行后生成
```

## 首次使用步骤

### 1. 安装依赖

在当前目录 `components` 下执行：

```bat
pip install -r wechat_group_assistant\requirements-wechat.txt
```

### 2. 复制配置文件

```bat
copy wechat_group_assistant\config.example.json wechat_group_assistant\config.local.json
```

然后编辑 `wechat_group_assistant\config.local.json`：

```json
{
  "target_group_name": "这里改成你的微信群名"
}
```

### 3. 打开电脑微信

请手动完成：

1. 登录电脑端微信。
2. 打开目标学院群。
3. 保持微信窗口不要最小化。

### 4. 运行只读探测

```bat
python wechat_group_assistant\probe_wechat.py --config wechat_group_assistant\config.local.json
```

或者双击：

```text
wechat_group_assistant\run_probe.bat
```

### 5. 如需测试复制当前可见聊天文本

确认微信当前打开的是目标群后，再运行：

```bat
python wechat_group_assistant\probe_wechat.py --config wechat_group_assistant\config.local.json --copy-visible
```

并且需要在配置中设置：

```json
"allow_copy_probe": true
```

## 输出结果

探测结果会写入：

```text
wechat_group_assistant/data/probe_result_时间戳.json
wechat_group_assistant/data/probe_visible_text_时间戳.txt
wechat_group_assistant/data/probe_clipboard_时间戳.txt
```

这些文件用于判断后续是否可以进入完整开发：

- 自动文字采集
- 自动日志去重
- PDF/docx/xlsx 附件归档和解析
- 图片点开 OCR
- 日报/周报生成

## 后续开发建议

如果探测结果显示能稳定识别目标群和可见文本，下一步可以开发：

1. `collector`：低频采集群文字消息，去重写入 JSONL。
2. `attachment_watcher`：监听微信文件目录，归档 PDF/docx/xlsx。
3. `document_parser`：解析附件正文。
4. `summarizer`：结合用户画像调用 LLM 分类、打标签、生成报告。
5. `safe_ocr`：安全模式下点开图片、截图、本地 OCR。

小程序内容建议先只记录卡片标题和提醒，等基础功能稳定后再做滚动截图 OCR。
