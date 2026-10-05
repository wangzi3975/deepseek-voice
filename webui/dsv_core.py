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
                out = os.path.join(DATA_DIR, "last_gen.png")
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

