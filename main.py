#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek 语音助手 —— Kivy 安卓版完整功能实现
深色科技风 / 冷色调 / 蓝紫渐变强调
功能：真实 DeepSeek 流式对话(Function Calling)、安卓原生 TTS 朗读、
联网搜索(博查 API + Bing 爬取兜底)、人设切换与编辑、立绘拖拽缩放、
设置页(DeepSeek Key / 搜索 Key / 音色 / 朗读开关 / 联网搜索开关)。
Windows 上本地预览与截图验证；安卓上自动启用原生 TTS。
"""

import json
import os
import re
import sys
import threading
import time
import platform
import urllib.request
import urllib.parse
import html as _html
import base64
import urllib.error

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle)
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

try:
    from plyer import filechooser
    _HAS_PLYER = True
except Exception:
    _HAS_PLYER = False

# ==================== 路径 ====================
# BASE_DIR：只读资源目录（随 APK 打包，如 personas.json、头像图片）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 【关键修复】DATA_DIR：可写目录。
# 安卓上 __file__ 所在目录（APK 内部）是只读的，往里面写 config.json /
# sessions.json / 日志会抛 PermissionError，导致一点图标就闪退。
# 桌面 / Windows 上仍沿用原目录，保持行为不变。
def _resolve_data_dir():
    # 1) 安卓（python-for-android 注入的环境变量，优先使用）
    for _env in ("ANDROID_PRIVATE", "ANDROID_APP_PATH", "ANDROID_ARGUMENT"):
        _p = os.environ.get(_env)
        if _p:
            try:
                if os.path.isdir(_p):
                    return _p
            except Exception:
                pass
    # 2) Kivy 的可写数据目录（安卓为 /data/data/<包名>/files）
    try:
        from kivy.utils import platform as _kpy_platform
        if _kpy_platform == "android":
            from kivy.app import App as _KApp
            _d = _KApp().user_data_dir  # 延迟取，失败则走兜底
            if _d:
                return _d
    except Exception:
        pass
    # 3) 桌面 / Windows：沿用脚本所在目录
    return BASE_DIR


DATA_DIR = _resolve_data_dir()
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = BASE_DIR

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
PERSONA_FILE = os.path.join(DATA_DIR, "personas.json")
SESSION_FILE = os.path.join(DATA_DIR, "sessions.json")

# 只读资源目录下的人设文件（随 APK 打包）
PERSONA_SRC = os.path.join(BASE_DIR, "personas.json")
# 首次运行：把打包内的只读 personas.json 复制到可写目录，
# 否则安卓上读不到默认人设、且后续保存人设会失败。
if DATA_DIR != BASE_DIR and not os.path.isfile(PERSONA_FILE):
    try:
        import shutil as _shutil
        if os.path.isfile(PERSONA_SRC):
            _shutil.copyfile(PERSONA_SRC, PERSONA_FILE)
    except Exception:
        try:
            if os.path.isfile(PERSONA_SRC):
                with open(PERSONA_SRC, "r", encoding="utf-8") as _f:
                    _t = _f.read()
                with open(PERSONA_FILE, "w", encoding="utf-8") as _f:
                    _f.write(_t)
        except Exception:
            pass

# 头像等只读资源仍从打包目录读
AVATAR_DIR = os.path.join(BASE_DIR, "assets", "avatars")
if not os.path.isdir(AVATAR_DIR):
    try:
        os.makedirs(AVATAR_DIR, exist_ok=True)
    except Exception:
        pass

# ==================== 平台判断 ====================
IS_ANDROID = False
try:
    import android  # noqa: F401  (python-for-android 内置模块)
    IS_ANDROID = True
except Exception:
    pass
if platform.system() == "Linux" and not IS_ANDROID:
    IS_ANDROID = False

# ==================== 安卓原生 TTS（jnius） ====================
try:
    from jnius import autoclass
    _HAS_JNIUS = True
except Exception:
    _HAS_JNIUS = False


class AndroidTTS:
    """安卓原生 TextToSpeech 封装；Windows 上为演示占位。
    语音包名: config.json voice 字段（如 "晓晓（女·温柔）" 为演示名），
    安卓上实际保存 Locale/Voice 名称。"""

    def __init__(self, app):
        self.app = app
        self._tts = None
        self._ok = False
        if IS_ANDROID and _HAS_JNIUS:
            try:
                TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                ctx = PythonActivity.mActivity
                self._tts = TextToSpeech(ctx, None)
                self._ok = True
            except Exception as e:
                print("TTS_INIT_ERR", repr(e))

    @property
    def available(self):
        return self._ok

    def speak(self, text):
        if not text or not self._ok:
            return False
        try:
            self._tts.stop()
            self._tts.speak(text, self._tts.QUEUE_FLUSH, None, "deepseek-tts")
            return True
        except Exception as e:
            print("TTS_SPEAK_ERR", repr(e))
            return False

    def stop(self):
        if self._ok:
            try:
                self._tts.stop()
            except Exception:
                pass

    def shutdown(self):
        if self._ok:
            try:
                self._tts.shutdown()
            except Exception:
                pass

    def system_voices(self):
        """读取系统中文 TTS 语音包名称列表；失败回退默认演示列表。"""
        voices = []
        if self._ok:
            try:
                vs = self._tts.getVoices()
                if vs is not None:
                    for v in vs:
                        try:
                            loc = v.getLocale()
                            lang = str(loc.getLanguage()) if loc else ""
                            name = str(v.getName())
                            if not name:
                                continue
                            if lang.lower() in ("zh", "cmn") or "chinese" in name.lower():
                                voices.append(name)
                        except Exception:
                            continue
            except Exception as e:
                print("TTS_VOICES_ERR", repr(e))
        if not voices:
            voices = list(VOICES) if "VOICES" in globals() else ["默认中文语音"]
        return voices


# ==================== 字体 ====================
FONT_CN = "MicrosoftYaHei"
FONT_SYMBOL = r"C:\Windows\Fonts\seguisym.ttf"
FONT_EMOJI = r"C:\Windows\Fonts\seguiemj.ttf"
for _name, _path in ((FONT_CN, r"C:\Windows\Fonts\msyh.ttc"),
                     ("SegoeSym", FONT_SYMBOL),
                     ("SegoeEmoji", FONT_EMOJI)):
    try:
        if os.path.isfile(_path):
            LabelBase.register(name=_name, fn_regular=_path)
    except Exception:
        pass

# Android 无 Windows 字体：探测系统自带中文字体兜底，避免中文变方块
if platform.system() != "Windows":
    for _p in ("/system/fonts/NotoSansCJK-Regular.ttc",
               "/system/fonts/DroidSansFallback.ttf",
               "/system/fonts/NotoSansSC-Regular.otf"):
        try:
            if os.path.isfile(_p):
                LabelBase.register(name=FONT_CN, fn_regular=_p)
                break
        except Exception:
            pass

# 【关键修复】SegoeSym / SegoeEmoji 是 Windows 专属字体，安卓上不存在。
# 若未注册，代码中大量 font_name="SegoeSym"/"SegoeEmoji" 的 Label 会在
# 构建界面的瞬间抛 OSError: File 'SegoeSym.ttf' not found → 启动闪退。
# 这里在非 Windows 环境下，把这几个名字统一指向一个确实存在的字体
# （优先中文字体兜底文件，其次 Kivy 自带字体），保证标签能正常创建。
_FALLBACK_FONT = None
if platform.system() != "Windows":
    for _p in ("/system/fonts/NotoSansCJK-Regular.ttc",
               "/system/fonts/DroidSansFallback.ttf",
               "/system/fonts/NotoSansSC-Regular.otf",
               "/system/fonts/Roboto-Regular.ttf"):
        try:
            if os.path.isfile(_p):
                _FALLBACK_FONT = _p
                break
        except Exception:
            pass
    if _FALLBACK_FONT:
        for _name in ("MicrosoftYaHei", "SegoeSym", "SegoeEmoji"):
            try:
                LabelBase.register(name=_name, fn_regular=_FALLBACK_FONT)
            except Exception:
                pass
    else:
        # 最后的兜底：用 Kivy 内置 Roboto，至少不让字体缺失导致崩溃
        try:
            from kivy.core.text import LabelBase as _LB2
            _LB2.register(name="SegoeSym", fn_regular="Roboto")
            _LB2.register(name="SegoeEmoji", fn_regular="Roboto")
        except Exception:
            pass

# ==================== 配色（写死） ====================
BG_1 = (0.059, 0.078, 0.125, 1)     # #0f1420
BG_2 = (0.047, 0.063, 0.102, 1)     # #0c101a
TOP_1 = (0.082, 0.114, 0.188, 1)    # #151d30
TOP_2 = (0.102, 0.137, 0.220, 1)    # #1a2338
AI_BUB_1 = (0.165, 0.247, 0.388, 1)  # #2a3f63
AI_BUB_2 = (0.118, 0.176, 0.286, 1)  # #1e2d49
AI_BORDER = (0.227, 0.318, 0.471, 1)  # #3a5178
AI_TEXT = (0.859, 0.902, 0.984, 1)    # #dbe6fb
USER_BUB_1 = (0.118, 0.533, 0.898, 1)  # #1e88e5
USER_BUB_2 = (0.082, 0.396, 0.753, 1)  # #1565c0
USER_TEXT = (1, 1, 1, 1)
ACCENT_1 = (0.302, 0.671, 0.969, 1)   # #4dabf7
ACCENT_2 = (0.486, 0.361, 1.0, 1)     # #7c5cff
INPUT_BG = (0.102, 0.137, 0.220, 1)   # #1a2338
INPUT_BORDER = (0.196, 0.251, 0.420, 1)  # #32406b
PLACEHOLDER = (0.361, 0.427, 0.561, 1)  # #5c6d8f
MUTED = (0.624, 0.706, 0.831, 1)      # #9fb3d9
DIVIDER = (0.149, 0.192, 0.290, 1)    # #26314a
NOTICE_RED = (1.0, 0.42, 0.42, 1)     # #ff6b6b
NOTICE_BG = (0.45, 0.10, 0.10, 0.55)  # 深红半透明背景条
CLOSE_ICON = (0.624, 0.706, 0.831, 1) # #9fb3d9
STOP_BG = (0.55, 0.18, 0.26, 1)       # 打断按钮底色（暗红）
DISABLED_BG = (0.086, 0.110, 0.176, 1)  # 锁定态按钮底色
DISABLED_FG = (0.36, 0.42, 0.54, 1)     # 锁定态图标/文字颜色

R10 = [(10, 10), (10, 10), (10, 10), (10, 10)]
R12 = [(12, 12), (12, 12), (12, 12), (12, 12)]
R14 = [(14, 14), (14, 14), (14, 14), (14, 14)]
R18 = [(18, 18), (18, 18), (18, 18), (18, 18)]


def _hex(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1)


def make_linear_texture(c1, c2, steps=256):
    """水平渐变纹理 c1 -> c2"""
    data = bytearray()
    for i in range(steps):
        t = i / (steps - 1)
        r = int((c1[0] + (c2[0] - c1[0]) * t) * 255)
        g = int((c1[1] + (c2[1] - c1[1]) * t) * 255)
        b = int((c1[2] + (c2[2] - c1[2]) * t) * 255)
        data.extend((r, g, b, 255))
    tex = Texture.create(size=(steps, 1))
    tex.blit_buffer(bytes(data), colorfmt="rgba", bufferfmt="ubyte")
    return tex


def make_diag_texture(c1, c2, size=256):
    """左上 -> 右下 对角渐变纹理"""
    data = bytearray()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            r = int((c1[0] + (c2[0] - c1[0]) * t) * 255)
            g = int((c1[1] + (c2[1] - c1[1]) * t) * 255)
            b = int((c1[2] + (c2[2] - c1[2]) * t) * 255)
            data.extend((r, g, b, 255))
    tex = Texture.create(size=(size, size))
    tex.blit_buffer(bytes(data), colorfmt="rgba", bufferfmt="ubyte")
    return tex


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = dict(default)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(default)


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ==================== 默认配置 / 人设 ====================
DEFAULT_CONFIG = {
    "api_key": "",
    "search_api_key": "",
    "vision_api_key": "",
    "image_api_key": "",
    "voice": "晓晓（女·温柔）",
    "persona": "龙族三人格",
    "speak_on_reply": True,
    "search_enabled": True,
    "show_avatar": True,
    "avatar_x": None,
    "avatar_y": None,
    "avatar_scale": 1.0,
}

VOICES = ["晓晓（女·温柔）", "晓伊（女·活泼）", "晓涵（女·沉稳）",
          "晓梦（女·自然）", "云希（男·自然）", "云扬（男·稳重）", "云健（男·阳光）"]

DEFAULT_PERSONAS = {
    "龙族三人格": "先结论后理由，三句话内说完。不用敬语、感叹号与 emoji。不知道就说不知道，不许编。",
    "DeepSeek 鲸鱼娘": "蓝色渐变长发、鲸鱼头鳍的傲娇天然呆娘。口语化、简短、偶尔撒娇。被叫胖要立刻反驳。",
    "简洁助手": "直接回答不寒暄，先结论后理由，默认三句话内说完，不用 emoji。",
    "自定义": "在这里写你自己的人设。",
}

FAKE_REPLIES = {
    "龙族三人格": "结论：可以。理由：Kivy 界面已在本地跑起来了，UI 元素全部真实渲染。",
    "DeepSeek 鲸鱼娘": "用户酱～界面做好啦！这个深蓝渐变是不是很酷？奖励我白米饭吧～",
    "简洁助手": "界面已完成，当前为演示模式，接入真实 API 后即可正常对话。",
    "自定义": "（这里会根据你的人设内容生成回复）",
}

# ==================== DeepSeek API / 联网搜索 ====================
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
SEARCH_TIMEOUT = 10  # 搜索超时秒数（后台线程，不阻塞 UI）

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取实时信息、最新数据、新闻、天气、政策等时效性内容。"
                       "当用户问题需要模型知识范围之外的实时信息时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或问题，尽量精简"}
            },
            "required": ["query"],
        },
    },
}

SEARCH_PROMPT_SUFFIX = (
    "遇到需要实时信息、最新数据、新闻、天气等问题时，主动调用搜索工具，"
    "不要凭空编造时效性信息。"
)


class WebSearch:
    """联网搜索接口层：博查 API（open.bochaai.com）优先，Bing 爬取兜底。
    可替换接口层：如需换搜索源，只需替换 _bocha_search 实现。"""

    def __init__(self, api_key=""):
        self.api_key = (api_key or "").strip()

    def search(self, query):
        """返回前 5 条 [{title, snippet, url}]；失败返回空列表。"""
        results = []
        if self.api_key:
            try:
                results = self._bocha_search(query)
            except Exception as e:
                print("BOCHA_ERR", repr(e))
        if not results:
            try:
                results = self._bing_fallback(query)
            except Exception as e:
                print("BING_ERR", repr(e))
        return results[:5]

    # ---------- 博查 API ----------
    def _bocha_search(self, query):
        url = "https://open.bochaai.com/v1/chat/search"
        body = {"query": query, "summary": True, "count": 5, "freshness": "noLimit"}
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        out = []
        pages = (((data.get("data") or {}).get("webPages") or {}).get("value")) or []
        for p in pages:
            out.append({
                "title": p.get("name") or "",
                "snippet": p.get("snippet") or p.get("summary") or "",
                "url": p.get("url") or "",
            })
        return out

    # ---------- Bing 爬取兜底 ----------
    def _bing_fallback(self, query):
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as r:
            content = r.read().decode("utf-8", "ignore")
        out = []
        for m in re.finditer(r'<li class="b_algo".*?</li>', content, re.S):
            item = m.group(0)
            tm = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                           item, re.S)
            if not tm:
                continue
            url = _html.unescape(tm.group(1))
            title = _html.unescape(re.sub(r"<[^>]+>", "", tm.group(2))).strip()
            pm = re.search(r"<p[^>]*>(.*?)</p>", item, re.S)
            snippet = ""
            if pm:
                snippet = _html.unescape(
                    re.sub(r"<[^>]+>", "", pm.group(1))).strip()
            out.append({"title": title, "snippet": snippet, "url": url})
            if len(out) >= 5:
                break
        return out


class DeepSeekClient:
    """DeepSeek API 客户端：流式输出 + Function Calling（web_search）。
    应在后台线程调用 chat()，回调会从该线程触发，调用方负责线程安全调度。"""

    def __init__(self, api_key):
        self.api_key = (api_key or "").strip()

    def _request_once(self, messages, on_delta, cancel_event=None):
        """发起一次流式请求。返回 (text, tool_parts, finish_reason)。
        tool_parts: {index: {"name":..., "args":...}}
        cancel_event: threading.Event，被 set 时提前中断读取（实时打断）。"""
        body = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "stream": True,
            "tools": [WEB_SEARCH_TOOL],
            "tool_choice": "auto",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }
        req = urllib.request.Request(
            DEEPSEEK_URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        text_parts = []
        tool_parts = {}
        finish = ""
        with urllib.request.urlopen(req, timeout=45) as resp:
            for raw in resp:
                if cancel_event is not None and cancel_event.is_set():
                    break
                line = raw.decode("utf-8", "ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except Exception:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                ch = choices[0]
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    text_parts.append(delta["content"])
                    on_delta(delta["content"])
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            tool_parts.setdefault(idx, {"name": fn["name"], "args": ""})
                        if fn.get("arguments"):
                            tool_parts.setdefault(idx, {"name": "", "args": ""})
                            tool_parts[idx]["args"] += fn["arguments"]
                finish = ch.get("finish_reason") or ""
        return "".join(text_parts), tool_parts, finish

    def chat(self, messages, on_delta, on_status, on_done, on_error,
             web_search=None, search_enabled=True, cancel_event=None):
        """完整对话流程（最多 2 轮：初始请求 -> 搜索 -> 补充回答）。
        on_status: ("searching"|"searched") 通知 UI 更新气泡状态行。
        cancel_event: threading.Event，被 set 时提前中断（实时打断）。"""
        for _round in range(2):
            if cancel_event is not None and cancel_event.is_set():
                on_done("")
                return
            try:
                text, tools, finish = self._request_once(messages, on_delta,
                                                         cancel_event)
            except Exception as e:
                on_error(str(e))
                return
            if tools and search_enabled and web_search is not None:
                tool = list(tools.values())[0] if tools else None
                if tool and tool.get("name") == "web_search":
                    try:
                        args = json.loads(tool.get("args") or "{}")
                    except Exception:
                        args = {}
                    query = str(args.get("query") or "").strip()
                    if query:
                        on_status("searching")
                        try:
                            results = web_search.search(query) or []
                        except Exception as e:
                            print("SEARCH_ERR", repr(e))
                            results = []
                        on_status("searched")
                        summary = json.dumps(results, ensure_ascii=False) \
                            if results else "[]"
                        messages.append({
                            "role": "assistant", "content": None,
                            "tool_calls": [{
                                "id": "call_web_search", "type": "function",
                                "function": {"name": "web_search",
                                             "arguments": tool.get("args") or "{}"},
                            }],
                        })
                        messages.append({
                            "role": "tool", "tool_call_id": "call_web_search",
                            "content": summary,
                        })
                        continue  # 带上搜索结果再请求一轮
            if text:
                on_delta("".join(text))
            on_done(text)
            return
        on_done("")


# ---------- 图片工具：编码 / 分类错误 / 视觉与生图客户端 ----------

def friendly_error(e):
    """把异常分类成简短中文提示；分类失败回退原错误码。"""
    try:
        msg = str(e)
        code = ""
        if hasattr(e, "status_code") and e.status_code is not None:
            code = str(e.status_code)
        else:
            m = re.search(r"(?:status|code)[^\d]{0,6}(\d{3})", msg, re.I)
            if m:
                code = m.group(1)
        if code == "401" or code == "403":
            return "API Key 无效"
        if code == "402":
            return "账户余额不足"
        if code == "429":
            return "请求过于频繁，请稍后再试"
        if "timeout" in msg.lower() or "timed out" in msg.lower() or "timedout" in msg.lower():
            return "网络连接超时，请稍后重试"
        if "connection" in msg.lower() or "network" in msg.lower() or "resolve" in msg.lower() or "ssl" in msg.lower():
            return "网络连接失败，请检查网络"
        if "401" in msg or "403" in msg:
            return "API Key 无效"
        if "402" in msg:
            return "账户余额不足"
        if "429" in msg:
            return "请求过于频繁，请稍后再试"
        if code:
            return "错误码 " + code
        if not msg:
            return "未知错误"
        return msg[:40]
    except Exception:
        return "未知错误"


def encode_image(path):
    """把图片文件读成 base64 字符串（失败返回空串）。"""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""


class VisionClient:
    """图像识别链路：聊天发图 → 视觉模型（如智谱 GLM-4V）。"""

    ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self, api_key):
        self.api_key = api_key or ""

    def ask(self, text, img_path, on_delta, on_done):
        def _run():
            if not self.api_key.strip():
                on_done("")
                return
            payload = {
                "model": "glm-4v",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text or "请描述这张图片的内容"},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encode_image(img_path)}},
                    ],
                }],
                "stream": False,
            }
            try:
                data = self._post(payload)
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if content:
                    on_delta(content)
                on_done(content)
            except Exception as e:
                on_done("")
                raise

        threading.Thread(target=_run, daemon=True).start()

    def _post(self, payload):
        req = urllib.request.Request(self.ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + self.api_key.strip())
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))


class ImageGenClient:
    """图片生成链路：AI 按钮 → 生图弹窗 → CogView。"""

    ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/images/generations"

    def __init__(self, api_key):
        self.api_key = api_key or ""

    def generate(self, prompt, on_ok, refs=None):
        def _run():
            if not self.api_key.strip():
                on_ok({"error": "未填写图片生成 API Key，请先到设置页填入"})
                return
            payload = {"model": "cogview-3-flash", "prompt": prompt}
            refs_local = refs or []
            if refs_local:
                urls = []
                for r in refs_local[:5]:
                    try:
                        with open(r, "rb") as f:
                            b = base64.b64encode(f.read()).decode("ascii")
                        ext = os.path.splitext(r)[1].lower().lstrip(".")
                        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                                "webp": "webp", "bmp": "bmp", "gif": "gif"}.get(ext, "png")
                        urls.append("data:image/%s;base64,%s" % (mime, b))
                    except Exception:
                        continue
                if len(urls) == 1:
                    payload["ref_image_url"] = urls[0]
                elif len(urls) > 1:
                    payload["ref_image_url_list"] = urls
            try:
                req = urllib.request.Request(self.ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", "Bearer " + self.api_key.strip())
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                url = ((data.get("data") or [{}])[0] or {}).get("url", "")
                if not url:
                    on_ok({"error": "生成失败：返回内容解析失败"})
                    return
                out = os.path.join(BASE_DIR, "last_gen.png")
                ok = False
                try:
                    with urllib.request.urlopen(urllib.request.Request(url), timeout=90) as img:
                        with open(out, "wb") as f:
                            f.write(img.read())
                    if os.path.getsize(out) > 1000:
                        ok = True
                except Exception:
                    pass
                if not ok:
                    try:
                        if os.path.exists(out):
                            os.remove(out)
                    except Exception:
                        pass
                    on_ok({"error": "生成失败：图片下载失败"})
                    return
                on_ok({"path": out})
            except Exception as e:
                on_ok({"error": "生成失败：" + friendly_error(e)})

        threading.Thread(target=_run, daemon=True).start()


try:
    from jnius import autoclass
    _activity = autoclass("org.kivy.android.PythonActivity").mActivity
except Exception:
    _activity = None


class Background(FloatLayout):
    """全局背景：左上到右下斜向渐变（FloatLayout 保证子控件正常布局）"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._tex = make_diag_texture(BG_1, BG_2)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._tex)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


