# -*- coding: utf-8 -*-
"""
DeepSeek 语音助手 —— 网页界面版（WebView）
================================================
与 Kivy 版的区别：只有「界面」换成了网页，功能全部沿用原实现。

保留（原封不动）：
  AndroidTTS      安卓原生语音播报
  WebSearch       联网搜索
  DeepSeekClient  DeepSeek 流式对话 + Function Calling
  VisionClient    图片理解
  ImageGenClient  图片生成

替换：
  Kivy 界面  ->  Android 原生 WebView + HTML/CSS/JS
"""

import os
import sys
import json
import threading
import time
import traceback
from datetime import datetime

# ============================================================
# 路径 & 早期日志
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_data_dir():
    for env in ("ANDROID_PRIVATE", "ANDROID_APP_PATH", "ANDROID_ARGUMENT"):
        p = os.environ.get(env)
        if p:
            try:
                if os.path.isdir(p):
                    return p
            except Exception:
                pass
    return BASE_DIR


DATA_DIR = _resolve_data_dir()
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = BASE_DIR

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
PERSONA_FILE = os.path.join(DATA_DIR, "personas.json")
CHAT_FILE = os.path.join(DATA_DIR, "chats.json")

LOG_FILE = os.path.join(DATA_DIR, "网页版_运行日志.txt")


def _log(msg):
    try:
        line = "[%s] %s\n" % (datetime.now().strftime("%m-%d %H:%M:%S"), msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print("[DSV]", msg)


def _log_everywhere(msg):
    """重要日志同时写到外部可读目录，方便手机上看。"""
    _log(msg)
    for d in ("/sdcard/Download", "/storage/emulated/0/Download"):
        try:
            with open(os.path.join(d, "网页版_启动日志.txt"),
                      "w", encoding="utf-8") as f:
                f.write(msg)
            break
        except Exception:
            continue


_log_everywhere("=== 网页版启动 ===")

# ============================================================
# 默认配置（沿用原实现）
# ============================================================
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
}

DEFAULT_PERSONAS = {
    "龙族三人格": "先结论后理由，三句话内说完。不用敬语、感叹号与 emoji。不知道就说不知道，不许编。",
    "DeepSeek 鲸鱼娘": "蓝色渐变长发、鲸鱼头鳍的傲娇天然呆娘。口语化、简短、偶尔撒娇。被叫胖要立刻反驳。",
    "简洁助手": "直接回答不寒暄，先结论后理由，默认三句话内说完，不用 emoji。",
    "自定义": "在这里写你自己的人设。",
}

VOICES = ["晓晓（女·温柔）", "晓伊（女·活泼）", "晓涵（女·沉稳）",
          "晓梦（女·自然）", "云希（男·自然）", "云扬（男·稳重）", "云健（男·阳光）"]


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


# ============================================================
# 载入抽出的功能类（643 行，原样复用）
# ============================================================
_log("载入功能模块…")
try:
    sys.path.insert(0, BASE_DIR)
    from dsv_core import (AndroidTTS, WebSearch, DeepSeekClient,
                          VisionClient, ImageGenClient)
    _log("功能模块载入成功")
except Exception:
    _log_everywhere("功能模块载入失败:\n" + traceback.format_exc())
    raise

from bridge import WebUIController

