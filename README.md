# astrbot_plugin_t2i_markdown_renderer

> 独立调用 t2i 服务将 Markdown 表格 / 加粗等渲染为图片，不受 AstrBot 全局 t2i 开关影响

AstrBot 插件，用于自动检测 LLM 输出中的 Markdown 表格、加粗语句、内置命令输出等内容，调用 AstrBot 配置的 t2i（text-to-image）服务渲染为图片并发送。

## ✨ 特性

- 🚀 **独立调用** — 直接使用 AstrBot 配置的 t2i API，**不受** AstrBot 全局 t2i 开关影响
- 📊 **智能检测** — 自动识别 Markdown 表格、`**加粗**` 语句、可选识别内置命令输出
- 🎨 **深色主题** — 内置现代化深色样式（marked.js + 自定义 CSS）
- ⚙️ **可配置** — WebUI 面板可调整触发阈值、开关各类渲染
- 🪶 **零依赖** — 不需要额外下载字体或模板，HTML 模板内嵌在插件内

## 📦 安装

### 方式一：从 AstrBot 插件市场安装

待发布到 AstrBot 官方插件市场后，可直接在 AstrBot WebUI 的「插件市场」搜索安装。

### 方式二：手动安装

```bash
cd /path/to/astrbot/data/plugins
git clone https://github.com/<your-name>/astrbot_plugin_t2i_markdown_renderer.git
```

然后在 AstrBot WebUI「插件管理」中点击「重载」即可。

## ⚙️ 配置

在 AstrBot WebUI → 插件管理 → Markdown T2I 渲染 中可调整以下配置项：

| 配置项 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `render_tables` | bool | `true` | 检测到 Markdown 表格时是否渲染为图片 |
| `render_bold` | bool | `true` | 检测到加粗语句 (`**text**`) 时是否渲染为图片 |
| `send_original_text` | bool | `false` | 发送图片后是否同时发送原文 |
| `render_builtin_commands` | bool | `false` | 是否将 `/help` 等内置指令输出渲染为图片 |
| `min_table_rows` | int | `2` | 触发表格渲染的最小行数（含表头） |
| `min_bold_count` | int | `3` | 触发加粗渲染的最小加粗块数 |
| `render_provider_command` | bool | `false` | 是否将 `/provider` 指令输出渲染为图片 |

## 🔧 前置要求

1. **AstrBot ≥ 4.22.x**（使用了新版插件 API）
2. **已配置 t2i Provider**（在 AstrBot 的 Provider 配置中添加任意 t2i 服务）
3. 可选：内网可访问的 t2i API 端点（HTTP）

> 插件不直接管理 t2i Provider 配置，复用 AstrBot 全局 Provider 即可。

## 📝 使用示例

假设 Bot 回复如下 Markdown 内容：

```markdown
以下是今天的学习计划：

| 时间 | 任务 | 优先级 |
|------|------|--------|
| 09:00 | 晨会 | 高 |
| 14:00 | 代码审查 | 中 |
| 16:00 | 文档整理 | 低 |

**注意**：请按优先级顺序处理。
```

当 LLM 输出包含上述内容时，插件会自动：

1. 检测到 Markdown 表格（行数 ≥ 2）
2. 调用 t2i API 渲染为深色主题图片
3. 替换原文本消息，发送图片

## 🛠️ 实现原理

```
LLM 输出
  ↓
正则匹配 Markdown 表格 / 加粗
  ↓
构建 HTML 字符串（marked.js CDN 渲染）
  ↓
调用 AstrBot t2i Provider API
  ↓
将返回的图片数据构造为 Image 消息组件
  ↓
替换原 Plain 文本，发送
```

## 🐛 故障排除

- **图片没渲染**：检查 AstrBot Provider 配置中是否正确启用了 t2i 服务
- **报 502 错误**：t2i 服务不可用，确认 API 端点可达
- **表格不触发**：调整 `min_table_rows` 阈值
- **加粗不触发**：调整 `min_bold_count` 阈值

## 📄 许可证

MIT License

## 👤 作者

Logan