class GlowDot(Widget):
    """顶栏左侧强调色发光小圆点"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint = (None, None)
        self.size = (dp(26), dp(26))
        with self.canvas:
            Color(*ACCENT_1, a=0.22)
            Ellipse(pos=(dp(0), dp(0)), size=(dp(26), dp(26)))
            Color(*ACCENT_1, a=0.45)
            Ellipse(pos=(dp(3), dp(3)), size=(dp(20), dp(20)))
            Color(*ACCENT_2)
            Ellipse(pos=(dp(8), dp(8)), size=(dp(10), dp(10)))


class TopBar(BoxLayout):
    """顶部栏：发光圆点 + 标题 | 人设下拉 + 设置"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.size_hint_y = None
        self.height = dp(58)
        self.padding = [dp(16), dp(10), dp(16), dp(10)]
        self.spacing = dp(12)
        self._tex = make_linear_texture(TOP_1, TOP_2)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._tex)
        self.bind(pos=self._update, size=self._update)

        left = BoxLayout(size_hint=(None, None), size=(dp(320), dp(36)),
                         spacing=dp(10))
        left.add_widget(GlowDot())
        title = Label(text="DeepSeek 语音助手", font_name=FONT_CN,
                      font_size=dp(16), bold=True, color=AI_TEXT,
                      halign="left", valign="middle", size_hint_x=None,
                      width=dp(280))
        left.add_widget(title)
        self.add_widget(left)

        right = BoxLayout(size_hint=(None, None), size=(dp(560), dp(36)),
                          spacing=dp(8), pos_hint={"right": 1})
        self.persona_spinner = Spinner(
            text=app.current_persona, values=list(app.personas.keys()),
            size_hint=(None, None), size=(dp(160), dp(36)),
            font_name=FONT_CN, font_size=dp(13), color=AI_TEXT,
            background_normal="", background_color=(0, 0, 0, 0))
        with self.persona_spinner.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.persona_spinner.pos,
                             size=self.persona_spinner.size, radius=R18)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.persona_spinner.x,
                                    self.persona_spinner.y,
                                    self.persona_spinner.width,
                                    self.persona_spinner.height,
                                    18, 18, 18, 18), width=dp(1))
        self.persona_spinner.bind(pos=self._repaint_spinner,
                                  size=self._repaint_spinner)
        self.persona_spinner.bind(text=app.on_persona_selected)
        right.add_widget(self.persona_spinner)

        ai_btn = Button(text="AI", size_hint=(None, None),
                        size=(dp(44), dp(36)), font_name=FONT_CN,
                        font_size=dp(13), bold=True, color=AI_TEXT,
                        background_normal="", background_color=(0, 0, 0, 0),
                        on_release=lambda b: app.open_image_gen())
        with ai_btn.canvas.before:
            Color(*ACCENT_1)
            RoundedRectangle(pos=ai_btn.pos, size=ai_btn.size, radius=R12)
        ai_btn.bind(pos=self._repaint_ai, size=self._repaint_ai)
        self._ai_ref = ai_btn
        right.add_widget(ai_btn)

        plus_btn = Button(text="＋", size_hint=(None, None),
                          size=(dp(36), dp(36)), font_name=FONT_CN,
                          font_size=dp(17), color=AI_TEXT,
                          background_normal="", background_color=(0, 0, 0, 0),
                          on_release=lambda b: app.create_conversation())
        with plus_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=plus_btn.pos, size=plus_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(plus_btn.x, plus_btn.y,
                                    plus_btn.width, plus_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        plus_btn.bind(pos=self._repaint_plus, size=self._repaint_plus)
        self._plus_ref = plus_btn
        right.add_widget(plus_btn)

        hist_btn = Button(text="≡", size_hint=(None, None),
                          size=(dp(36), dp(36)), font_name="SegoeSym",
                          font_size=dp(22), color=AI_TEXT,
                          background_normal="", background_color=(0, 0, 0, 0),
                          on_release=lambda b: app.open_conversation_list())
        with hist_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=hist_btn.pos, size=hist_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(hist_btn.x, hist_btn.y,
                                    hist_btn.width, hist_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        hist_btn.bind(pos=self._repaint_hist, size=self._repaint_hist)
        self._hist_ref = hist_btn
        right.add_widget(hist_btn)

        gear = Button(text="\u2699", size_hint=(None, None),
                      size=(dp(36), dp(36)), font_name="SegoeSym",
                      font_size=dp(20), color=AI_TEXT,
                      background_normal="", background_color=(0, 0, 0, 0),
                      on_release=lambda b: app.open_settings())
        with gear.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=gear.pos, size=gear.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(gear.x, gear.y, gear.width, gear.height,
                                    12, 12, 12, 12), width=dp(1))
        gear.bind(pos=self._repaint_gear, size=self._repaint_gear)
        self._gear_ref = gear
        right.add_widget(gear)

        self.add_widget(right)

    def _update(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _repaint_spinner(self, *a):
        self.persona_spinner.canvas.before.clear()
        with self.persona_spinner.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.persona_spinner.pos,
                             size=self.persona_spinner.size, radius=R18)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.persona_spinner.x,
                                    self.persona_spinner.y,
                                    self.persona_spinner.width,
                                    self.persona_spinner.height,
                                    18, 18, 18, 18), width=dp(1))

    def _repaint_gear(self, *a):
        g = self._gear_ref
        if g is None:
            return
        g.canvas.before.clear()
        with g.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=g.pos, size=g.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(g.x, g.y, g.width, g.height,
                                    12, 12, 12, 12), width=dp(1))

    def _repaint_ai(self, *a):
        b = self._ai_ref
        if b is None:
            return
        b.canvas.before.clear()
        with b.canvas.before:
            Color(*ACCENT_1)
            RoundedRectangle(pos=b.pos, size=b.size, radius=R12)
            Color(*ACCENT_2, a=0.35)
            Line(rounded_rectangle=(b.x, b.y, b.width, b.height,
                                    12, 12, 12, 12), width=dp(1))

    def _repaint_plus(self, *a):
        b = self._plus_ref
        if b is None:
            return
        b.canvas.before.clear()
        with b.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=b.pos, size=b.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(b.x, b.y, b.width, b.height,
                                    12, 12, 12, 12), width=dp(1))

    def _repaint_hist(self, *a):
        b = self._hist_ref
        if b is None:
            return
        b.canvas.before.clear()
        with b.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=b.pos, size=b.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(b.x, b.y, b.width, b.height,
                                    12, 12, 12, 12), width=dp(1))


class AvatarCard(BoxLayout):
    """左侧立绘卡片：圆角 14px、深色渐变底、透明 PNG 立绘"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.size_hint = (None, 1)
        self.width = dp(250)
        self.padding = [dp(12), dp(12), dp(12), dp(10)]
        self.spacing = dp(8)
        self._speaking = False
        self._anchor_y = 0.0
        self._dragged = False
        self._scale = 1.0
        self._base_size = (0, 0)
        self._active_touch = None
        self._pinch_dist = 0.0
        self._drag_off = (0, 0)
        self._tex = make_diag_texture(TOP_1, BG_2)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size,
                                        radius=R14, texture=self._tex)
            Color(*DIVIDER)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height,
                                    14, 14, 14, 14), width=dp(1))
        self.bind(pos=self._update, size=self._update)

        self.img = Image(size_hint=(None, None))
        self.img.bind(on_touch_down=self._on_img_down,
                      on_touch_move=self._on_img_move,
                      on_touch_up=self._on_img_up)

        self.name_lbl = Label(text=app.current_persona, font_name=FONT_CN,
                              font_size=dp(14), color=MUTED,
                              halign="center", valign="middle",
                              size_hint_y=None, height=dp(28))
        self.add_widget(self.name_lbl)

        with self.canvas.after:
            Color(*DIVIDER, a=0.6)
            self._line = Rectangle(size=(dp(1), dp(1)))
        self.bind(pos=self._update_line, size=self._update_line)
        self.bind(pos=self._sync_img_geom, size=self._sync_img_geom)

        # 拖拽高亮边框（挂 root 顶层，跟随立绘）
        self._hl = Widget(size_hint=(None, None))
        with self._hl.canvas:
            Color(*ACCENT_2, a=0.9)
            self._hl_line = Line(rounded_rectangle=(0, 0, 0, 0, 8, 8, 8, 8),
                                 width=dp(2))
        self._hl.opacity = 0

        Clock.schedule_once(self._attach_img, 0)
        self.refresh()

    # ---------- 立绘挂载与几何 ----------
    def _attach_img(self, *a):
        """把立绘挂到全局 FloatLayout（root）顶层，便于自由拖拽与缩放"""
        root = getattr(self.app, "root", None)
        if root is None:
            Clock.schedule_once(self._attach_img, 0)
            return
        if self.img.parent is not None:
            return
        root.add_widget(self.img)
        root.add_widget(self._hl)
        self._sync_img_geom()
        self.restore_geom()

    def _sync_img_geom(self, *a):
        if self._dragged:
            return
        w = self.width - dp(24)
        h = self.height - dp(84)
        self.img.size = (w, h)
        self.img.pos = (self.x + dp(12), self.y + dp(10))
        self._base_size = (w, h)
        self._anchor_y = self.img.y

    # ---------- 拖拽 / 双指缩放 ----------
    def _on_img_down(self, img, touch):
        if not img.collide_point(*touch.pos):
            return False
        touch.grab(img)
        self._stop_bounce()
        if self._active_touch is None:
            self._active_touch = touch
            self._drag_off = (touch.x - img.x, touch.y - img.y)
            self._dragged = True
            self._show_highlight(True)
        else:
            # 第二根手指：记录捏合基线距离
            t0 = self._active_touch
            dx = t0.x - touch.x
            dy = t0.y - touch.y
            self._pinch_dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
        return True

    def _on_img_move(self, img, touch):
        if touch.grab_current is not img:
            return False
        if self._pinch_dist > 0 and self._active_touch is not None \
                and touch is not self._active_touch:
            # 双指捏合缩放
            t0 = self._active_touch
            dx = t0.x - touch.x
            dy = t0.y - touch.y
            dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
            factor = dist / self._pinch_dist
            self._pinch_dist = dist
            self._apply_scale(factor)
        elif touch is self._active_touch:
            self.img.pos = (touch.x - self._drag_off[0],
                            touch.y - self._drag_off[1])
            self._clamp()
        self._anchor_y = self.img.y
        self._update_highlight()
        self._save_geom()
        return True

    def _on_img_up(self, img, touch):
        if touch.grab_current is not img:
            return False
        touch.ungrab(img)
        if touch is self._active_touch:
            self._active_touch = None
            self._pinch_dist = 0.0
        elif self._pinch_dist > 0:
            self._pinch_dist = 0.0
        if self._active_touch is None:
            self._dragged = True
            self._anchor_y = self.img.y
            self._save_geom()
            self._show_highlight(False)
            if self._speaking:
                self._start_bounce()
        return True

    def set_dragged_pos(self, x, y):
        """程序化设置立绘位置（供 --drag 截图参数使用），落点成为浮动锚点"""
        self._dragged = True
        self._stop_bounce()
        self.img.pos = (x, y)
        self._clamp()
        self._anchor_y = y

    # ---------- 缩放与边界钳制 ----------
    def _apply_scale(self, factor):
        w, h = self.img.size
        base_w, base_h = self._base_size
        if base_w <= 0:
            base_w = self.width - dp(24)
            base_h = self.height - dp(84)
        scale = (w * factor / base_w) if base_w else 1.0
        scale = max(0.5, min(2.0, scale))  # 缩放钳制 0.5x ~ 2.0x
        nw = base_w * scale
        nh = base_h * scale
        cx, cy = self.img.center_x, self.img.center_y
        self.img.size = (nw, nh)
        self.img.pos = (cx - nw / 2.0, cy - nh / 2.0)
        self._scale = scale
        self._clamp()

    def _clamp(self):
        """钳制：立绘至少保留 50% 宽高在屏幕内，绝不跑出屏幕看不见"""
        root = getattr(self.app, "root", None)
        if root is None:
            return
        w, h = self.img.size
        min_x = -w * 0.5
        max_x = root.width - w * 0.5
        min_y = -h * 0.5
        max_y = root.height - h * 0.5
        nx = max(min_x, min(self.img.x, max_x))
        ny = max(min_y, min(self.img.y, max_y))
        self.img.pos = (nx, ny)

    def _save_geom(self):
        try:
            self.app.cfg["avatar_x"] = self.img.x
            self.app.cfg["avatar_y"] = self.img.y
            self.app.cfg["avatar_scale"] = self._scale
            save_json(CONFIG_FILE, self.app.cfg)
        except Exception:
            pass

    def restore_geom(self):
        """启动时恢复上次保存的立绘位置与缩放"""
        try:
            x = self.app.cfg.get("avatar_x")
            y = self.app.cfg.get("avatar_y")
            s = float(self.app.cfg.get("avatar_scale") or 1.0)
        except Exception:
            return
        if x is None or y is None:
            return
        self._dragged = True
        self._stop_bounce()
        self.img.pos = (float(x), float(y))
        self._anchor_y = float(y)
        if s != 1.0:
            w = (self.width - dp(24)) * s
            h = (self.height - dp(84)) * s
            self.img.size = (w, h)
            self._scale = s
        self._clamp()

    def reset_position(self):
        """设置页：重置立绘位置到默认卡片位，清除保存的几何"""
        self._dragged = False
        self._scale = 1.0
        self._pinch_dist = 0.0
        self._active_touch = None
        self._stop_bounce()
        self._sync_img_geom()
        self.app.cfg["avatar_x"] = None
        self.app.cfg["avatar_y"] = None
        self.app.cfg["avatar_scale"] = 1.0
        save_json(CONFIG_FILE, self.app.cfg)
        self._show_highlight(False)

    # ---------- 拖拽高亮边框 ----------
    def _update_highlight(self):
        self._hl.pos = (self.img.x - dp(6), self.img.y - dp(6))
        self._hl.size = (self.img.width + dp(12), self.img.height + dp(12))
        self._hl_line.rounded_rectangle = (
            0, 0, self._hl.width, self._hl.height, 8, 8, 8, 8)

    def _show_highlight(self, on):
        self._update_highlight()
        self._hl.opacity = 1.0 if on else 0.0

    # ---------- 说话浮动（呼吸动画） ----------
    def set_speaking(self, on):
        if on == self._speaking:
            return
        self._speaking = bool(on)
        if on:
            self._start_bounce()
        else:
            self._stop_bounce(back=True)

    def _start_bounce(self, *a):
        if not self._speaking:
            return
        anim = Animation(y=self._anchor_y + dp(10), duration=0.125,
                         t="out_quad")
        anim.bind(on_complete=self._bounce_down)
        anim.start(self.img)

    def _bounce_down(self, *a):
        if not self._speaking:
            return
        anim = Animation(y=self._anchor_y, duration=0.125, t="in_quad")
        anim.bind(on_complete=self._start_bounce)
        anim.start(self.img)

    def _stop_bounce(self, back=False):
        Animation.cancel_all(self.img, "y")
        if back:
            anim = Animation(y=self._anchor_y, duration=0.2, t="out_quad")
            anim.start(self.img)

    def _update(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _update_line(self, *a):
        self._line.pos = (self.right + dp(6), self.y)
        self._line.size = (dp(1), self.height)

    def avatar_path(self, name):
        if not os.path.isdir(AVATAR_DIR):
            return None
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = os.path.join(AVATAR_DIR, name + ext)
            if os.path.isfile(p):
                return p
        return None

    def refresh(self, name=None):
        name = name or self.app.current_persona
        self.name_lbl.text = name
        path = self.avatar_path(name)
        if path:
            self.img.source = path
            self.img.opacity = 1
            self._placeholder = False
        else:
            self.img.source = ""
            self.img.canvas.clear()
            with self.img.canvas:
                Color(*PLACEHOLDER, a=0.85)
                Rectangle(pos=self.img.pos, size=self.img.size)
                Color(*MUTED)
                self._ph_txt = Label(text="暂无立绘\n\n把透明 PNG 图片放入\navatars 文件夹",
                                     font_name=FONT_CN, font_size=dp(13),
                                     color=MUTED, halign="center",
                                     valign="middle")
            self._placeholder = True
        self.img.canvas.ask_update()


class ChatArea(ScrollView):
    """聊天区：消息气泡列表 + 未填 Key 引导文字"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.do_scroll_x = False
        self.do_scroll_y = True
        self.bar_width = dp(6)
        self.list = BoxLayout(orientation="vertical", size_hint_y=None,
                              padding=[dp(10), dp(8), dp(10), dp(8)],
                              spacing=dp(4))
        self.list.bind(minimum_height=self.list.setter("height"))
        self.add_widget(self.list)

    def clear_messages(self):
        self.list.clear_widgets()

    def add_message(self, who, text, img_path=None):
        row = MessageRow(who=who, text=text, app=self.app, img_path=img_path)
        self.list.add_widget(row)
        Clock.schedule_once(self.scroll_to_bottom, 0.05)
        return row

    def scroll_to_bottom(self, *a):
        self.scroll_y = 0

    def show_guide(self, text="请点击右上角设置，填入你的 DeepSeek API Key"):
        self.clear_messages()
        g = Label(text=text, font_name=FONT_CN, font_size=dp(15),
                  color=MUTED, halign="center", valign="middle",
                  size_hint_y=None, height=dp(320))
        self.list.add_widget(g)
        Clock.schedule_once(self.scroll_to_bottom, 0.05)

    def has_guide(self):
        return len(self.list.children) == 1 and isinstance(self.list.children[0], Label)

    def check_guide(self):
        key = (self.app.cfg.get("api_key") or "").strip()
        if not key.startswith("sk-"):
            self.show_guide()
        elif self.has_guide():
            self.clear_messages()


