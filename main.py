"""astrbot_plugin_t2i_markdown_renderer - 独立 Markdown T2I 渲染插件

独立调用 AstrBot 配置中的 t2i 服务 API，不受全局 t2i 开关影响。
检测 LLM 输出中的 Markdown 表格、加粗等内容，自动渲染为图片。
"""
import base64
import json
import os
import re
import uuid
from pathlib import Path
from typing import Optional

import requests

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.api.message_components import Plain, Image


# ---------------------------------------------------------------------------
# HTML 模板：简洁现代风格，深色主题，marked.js CDN 渲染 markdown
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.8;
      color: #e0e0e0;
      background: #1a1a2e;
      min-height: 100vh;
      padding: 32px 0;
    }
    .wrapper {
      max-width: 780px;
      margin: 0 auto;
      padding: 28px 36px;
      background: #16213e;
      border-radius: 12px;
      box-shadow: 0 4px 32px rgba(0, 0, 0, 0.45);
    }
    /* marked.js 渲染后使用 #content 包裹 */
    #content h1, #content h2, #content h3, #content h4, #content h5, #content h6 {
      color: #7ec8e3;
      margin-top: 1.2em;
      margin-bottom: 0.5em;
      font-weight: 600;
      line-height: 1.4;
    }
    #content h1 { font-size: 1.75em; border-bottom: 2px solid #3a506b; padding-bottom: 6px; }
    #content h2 { font-size: 1.45em; border-bottom: 1px solid #3a506b; padding-bottom: 4px; }
    #content h3 { font-size: 1.2em; }
    #content p { margin: 0.7em 0; }
    #content strong { color: #f0c27b; font-weight: 700; }
    #content em { color: #c3aed6; }
    #content code {
      font-family: "Fira Code", "Cascadia Code", Consolas, monospace;
      font-size: 0.85em;
      background: #0f3460;
      color: #e94560;
      padding: 2px 6px;
      border-radius: 4px;
    }
    #content pre {
      background: #0f3460;
      border: 1px solid #3a506b;
      border-radius: 8px;
      padding: 14px 16px;
      overflow-x: auto;
      margin: 0.8em 0;
    }
    #content pre code {
      background: transparent;
      color: #c3d4e6;
      padding: 0;
      font-size: 0.82em;
    }
    #content blockquote {
      border-left: 4px solid #7ec8e3;
      padding: 6px 16px;
      margin: 0.8em 0;
      background: rgba(126, 200, 227, 0.08);
      color: #b0c4de;
      border-radius: 0 6px 6px 0;
    }
    #content table {
      width: 100%;
      border-collapse: collapse;
      margin: 0.8em 0;
      font-size: 0.9em;
      border-radius: 8px;
      overflow: hidden;
    }
    #content thead {
      background: linear-gradient(135deg, #0f3460, #1a1a40);
      color: #7ec8e3;
    }
    #content th, #content td {
      padding: 10px 14px;
      text-align: left;
      border: 1px solid #3a506b;
    }
    #content tbody tr:nth-child(odd) { background: rgba(15, 52, 96, 0.3); }
    #content tbody tr:nth-child(even) { background: rgba(22, 33, 62, 0.5); }
    #content tbody tr:hover { background: rgba(126, 200, 227, 0.12); }
    #content a { color: #7ec8e3; text-decoration: none; border-bottom: 1px dotted #7ec8e3; }
    #content a:hover { color: #f0c27b; border-color: #f0c27b; }
    #content ul, #content ol { padding-left: 1.5em; margin: 0.6em 0; }
    #content li { margin: 0.25em 0; }
    #content hr {
      border: none;
      border-top: 1px solid #3a506b;
      margin: 1.2em 0;
    }
    #content img { max-width: 100%; border-radius: 8px; margin: 0.5em 0; }
    .footer {
      margin-top: 24px;
      padding-top: 12px;
      border-top: 1px solid #3a506b;
      text-align: center;
      font-size: 0.75em;
      color: #5a6d8a;
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div id="content"></div>
    <div class="footer">AstrBot · Markdown Renderer</div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    (function () {
      var contentEl = document.getElementById("content");
      var source = decodeBase64Utf8("{{ text_base64 }}");
      contentEl.innerHTML = marked.parse(source || "");

      function decodeBase64Utf8(base64Text) {
        var binary = window.atob(base64Text || "");
        var bytes = new Uint8Array(binary.length);
        for (var i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        if (window.TextDecoder) {
          return new TextDecoder("utf-8").decode(bytes);
        }
        var fallback = "";
        bytes.forEach(function (byte) { fallback += String.fromCharCode(byte); });
        return decodeURIComponent(escape(fallback));
      }
    })();
  </script>
</body>
</html>"""


@register(
    "astrbot_plugin_t2i_markdown_renderer",
    "Logan",
    "独立调用 t2i 服务将 Markdown 表格/加粗渲染为图片",
    "1.0",
)
class T2IMarkdownRenderer(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()

        # --- 缓存目录 ---
        self.cache_dir = Path(StarTools.get_data_dir()) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # --- t2i endpoint：优先从 cmd_config 的 t2i_endpoint 读取 ---
        self.t2i_endpoint = self._load_t2i_endpoint()

        # --- 配置快照 ---
        self.render_tables: bool = self.config.get("render_tables", True)
        self.render_bold: bool = self.config.get("render_bold", True)
        self.send_original_text: bool = self.config.get("send_original_text", False)
        self.render_builtin_commands: bool = self.config.get("render_builtin_commands", False)
        self.render_provider_command: bool = self.config.get("render_provider_command", False)
        self.min_table_rows: int = self.config.get("min_table_rows", 2)
        self.min_bold_count: int = self.config.get("min_bold_count", 3)

        # --- 正则 ---
        # 表格：匹配至少含有 |---| 分隔行的 GFM 表格
        # 行格式：| col1 | col2 | ... |
        self._table_row_re = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
        # 加粗：**text**
        self._bold_re = re.compile(r"\*\*(.+?)\*\*")

        logger.info(
            f"[T2IMD] 插件已加载 | endpoint={self.t2i_endpoint} | "
            f"tables={self.render_tables}(≥{self.min_table_rows}行) | "
            f"bold={self.render_bold}(≥{self.min_bold_count}块) | "
            f"builtin={self.render_builtin_commands} | "
            f"provider={self.render_provider_command} | "
            f"send_original={self.send_original_text}"
        )

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _load_t2i_endpoint(self) -> str:
        """从 AstrBot 全局配置读取 t2i_endpoint，失败时回退默认值。"""
        try:
            cmd_config_path = Path(__file__).resolve().parent.parent.parent / "cmd_config.json"
            if cmd_config_path.exists():
                with open(cmd_config_path, "r", encoding="utf-8-sig") as f:
                    raw = json.load(f)
                ep = raw.get("t2i_endpoint", "").strip()
                if ep:
                    return ep
        except Exception as e:
            logger.warning(f"[T2IMD] 读取 cmd_config.json 失败: {e}")
        return "http://192.168.1.103:8999"

    def _count_table_rows(self, text: str) -> int:
        """统计以 |...| 开头的行数，且至少包含一个 |---| 分隔行才认为是表格。"""
        lines = [l for l in text.splitlines() if self._table_row_re.match(l)]
        if len(lines) < 2:
            return 0
        # 检查是否存在分隔行：| --- | --- | 之类
        has_sep = any(re.match(r"^\s*\|[\s\-:]+\|", l) for l in lines)
        return len(lines) if has_sep else 0

    def _count_bold_blocks(self, text: str) -> int:
        return len(self._bold_re.findall(text))

    def _should_render(self, text: str, is_llm: bool) -> bool:
        """判断是否应触发 T2I 渲染。"""
        if not text.strip():
            return False

        if is_llm:
            # LLM 输出：检查表格 / 加粗
            if self.render_tables and self._count_table_rows(text) >= self.min_table_rows:
                return True
            if self.render_bold and self._count_bold_blocks(text) >= self.min_bold_count:
                return True
        else:
            # 内置指令输出
            if self.render_builtin_commands:
                return True
            # /provider 指令单独控制
            if self.render_provider_command and self._is_provider_output(text):
                return True

        return False

    def _is_provider_output(self, text: str) -> bool:
        """检测文本是否为 /provider 指令的输出。"""
        # provider 输出特征：包含提供商ID和模型名配对列表
        indicators = [
            "提供商", "provider", "模型列表",  # 中文特征
            "当前会话",
        ]
        score = sum(1 for kw in indicators if kw.lower() in text.lower())
        # 同时检测是否有多行短文本（模型列表特征）
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        list_like = len(lines) >= 3 and all(len(l) < 80 for l in lines)
        return (score >= 1 and list_like) or (score >= 3)

    def _build_html(self, text: str) -> str:
        """将 markdown 文本嵌入 HTML 模板。"""
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return HTML_TEMPLATE.replace("{{ text_base64 }}", text_b64)

    def _call_t2i(self, html: str) -> Optional[Path]:
        """调用 t2i 服务，返回保存的图片路径，失败返回 None。"""
        url = f"{self.t2i_endpoint.rstrip('/')}/text2img/generate"
        try:
            resp = requests.post(
                url,
                json={"html": html, "full_page": True, "type": "png"},
                timeout=60,
            )
            if resp.status_code == 200:
                filename = f"t2imd_{uuid.uuid4().hex[:10]}.png"
                filepath = self.cache_dir / filename
                filepath.write_bytes(resp.content)
                logger.info(f"[T2IMD] 图片已生成: {filepath}")
                return filepath
            else:
                logger.error(f"[T2IMD] t2i 返回非 200: {resp.status_code} | {resp.text[:300]}")
        except requests.exceptions.Timeout:
            logger.error("[T2IMD] t2i 请求超时")
        except requests.exceptions.ConnectionError:
            logger.error(f"[T2IMD] 无法连接 t2i 服务: {url}")
        except Exception as e:
            logger.error(f"[T2IMD] t2i 调用异常: {e}")
        return None

    # ------------------------------------------------------------------
    # 钩子：拦截所有输出结果
    # ------------------------------------------------------------------
    @filter.on_decorating_result(priority=-500)
    async def on_decorating_result(self, event: AstrMessageEvent):
        """拦截 LLM / 插件指令输出，检测 Markdown 并触发 T2I 渲染。"""
        result = event.get_result()
        if not result or not result.chain:
            return

        # 判断是否为 LLM 结果
        is_llm = getattr(result, "is_llm_result", None)
        if callable(is_llm):
            try:
                is_llm = bool(is_llm())
            except Exception:
                is_llm = True  # 保守：当作 LLM 结果
        else:
            is_llm = True  # 默认

        # 收集纯文本
        plain_texts: list[str] = []
        for comp in result.chain:
            if isinstance(comp, Plain) and comp.text:
                plain_texts.append(comp.text)

        full_text = "\n".join(plain_texts)

        if not self._should_render(full_text, is_llm):
            return

        logger.info(
            f"[T2IMD] 触发渲染 | is_llm={is_llm} | "
            f"tables={self._count_table_rows(full_text)}r | "
            f"bold={self._count_bold_blocks(full_text)} | "
            f"len={len(full_text)}"
        )

        # 构建 HTML 并调 t2i
        html = self._build_html(full_text)
        img_path = self._call_t2i(html)

        if img_path is None:
            logger.warning("[T2IMD] t2i 失败，保留原始文本输出")
            return

        # 构建新的 chain：图片在前
        img_url = f"file:////{str(img_path)}"
        new_chain = [Image(file=str(img_path), url=img_url)]

        if self.send_original_text:
            # 图片后保留原文
            new_chain.extend(result.chain)

        result.chain = new_chain

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def initialize(self):
        logger.info("[T2IMD] 初始化完成")

    async def terminate(self):
        logger.info("[T2IMD] 插件已停止")