# ============================================================
# 后端：把功能类接到网页
# ============================================================
class WebBackend(object):
    """网页调用的所有动作都在这里实现。"""

    def __init__(self, ui):
        self.ui = ui
        self.cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        self.personas = load_json(PERSONA_FILE, DEFAULT_PERSONAS)
        if not os.path.exists(CONFIG_FILE):
            save_json(CONFIG_FILE, self.cfg)

        # 消息历史
        self.messages = []
        self.cancel_event = None
        self.busy = False
        self.tts = AndroidTTS(self)
        _log("后端就绪")

    # ---------- 设置 ----------
    def get_settings(self):
        return {
            "api_key": self.cfg.get("api_key", ""),
            "search_api_key": self.cfg.get("search_api_key", ""),
            "vision_api_key": self.cfg.get("vision_api_key", ""),
            "image_api_key": self.cfg.get("image_api_key", ""),
            "voice": self.cfg.get("voice", VOICES[0]),
            "voices": VOICES,
            "persona": self.cfg.get("persona", "龙族三人格"),
            "personas": list(self.personas.keys()),
            "speak_on_reply": bool(self.cfg.get("speak_on_reply", True)),
            "search_enabled": bool(self.cfg.get("search_enabled", True)),
            "tts_available": self.tts.available() if self.tts else False,
        }

    def on_save_settings(self, d):
        try:
            for k in ("api_key", "search_api_key", "vision_api_key",
                      "image_api_key", "voice", "persona"):
                if k in d and d[k] is not None:
                    self.cfg[k] = d[k]
            for k in ("speak_on_reply", "search_enabled", "show_avatar"):
                if k in d:
                    self.cfg[k] = bool(d[k])
            save_json(CONFIG_FILE, self.cfg)
            _log("设置已保存")
        except Exception:
            _log("保存设置出错:\n" + traceback.format_exc())

    def get_conversations(self):
        try:
            if os.path.exists(CHAT_FILE):
                with open(CHAT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def on_clear_chat(self):
        self.messages = []
        _log("对话已清空")

    # ---------- 发送消息（核心） ----------
    def on_send(self, text):
        if self.busy:
            self.ui.toast("正在回答中，请先打断")
            return
        if not text or not text.strip():
            return

        key = (self.cfg.get("api_key") or "").strip()
        if not key:
            self.ui.toast("还没有填 API Key，请到设置里填")
            self.ui.ai_done({})
            return

        self.busy = True
        self.cancel_event = threading.Event()

        persona = self.cfg.get("persona", "龙族三人格")
        sys_prompt = self.personas.get(persona) or DEFAULT_PERSONAS["简洁助手"]

        self.messages.append({"role": "user", "content": text})

        payload = [{"role": "system", "content": sys_prompt}] + self.messages
        client = DeepSeekClient(key)
        search = None
        if self.cfg.get("search_enabled", True):
            skey = (self.cfg.get("search_api_key") or "").strip()
            search = WebSearch(skey)

        acc = []

        def on_delta(t):
            if not t:
                return
            acc.append(t)
            self.ui.ai_chunk(t)

        def on_status(s):
            if s == "searching":
                self.ui.status("busy", "正在搜索…")
            elif s == "searched":
                self.ui.status("busy", "思考中…")

        def on_done(full):
            self.busy = False
            if full:
                self.messages.append({"role": "assistant", "content": full})
            self.ui.ai_done({})
            self.ui.status("idle", "DeepSeek")
            # 语音播报
            if full and self.cfg.get("speak_on_reply", True) and self.tts:
                try:
                    self.tts.speak(full)
                except Exception:
                    _log("TTS 出错:\n" + traceback.format_exc())

        def on_error(msg):
            self.busy = False
            self.ui.ai_chunk(u"[出错] " + str(msg))
            self.ui.ai_done({})
            self.ui.status("err", "出错")

        def run():
            try:
                client.chat(
                    payload, on_delta, on_status, on_done, on_error,
                    web_search=search,
                    search_enabled=self.cfg.get("search_enabled", True),
                    cancel_event=self.cancel_event)
            except Exception:
                on_error(traceback.format_exc())

        threading.Thread(target=run, daemon=True).start()

    def on_interrupt(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
        if self.tts:
            try:
                self.tts.stop()
            except Exception:
                pass
        self.busy = False
        self.ui.toast("已打断")

    # ---------- 录音（占位，后续接语音识别） ----------
    def on_start_record(self):
        self.ui.rec_start()
        self.ui.toast("录音功能待接入")

    def on_stop_record(self):
        self.ui.rec_stop()


# ============================================================
# 界面 HTML（读取同目录的 index.html）
# ============================================================
def load_ui_html():
    for p in (os.path.join(BASE_DIR, "index.html"),
              os.path.join(BASE_DIR, "ui", "index.html")):
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception:
            continue
    return u"<h1>界面文件缺失</h1><p>请把 index.html 放到程序目录。</p>"


# ============================================================
# 启动
# ============================================================
def main():
    _log_everywhere("准备创建 WebView…")
    try:
        ui = WebUIController(None)          # backend 稍后注入
        backend = WebBackend(ui)
        ui.backend = backend

        def on_ready():
            _log_everywhere("WebView 已就绪，加载界面")
            ui.load_html(load_ui_html())
            time.sleep(0.6)
            ui.js("onStatus", "idle", "DeepSeek")
            _log_everywhere("★网页版启动成功★")

        html = load_ui_html()
        ui.attach(html, on_ready=on_ready)

        # 保持主线程存活
        while True:
            time.sleep(1)
    except Exception:
        tb = traceback.format_exc()
        _log_everywhere("启动失败:\n" + tb)
        raise


if __name__ == "__main__":
    main()