class MessageRow(BoxLayout):
    """单条消息行：用户靠右、AI 靠左，可带图片缩略图"""

    def __init__(self, who, text, app, img_path=None, **kw):
        super().__init__(**kw)
        self.who = who
        self.app = app
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = [dp(8), dp(3), dp(8), dp(3)]

        self.bubble = BubbleBody(who=who, text=text, app=app,
                                 on_speak=(lambda: app.speak(text, self)) if who == "ai" else None)
        self._img = None
        if img_path and os.path.isfile(img_path):
            self._img = MessageImage(img_path)
        spacer = Widget(size_hint_x=1)
        if who == "user":
            self.add_widget(spacer)
            if self._img is not None:
                self.add_widget(self._img)
            self.add_widget(self.bubble)
        else:
            self.add_widget(self.bubble)
            if self._img is not None:
                self.add_widget(self._img)
            self.add_widget(spacer)

        self.bubble.bind(height=self._sync_height)
        self.height = self.bubble.height
        self.opacity = 0
        Animation(opacity=1, duration=0.2, t="out_quad").start(self)

    def _sync_height(self, inst, h):
        m = h
        if self._img is not None:
            m = max(m, self._img.height)
        self.height = m + dp(6)

    def update_text(self, text):
        self.bubble.update_text(text)

    def set_status_text(self, text):
        self.bubble.set_status_text(text)

    def attach_image(self, path):
        """后台生图完成后：把图片缩略图挂到这条消息上（AI 左侧）。"""
        try:
            if self._img is not None or not path or not os.path.isfile(path):
                return
            self._img = MessageImage(path)
            # AI 行：气泡在左，图片紧随其后（插到 spacer 之前）
            self.add_widget(self._img, index=len(self.children) - 1)
            self._sync_height(self.bubble, self.bubble.height)
        except Exception as e:
            print("ATTACH_IMG_ERR", repr(e))


class MessageImage(FloatLayout):
    """消息内嵌图片缩略图：圆角 12px 深色描边，固定 160x160"""

    def __init__(self, path, **kw):
        super().__init__(**kw)
        self.size_hint = (None, None)
        self.size = (dp(160), dp(160))
        self.img = Image(source=path, size_hint=(None, None),
                         size=(dp(148), dp(148)),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.add_widget(self.img)
        self._paint()
        self.bind(pos=self._paint, size=self._paint)

    def _paint(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.pos, size=self.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height,
                                    12, 12, 12, 12), width=dp(1))


class BubbleBody(BoxLayout):
    """气泡：渐变圆角 12px + 描边 + 尾巴 + 柔和投影；AI 带小喇叭"""

    def __init__(self, who, text, app, on_speak=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.who = who
        self.is_user = (who == "user")
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.padding = [dp(14), dp(9), dp(14), dp(8)]
        self.spacing = dp(2)
        self._sizing = False

        self._tex = make_linear_texture(USER_BUB_1, USER_BUB_2) if self.is_user \
            else make_linear_texture(AI_BUB_1, AI_BUB_2)

        self.lbl = Label(
            text=text, font_name=FONT_CN, font_size=dp(15),
            color=USER_TEXT if self.is_user else AI_TEXT,
            halign="left" if not self.is_user else "right",
            valign="top", size_hint=(None, None))
        self.add_widget(self.lbl)

        if on_speak is not None:
            # AI 气泡：状态行（正在朗读 / 正在联网搜索 / 已联网搜索）
            self.status_lbl = Label(text="", font_name=FONT_CN, font_size=dp(11),
                                    color=MUTED, halign="left", valign="middle",
                                    size_hint_y=None, height=0)
            self.add_widget(self.status_lbl)
            foot = BoxLayout(size_hint=(None, None), size=(dp(120), dp(22)),
                             pos_hint={"right": 1})
            spk = Button(text="\U0001F50A", size_hint=(None, None),
                         size=(dp(30), dp(20)), font_name="SegoeEmoji",
                         font_size=dp(14), color=AI_TEXT,
                         background_normal="", background_color=(0, 0, 0, 0),
                         on_release=lambda b: on_speak())
            foot.add_widget(Widget())
            foot.add_widget(spk)
            self.add_widget(foot)

        Clock.schedule_once(self._relayout, 0)
        self._paint()
        self.bind(pos=self._paint, size=self._paint)

    def _relayout(self, *a):
        """气泡尺寸由文字动态决定：
        换行宽度 = 气泡宽 - 左右内边距(24px)，高度用 texture_size 反推。
        """
        if self._sizing:
            return
        self._sizing = True
        try:
            chat = getattr(self.app, "chat", None)
            avail = (chat.width if chat else dp(820)) - dp(36)
            max_w = min(max(avail, dp(80)), dp(460))
            # 先不换行测自然宽
            self.lbl.text_size = (None, None)
            self.lbl.texture_update()
            nat_w = self.lbl.texture_size[0]
            if nat_w + dp(28) > max_w:
                w = max_w
            else:
                w = nat_w + dp(28)
            # 按换行宽 = 气泡宽 - 24px 重新排文字
            text_w = w - dp(24)
            self.lbl.text_size = (text_w, None)
            self.lbl.texture_update()
            text_h = self.lbl.texture_size[1]
            self.lbl.size = (text_w, text_h)
            # 高度 = 文字高 + 上下内边距；AI 额外留小喇叭行
            h = text_h + dp(17)
            if not self.is_user:
                h += dp(24)
                if getattr(self, "status_lbl", None) and self.status_lbl.text:
                    h += dp(18)
            self.width = max(w, dp(60))
            self.height = max(h, dp(40))
        finally:
            self._sizing = False

    def set_status_text(self, text):
        """状态行：正在朗读 / 正在联网搜索 / 已联网搜索"""
        if not hasattr(self, "status_lbl"):
            return
        self.status_lbl.text = text or ""
        self.status_lbl.height = dp(18) if text else 0
        self.status_lbl.y = self.y + dp(6)
        self._relayout()

    def update_text(self, text):
        """流式增量更新气泡文字"""
        self.lbl.text = text
        self._relayout()

    def _paint(self, *a):
        c = self.canvas.before
        c.clear()
        x, y = self.pos
        w, h = self.size
        with c:
            # 柔和投影
            Color(0, 0, 0, 0.22)
            RoundedRectangle(pos=(x + dp(2), y - dp(2)), size=(w, h), radius=R12)
            # 渐变填充
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=R12, texture=self._tex)
            # 描边
            Color(*AI_BORDER) if not self.is_user else Color(1, 1, 1, 0.15)
            Line(rounded_rectangle=(x, y, w, h, 12, 12, 12, 12), width=dp(1))
            # 尾巴
            if self.is_user:
                pts = [(x + w, y + dp(8)), (x + w + dp(9), y + dp(2)),
                       (x + w + dp(9), y + dp(16))]
            else:
                pts = [(x, y + dp(8)), (x - dp(9), y + dp(2)),
                       (x - dp(9), y + dp(16))]
            Color(*USER_BUB_2 if self.is_user else AI_BUB_2)
            Line(points=pts, width=dp(2))


def read_clipboard():
    """读取系统剪贴板。返回 (kind, text)：
    - ('text', str)：剪贴板含文本
    - ('empty', '')：剪贴板为空
    - ('not_text', '')：剪贴板有内容但不是文本（如图片）
    Android 走 pyjnius；桌面走 Kivy Clipboard。任何失败兜底为 empty，绝不抛异常。"""
    try:
        if platform.system().lower() == "android":
            from jnius import autoclass, cast
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            activity = PythonActivity.mActivity
            cm = cast("android.content.ClipboardManager",
                      activity.getSystemService(Context.CLIPBOARD_SERVICE))
            clip = cm.getPrimaryClip()
            if clip is None or clip.getItemCount() <= 0:
                return ("empty", "")
            item = clip.getItemAt(0)
            text = item.getText()
            if text is None:
                return ("not_text", "")
            return ("text", str(text))
        # 桌面端：Kivy Clipboard 读文本
        from kivy.core.clipboard import Clipboard
        data = Clipboard.paste()
        if data and str(data).strip():
            return ("text", str(data))
        # 文本为空：区分"真空"与"有内容但非文本"
        if _desktop_clipboard_not_text():
            return ("not_text", "")
        return ("empty", "")
    except Exception:
        return ("empty", "")


def _desktop_clipboard_not_text():
    """桌面端辅助：Windows 上检查系统剪贴板是否有文本格式。
    有文本格式或无内容 -> False（按空/文本处理）；有内容但无文本格式 -> True。"""
    try:
        import ctypes
        CF_TEXT = 1
        CF_UNICODETEXT = 13
        if not ctypes.windll.user32.OpenClipboard(0):
            return False
        try:
            if ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT):
                return False
            if ctypes.windll.user32.GetClipboardData(CF_TEXT):
                return False
            # 无文本格式：再查是否有其他格式（说明剪贴板有内容）
            fmt = ctypes.windll.user32.EnumClipboardFormats(0)
            return bool(fmt)
        finally:
            ctypes.windll.user32.CloseClipboard()
    except Exception:
        return False


class InputBar(BoxLayout):
    """底部输入区：图片按钮 + 圆角胶囊输入框 + 圆形发送按钮（渐变 + 外发光）
    选择图片后顶部显示附件条（缩略图 + 文件名 + 取消 ×）"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(72)
        self.padding = [dp(16), dp(9), dp(16), dp(9)]
        self.spacing = dp(6)
        self._att_path = None
        self._locked = False

        # ---------- 附件条（默认隐藏） ----------
        self.att_row = BoxLayout(size_hint_y=None, height=0,
                                 size_hint_x=1, spacing=dp(10))
        self.att_img = Image(source="", size_hint=(None, None),
                             size=(dp(52), dp(52)))
        self.att_name = Label(text="", font_name=FONT_CN, font_size=dp(13),
                              color=AI_TEXT, halign="left", valign="middle",
                              size_hint_x=1)
        self.att_del = Button(text="\u2715", size_hint=(None, None),
                              size=(dp(30), dp(30)), font_name="SegoeSym",
                              font_size=dp(16), color=CLOSE_ICON,
                              background_normal="",
                              background_color=(0, 0, 0, 0),
                              on_release=lambda b: self.clear_attachment())
        with self.att_row.canvas.before:
            Color(*NOTICE_BG)
            self._att_bg = RoundedRectangle(pos=self.att_row.pos,
                                            size=self.att_row.size,
                                            radius=R12)
        self.att_row.bind(pos=self._repaint_att, size=self._repaint_att)
        self.att_row.add_widget(self.att_img)
        self.att_row.add_widget(self.att_name)
        self.att_row.add_widget(self.att_del)
        self.add_widget(self.att_row)

        # ---------- 主输入行 ----------
        main_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))

        self.pick = Button(text="\U0001F5BC", size_hint=(None, None),
                           size=(dp(46), dp(46)), font_name="SegoeEmoji",
                           font_size=dp(22), color=AI_TEXT,
                           background_normal="",
                           background_color=(0, 0, 0, 0),
                           on_release=lambda b: app.pick_chat_image())
        with self.pick.canvas.before:
            Color(*INPUT_BG)
            self._pick_bg = RoundedRectangle(pos=self.pick.pos,
                                             size=self.pick.size, radius=R12)
            Color(*INPUT_BORDER)
            self._pick_bd = Line(rounded_rectangle=(self.pick.x, self.pick.y,
                                                    self.pick.width,
                                                    self.pick.height,
                                                    12, 12, 12, 12), width=dp(1))
        self.pick.bind(pos=self._repaint_pick, size=self._repaint_pick)
        main_row.add_widget(self.pick)

        # ---------- 语音（麦克风）按钮 ----------
        self.mic = Button(text="\U0001F3A4", size_hint=(None, None),
                          size=(dp(46), dp(46)), font_name="SegoeEmoji",
                          font_size=dp(20), color=AI_TEXT,
                          background_normal="",
                          background_color=(0, 0, 0, 0),
                          on_release=lambda b: self.toggle_mic())
        with self.mic.canvas.before:
            Color(*INPUT_BG)
            self._mic_bg = RoundedRectangle(pos=self.mic.pos,
                                            size=self.mic.size, radius=R12)
            Color(*INPUT_BORDER)
            self._mic_bd = Line(rounded_rectangle=(self.mic.x, self.mic.y,
                                                   self.mic.width,
                                                   self.mic.height,
                                                   12, 12, 12, 12), width=dp(1))
        self.mic.bind(pos=self._repaint_mic, size=self._repaint_mic)
        main_row.add_widget(self.mic)

        self.entry = TextInput(
            multiline=False, size_hint_x=1,
            font_name=FONT_CN, font_size=dp(14),
            hint_text="输入消息…",
            hint_text_color=PLACEHOLDER,
            foreground_color=AI_TEXT,
            cursor_color=ACCENT_1,
            background_normal="", background_active="",
            padding=[dp(16), dp(11)],
            on_text_validate=lambda *a: app.on_send())
        with self.entry.canvas.before:
            Color(*INPUT_BG)
            self._bg = RoundedRectangle(pos=self.entry.pos, size=self.entry.size,
                                        radius=R18)
            Color(*INPUT_BORDER)
            self._bd = Line(rounded_rectangle=(self.entry.x, self.entry.y,
                                               self.entry.width, self.entry.height,
                                               18, 18, 18, 18), width=dp(1))
        self.entry.bind(pos=self._repaint_entry, size=self._repaint_entry)
        main_row.add_widget(self.entry)

        # ---------- 粘贴按钮（输入框右侧、发送按钮旁） ----------
        self.paste = Button(text="\U0001F4CB", size_hint=(None, None),
                            size=(dp(46), dp(46)), font_name="SegoeEmoji",
                            font_size=dp(20), color=AI_TEXT,
                            background_normal="",
                            background_color=(0, 0, 0, 0),
                            on_release=lambda b: self._on_paste())
        with self.paste.canvas.before:
            Color(*INPUT_BG)
            self._paste_bg = RoundedRectangle(pos=self.paste.pos,
                                              size=self.paste.size, radius=R12)
            Color(*INPUT_BORDER)
            self._paste_bd = Line(rounded_rectangle=(self.paste.x, self.paste.y,
                                                     self.paste.width,
                                                     self.paste.height,
                                                     12, 12, 12, 12), width=dp(1))
        self.paste.bind(pos=self._repaint_paste, size=self._repaint_paste)
        main_row.add_widget(self.paste)

        # ---------- 实时打断按钮（AI 思考/回答时出现，点击立即中断） ----------
        self.stop = Button(text="\u25A0", size_hint=(None, None),
                           size=(dp(46), dp(46)), font_name="SegoeSym",
                           font_size=dp(17), color=(1, 1, 1, 1),
                           background_normal="", background_color=(0, 0, 0, 0),
                           on_release=lambda b: app.on_interrupt())
        with self.stop.canvas.before:
            Color(*STOP_BG)
            self._stop_circle = RoundedRectangle(pos=self.stop.pos,
                                                 size=self.stop.size, radius=R12)
            Color(1, 0.45, 0.45, 0.85)
            self._stop_ring = Line(rounded_rectangle=(0, 0, 0, 0, 12, 12, 12, 12),
                                   width=dp(1.2))
        self.stop.bind(pos=self._repaint_stop, size=self._repaint_stop)
        self.stop.opacity = 0
        self.stop.disabled = True
        main_row.add_widget(self.stop)

        self.send = Button(text="\u2192", size_hint=(None, None),
                           size=(dp(46), dp(46)), font_name="SegoeSym",
                           font_size=dp(24), color=(1, 1, 1, 1),
                           background_normal="", background_color=(0, 0, 0, 0),
                           on_release=lambda b: app.on_send())
        self._send_tex = make_linear_texture(ACCENT_1, ACCENT_2)
        with self.send.canvas.before:
            Color(*ACCENT_1, a=0.25)
            self._glow = Ellipse(pos=(self.send.x - dp(5), self.send.y - dp(5)),
                                 size=(self.send.width + dp(10),
                                       self.send.height + dp(10)))
            Color(1, 1, 1, 1)
            self._circle = Ellipse(pos=self.send.pos, size=self.send.size,
                                   texture=self._send_tex)
        self.send.bind(pos=self._repaint_send, size=self._repaint_send)
        main_row.add_widget(self.send)

        self.add_widget(main_row)

    # ---------- 附件 ----------
    @property
    def attachment(self):
        return self._att_path

    def set_attachment(self, path):
        if not path or not os.path.isfile(path):
            return
        self._att_path = path
        self.att_img.source = path
        self.att_name.text = os.path.basename(path)
        self.att_row.height = dp(52)
        self.height = dp(136)
        self.set_status("已选择图片，输入问题后发送即可识别")

    def clear_attachment(self, *a):
        self._att_path = None
        self.att_img.source = ""
        self.att_name.text = ""
        self.att_row.height = 0
        self.height = dp(72)

    def _on_paste(self, *a):
        """点击粘贴：读取剪贴板文本追加到输入框末尾，光标移到末尾。
        空剪贴板 / 非文本 / 读取失败均轻提示，绝不崩溃。"""
        try:
            kind, text = read_clipboard()
        except Exception:
            self.set_status("剪贴板没有内容")
            return
        if kind == "text":
            self.entry.text = (self.entry.text or "") + text
            self.entry.cursor = (len(self.entry.text), 0)
        elif kind == "not_text":
            self.set_status("剪贴板不是文字")
        else:
            self.set_status("剪贴板没有内容")

    def set_status(self, text):
        self.app.set_status(text)

    def _repaint_paste(self, *a):
        b = self.paste
        self._paste_bg.pos = b.pos
        self._paste_bg.size = b.size
        self._paste_bd.rounded_rectangle = (b.x, b.y, b.width, b.height,
                                            12, 12, 12, 12)

    def _repaint_entry(self, *a):
        e = self.entry
        self._bg.pos = e.pos
        self._bg.size = e.size
        self._bd.rounded_rectangle = (e.x, e.y, e.width, e.height, 18, 18, 18, 18)

    def _repaint_send(self, *a):
        s = self.send
        self._glow.pos = (s.x - dp(5), s.y - dp(5))
        self._glow.size = (s.width + dp(10), s.height + dp(10))
        self._circle.pos = s.pos
        self._circle.size = s.size

    def _repaint_mic(self, *a):
        m = self.mic
        self._mic_bg.pos = m.pos
        self._mic_bg.size = m.size
        self._mic_bd.rounded_rectangle = (m.x, m.y, m.width, m.height,
                                          12, 12, 12, 12)

    def _repaint_pick(self, *a):
        p = self.pick
        self._pick_bg.pos = p.pos
        self._pick_bg.size = p.size
        self._pick_bd.rounded_rectangle = (p.x, p.y, p.width, p.height,
                                           12, 12, 12, 12)

    def _repaint_att(self, *a):
        self._att_bg.pos = self.att_row.pos
        self._att_bg.size = self.att_row.size

    def _repaint_stop(self, *a):
        s = self.stop
        self._stop_circle.pos = s.pos
        self._stop_circle.size = s.size
        self._stop_ring.rounded_rectangle = (s.x, s.y, s.width, s.height,
                                             12, 12, 12, 12)

    # ---------- 思考态：锁定 / 解锁输入区（图片 / 语音 / 发送） ----------
    def set_locked(self, locked):
        """AI 思考或回答期间调用。
        locked=True：图片按钮、语音按钮、发送按钮变灰且点击无效，
                     同时显示实时打断按钮。
        locked=False：恢复可点，打断按钮淡出。"""
        self._locked = bool(locked)
        for btn in (self.pick, self.mic, self.send, self.paste):
            btn.disabled = bool(locked)
            btn.disabled_color = DISABLED_FG
            btn.color = DISABLED_FG if locked else AI_TEXT
        self._send_grad_dark(bool(locked))
        self.set_interruptible(bool(locked))

    def _send_grad_dark(self, dark):
        """发送按钮渐变圆 变暗/恢复。"""
        try:
            self._glow.a = 0.06 if dark else 0.25
            self._circle.rgba = ((0.30, 0.36, 0.48, 1) if dark
                                 else (1, 1, 1, 1))
        except Exception:
            pass

    def set_interruptible(self, on):
        """显示/隐藏实时打断按钮。"""
        self.stop.disabled = not on
        Animation(opacity=1 if on else 0, duration=0.18).start(self.stop)

    def toggle_mic(self):
        """语音输入按钮：安卓上用系统语音识别；桌面环境给出提示。"""
        self.app.start_voice_input()


class SettingsPopup(Popup):
    """设置页：API Key + 独立保存、音色下拉、朗读开关、人设编辑入口"""

    def __init__(self, app, **kw):
        # 远程会话/无 DPI 环境下 Window.dpi 可能为 0，导致 Kivy 内置 Switch
        # style.kv 的 touch_distance / sp(41) 除零崩溃，这里做兜底。
        if Window.dpi <= 0:
            Window.dpi = 96.0
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(470), dp(670))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.62)
        self.auto_dismiss = True

        content = BoxLayout(orientation="vertical", padding=dp(20),
                            spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                            bar_width=dp(4),
                            bar_color=(0.35, 0.35, 0.4, 0.55),
                            bar_inactive_color=(0.35, 0.35, 0.4, 0.2),
                            scroll_type=["bars", "content"])
        with scroll.canvas.before:
            Color(*BG_1)
            self._bg = RoundedRectangle(pos=scroll.pos, size=scroll.size,
                                        radius=R14)
            Color(*INPUT_BORDER)
            self._bd = Line(rounded_rectangle=(scroll.x, scroll.y,
                                               scroll.width, scroll.height,
                                               14, 14, 14, 14), width=dp(1))
        scroll.bind(pos=self._repaint, size=self._repaint)
        scroll.add_widget(content)
        self._scroll = scroll

        title = Label(text="设置", font_name=FONT_CN, font_size=dp(18),
                      bold=True, color=AI_TEXT, size_hint_y=None, height=dp(30))
        content.add_widget(title)

        # DeepSeek API Key（用于 AI 对话）
        self.key_title = Label(text="DeepSeek API Key", font_name=FONT_CN,
                               font_size=dp(13), color=MUTED, halign="left",
                               size_hint_y=None, height=dp(18))
        content.add_widget(self.key_title)
        key_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._key_hidden = True
        self.key_input = TextInput(text=app.cfg.get("api_key", ""),
                                   multiline=False, font_name=FONT_CN,
                                   font_size=dp(13), foreground_color=AI_TEXT,
                                   cursor_color=ACCENT_1,
                                   hint_text="sk-...",
                                   hint_text_color=PLACEHOLDER,
                                   password=True, password_mask="\u25cf",
                                   background_normal="", background_active="",
                                   padding=[dp(12), dp(9)], size_hint_x=1)
        with self.key_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.key_input.pos, size=self.key_input.size,
                             radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.key_input.x, self.key_input.y,
                                    self.key_input.width, self.key_input.height,
                                    12, 12, 12, 12), width=dp(1))
        self.key_input.bind(pos=self._repaint_key, size=self._repaint_key)
        key_row.add_widget(self.key_input)
        # 小眼睛：点击切换明文/密文
        self.key_eye = Button(size_hint=(None, None),
                              size=(dp(38), dp(38)),
                              background_normal="",
                              background_color=(0, 0, 0, 0),
                              on_release=lambda b: self.toggle_key_eye())
        with self.key_eye.canvas.before:
            Color(*INPUT_BG)
            self._key_eye_bg = RoundedRectangle(pos=self.key_eye.pos,
                                                size=self.key_eye.size,
                                                radius=R12)
            Color(*MUTED)
            self._key_eye_ring = Line(ellipse=(0, 0, 0, 0), width=dp(1.5))
            Color(*ACCENT_1)
            self._key_eye_pupil = Ellipse(pos=(0, 0), size=(dp(3.5), dp(3.5)))
        self.key_eye.bind(pos=self._repaint_key_eye, size=self._repaint_key_eye)
        key_row.add_widget(self.key_eye)
        self.key_save_btn = Button(text="保存", size_hint=(None, None),
                                   size=(dp(66), dp(38)), font_name=FONT_CN,
                                   font_size=dp(13), color=(1, 1, 1, 1),
                                   background_normal="",
                                   background_color=(0, 0, 0, 0),
                                   on_release=lambda b: self.on_save_key())
        with self.key_save_btn.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.key_save_btn.pos,
                             size=self.key_save_btn.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        key_row.add_widget(self.key_save_btn)
        # 测试按钮
        self.key_test_btn = Button(text="测试", size_hint=(None, None),
                                   size=(dp(66), dp(38)), font_name=FONT_CN,
                                   font_size=dp(13), color=AI_TEXT,
                                   background_normal="",
                                   background_color=(0, 0, 0, 0),
                                   on_release=lambda b: self.on_test_key())
        with self.key_test_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=self.key_test_btn.pos,
                             size=self.key_test_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.key_test_btn.x,
                                    self.key_test_btn.y,
                                    self.key_test_btn.width,
                                    self.key_test_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        key_row.add_widget(self.key_test_btn)

        # 删除按钮：清空输入框 + config 字段置空（带二次确认）
        self.key_del_btn = Button(text="删除", size_hint=(None, None),
                                 size=(dp(66), dp(38)), font_name=FONT_CN,
                                 font_size=dp(13), color=(0.95, 0.42, 0.42, 1),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.on_delete_key())
        with self.key_del_btn.canvas.before:
            Color(0.26, 0.13, 0.15, 1)
            RoundedRectangle(pos=self.key_del_btn.pos,
                             size=self.key_del_btn.size, radius=R12)
            Color(0.95, 0.42, 0.42, 1)
            Line(rounded_rectangle=(self.key_del_btn.x,
                                    self.key_del_btn.y,
                                    self.key_del_btn.width,
                                    self.key_del_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        key_row.add_widget(self.key_del_btn)
        content.add_widget(key_row)
        content.add_widget(Label(text="用于 AI 对话", font_name=FONT_CN,
                                 font_size=dp(11), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(15)))
        self.key_status = Label(text="", font_name=FONT_CN, font_size=dp(12),
                                color=ACCENT_1, halign="left",
                                size_hint_y=None, height=dp(16))
        content.add_widget(self.key_status)

        # 与 DeepSeek Key 组的间距 16-20px
        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # 搜索 API Key（用于联网搜索）
        self._search_hidden = True
        self.search_title = Label(text="搜索 API Key（用于联网搜索）",
                                  font_name=FONT_CN,
                                  font_size=dp(13), color=MUTED, halign="left",
                                  size_hint_y=None, height=dp(18))
        content.add_widget(self.search_title)
        search_key_row = BoxLayout(size_hint_y=None, height=dp(40),
                                   spacing=dp(8))
        self.search_input = TextInput(text=app.cfg.get("search_api_key", ""),
                                      multiline=False, font_name=FONT_CN,
                                      font_size=dp(13),
                                      foreground_color=AI_TEXT,
                                      cursor_color=ACCENT_1,
                                      hint_text="可选，用于联网搜索",
                                      hint_text_color=PLACEHOLDER,
                                      password=True, password_mask="\u25cf",
                                      background_normal="",
                                      background_active="",
                                      padding=[dp(12), dp(9)], size_hint_x=1)
        with self.search_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.search_input.pos,
                             size=self.search_input.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.search_input.x,
                                    self.search_input.y,
                                    self.search_input.width,
                                    self.search_input.height,
                                    12, 12, 12, 12), width=dp(1))
        self.search_input.bind(pos=self._repaint_search_key,
                               size=self._repaint_search_key)
        search_key_row.add_widget(self.search_input)
        # 小眼睛：点击切换明文/密文
        self.search_eye = Button(size_hint=(None, None),
                                 size=(dp(38), dp(38)),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.toggle_search_eye())
        with self.search_eye.canvas.before:
            Color(*INPUT_BG)
            self._eye_bg = RoundedRectangle(pos=self.search_eye.pos,
                                            size=self.search_eye.size,
                                            radius=R12)
            Color(*MUTED)
            self._eye_ring = Line(ellipse=(0, 0, 0, 0), width=dp(1.5))
            Color(*ACCENT_1)
            self._eye_pupil = Ellipse(pos=(0, 0), size=(dp(3.5), dp(3.5)))
        self.search_eye.bind(pos=self._repaint_eye, size=self._repaint_eye)
        search_key_row.add_widget(self.search_eye)
        # 保存按钮
        self.search_save_btn = Button(text="保存", size_hint=(None, None),
                                      size=(dp(66), dp(38)), font_name=FONT_CN,
                                      font_size=dp(13), color=(1, 1, 1, 1),
                                      background_normal="",
                                      background_color=(0, 0, 0, 0),
                                      on_release=lambda b: self.on_save_search_key())
        with self.search_save_btn.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.search_save_btn.pos,
                             size=self.search_save_btn.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        search_key_row.add_widget(self.search_save_btn)
        # 测试按钮
        self.search_test_btn = Button(text="测试", size_hint=(None, None),
                                      size=(dp(66), dp(38)), font_name=FONT_CN,
                                      font_size=dp(13), color=AI_TEXT,
                                      background_normal="",
                                      background_color=(0, 0, 0, 0),
                                      on_release=lambda b: self.on_test_search_key())
        with self.search_test_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=self.search_test_btn.pos,
                             size=self.search_test_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.search_test_btn.x,
                                    self.search_test_btn.y,
                                    self.search_test_btn.width,
                                    self.search_test_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        search_key_row.add_widget(self.search_test_btn)

        # 删除按钮：清空输入框 + config 字段置空（带二次确认）
        self.search_del_btn = Button(text="删除", size_hint=(None, None),
                                 size=(dp(66), dp(38)), font_name=FONT_CN,
                                 font_size=dp(13), color=(0.95, 0.42, 0.42, 1),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.on_delete_search_key())
        with self.search_del_btn.canvas.before:
            Color(0.26, 0.13, 0.15, 1)
            RoundedRectangle(pos=self.search_del_btn.pos,
                             size=self.search_del_btn.size, radius=R12)
            Color(0.95, 0.42, 0.42, 1)
            Line(rounded_rectangle=(self.search_del_btn.x,
                                    self.search_del_btn.y,
                                    self.search_del_btn.width,
                                    self.search_del_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        search_key_row.add_widget(self.search_del_btn)
        content.add_widget(search_key_row)
        self.search_status = Label(text="", font_name=FONT_CN, font_size=dp(12),
                                   color=ACCENT_1, halign="left",
                                   size_hint_y=None, height=dp(16))
        content.add_widget(self.search_status)

        # 与搜索 Key 组的间距 16-20px
        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # 图像识别 API Key（用于图片识别）
        self._vision_hidden = True
        content.add_widget(Label(text="图像识别 API Key", font_name=FONT_CN,
                                 font_size=dp(13), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(18)))
        vision_key_row = BoxLayout(size_hint_y=None, height=dp(40),
                                   spacing=dp(8))
        self.vision_input = TextInput(text=app.cfg.get("vision_api_key", ""),
                                      multiline=False, font_name=FONT_CN,
                                      font_size=dp(13),
                                      foreground_color=AI_TEXT,
                                      cursor_color=ACCENT_1,
                                      hint_text="可选，用于图片识别",
                                      hint_text_color=PLACEHOLDER,
                                      password=True, password_mask="\u25cf",
                                      background_normal="",
                                      background_active="",
                                      padding=[dp(12), dp(9)], size_hint_x=1)
        with self.vision_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.vision_input.pos,
                             size=self.vision_input.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.vision_input.x,
                                    self.vision_input.y,
                                    self.vision_input.width,
                                    self.vision_input.height,
                                    12, 12, 12, 12), width=dp(1))
        self.vision_input.bind(pos=self._repaint_vision_key,
                               size=self._repaint_vision_key)
        vision_key_row.add_widget(self.vision_input)
        # 小眼睛：点击切换明文/密文
        self.vision_eye = Button(size_hint=(None, None),
                                 size=(dp(38), dp(38)),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.toggle_vision_eye())
        with self.vision_eye.canvas.before:
            Color(*INPUT_BG)
            self._vision_eye_bg = RoundedRectangle(pos=self.vision_eye.pos,
                                                   size=self.vision_eye.size,
                                                   radius=R12)
            Color(*MUTED)
            self._vision_eye_ring = Line(ellipse=(0, 0, 0, 0), width=dp(1.5))
            Color(*ACCENT_1)
            self._vision_eye_pupil = Ellipse(pos=(0, 0), size=(dp(3.5), dp(3.5)))
        self.vision_eye.bind(pos=self._repaint_vision_eye,
                             size=self._repaint_vision_eye)
        vision_key_row.add_widget(self.vision_eye)
        # 保存按钮
        self.vision_save_btn = Button(text="保存", size_hint=(None, None),
                                      size=(dp(66), dp(38)), font_name=FONT_CN,
                                      font_size=dp(13), color=(1, 1, 1, 1),
                                      background_normal="",
                                      background_color=(0, 0, 0, 0),
                                      on_release=lambda b: self.on_save_vision_key())
        with self.vision_save_btn.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.vision_save_btn.pos,
                             size=self.vision_save_btn.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        vision_key_row.add_widget(self.vision_save_btn)
        # 测试按钮
        self.vision_test_btn = Button(text="测试", size_hint=(None, None),
                                      size=(dp(66), dp(38)), font_name=FONT_CN,
                                      font_size=dp(13), color=AI_TEXT,
                                      background_normal="",
                                      background_color=(0, 0, 0, 0),
                                      on_release=lambda b: self.on_test_vision_key())
        with self.vision_test_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=self.vision_test_btn.pos,
                             size=self.vision_test_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.vision_test_btn.x,
                                    self.vision_test_btn.y,
                                    self.vision_test_btn.width,
                                    self.vision_test_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        vision_key_row.add_widget(self.vision_test_btn)

        # 删除按钮：清空输入框 + config 字段置空（带二次确认）
        self.vision_del_btn = Button(text="删除", size_hint=(None, None),
                                 size=(dp(66), dp(38)), font_name=FONT_CN,
                                 font_size=dp(13), color=(0.95, 0.42, 0.42, 1),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.on_delete_vision_key())
        with self.vision_del_btn.canvas.before:
            Color(0.26, 0.13, 0.15, 1)
            RoundedRectangle(pos=self.vision_del_btn.pos,
                             size=self.vision_del_btn.size, radius=R12)
            Color(0.95, 0.42, 0.42, 1)
            Line(rounded_rectangle=(self.vision_del_btn.x,
                                    self.vision_del_btn.y,
                                    self.vision_del_btn.width,
                                    self.vision_del_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        vision_key_row.add_widget(self.vision_del_btn)
        content.add_widget(vision_key_row)
        content.add_widget(Label(text="用于聊天时看懂图片（智谱 GLM-4V）",
                                 font_name=FONT_CN,
                                 font_size=dp(11), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(15)))
        self.vision_status = Label(text="", font_name=FONT_CN, font_size=dp(12),
                                   color=ACCENT_1, halign="left",
                                   size_hint_y=None, height=dp(16))
        content.add_widget(self.vision_status)

        # 与图像识别 Key 组的间距 16-20px
        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # 图片生成 API Key（用于 AI 按钮生成图片）
        self._image_hidden = True
        content.add_widget(Label(text="图片生成 API Key", font_name=FONT_CN,
                                 font_size=dp(13), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(18)))
        image_key_row = BoxLayout(size_hint_y=None, height=dp(40),
                                  spacing=dp(8))
        self.image_input = TextInput(text=app.cfg.get("image_api_key", ""),
                                     multiline=False, font_name=FONT_CN,
                                     font_size=dp(13),
                                     foreground_color=AI_TEXT,
                                     cursor_color=ACCENT_1,
                                     hint_text="可选，用于生成图片",
                                     hint_text_color=PLACEHOLDER,
                                     password=True, password_mask="\u25cf",
                                     background_normal="",
                                     background_active="",
                                     padding=[dp(12), dp(9)], size_hint_x=1)
        with self.image_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.image_input.pos,
                             size=self.image_input.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.image_input.x,
                                    self.image_input.y,
                                    self.image_input.width,
                                    self.image_input.height,
                                    12, 12, 12, 12), width=dp(1))
        self.image_input.bind(pos=self._repaint_image_key,
                              size=self._repaint_image_key)
        image_key_row.add_widget(self.image_input)
        # 小眼睛：点击切换明文/密文
        self.image_eye = Button(size_hint=(None, None),
                                size=(dp(38), dp(38)),
                                background_normal="",
                                background_color=(0, 0, 0, 0),
                                on_release=lambda b: self.toggle_image_eye())
        with self.image_eye.canvas.before:
            Color(*INPUT_BG)
            self._image_eye_bg = RoundedRectangle(pos=self.image_eye.pos,
                                                  size=self.image_eye.size,
                                                  radius=R12)
            Color(*MUTED)
            self._image_eye_ring = Line(ellipse=(0, 0, 0, 0), width=dp(1.5))
            Color(*ACCENT_1)
            self._image_eye_pupil = Ellipse(pos=(0, 0), size=(dp(3.5), dp(3.5)))
        self.image_eye.bind(pos=self._repaint_image_eye,
                            size=self._repaint_image_eye)
        image_key_row.add_widget(self.image_eye)
        # 保存按钮
        self.image_save_btn = Button(text="保存", size_hint=(None, None),
                                     size=(dp(66), dp(38)), font_name=FONT_CN,
                                     font_size=dp(13), color=(1, 1, 1, 1),
                                     background_normal="",
                                     background_color=(0, 0, 0, 0),
                                     on_release=lambda b: self.on_save_image_key())
        with self.image_save_btn.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.image_save_btn.pos,
                             size=self.image_save_btn.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        image_key_row.add_widget(self.image_save_btn)
        # 测试按钮
        self.image_test_btn = Button(text="测试", size_hint=(None, None),
                                     size=(dp(66), dp(38)), font_name=FONT_CN,
                                     font_size=dp(13), color=AI_TEXT,
                                     background_normal="",
                                     background_color=(0, 0, 0, 0),
                                     on_release=lambda b: self.on_test_image_key())
        with self.image_test_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=self.image_test_btn.pos,
                             size=self.image_test_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.image_test_btn.x,
                                    self.image_test_btn.y,
                                    self.image_test_btn.width,
                                    self.image_test_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        image_key_row.add_widget(self.image_test_btn)

        # 删除按钮：清空输入框 + config 字段置空（带二次确认）
        self.image_del_btn = Button(text="删除", size_hint=(None, None),
                                 size=(dp(66), dp(38)), font_name=FONT_CN,
                                 font_size=dp(13), color=(0.95, 0.42, 0.42, 1),
                                 background_normal="",
                                 background_color=(0, 0, 0, 0),
                                 on_release=lambda b: self.on_delete_image_key())
        with self.image_del_btn.canvas.before:
            Color(0.26, 0.13, 0.15, 1)
            RoundedRectangle(pos=self.image_del_btn.pos,
                             size=self.image_del_btn.size, radius=R12)
            Color(0.95, 0.42, 0.42, 1)
            Line(rounded_rectangle=(self.image_del_btn.x,
                                    self.image_del_btn.y,
                                    self.image_del_btn.width,
                                    self.image_del_btn.height,
                                    12, 12, 12, 12), width=dp(1))
        image_key_row.add_widget(self.image_del_btn)
        content.add_widget(image_key_row)
        content.add_widget(Label(text="用于 AI 按钮生成图片（智谱 CogView）",
                                 font_name=FONT_CN,
                                 font_size=dp(11), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(15)))
        self.image_status = Label(text="", font_name=FONT_CN, font_size=dp(12),
                                  color=ACCENT_1, halign="left",
                                  size_hint_y=None, height=dp(16))
        content.add_widget(self.image_status)

        # 音色（读取系统中文 TTS 语音包）
        content.add_widget(Label(text="音色", font_name=FONT_CN,
                                 font_size=dp(13), color=MUTED, halign="left",
                                 size_hint_y=None, height=dp(18)))
        voice_values = self.app.tts.system_voices()
        cur_voice = app.cfg.get("voice", "")
        if cur_voice not in voice_values:
            cur_voice = voice_values[0] if voice_values else ""
        self.voice_spinner = Spinner(text=cur_voice,
                                     values=voice_values, size_hint_y=None,
                                     height=dp(38), font_name=FONT_CN,
                                     font_size=dp(13), color=AI_TEXT,
                                     background_normal="",
                                     background_color=(0, 0, 0, 0))
        with self.voice_spinner.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.voice_spinner.pos,
                             size=self.voice_spinner.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.voice_spinner.x,
                                    self.voice_spinner.y,
                                    self.voice_spinner.width,
                                    self.voice_spinner.height,
                                    12, 12, 12, 12), width=dp(1))
        self.voice_spinner.bind(pos=self._repaint_voice,
                                size=self._repaint_voice)
        self.voice_spinner.bind(text=self.on_voice_changed)
        content.add_widget(self.voice_spinner)

        # 朗读开关
        sw_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        sw_row.add_widget(Label(text="自动朗读回复", font_name=FONT_CN,
                                font_size=dp(13), color=MUTED, halign="left"))
        self.speak_switch = Switch(active=bool(app.cfg.get("speak_on_reply", True)),
                                   size_hint=(None, None), size=(dp(52), dp(30)),
                                   pos_hint={"right": 1})
        sw_row.add_widget(Widget())
        sw_row.add_widget(self.speak_switch)
        content.add_widget(sw_row)
        self.speak_switch.bind(active=self.on_speak_switch)

        # 联网搜索开关
        sw_row2 = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        sw_row2.add_widget(Label(text="联网搜索", font_name=FONT_CN,
                                 font_size=dp(13), color=MUTED, halign="left"))
        self.search_switch = Switch(active=bool(app.cfg.get("search_enabled", False)),
                                    size_hint=(None, None), size=(dp(52), dp(30)),
                                    pos_hint={"right": 1})
        sw_row2.add_widget(Widget())
        sw_row2.add_widget(self.search_switch)
        content.add_widget(sw_row2)
        self.search_switch.bind(active=self.on_search_switch)

        # 重置立绘位置
        reset_btn = Button(text="重置立绘位置", size_hint_y=None,
                           height=dp(40), font_name=FONT_CN, font_size=dp(13),
                           color=AI_TEXT, background_normal="",
                           background_color=(0, 0, 0, 0),
                           on_release=lambda b: self.on_reset_avatar())
        with reset_btn.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=reset_btn.pos, size=reset_btn.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(reset_btn.x, reset_btn.y, reset_btn.width,
                                    reset_btn.height, 12, 12, 12, 12),
                 width=dp(1))
        content.add_widget(reset_btn)

        # 人设编辑入口
        edit_p = Button(text="编辑当前人设内容", size_hint_y=None,
                        height=dp(40), font_name=FONT_CN, font_size=dp(13),
                        color=AI_TEXT, background_normal="",
                        background_color=(0, 0, 0, 0),
                        on_release=lambda b: self.open_persona_editor())
        with edit_p.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=edit_p.pos, size=edit_p.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(edit_p.x, edit_p.y, edit_p.width,
                                    edit_p.height, 12, 12, 12, 12), width=dp(1))
        content.add_widget(edit_p)

        close_btn = Button(text="关闭", size_hint_y=None, height=dp(40),
                           font_name=FONT_CN, font_size=dp(14),
                           color=(1, 1, 1, 1), background_normal="",
                           background_color=(0, 0, 0, 0),
                           on_release=lambda b: self.dismiss())
        with close_btn.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=close_btn.pos, size=close_btn.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        content.add_widget(close_btn)

        self.content = scroll

    def _repaint(self, *a):
        self._bg.pos = self.content.pos
        self._bg.size = self.content.size
        self._bd.rounded_rectangle = (self.content.x, self.content.y,
                                      self.content.width, self.content.height,
                                      14, 14, 14, 14)

    def _repaint_key(self, *a):
        k = self.key_input
        k.canvas.before.clear()
        with k.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=k.pos, size=k.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(k.x, k.y, k.width, k.height, 12, 12, 12, 12),
                 width=dp(1))

    def _repaint_voice(self, *a):
        v = self.voice_spinner
        v.canvas.before.clear()
        with v.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=v.pos, size=v.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(v.x, v.y, v.width, v.height, 12, 12, 12, 12),
                 width=dp(1))

    def on_save_key(self):
        key = self.key_input.text.strip()
        if not key.startswith("sk-"):
            self.key_status.text = "Key 格式不对，应以 sk- 开头"
            self.key_status.color = (0.95, 0.45, 0.45, 1)
            return
        self.app.cfg["api_key"] = key
        save_json(CONFIG_FILE, self.app.cfg)
        self.key_status.text = "已保存"
        self.key_status.color = ACCENT_1
        self.key_save_btn.text = "已保存 \u2713"
        self.app.chat.check_guide()
        self.app.set_status("API Key 已保存")
        Clock.schedule_once(self._restore_key_btn, 2.0)

    def _restore_key_btn(self, *a):
        self.key_save_btn.text = "保存"

    def on_speak_switch(self, inst, val):
        self.app.cfg["speak_on_reply"] = bool(val)
        save_json(CONFIG_FILE, self.app.cfg)
        self.app.set_status("自动朗读：" + ("开" if val else "关"))

    def on_search_switch(self, inst, val):
        self.app.cfg["search_enabled"] = bool(val)
        save_json(CONFIG_FILE, self.app.cfg)
        self.app.set_status("联网搜索：" + ("开" if val else "关"))

    def on_voice_changed(self, spinner, text):
        self.app.cfg["voice"] = text
        save_json(CONFIG_FILE, self.app.cfg)
        self.app.set_status("音色已选择：" + text)

    def on_reset_avatar(self):
        self.app.avatar.reset_position()
        self.app.set_status("立绘位置已重置")

    def _repaint_search_key(self, *a):
        k = self.search_input
        k.canvas.before.clear()
        with k.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=k.pos, size=k.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(k.x, k.y, k.width, k.height, 12, 12, 12, 12),
                 width=dp(1))

    def _repaint_eye(self, *a):
        e = self.search_eye
        self._eye_bg.pos = e.pos
        self._eye_bg.size = e.size
        cx = e.x + e.width / 2.0
        cy = e.y + e.height / 2.0
        self._eye_ring.ellipse = (cx - dp(8), cy - dp(5), dp(16), dp(10))
        self._eye_pupil.pos = (cx - dp(1.75), cy - dp(1.75))
        self._eye_pupil.size = (dp(3.5), dp(3.5))

    def toggle_search_eye(self):
        self._search_hidden = not self._search_hidden
        self.search_input.password = self._search_hidden

    def on_save_search_key(self):
        key = self.search_input.text.strip()
        self.app.cfg["search_api_key"] = key
        save_json(CONFIG_FILE, self.app.cfg)
        self.search_status.text = "已保存"
        self.search_status.color = ACCENT_1
        self.search_save_btn.text = "已保存 \u2713"
        self.app.set_status("搜索 API Key 已保存")
        Clock.schedule_once(self._restore_search_btn, 2.0)

    def _restore_search_btn(self, *a):
        self.search_save_btn.text = "保存"

    def _repaint_vision_key(self, *a):
        k = self.vision_input
        k.canvas.before.clear()
        with k.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=k.pos, size=k.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(k.x, k.y, k.width, k.height, 12, 12, 12, 12),
                 width=dp(1))

    def _repaint_vision_eye(self, *a):
        e = self.vision_eye
        self._vision_eye_bg.pos = e.pos
        self._vision_eye_bg.size = e.size
        cx = e.x + e.width / 2.0
        cy = e.y + e.height / 2.0
        self._vision_eye_ring.ellipse = (cx - dp(8), cy - dp(5), dp(16), dp(10))
        self._vision_eye_pupil.pos = (cx - dp(1.75), cy - dp(1.75))
        self._vision_eye_pupil.size = (dp(3.5), dp(3.5))

    def toggle_vision_eye(self):
        self._vision_hidden = not self._vision_hidden
        self.vision_input.password = self._vision_hidden

    def on_save_vision_key(self):
        key = self.vision_input.text.strip()
        self.app.cfg["vision_api_key"] = key
        save_json(CONFIG_FILE, self.app.cfg)
        self.vision_status.text = "已保存"
        self.vision_status.color = ACCENT_1
        self.vision_save_btn.text = "已保存 \u2713"
        self.app.set_status("图像识别 API Key 已保存")
        Clock.schedule_once(self._restore_vision_btn, 2.0)

    def _restore_vision_btn(self, *a):
        self.vision_save_btn.text = "保存"

    # ---------- 眼睛显隐（DeepSeek / 图片生成组） ----------

    def toggle_key_eye(self, *a):
        self.key_input.password = not self.key_input.password
        self._repaint_key_eye()

    def _repaint_key_eye(self, *a):
        try:
            txt = "⊙" if self.key_input.password else "◉"
            self.key_eye.text = txt
        except Exception:
            pass

    def toggle_image_eye(self, *a):
        self.image_input.password = not self.image_input.password
        self._repaint_image_eye()

    def _repaint_image_eye(self, *a):
        try:
            txt = "⊙" if self.image_input.password else "◉"
            self.image_eye.text = txt
        except Exception:
            pass

    def _repaint_image_key(self, *a):
        self.image_input.password = True
        self._repaint_image_eye()

    # ---------- 测试按钮 ----------

    def _test_state(self, btn, ok, text="测试通过"):
        btn.text = text
        self.app.set_status(text)
        Clock.schedule_once(lambda dt: setattr(btn, "text", "测试"), 2.0)

    def on_test_key(self, *a):
        key = self.key_input.text.strip()
        if not key:
            self.app.set_status("请先填写 DeepSeek API Key")
            return
        self.key_test_btn.text = "测试中…"
        self.app.set_status("正在测试 DeepSeek Key…")
        self.app.test_key_request("api_key", key, "DeepSeek API Key", self.key_test_btn, "GET", "https://api.deepseek.com/models", None)

    def on_test_search_key(self, *a):
        key = self.search_input.text.strip()
        if not key:
            self.app.set_status("请先填写搜索 API Key")
            return
        self.search_test_btn.text = "测试中…"
        self.app.set_status("正在测试搜索 Key…")
        self.app.test_key_request("search_api_key", key, "搜索 API Key", self.search_test_btn, "POST", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "hi")

    def on_test_vision_key(self, *a):
        key = self.vision_input.text.strip()
        if not key:
            self.app.set_status("请先填写图像识别 API Key")
            return
        self.vision_test_btn.text = "测试中…"
        self.app.set_status("正在测试图像识别 Key…")
        self.app.test_key_request("vision_api_key", key, "图像识别 API Key", self.vision_test_btn, "POST", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "hi")

    def on_test_image_key(self, *a):
        self.image_test_btn.text = "测试"
        self.app.set_status("图片生成功能尚未接入，敬请期待")

    # ---------- 保存图片生成 Key ----------

    def on_save_image_key(self, *a):
        self.app.cfg["image_api_key"] = self.image_input.text.strip()
        save_json(CONFIG_FILE, self.app.cfg)
        self.image_save_btn.text = "已保存 \u2713"
        self.app.set_status("图片生成 API Key 已保存")
        Clock.schedule_once(self._restore_image_btn, 2.0)

    def _restore_image_btn(self, *a):
        self.image_save_btn.text = "保存"


    # ---------- 删除 Key（清空输入框 + config 字段置空，带二次确认） ----------
    def _confirm_delete(self, cfg_field, input_widget, status_label, label_name):
        try:
            if not (input_widget.text or "").strip() and \
               not (self.app.cfg.get(cfg_field) or "").strip():
                if status_label is not None:
                    status_label.text = label_name + " 未配置"
                    status_label.color = (0.95, 0.45, 0.45, 1)
                self.app.set_status(label_name + " 未配置")
                return
            pop = Popup(title="删除确认", size_hint=(None, None),
                        size=(dp(340), dp(190)), auto_dismiss=True,
                        background="", background_color=(0, 0, 0, 0),
                        overlay_color=(0, 0, 0, 0.62))
            body = BoxLayout(orientation="vertical", padding=dp(18),
                             spacing=dp(14))
            msg = Label(text="确定删除吗？", font_name=FONT_CN, font_size=dp(15),
                        color=AI_TEXT, halign="center", valign="middle")
            body.add_widget(msg)
            btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
            cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(13),
                            color=AI_TEXT, background_normal="",
                            background_color=(0, 0, 0, 0),
                            on_release=lambda b: pop.dismiss())
            with cancel.canvas.before:
                Color(*TOP_2)
                RoundedRectangle(pos=cancel.pos, size=cancel.size, radius=R12)
                Color(*INPUT_BORDER)
                Line(rounded_rectangle=(cancel.x, cancel.y, cancel.width,
                                        cancel.height, 12, 12, 12, 12),
                     width=dp(1))
            ok_btn = Button(text="删除", font_name=FONT_CN, font_size=dp(13),
                            color=(1, 1, 1, 1), background_normal="",
                            background_color=(0, 0, 0, 0),
                            on_release=lambda b: self._do_delete_key(
                                pop, cfg_field, input_widget, status_label,
                                label_name))
            with ok_btn.canvas.before:
                Color(0.92, 0.35, 0.35, 1)
                RoundedRectangle(pos=ok_btn.pos, size=ok_btn.size, radius=R12)
            btns.add_widget(cancel)
            btns.add_widget(ok_btn)
            body.add_widget(btns)
            pop.content = body
            pop.open()
        except Exception as e:
            try:
                self.app.set_status("删除确认失败：" + str(e))
            except Exception:
                pass

    def _do_delete_key(self, pop, cfg_field, input_widget, status_label,
                       label_name):
        try:
            pop.dismiss()
        except Exception:
            pass
        try:
            input_widget.text = ""
            self.app.cfg[cfg_field] = ""
            save_json(CONFIG_FILE, self.app.cfg)
        except Exception as e:
            try:
                self.app.set_status("删除失败：写配置文件出错 " + str(e))
            except Exception:
                pass
            return
        try:
            if status_label is not None:
                status_label.text = "已删除 " + label_name
                status_label.color = (0.95, 0.42, 0.42, 1)
            self.app.set_status("已删除 " + label_name)
            self.app.chat.check_guide()
        except Exception:
            pass

    def on_delete_key(self, *a):
        self._confirm_delete("api_key", self.key_input, self.key_status,
                             "DeepSeek API Key")

    def on_delete_search_key(self, *a):
        self._confirm_delete("search_api_key", self.search_input,
                             self.search_status, "搜索 API Key")

    def on_delete_vision_key(self, *a):
        self._confirm_delete("vision_api_key", self.vision_input,
                             self.vision_status, "图像识别 API Key")

    def on_delete_image_key(self, *a):
        self._confirm_delete("image_api_key", self.image_input, None,
                             "图片生成 API Key")

    def open_persona_editor(self):
        self.dismiss()
        self.app.open_persona_editor()


class PersonaEditPopup(Popup):
    """人设编辑入口：编辑当前人设名称与内容"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(520), dp(520))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.62)
        self.auto_dismiss = True

        content = BoxLayout(orientation="vertical", padding=dp(20),
                            spacing=dp(10))
        with content.canvas.before:
            Color(*BG_1)
            RoundedRectangle(pos=content.pos, size=content.size, radius=R14)

        content.add_widget(Label(text="编辑人设", font_name=FONT_CN,
                                 font_size=dp(17), bold=True, color=AI_TEXT,
                                 size_hint_y=None, height=dp(28)))
        self.name_input = TextInput(text=app.current_persona, multiline=False,
                                    font_name=FONT_CN, font_size=dp(13),
                                    foreground_color=AI_TEXT,
                                    cursor_color=ACCENT_1,
                                    background_normal="", background_active="",
                                    padding=[dp(10), dp(8)],
                                    size_hint_y=None, height=dp(38),
                                    hint_text="人设名称",
                                    hint_text_color=PLACEHOLDER)
        with self.name_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.name_input.pos, size=self.name_input.size,
                             radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.name_input.x, self.name_input.y,
                                    self.name_input.width, self.name_input.height,
                                    12, 12, 12, 12), width=dp(1))
        content.add_widget(self.name_input)

        self.body_input = TextInput(
            text=app.personas.get(app.current_persona, ""), multiline=True,
            font_name=FONT_CN, font_size=dp(13), foreground_color=AI_TEXT,
            cursor_color=ACCENT_1, background_normal="", background_active="",
            padding=[dp(10), dp(8)], size_hint=(1, 1),
            hint_text="人设内容", hint_text_color=PLACEHOLDER)
        with self.body_input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.body_input.pos, size=self.body_input.size,
                             radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.body_input.x, self.body_input.y,
                                    self.body_input.width, self.body_input.height,
                                    12, 12, 12, 12), width=dp(1))
        content.add_widget(self.body_input)

        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(10))
        cancel = Button(text="取消", size_hint_x=1, font_name=FONT_CN,
                        font_size=dp(13), color=AI_TEXT, background_normal="",
                        background_color=(0, 0, 0, 0),
                        on_release=lambda b: self.dismiss())
        with cancel.canvas.before:
            Color(*TOP_2)
            RoundedRectangle(pos=cancel.pos, size=cancel.size, radius=R12)
        save_b = Button(text="保存人设", size_hint_x=1, font_name=FONT_CN,
                        font_size=dp(13), color=(1, 1, 1, 1),
                        background_normal="", background_color=(0, 0, 0, 0),
                        on_release=lambda b: self.on_save())
        with save_b.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=save_b.pos, size=save_b.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        bar.add_widget(cancel)
        bar.add_widget(save_b)
        content.add_widget(bar)

        self.content = content

    def on_save(self):
        name = self.name_input.text.strip()
        body = self.body_input.text.strip()
        if not name:
            return
        self.app.personas[name] = body
        save_json(PERSONA_FILE, self.app.personas)
        self.app.current_persona = name
        self.app.cfg["persona"] = name
        self.app.refresh_persona_ui()
        self.dismiss()
        self.app.set_status("人设已保存：" + name)


class ImageGenPopup(Popup):
    """AI 生图弹窗：提示词 + 生成按钮 + 结果图 + 右上角关闭 × + 顶部失败提示条(3秒淡出)"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(460), dp(560))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.62)
        self.auto_dismiss = False
        self._busy = False
        self._has_new = False

        root = BoxLayout(orientation="vertical",
                         padding=[dp(18), dp(14), dp(18), dp(14)], spacing=dp(10))

        # 标题栏 + 右上角关闭 ×
        head = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        head.add_widget(Label(text="AI 生图", font_name=FONT_CN, font_size=dp(17),
                              bold=True, color=AI_TEXT, halign="left",
                              valign="middle", size_hint_x=1))
        close = Button(text="\u2715", size_hint=(None, None), size=(dp(34), dp(34)),
                       font_name="SegoeSym", font_size=dp(18), color=CLOSE_ICON,
                       background_normal="", background_color=(0, 0, 0, 0),
                       on_release=lambda b: self._close())
        head.add_widget(close)
        root.add_widget(head)

        # 失败提示条（默认隐藏，出错时显示 3 秒淡出）
        self.err_bar = Label(text="", font_name=FONT_CN, font_size=dp(12),
                             color=NOTICE_RED, halign="left", valign="middle",
                             size_hint_y=None, height=0, padding=[dp(14), 0])
        with self.err_bar.canvas.before:
            Color(*NOTICE_BG)
            self._err_bg = RoundedRectangle(pos=self.err_bar.pos,
                                            size=self.err_bar.size, radius=R10)
        self.err_bar.bind(pos=self._repaint_err, size=self._repaint_err)
        root.add_widget(self.err_bar)

        self.prompt = TextInput(text="", multiline=True, size_hint_y=None,
                                height=dp(110), font_name=FONT_CN, font_size=dp(14),
                                hint_text="描述你想生成的画面，例如：赛博朋克风格的鲸鱼娘…",
                                hint_text_color=PLACEHOLDER,
                                foreground_color=AI_TEXT, cursor_color=ACCENT_1,
                                background_normal="", background_active="")
        with self.prompt.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.prompt.pos, size=self.prompt.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.prompt.x, self.prompt.y,
                                    self.prompt.width, self.prompt.height,
                                    12, 12, 12, 12), width=dp(1))
        self.prompt.bind(pos=self._repaint_prompt, size=self._repaint_prompt)
        root.add_widget(self.prompt)

        # 参考图（最多 5 张，支持常见图片格式；点击缩略图上的 × 移除）
        ref_head = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        self.ref_lbl = Label(text="参考图 (0/5)", font_name=FONT_CN,
                             font_size=dp(12), color=MUTED, halign="left",
                             valign="middle", size_hint_x=1)
        ref_head.add_widget(self.ref_lbl)
        root.add_widget(ref_head)
        self.refs = []
        self.refs_row = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(8))
        self.add_ref_btn = Button(text="＋ 添加参考图", size_hint=(None, None),
                                  size=(dp(124), dp(72)), font_name=FONT_CN,
                                  font_size=dp(13), color=ACCENT_1,
                                  background_normal="",
                                  background_color=(0.15, 0.19, 0.29, 1),
                                  on_release=lambda b: self._choose_ref())
        with self.add_ref_btn.canvas.before:
            Color(*INPUT_BG)
            self._ref_btn_bg = RoundedRectangle(pos=self.add_ref_btn.pos,
                                                size=self.add_ref_btn.size,
                                                radius=R10)
            Color(*INPUT_BORDER)
            self._ref_btn_bd = Line(rounded_rectangle=(
                self.add_ref_btn.x, self.add_ref_btn.y,
                self.add_ref_btn.width, self.add_ref_btn.height,
                10, 10, 10, 10), width=dp(1))
        self.add_ref_btn.bind(pos=self._repaint_ref_btn, size=self._repaint_ref_btn)
        self.refs_row.add_widget(self.add_ref_btn)
        root.add_widget(self.refs_row)

        self.gen_btn = Button(text="生成图片", size_hint_y=None, height=dp(44),
                              font_name=FONT_CN, font_size=dp(15), bold=True,
                              color=(1, 1, 1, 1), background_normal="",
                              background_color=(0, 0, 0, 0),
                              on_release=lambda b: self._generate())
        with self.gen_btn.canvas.before:
            Color(*ACCENT_1)
            RoundedRectangle(pos=self.gen_btn.pos, size=self.gen_btn.size, radius=R12)
        self.gen_btn.bind(pos=self._repaint_btn, size=self._repaint_btn)
        root.add_widget(self.gen_btn)

        self.img_holder = BoxLayout(size_hint_y=1)
        self.result_img = Image(source="", allow_stretch=True, keep_ratio=True)
        self.img_holder.add_widget(self.result_img)
        root.add_widget(self.img_holder)

        self.save_btn = Button(text="保存图片", size_hint_y=None, height=0,
                               font_name=FONT_CN, font_size=dp(14),
                               color=(1, 1, 1, 1), background_normal="",
                               background_color=(0.24, 0.30, 0.44, 1),
                               on_release=lambda b: self._save())
        root.add_widget(self.save_btn)

        self.add_widget(root)

    def _repaint_err(self, *a):
        self._err_bg.pos = self.err_bar.pos
        self._err_bg.size = self.err_bar.size

    def _repaint_prompt(self, *a):
        self.prompt.canvas.before.clear()
        with self.prompt.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.prompt.pos, size=self.prompt.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.prompt.x, self.prompt.y,
                                    self.prompt.width, self.prompt.height,
                                    12, 12, 12, 12), width=dp(1))

    def _repaint_btn(self, *a):
        self.gen_btn.canvas.before.clear()
        with self.gen_btn.canvas.before:
            Color(*ACCENT_1)
            RoundedRectangle(pos=self.gen_btn.pos, size=self.gen_btn.size, radius=R12)

    def _repaint_ref_btn(self, *a):
        self._ref_btn_bg.pos = self.add_ref_btn.pos
        self._ref_btn_bg.size = self.add_ref_btn.size
        self._ref_btn_bd.rounded_rectangle = (self.add_ref_btn.x,
                                              self.add_ref_btn.y,
                                              self.add_ref_btn.width,
                                              self.add_ref_btn.height,
                                              10, 10, 10, 10)

    def _build_refs_ui(self):
        self.refs_row.clear_widgets()
        for path in self.refs[:5]:
            w = FloatLayout(size_hint=(None, None), size=(dp(72), dp(72)))
            with w.canvas.before:
                Color(*INPUT_BG)
                RoundedRectangle(pos=w.pos, size=w.size, radius=R10)
                Color(*INPUT_BORDER)
                Line(rounded_rectangle=(w.x, w.y, w.width, w.height,
                                        10, 10, 10, 10), width=dp(1))
            w.bind(pos=self._repaint_thumb, size=self._repaint_thumb)
            img = Image(source=path, allow_stretch=True, keep_ratio=True,
                        pos_hint={"center_x": 0.5, "center_y": 0.45},
                        size_hint=(0.9, 0.8))
            w.add_widget(img)
            rm = Button(text="\u2715", size_hint=(None, None),
                        size=(dp(20), dp(20)), pos_hint={"right": 1, "top": 1},
                        font_name="SegoeSym", font_size=dp(12),
                        color=(1, 1, 1, 1), background_normal="",
                        background_color=(0.6, 0.22, 0.22, 1),
                        on_release=lambda b, p=path: self._remove_ref(p))
            w.add_widget(rm)
            self.refs_row.add_widget(w)
        if len(self.refs) < 5:
            self.refs_row.add_widget(self.add_ref_btn)
        self.ref_lbl.text = "参考图 (%d/5)" % len(self.refs)

    def _repaint_thumb(self, w, *a):
        w.canvas.before.clear()
        with w.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=w.pos, size=w.size, radius=R10)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(w.x, w.y, w.width, w.height,
                                    10, 10, 10, 10), width=dp(1))

    def _choose_ref(self):
        if self._busy:
            return
        if len(self.refs) >= 5:
            self.show_error("参考图最多 5 张")
            return
        try:
            from kivy.uix.filechooser import FileChooserIconView
        except Exception:
            self.show_error("当前环境不支持选择参考图")
            return
        fc = FileChooserIconView(filters=["*.jpg", "*.jpeg", "*.png",
                                          "*.webp", "*.bmp", "*.gif"],
                                 path=os.path.expanduser("~") or BASE_DIR,
                                 size_hint=(None, None),
                                 size=(dp(430), dp(300)))
        p = Popup(title="", size_hint=(None, None), size=(dp(460), dp(430)),
                  background="", background_color=(0, 0, 0, 0),
                  overlay_color=(0, 0, 0, 0.55), auto_dismiss=True)
        box = BoxLayout(orientation="vertical",
                        padding=[dp(14), dp(12), dp(14), dp(12)], spacing=dp(8))
        box.add_widget(Label(text="选择参考图（最多 5 张）", font_name=FONT_CN,
                             font_size=dp(14), bold=True, color=AI_TEXT,
                             halign="center", valign="middle",
                             size_hint_y=None, height=dp(26)))
        box.add_widget(fc)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        ok = Button(text="添加", font_name=FONT_CN, font_size=dp(14),
                    color=(1, 1, 1, 1), background_normal="",
                    background_color=ACCENT_1,
                    on_release=lambda b: self._add_ref(fc.selection, p))
        cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(14),
                        color=AI_TEXT, background_normal="",
                        background_color=TOP_2, on_release=lambda b: p.dismiss())
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        p.add_widget(box)
        p.open()

    def _add_ref(self, selection, popup):
        popup.dismiss()
        for path in list(selection):
            path = str(path)
            if len(self.refs) >= 5:
                self.show_error("参考图最多 5 张，多余已忽略")
                break
            if path in self.refs:
                continue
            try:
                if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                    continue
            except Exception:
                continue
            self.refs.append(path)
        self._build_refs_ui()

    def _remove_ref(self, path):
        try:
            if path in self.refs:
                self.refs.remove(path)
            self._build_refs_ui()
        except Exception:
            pass

    def _close(self):
        if self._busy:
            self.dismiss()
            return
        if self._has_new:
            self._ask_discard()
        else:
            self.dismiss()

    def _ask_discard(self):
        def _ok(*a):
            p.dismiss()
            self.dismiss()
        p = Popup(title="", size_hint=(None, None), size=(dp(360), dp(190)),
                  background="", background_color=(0, 0, 0, 0),
                  overlay_color=(0, 0, 0, 0.55), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", padding=[dp(18), dp(16), dp(18), dp(16)],
                        spacing=dp(14))
        box.add_widget(Label(text="生成的图片尚未保存，确定关闭吗？", font_name=FONT_CN,
                             font_size=dp(14), color=AI_TEXT, halign="center",
                             valign="middle"))
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        ok = Button(text="确定", font_name=FONT_CN, font_size=dp(14),
                    color=(1, 1, 1, 1), background_normal="",
                    background_color=(0.8, 0.3, 0.3, 1), on_release=_ok)
        cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(14),
                        color=(1, 1, 1, 1), background_normal="",
                        background_color=TOP_2, on_release=lambda b: p.dismiss())
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        p.add_widget(box)
        p.open()

    def _generate(self):
        prompt = self.prompt.text.strip()
        if not prompt:
            self.show_error("请先输入画面描述")
            return
        if self._busy:
            return
        self._busy = True
        self.gen_btn.text = "生成中…"
        self.result_img.source = ""
        self._has_new = False
        self.app.set_status("正在生成图片…")
        client = ImageGenClient(self.app.cfg.get("image_api_key") or "")
        client.generate(prompt, self._on_gen_result, refs=list(self.refs))

    def _on_gen_result(self, res):
        Clock.schedule_once(lambda dt: self._apply_result(res), 0)

    def _apply_result(self, res):
        self._busy = False
        self.gen_btn.text = "生成图片"
        if res.get("error"):
            self.show_error(res["error"])
            return
        path = res.get("path")
        if path and os.path.isfile(path):
            self.result_img.source = path
            self.save_btn.height = dp(42)
            self._has_new = True
            self.app.set_status("图片生成成功")
        else:
            self.show_error("生成失败：未取得图片")

    def _save(self):
        if not self._has_new or not self.result_img.source:
            return
        out_dir = os.path.join(DATA_DIR, "images")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            pass
        out = os.path.join(out_dir, "gen_" + time.strftime("%Y%m%d_%H%M%S") + ".png")
        try:
            with open(self.result_img.source, "rb") as f:
                data = f.read()
            with open(out, "wb") as f:
                f.write(data)
            self.app.set_status("已保存：" + out)
            self.save_btn.text = "已保存 \u2713"
            Clock.schedule_once(lambda dt: setattr(self.save_btn, "text", "保存图片"), 2.0)
        except Exception as e:
            self.show_error("保存失败：" + str(e))

    def show_error(self, msg):
        self.err_bar.text = msg
        self.err_bar.height = dp(36)
        self.err_bar.opacity = 1
        Clock.unschedule(self._fade_out)
        Clock.schedule_once(self._fade_out, 3.0)

    def _fade_out(self, *a):
        Animation(opacity=0, duration=0.3).start(self.err_bar)
        Clock.schedule_once(lambda dt: setattr(self.err_bar, "height", 0), 0.32)


class _ConvItem(BoxLayout):
    """对话列表条目：点击切换，长按弹菜单（重命名/删除）。"""

    def __init__(self, app, popup, sid, **kw):
        super().__init__(**kw)
        self.app = app
        self.popup = popup
        self.sid = sid
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(58)
        self.padding = [dp(12), dp(6), dp(12), dp(6)]
        self.spacing = dp(8)
        self._down_t = None
        self._down_pos = None
        s = app.sessions.get("对话", {}).get(sid, {})
        left = BoxLayout(orientation="vertical", spacing=dp(2))
        name = Label(text=s.get("名称", "对话"), font_name=FONT_CN,
                     font_size=dp(14), bold=True, color=AI_TEXT,
                     halign="left", valign="middle", size_hint_y=None,
                     height=dp(24))
        name.bind(size=lambda *a: setattr(name, "text_size",
                                          (name.width, None)))
        left.add_widget(name)
        meta = Label(text=app._session_summary(s) + "  ·  " + app._fmt_ts(s.get("时间", 0)),
                     font_name=FONT_CN, font_size=dp(12), color=MUTED,
                     halign="left", valign="middle", size_hint_y=None,
                     height=dp(20))
        meta.bind(size=lambda *a: setattr(meta, "text_size",
                                          (meta.width, None)))
        left.add_widget(meta)
        self.add_widget(left)
        tag = Label(text="当前" if sid == app.current_session_id else "",
                    font_name=FONT_CN, font_size=dp(12), color=ACCENT_1,
                    size_hint=(None, None), size=(dp(44), dp(20)),
                    halign="right", valign="middle")
        self.add_widget(tag)
        with self.canvas.before:
            Color(*INPUT_BG)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=R12)
            Color(*INPUT_BORDER)
            self._bd = Line(rounded_rectangle=(self.x, self.y, self.width,
                                               self.height, 12, 12, 12, 12),
                            width=dp(1))
        self.bind(pos=self._repaint, size=self._repaint)

    def _repaint(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width,
                                      self.height, 12, 12, 12, 12)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._down_t = time.time()
            self._down_pos = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._down_t is None:
            return super().on_touch_up(touch)
        dt = time.time() - self._down_t
        try:
            moved = abs(touch.pos[0] - self._down_pos[0]) + \
                    abs(touch.pos[1] - self._down_pos[1])
        except Exception:
            moved = 0
        self._down_t = None
        if moved > 24:
            return True
        if dt >= 0.6:
            self.popup._open_item_menu(self.sid)
        else:
            self.popup._switch(self.sid)
        return True


class RenamePopup(Popup):
    """重命名对话弹窗。"""

    def __init__(self, app, sid, current, on_ok, **kw):
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(400), dp(230))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.55)
        self.auto_dismiss = False
        box = BoxLayout(orientation="vertical",
                        padding=[dp(18), dp(16), dp(18), dp(16)], spacing=dp(14))
        box.add_widget(Label(text="重命名对话", font_name=FONT_CN,
                             font_size=dp(16), bold=True, color=AI_TEXT,
                             halign="center", valign="middle",
                             size_hint_y=None, height=dp(30)))
        self.input = TextInput(text=current, multiline=False,
                               font_name=FONT_CN, font_size=dp(14),
                               foreground_color=AI_TEXT, cursor_color=ACCENT_1,
                               background_normal="", background_active="",
                               hint_text="输入新对话名", hint_text_color=PLACEHOLDER,
                               padding=[dp(12), dp(8)])
        with self.input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.input.pos, size=self.input.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.input.x, self.input.y,
                                    self.input.width, self.input.height,
                                    12, 12, 12, 12), width=dp(1))
        self.input.bind(pos=self._repaint_input, size=self._repaint_input)
        box.add_widget(self.input)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        ok = Button(text="确定", font_name=FONT_CN, font_size=dp(14),
                    color=(1, 1, 1, 1), background_normal="",
                    background_color=ACCENT_1, on_release=lambda b: self._ok())
        cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(14),
                        color=AI_TEXT, background_normal="",
                        background_color=TOP_2,
                        on_release=lambda b: self.dismiss())
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        self.add_widget(box)
        self._on_ok = on_ok

    def _repaint_input(self, *a):
        self.input.canvas.before.clear()
        with self.input.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.input.pos, size=self.input.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.input.x, self.input.y,
                                    self.input.width, self.input.height,
                                    12, 12, 12, 12), width=dp(1))

    def _ok(self):
        name = self.input.text.strip()
        if name:
            self._on_ok(name)
            self.dismiss()


class ConversationListPopup(Popup):
    """对话列表弹窗：按角色分组显示；点击切换、长按重命名/删除。"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(540), dp(640))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.62)
        self.auto_dismiss = False
        root = BoxLayout(orientation="vertical",
                         padding=[dp(16), dp(12), dp(16), dp(12)], spacing=dp(8))
        head = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        head.add_widget(Label(text="对话列表", font_name=FONT_CN,
                              font_size=dp(17), bold=True, color=AI_TEXT,
                              halign="left", valign="middle", size_hint_x=1))
        close = Button(text="\u2715", size_hint=(None, None),
                       size=(dp(34), dp(34)), font_name="SegoeSym",
                       font_size=dp(18), color=CLOSE_ICON,
                       background_normal="", background_color=(0, 0, 0, 0),
                       on_release=lambda b: self.dismiss())
        head.add_widget(close)
        root.add_widget(head)
        hint = Label(text="点击切换对话 · 长按可重命名 / 删除",
                     font_name=FONT_CN, font_size=dp(12), color=MUTED,
                     halign="left", valign="middle", size_hint_y=None,
                     height=dp(20))
        root.add_widget(hint)
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                                 bar_width=dp(4),
                                 bar_color=(0.35, 0.35, 0.4, 0.55),
                                 bar_inactive_color=(0.35, 0.35, 0.4, 0.2),
                                 scroll_type=["bars", "content"])
        with self.scroll.canvas.before:
            Color(*BG_1)
            self._bg = RoundedRectangle(pos=self.scroll.pos,
                                        size=self.scroll.size, radius=R14)
            Color(*INPUT_BORDER)
            self._bd = Line(rounded_rectangle=(self.scroll.x, self.scroll.y,
                                               self.scroll.width,
                                               self.scroll.height,
                                               14, 14, 14, 14), width=dp(1))
        self.scroll.bind(pos=self._repaint, size=self._repaint)
        self.body = BoxLayout(orientation="vertical", size_hint_y=None,
                              padding=[dp(6), dp(6), dp(6), dp(6)], spacing=dp(6))
        self.body.bind(minimum_height=self.body.setter("height"))
        self.scroll.add_widget(self.body)
        root.add_widget(self.scroll)
        self.add_widget(root)
        self._refresh()

    def _repaint(self, *a):
        self._bg.pos = self.scroll.pos
        self._bg.size = self.scroll.size
        self._bd.rounded_rectangle = (self.scroll.x, self.scroll.y,
                                      self.scroll.width, self.scroll.height,
                                      14, 14, 14, 14)

    def _refresh(self):
        self.body.clear_widgets()
        conv = self.app.sessions.get("对话", {})
        personas = list(self.app.personas.keys())
        seen = []
        for p in personas:
            if any(s.get("角色") == p for s in conv.values()):
                seen.append(p)
        for p in personas:
            if p not in seen:
                seen.append(p)
        for p in seen:
            items = [sid for sid, s in conv.items() if s.get("角色") == p]
            if not items:
                continue
            g = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(2), padding=[dp(2), dp(2), dp(2), dp(2)])
            g.bind(minimum_height=g.setter("height"))
            tl = Label(text=p, font_name=FONT_CN, font_size=dp(14),
                       bold=True, color=ACCENT_1, halign="left",
                       valign="middle", size_hint_y=None, height=dp(24),
                       padding=[dp(6), 0])
            g.add_widget(tl)
            for sid in items:
                g.add_widget(_ConvItem(self.app, self, sid))
            self.body.add_widget(g)

    def _switch(self, sid):
        if sid == self.app.current_session_id:
            self.dismiss()
            return
        self.app._switch_session(sid)
        self.set_status_hint("已切换到对话")
        self.dismiss()

    def set_status_hint(self, text):
        try:
            self.app.set_status(text)
        except Exception:
            pass

    def _open_item_menu(self, sid):
        s = self.app.sessions.get("对话", {}).get(sid, {})
        name = s.get("名称", "对话")
        p = Popup(title="", size_hint=(None, None), size=(dp(360), dp(250)),
                  background="", background_color=(0, 0, 0, 0),
                  overlay_color=(0, 0, 0, 0.55), auto_dismiss=True)
        box = BoxLayout(orientation="vertical",
                        padding=[dp(18), dp(16), dp(18), dp(16)], spacing=dp(12))
        box.add_widget(Label(text=name, font_name=FONT_CN, font_size=dp(15),
                             bold=True, color=AI_TEXT, halign="center",
                             valign="middle", size_hint_y=None, height=dp(30)))
        btn_ren = Button(text="重命名", font_name=FONT_CN, font_size=dp(14),
                         color=AI_TEXT, background_normal="",
                         background_color=TOP_2, size_hint_y=None, height=dp(40),
                         on_release=lambda b: self._open_rename(p, sid))
        btn_del = Button(text="删除对话", font_name=FONT_CN, font_size=dp(14),
                         color=(1, 1, 1, 1), background_normal="",
                         background_color=(0.62, 0.24, 0.24, 1),
                         size_hint_y=None, height=dp(40),
                         on_release=lambda b: self._confirm_delete(p, sid))
        btn_cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(14),
                            color=MUTED, background_normal="",
                            background_color=(0.13, 0.17, 0.26, 1),
                            size_hint_y=None, height=dp(36),
                            on_release=lambda b: p.dismiss())
        box.add_widget(btn_ren)
        box.add_widget(btn_del)
        box.add_widget(btn_cancel)
        p.add_widget(box)
        p.open()

    def _open_rename(self, menu, sid):
        menu.dismiss()
        s = self.app.sessions.get("对话", {}).get(sid, {})

        def _ok(name):
            self.app.rename_session(sid, name)
            self._refresh()
            self.set_status_hint("已重命名对话")

        RenamePopup(self.app, sid, s.get("名称", ""), _ok).open()

    def _confirm_delete(self, menu, sid):
        menu.dismiss()
        p = Popup(title="", size_hint=(None, None), size=(dp(360), dp(200)),
                  background="", background_color=(0, 0, 0, 0),
                  overlay_color=(0, 0, 0, 0.55), auto_dismiss=True)
        box = BoxLayout(orientation="vertical",
                        padding=[dp(18), dp(16), dp(18), dp(16)], spacing=dp(14))
        box.add_widget(Label(text="确定删除该对话吗？删除后不可恢复。",
                             font_name=FONT_CN, font_size=dp(14),
                             color=AI_TEXT, halign="center", valign="middle",
                             size_hint_y=None, height=dp(40)))
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        ok = Button(text="确定删除", font_name=FONT_CN, font_size=dp(14),
                    color=(1, 1, 1, 1), background_normal="",
                    background_color=(0.8, 0.3, 0.3, 1),
                    on_release=lambda b: self._do_delete(p, sid))
        cancel = Button(text="取消", font_name=FONT_CN, font_size=dp(14),
                        color=AI_TEXT, background_normal="",
                        background_color=TOP_2, on_release=lambda b: p.dismiss())
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        p.add_widget(box)
        p.open()

    def _do_delete(self, confirm, sid):
        confirm.dismiss()
        self.app.delete_session(sid)
        self._refresh()
        self.set_status_hint("对话已删除")


class BackendImageGenPopup(Popup):
    """后台生图：输入描述 → 点击生成 → 弹窗关闭，生图在后台进行，
    期间可继续与 AI 对话；完成后图片自动插入消息区。"""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.title = ""
        self.size_hint = (None, None)
        self.size = (dp(460), dp(300))
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.62)
        self.auto_dismiss = True

        box = BoxLayout(orientation="vertical",
                        padding=[dp(18), dp(16), dp(18), dp(16)], spacing=dp(12))

        head = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(10))
        head.add_widget(Label(text="AI 生图（后台运行）", font_name=FONT_CN,
                              font_size=dp(16), bold=True, color=AI_TEXT,
                              halign="left", valign="middle", size_hint_x=1))
        close = Button(text="\u2715", size_hint=(None, None), size=(dp(30), dp(30)),
                       font_name="SegoeSym", font_size=dp(16), color=CLOSE_ICON,
                       background_normal="", background_color=(0, 0, 0, 0),
                       on_release=lambda b: self.dismiss())
        head.add_widget(close)
        box.add_widget(head)

        box.add_widget(Label(text="图片会在后台生成，不耽误你继续聊天。",
                             font_name=FONT_CN, font_size=dp(12),
                             color=MUTED, halign="left", valign="middle",
                             size_hint_y=None, height=dp(20)))

        self.prompt = TextInput(
            text="", multiline=True, size_hint_y=None, height=dp(100),
            font_name=FONT_CN, font_size=dp(14),
            hint_text="描述你想生成的画面，例如：赛博朋克风格的鲸鱼娘…",
            hint_text_color=PLACEHOLDER, foreground_color=AI_TEXT,
            cursor_color=ACCENT_1, background_normal="", background_active="")
        with self.prompt.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.prompt.pos, size=self.prompt.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.prompt.x, self.prompt.y,
                                    self.prompt.width, self.prompt.height,
                                    12, 12, 12, 12), width=dp(1))
        self.prompt.bind(pos=self._repaint_prompt)
        box.add_widget(self.prompt)

        gen = Button(text="开始生成（后台）", size_hint_y=None, height=dp(44),
                     font_name=FONT_CN, font_size=dp(15), bold=True,
                     color=(1, 1, 1, 1), background_normal="",
                     background_color=(0, 0, 0, 0),
                     on_release=lambda b: self._go())
        with gen.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=gen.pos, size=gen.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))
        gen.bind(pos=self._repaint_gen, size=self._repaint_gen)
        box.add_widget(gen)

        self._gen = gen
        self.add_widget(box)

    def _repaint_prompt(self, *a):
        self.prompt.canvas.before.clear()
        with self.prompt.canvas.before:
            Color(*INPUT_BG)
            RoundedRectangle(pos=self.prompt.pos, size=self.prompt.size, radius=R12)
            Color(*INPUT_BORDER)
            Line(rounded_rectangle=(self.prompt.x, self.prompt.y,
                                    self.prompt.width, self.prompt.height,
                                    12, 12, 12, 12), width=dp(1))

    def _repaint_gen(self, *a):
        self._gen.canvas.before.clear()
        with self._gen.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self._gen.pos, size=self._gen.size, radius=R12,
                             texture=make_linear_texture(ACCENT_1, ACCENT_2))

    def _go(self):
        prompt = (self.prompt.text or "").strip()
        if not prompt:
            self.prompt.hint_text_color = NOTICE_RED
            return
        self.app.start_background_image_gen(prompt, popup=self)


class DeepSeekVoiceApp(App):
    title = "DeepSeek 语音助手"

    def build(self):
        Window.clearcolor = BG_2
        # 【关键修复】安卓上 SDL2 窗口由系统管理，赋值 Window.size 会导致
        # 启动即崩溃（窗口 resize 请求系统不支持）。仅桌面环境设置。
        if not IS_ANDROID:
            try:
                Window.size = (1100, 760)
            except Exception:
                pass
        self.cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        if not os.path.exists(CONFIG_FILE):
            save_json(CONFIG_FILE, self.cfg)
        self.personas = load_json(PERSONA_FILE, DEFAULT_PERSONAS)
        self.current_persona = self.cfg.get("persona", "龙族三人格")
        if self.current_persona not in self.personas:
            self.current_persona = list(self.personas.keys())[0]
        self.sessions = self._load_sessions()
        self.records = []
        self.busy = False
        self.tts = AndroidTTS(self)
        # 实时打断：置位后后台流式线程会尽快退出
        self._cancel_evt = threading.Event()

        root = Background()
        layout = BoxLayout(orientation="vertical")
        root.add_widget(layout)

        self.topbar = TopBar(self)
        layout.add_widget(self.topbar)

        main_row = BoxLayout(orientation="horizontal", spacing=dp(4))
        self.avatar = AvatarCard(self)
        main_row.add_widget(self.avatar)
        self.chat = ChatArea(self)
        main_row.add_widget(self.chat)
        layout.add_widget(main_row)

        self.status_lbl = Label(text="就绪", font_name=FONT_CN,
                                font_size=dp(12), color=MUTED, halign="left",
                                size_hint_y=None, height=dp(20),
                                padding=[dp(18), 0])
        layout.add_widget(self.status_lbl)

        self.inputbar = InputBar(self)
        layout.add_widget(self.inputbar)

        self._init_sessions()
        self._load_messages_into_chat()
        self.chat.check_guide()
        self._handle_args()
        return root

    # ---------- 命令行辅助（截图用；未知参数会被 Kivy 拦截，故用环境变量开关） ----------
    def _handle_args(self):
        args = sys.argv[1:]
        print("ARGS_DEBUG", sys.argv, flush=True)
        env_open = os.environ.get("DSV_OPEN_SETTINGS") == "1"
        env_shot = os.environ.get("DSV_SCREENSHOT", "")
        if env_open:
            Clock.schedule_once(lambda dt: self.open_settings(), 2.2)
        if env_shot:
            Clock.schedule_once(lambda dt: self._do_screenshot(env_shot), 4.5)
        if "--persona" in args:
            i = args.index("--persona")
            if i + 1 < len(args):
                Clock.schedule_once(
                    lambda dt: self.switch_persona(args[i + 1]), 0.6)
        if "--drag" in args:
            i = args.index("--drag")
            if i + 1 < len(args):
                xy = args[i + 1].split(",")
                try:
                    dx, dy = float(xy[0]), float(xy[1])
                except Exception:
                    dx = dy = 0.0
                Clock.schedule_once(
                    lambda dt: self.avatar.set_dragged_pos(dx, dy), 1.2)
        if "--demo" in args:
            Clock.schedule_once(lambda dt: self._demo(), 1.5)
        if "--open-settings" in args:
            print("SETTINGS_ARG_HIT", flush=True)
            i = args.index("--open-settings")
            Clock.schedule_once(lambda dt: self.open_settings(), 2.2)
        if "--screenshot" in args:
            i = args.index("--screenshot")
            if i + 1 < len(args):
                Clock.schedule_once(
                    lambda dt: self._do_screenshot(args[i + 1]), 4.5)

    def _do_screenshot(self, path):
        try:
            Window.raise_window()
        except Exception:
            pass
        Clock.schedule_once(lambda dt: self._shot_now(path), 0.8)

    def _shot_now(self, path):
        ok = False
        try:
            try:
                Window.raise_window()
            except Exception:
                pass
            Clock.schedule_once(lambda dt: self._shot_now2(path), 2.0)
            return
        except Exception as e:
            print("SCREENSHOT_ERR", repr(e))

    def _shot_now2(self, path):
        ok = False
        try:
            try:
                Window.flip()
            except Exception:
                pass
            ok = Window.screenshot(path)
        except Exception as e:
            print("SCREENSHOT_ERR", repr(e))
        print("SCREENSHOT_RET", ok, os.path.exists(path))
        Clock.schedule_once(lambda dt: self.stop(), 0.5)

    def _demo(self):
        self.switch_persona("DeepSeek 鲸鱼娘")
        self.chat.check_guide()
        Clock.schedule_once(lambda dt: self.chat.add_message(
            "user", "你好呀，今天能陪我聊聊天吗？"), 0.8)
        Clock.schedule_once(lambda dt: self.chat.add_message(
            "ai", FAKE_REPLIES.get("DeepSeek 鲸鱼娘", "嗨～")), 1.4)
        Clock.schedule_once(lambda dt: self.chat.add_message(
            "ai",
            "用户酱～给你讲个长长的故事验证一下气泡高度！"
            "气泡的高度会跟着文字数量动态变化，文字多的时候气泡就变高，"
            "文字少的时候气泡就变矮，绝对不会出现文字溢出气泡、"
            "或者气泡里留一大片空白的问题。你看这一大段文字是不是整整齐齐"
            "地被气泡完整包住了？尾巴也好好地待在气泡左下角，"
            "这段文字已经足够长，足够用来验证多行换行时的显示效果了，"
            "希望它能完整显示而不被截断。"), 1.8)

        def _speak_demo(*a):
            self.avatar.set_speaking(True)
            self.set_status("演示模式：说话中，立绘正在浮动")

        Clock.schedule_once(_speak_demo, 2.6)
        Clock.schedule_once(lambda dt: self.set_status("演示模式：假数据回复"), 3.2)

    # ---------- 状态 ----------
    def set_status(self, text):
        self.status_lbl.text = text

    # ---------- 多会话（sessions.json 持久化） ----------
    @staticmethod
    def _new_session_id():
        return "s_" + ("%x" % int(time.time() * 1000)) + "_" + ("%x" % abs(id(object())))[-4:]

    @staticmethod
    def _fmt_ts(ts):
        try:
            t = time.localtime(float(ts))
            now = time.localtime()
            if (t.tm_year, t.tm_mon, t.tm_mday) == (now.tm_year, now.tm_mon, now.tm_mday):
                return "%02d:%02d" % (t.tm_hour, t.tm_min)
            if t.tm_year == now.tm_year:
                return "%02d-%02d" % (t.tm_mon, t.tm_mday)
            return "%04d-%02d" % (t.tm_year, t.tm_mon)
        except Exception:
            return ""

    def _load_sessions(self):
        empty = {"当前角色": self.current_persona,
                 "当前对话": "",
                 "对话": {}}
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("对话"), dict):
                    conv = data["对话"]
                    for sid, s in list(conv.items()):
                        if not isinstance(s, dict):
                            conv.pop(sid, None)
                            continue
                        s.setdefault("角色", self.current_persona)
                        s.setdefault("名称", "对话 1")
                        s.setdefault("时间", time.time())
                        if not isinstance(s.get("消息"), list):
                            s["消息"] = []
                    data.setdefault("当前角色", self.current_persona)
                    data.setdefault("当前对话", "")
                    return data
            except Exception:
                pass
        return empty

    def _save_sessions(self):
        try:
            self.sessions["当前角色"] = self.current_persona
            self.sessions["当前对话"] = self.current_session_id
        except Exception:
            pass
        save_json(SESSION_FILE, self.sessions)

    def _default_session_name(self, persona):
        n = 1
        for s in self.sessions.get("对话", {}).values():
            if s.get("角色") == persona:
                try:
                    n += 1
                except Exception:
                    pass
        return "对话 %d" % n

    def _new_session(self, persona, name=None):
        sid = self._new_session_id()
        while sid in self.sessions.get("对话", {}):
            sid = self._new_session_id()
        self.sessions.setdefault("对话", {})[sid] = {
            "角色": persona,
            "名称": name or self._default_session_name(persona),
            "时间": time.time(),
            "消息": [],
        }
        return sid

    def _ensure_persona_session(self, persona):
        for s in self.sessions.get("对话", {}).values():
            if s.get("角色") == persona:
                return True
        self._new_session(persona)
        return True

    def _select_session_for_persona(self, persona):
        best = None
        best_ts = -1
        for sid, s in self.sessions.get("对话", {}).items():
            if s.get("角色") != persona:
                continue
            try:
                ts = float(s.get("时间", 0))
            except Exception:
                ts = 0
            if ts >= best_ts:
                best, best_ts = sid, ts
        return best

    def _init_sessions(self):
        self.sessions = self._load_sessions()
        self._ensure_persona_session(self.current_persona)
        cur = self.sessions.get("当前对话", "")
        cur_ok = bool(cur and cur in self.sessions.get("对话", {}) and
                      self.sessions["对话"][cur].get("角色") == self.current_persona)
        if not cur_ok:
            cur = self._select_session_for_persona(self.current_persona) or \
                  self._new_session(self.current_persona)
        self.current_session_id = cur
        self.records = self.sessions["对话"][cur].get("消息", [])
        self._save_sessions()

    def _switch_session(self, sid, save=True):
        conv = self.sessions.get("对话", {})
        if sid not in conv:
            return
        self.current_session_id = sid
        self.records = conv[sid].get("消息", [])
        self._load_messages_into_chat()
        if save:
            self._save_sessions()

    def _load_messages_into_chat(self):
        try:
            self.chat.clear_messages()
        except Exception:
            return
        for m in list(self.records):
            try:
                self.chat.add_message(m.get("role", "user"), m.get("content", ""))
            except Exception:
                continue
        try:
            Clock.schedule_once(self.chat.scroll_to_bottom, 0.05)
        except Exception:
            pass

    def _touch_session(self):
        try:
            s = self.sessions.get("对话", {}).get(self.current_session_id)
            if s is not None:
                s["时间"] = time.time()
            self._save_sessions()
        except Exception:
            pass

    def _check_long_chat(self):
        try:
            if len(self.records) >= 500:
                self.set_status("对话过长，建议新建对话")
        except Exception:
            pass

    def create_conversation(self):
        """顶栏＋：为当前角色创建新对话并立即切换（空对话直接开聊）。"""
        sid = self._new_session(self.current_persona)
        self._switch_session(sid)
        self._save_sessions()
        self.set_status("已创建新对话：" +
                        self.sessions["对话"][sid].get("名称", ""))

    def open_conversation_list(self):
        ConversationListPopup(self).open()

    def delete_session(self, sid):
        conv = self.sessions.get("对话", {})
        if sid not in conv:
            return
        removed = conv.pop(sid, None)
        was_current = (sid == self.current_session_id)
        self._save_sessions()
        if not was_current:
            return
        # 当前对话被删：切到同角色另一个（时间最新），没有就自动建空的
        nxt = self._select_session_for_persona(self.current_persona)
        if nxt is None:
            nxt = self._new_session(self.current_persona)
        self._switch_session(nxt)
        self.set_status("已删除对话，当前对话已切换")

    def rename_session(self, sid, name):
        conv = self.sessions.get("对话", {})
        if sid not in conv:
            return
        name = (name or "").strip()
        if not name:
            return
        conv[sid]["名称"] = name
        self._save_sessions()

    @staticmethod
    def _session_summary(s):
        msgs = s.get("消息") or []
        if not msgs:
            return "（空对话）"
        last = msgs[-1]
        text = last.get("content", "") if isinstance(last, dict) else str(last)
        text = text.replace("\n", " ").strip()
        return text if len(text) <= 22 else text[:22] + "…"

    # ---------- 人设 ----------
    def on_persona_selected(self, spinner, text):
        self.switch_persona(text)

    def switch_persona(self, name):
        if name not in self.personas:
            return
        self.current_persona = name
        self.cfg["persona"] = name
        save_json(CONFIG_FILE, self.cfg)
        self._ensure_persona_session(name)
        sid = self._select_session_for_persona(name)
        self._switch_session(sid)
        self.refresh_persona_ui()
        self.set_status("已切换到人设：" + name)

    def refresh_persona_ui(self):
        self.topbar.persona_spinner.text = self.current_persona
        # 立绘淡出 -> 换图 -> 淡入
        img = self.avatar.img
        Animation(opacity=0, duration=0.15).start(img)

        def _do(dt):
            self.avatar.refresh(self.current_persona)
            Animation(opacity=1, duration=0.15).start(img)

        Clock.schedule_once(_do, 0.16)

    # ---------- 聊天（真实 DeepSeek 流式对话） ----------
    def _set_busy(self, on, status=None):
        """统一的忙碌态切换：锁定输入区按钮 + 显隐打断按钮 + 状态文字。"""
        self.busy = bool(on)
        try:
            self.inputbar.set_locked(bool(on))
        except Exception:
            pass
        if status:
            self.set_status(status)

    def on_send(self):
        msg = self.inputbar.entry.text.strip()
        img_path = self.inputbar.attachment
        if (not msg and not img_path) or self.busy:
            return
        key = (self.cfg.get("api_key") or "").strip()
        if not key.startswith("sk-"):
            self.chat.show_guide()
            self.set_status("请先填 DeepSeek API Key")
            return
        self.inputbar.entry.text = ""
        self.inputbar.clear_attachment()
        self.chat.add_message("user", msg, img_path=img_path)
        self.records.append({"role": "user",
                             "content": msg + (" [图片]" if img_path else "")})
        self._touch_session()
        self._check_long_chat()
        self._cancel_evt.clear()
        self._set_busy(True, "识别图片中…" if img_path else "思考中…")
        if img_path:
            threading.Thread(target=self._vision_ask,
                             args=(msg, img_path), daemon=True).start()
        else:
            threading.Thread(target=self._stream_ask, args=(msg,), daemon=True).start()

    def on_interrupt(self):
        """实时打断：停止 AI 流式输出 + 停止 TTS 朗读。"""
        if not self.busy:
            return
        self._cancel_evt.set()
        try:
            self.tts.stop()
        except Exception:
            pass
        try:
            self.avatar.set_speaking(False)
        except Exception:
            pass
        self._set_busy(False, "已打断")

    def _vision_ask(self, msg, img_path):
        """后台线程：发图走视觉模型识别链路。
        UI 操作（add_message 创建气泡、update_text、完成/错误回调）全部经
        Clock.schedule_once 回主线程执行；后台线程仅做网络请求。"""
        acc = []

        def _start(dt):
            # 主线程：创建 AI 气泡（Kivy 仅主线程可创建 Widget）
            row = self.chat.add_message("ai", "")

            def on_delta(delta):
                acc.append(delta)
                Clock.schedule_once(lambda dt: row.update_text("".join(acc)), 0)

            def on_done(text):
                final = "".join(acc) or text or "（无法识别图片内容）"
                Clock.schedule_once(
                    lambda dt: self._on_reply_done(row, final), 0)

            def _work():
                client = VisionClient(self.cfg.get("vision_api_key") or "")
                try:
                    client.ask(msg or "请描述这张图片的内容", img_path,
                               on_delta, on_done)
                except Exception as exc:
                    err = friendly_error(exc)
                    Clock.schedule_once(
                        lambda dt: self._on_reply_error(row, err), 0)

            threading.Thread(target=_work, daemon=True).start()

        Clock.schedule_once(_start, 0)

    def _stream_ask(self, msg):
        """后台线程：构造历史 -> DeepSeek 流式请求 -> 线程安全回调 UI。
        UI 操作（add_message 创建气泡、update_text、set_status_text、完成/错误回调）
        全部经 Clock.schedule_once 回主线程执行；后台线程仅做网络请求。"""
        persona = self.personas.get(self.current_persona) or ""
        system_prompt = (persona + "\n" + SEARCH_PROMPT_SUFFIX).strip()
        history = [{"role": "system", "content": system_prompt}]
        for m in self.records[:-1]:
            history.append({"role": "user" if m.get("role") == "user" else "assistant",
                            "content": m.get("content", "")})
        history.append({"role": "user", "content": msg})

        search_key = (self.cfg.get("search_api_key") or "").strip()
        search_on = bool(self.cfg.get("search_enabled", False)) and bool(search_key)
        searcher = WebSearch(search_key) if search_on else None
        acc = []

        def _start(dt):
            # 主线程：创建 AI 气泡（Kivy 仅主线程可创建 Widget）
            row = self.chat.add_message("ai", "")

            def on_delta(delta):
                # 流式增量：打字机效果
                acc.append(delta)
                Clock.schedule_once(
                    lambda dt: row.update_text("".join(acc)), 0)

            def on_status(st):
                if st == "searching":
                    Clock.schedule_once(
                        lambda dt: row.set_status_text("正在联网搜索…"), 0)
                elif st == "searched":
                    Clock.schedule_once(
                        lambda dt: row.set_status_text("已联网搜索"), 0)

            def on_done(text):
                Clock.schedule_once(
                    lambda dt: self._on_reply_done(row, text), 0)

            def on_error(err):
                Clock.schedule_once(
                    lambda dt: self._on_reply_error(row, err), 0)

            def _work():
                client = DeepSeekClient(self.cfg.get("api_key") or "")
                try:
                    client.chat(history, on_delta, on_status, on_done, on_error,
                                web_search=searcher, search_enabled=search_on,
                                cancel_event=self._cancel_evt)
                except Exception as e:
                    on_error(str(e))

            threading.Thread(target=_work, daemon=True).start()

        Clock.schedule_once(_start, 0)

    def _on_reply_done(self, row, text):
        final = "".join(text) if text else "（无回复）"
        if self._cancel_evt.is_set() and not final.strip():
            final = "（已打断）"
        row.update_text(final)
        self.records.append({"role": "ai", "content": final})
        self._touch_session()
        self._check_long_chat()
        self._set_busy(False, "就绪")
        if self.cfg.get("speak_on_reply", True) and not self._cancel_evt.is_set():
            self.speak(final, row)

    def _on_reply_error(self, row, err):
        msg = "请求失败：" + (friendly_error(err) if isinstance(err, Exception) else str(err))
        row.update_text(msg)
        self.records.append({"role": "ai", "content": msg})
        self._touch_session()
        self._check_long_chat()
        self._set_busy(False, "请求失败，请检查 Key 或网络")

    def speak(self, text, row=None):
        """朗读：安卓原生 TTS；Windows 上为演示浮动（无真实发声）"""
        if not text:
            return
        if row is not None:
            row.set_status_text("正在朗读…")
        est = max(1.5, min(20.0, len(text) / 3.0))

        def _clear(*a):
            self.avatar.set_speaking(False)
            if row is not None:
                row.set_status_text("")
            self.set_status("就绪")

        if self.tts.available:
            self.tts.speak(text)
            self.set_status("正在朗读…")
            Clock.schedule_once(_clear, est)
        else:
            self.avatar.set_speaking(True)
            self.set_status("正在朗读…（Windows 演示，无真实发声）")
            Clock.schedule_once(_clear, est)

    # ---------- 语音输入（麦克风按钮） ----------
    def start_voice_input(self):
        """安卓：调用系统语音识别，识别结果写入输入框。
        桌面 / 无 jnius 环境：给出提示，不影响使用。"""
        if platform.system() != "Linux" or "android" not in sys.platform.lower():
            pass  # 继续尝试 jnius（安卓 python-for-android 下 sys.platform 为 linux）
        try:
            from jnius import autoclass, PythonJavaClass, java_method
        except Exception:
            self.set_status("当前环境不支持语音输入（仅安卓可用）")
            return
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            activity = PythonActivity.mActivity

            class _Cb(PythonJavaClass):
                __javainterfaces__ = [
                    "org/kivy/android/PythonActivity$ActivityResultListener"]
                __javacontext__ = "app"

                @java_method("(IILandroid/content/Intent;)V")
                def onActivityResult(self, requestCode, resultCode, data):
                    try:
                        if resultCode != -1 or data is None:
                            return
                        results = data.getStringArrayListExtra(
                            RecognizerIntent.EXTRA_RESULTS)
                        if results and results.size() > 0:
                            text = results.get(0)
                            Clock.schedule_once(
                                lambda dt: self._fill_voice_text(text), 0)
                    except Exception as e:
                        print("VOICE_RESULT_ERR", repr(e))

            cb = _Cb()
            self._voice_cb = cb  # 防止被 GC
            activity.bindActivityResultListener(cb)
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "请说话…")
            activity.startActivityForResult(intent, 0x5A01)
            self.set_status("请说话…")
        except Exception as e:
            self.set_status("语音输入不可用：" + str(e)[:30])

    def _fill_voice_text(self, text):
        try:
            cur = self.inputbar.entry.text or ""
            self.inputbar.entry.text = (cur + text).strip()
            self.inputbar.entry.cursor = (len(self.inputbar.entry.text), 0)
            self.set_status("已写入语音内容")
        except Exception:
            pass

    # ---------- 生图：后台运行，不阻塞对话 ----------
    def open_image_gen(self):
        """弹出轻量生图输入框（输入描述 → 后台生成，期间可继续对话）。"""
        if not (self.cfg.get("image_api_key") or "").strip():
            self.set_status("请先配置图片生成 API Key")
            return
        BackendImageGenPopup(self).open()

    def start_background_image_gen(self, prompt, popup=None):
        """后台线程生图：立即返回，用户可继续聊天；完成后消息区插入图片。"""
        prompt = (prompt or "").strip()
        if not prompt:
            return
        if popup is not None:
            try:
                popup.dismiss()
            except Exception:
                pass
        self.set_status("正在后台生成图片：%s" % prompt[:14])

        def _start(dt):
            row = self.chat.add_message("ai", "（正在生成图片…）")
            row.update_text("根据描述生成图片：%s" % prompt)

            def _work():
                try:
                    results = {}
                    done = threading.Event()

                    def on_ok(data):
                        results["data"] = data
                        done.set()

                    client = ImageGenClient(self.cfg.get("image_api_key") or "")
                    client.generate(prompt, on_ok)
                    done.wait(timeout=120)
                    data = results.get("data") or {}
                    if data.get("error"):
                        Clock.schedule_once(
                            lambda dt: self._on_image_gen_error(row, data["error"]), 0)
                    else:
                        path = data.get("path") or data.get("file") or ""
                        Clock.schedule_once(
                            lambda dt: self._on_image_gen_ok(row, path), 0)
                except Exception as e:
                    err = friendly_error(e)
                    Clock.schedule_once(
                        lambda dt: self._on_image_gen_error(row, err), 0)

            threading.Thread(target=_work, daemon=True).start()

        Clock.schedule_once(_start, 0)

    def _on_image_gen_ok(self, row, path):
        if path and os.path.isfile(path):
            row.attach_image(path)
            row.update_text("图片已生成（已保存到相册目录）")
        else:
            row.update_text("图片已生成，但保存路径异常")
        self.set_status("图片生成完成")

    def _on_image_gen_error(self, row, err):
        row.update_text("生图失败：" + str(err))
        self.set_status("生图失败，请检查图片生成 Key 或网络")

    # ---------- 聊天发图 ----------
    def pick_chat_image(self):
        if not (self.cfg.get("vision_api_key") or "").strip():
            self.set_status("请先配置图像识别 API Key")
            return
        if not _HAS_PLYER:
            self.set_status("当前环境不支持文件选择器")
            return
        try:
            filechooser.open_file(
                filters=["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"],
                on_selection=self._on_pick_image)
        except Exception as e:
            self.set_status("打开文件选择器失败：" + str(e))

    def _on_pick_image(self, selection):
        path = selection[0] if selection else None
        if path:
            Clock.schedule_once(lambda dt: self.inputbar.set_attachment(path), 0)

    # ---------- 设置页 Key 测试 ----------
    def test_key_request(self, kind, key, label, btn, method, url, body):
        def _run():
            ok, msg = self._probe(key, method, url, body)
            Clock.schedule_once(
                lambda dt: self._finish_test(ok, msg, kind, key, label, btn), 0)
        threading.Thread(target=_run, daemon=True).start()

    def _probe(self, key, method, url, body):
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("Authorization", "Bearer " + key.strip())
            req.add_header("Content-Type", "application/json")
            if isinstance(body, str) and body:
                req.data = json.dumps({"content": body}).encode("utf-8")
            with urllib.request.urlopen(req, timeout=12) as resp:
                return True, "连接成功 (" + str(resp.status) + ")"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Key 无效 (401)"
            if e.code == 402:
                return False, "账户余额不足 (402)"
            if e.code == 429:
                return False, "请求过于频繁 (429)"
            return False, "HTTP " + str(e.code)
        except urllib.error.URLError as e:
            return False, "网络错误：" + str(e.reason)
        except Exception as e:
            return False, "连接失败：" + str(e)

    def _finish_test(self, ok, msg, kind, key, label, btn):
        if ok:
            self.cfg[kind] = key
            save_json(CONFIG_FILE, self.cfg)
            btn.text = "\u2713 " + msg
            self.set_status(label + " 测试通过，已保存")
        else:
            btn.text = "测试"
            self.set_status(label + " " + msg)
        Clock.schedule_once(lambda dt: setattr(btn, "text", "测试"), 2.0)

    # ---------- 设置 ----------
    def open_settings(self):
        SettingsPopup(self).open()

    def open_persona_editor(self):
        PersonaEditPopup(self).open()


# ==================== 全局异常捕获（Kivy ExceptionManager） ====================
try:
    from kivy.base import ExceptionHandler as _KivyExceptionHandler
    from kivy.base import ExceptionManager as _KivyExceptionManager
    _HAS_EXC_MGR = True
except Exception:
    _KivyExceptionHandler = object
    _KivyExceptionManager = None
    _HAS_EXC_MGR = False


LOG_DIR = os.path.join(DATA_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "Bug日志.txt")
LOG_MARK = os.path.join(LOG_DIR, ".bug_mark")
LOG_COOLDOWN = 7 * 24 * 3600


def _buglog_read():
    """读取 Bug日志；不存在或损坏时返回空 dict（自动重建，不崩）。"""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _buglog_write(data):
    """只写 Bug日志，不动隐藏标记（标记只在检测到删除时打，写入不刷新）。"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _buglog_mark_read():
    """读隐藏标记时间戳；无标记/损坏返回 None。"""
    try:
        with open(LOG_MARK, "r", encoding="utf-8") as f:
            return time.mktime(time.strptime(
                f.read().strip(), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _buglog_mark_write():
    try:
        with open(LOG_MARK, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass


def _buglog_mark_clear():
    try:
        os.remove(LOG_MARK)
    except Exception:
        pass


def _buglog_append(inst):
    """同类型+同位置只记 1 条，更新 [首次][最近][出现次数]。"""
    try:
        import traceback as _tb
        tb = getattr(inst, "__traceback__", None)
        loc = "?"
        if tb is not None:
            frames = _tb.extract_tb(tb)
            if frames:
                last = frames[-1]
                loc = "%s:%d" % (os.path.basename(last.filename), last.lineno)
        etype = type(inst).__name__
        key = "%s@%s" % (etype, loc)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        # 冷却：日志文件被删后 7 天内不重建
        # 标记只在"检测到文件不存在"时打一次；写入/启动都不动它；
        # 满 7 天后首次崩溃重建，并清除标记
        if not os.path.isfile(LOG_FILE):
            mark_ts = _buglog_mark_read()
            if mark_ts is None:
                _buglog_mark_write()  # 首次检测到删除 → 打标记，开始冷却
                return
            if (time.time() - mark_ts) < LOG_COOLDOWN:
                return  # 冷却期内，不生成
            _buglog_mark_clear()  # 冷却期满 → 清除标记并重建
        data = _buglog_read()
        if key in data:
            data[key]["count"] = int(data[key].get("count", 1)) + 1
            data[key]["recent"] = now
            data[key]["trace"] = "".join(_tb.format_exception(etype, inst, tb))
        else:
            data[key] = {
                "type": etype, "location": loc,
                "first": now, "recent": now, "count": 1,
                "trace": "".join(_tb.format_exception(etype, inst, tb)),
            }
        _buglog_write(data)
    except Exception:
        pass


class DSVExceptionHandler(_KivyExceptionHandler):
    """全局兜底：未处理异常打日志并吞掉，让 App 尽量不崩。"""

    def handle_exception(self, inst):
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        try:
            print("DSV_GLOBAL_EXC", repr(inst))
        except Exception:
            pass
        # bug 日志：异常写入 Bug日志.txt（按 类型+位置 去重，带冷却与自动重建）
        _buglog_append(inst)
        if _KivyExceptionManager is not None:
            return _KivyExceptionManager.PASS
        return True


def _install_exception_handler():
    if _KivyExceptionManager is not None:
        try:
            _KivyExceptionManager.add_handler(DSVExceptionHandler())
        except Exception:
            pass


def main():
    _install_exception_handler()
    DeepSeekVoiceApp().run()


if __name__ == "__main__":
    main()
