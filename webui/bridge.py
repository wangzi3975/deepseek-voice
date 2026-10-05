# -*- coding: utf-8 -*-
"""
DSV 网页桥接层
把 Android 原生 WebView 与 Python 后端连起来。

通信方案（两条路，都不需要自定义 Java 接口，规避 pyjnius 接口注册风险）：

  JS  ->  Python : 网页跳转伪链接  dsv://call/send?d=<urlencoded json>
                   WebViewClient.shouldOverrideUrlLoading 拦截后转发给 Python

  Python -> JS   : webview.evaluateJavascript("window.onAIChunk(...)")

这样做的原因：
  addJavascriptInterface 需要注册自定义 Java 接口，p4a 下容易因接口签名
  不匹配导致启动崩溃；URL 拦截只用系统已有的 WebViewClient，最稳。
"""

import base64
import json
import threading
import time
import traceback
import urllib.parse

from jnius import autoclass, PythonJavaClass, java_method

# ============================================================
# Android 类引用
# ============================================================
WebView = autoclass("android.webkit.WebView")
WebViewClient = autoclass("android.webkit.WebViewClient")
PythonActivity = autoclass("org.kivy.android.PythonActivity")
LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
Color = autoclass("android.graphics.Color")

SCHEME = "dsv"


def _get_activity():
    """拿到当前 Activity（p4a 各版本取名不同，逐个兜底）。"""
    for name in ("mActivity", "m_activity"):
        try:
            a = getattr(PythonActivity, name)
            if a is not None:
                return a
        except Exception:
            pass
    raise RuntimeError("无法获取 Android Activity")


# ============================================================
# Java Runnable（把 Python 函数丢到 UI 线程执行）
# ============================================================
class _JavaRunnable(PythonJavaClass):
    __javainterfaces__ = ["java/lang/Runnable"]
    __javacontext__ = "app"

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @java_method("()V")
    def run(self):
        try:
            self.fn()
        except Exception:
            traceback.print_exc()


# ============================================================
# WebViewClient：拦截 dsv:// 伪链接
# ============================================================
class _BridgeClient(PythonJavaClass):
    """
    继承 android.webkit.WebViewClient，覆盖 shouldOverrideUrlLoading。
    注意：不继承原类的实现，只作为替身（返回 True 表示已处理，阻止导航）。
    """
    __javainterfaces__ = ["android/webkit/WebViewClient"]
    __javacontext__ = "app"

    def __init__(self, handler):
        super().__init__()
        self.handler = handler

    @java_method("(Landroid/webkit/WebView;Ljava/lang/String;)Z")
    def shouldOverrideUrlLoading(self, view, url):
        try:
            url = str(url)
            if url.startswith(SCHEME + "://"):
                self._dispatch(url)
                return True          # 拦截，不让 WebView 真去导航
        except Exception:
            traceback.print_exc()
        return False

    @java_method("(Landroid/webkit/WebView;Landroid/webkit/WebResourceRequest;)Z")
    def shouldOverrideUrlLoading2(self, view, request):
        try:
            url = str(request.getUrl().toString())
            if url.startswith(SCHEME + "://"):
                self._dispatch(url)
                return True
        except Exception:
            traceback.print_exc()
        return False

    def _dispatch(self, url):
        """dsv://call/<action>?d=<urlencoded json>"""
        try:
            rest = url[len(SCHEME) + 3:]
            if "?" in rest:
                path, qs = rest.split("?", 1)
            else:
                path, qs = rest, ""
            action = path.strip("/")
            params = urllib.parse.parse_qs(qs)
            raw = (params.get("d") or ["{}"])[0]
            data = json.loads(raw) if raw else {}
        except Exception:
            action, data = "unknown", {}
        # 放到后台线程处理，不阻塞 UI 线程
        threading.Thread(
            target=lambda: self.handler(action, data), daemon=True).start()


# ============================================================
# 主控制器
# ============================================================
class WebUIController(object):

    def __init__(self, backend):
        self.backend = backend
        self.webview = None
        self.activity = None

    # ---------- 创建 WebView ----------
    def attach(self, html, on_ready=None):
        self.activity = _get_activity()

        def _do():
            try:
                activity = self.activity
                wv = WebView(activity)

                st = wv.getSettings()
                st.setJavaScriptEnabled(True)
                st.setDomStorageEnabled(True)
                st.setDatabaseEnabled(True)
                st.setAllowFileAccess(True)
                st.setLoadWithOverviewMode(True)
                st.setUseWideViewPort(True)
                try:
                    st.setMediaPlaybackRequiresUserGesture(False)
                except Exception:
                    pass

                wv.setBackgroundColor(Color.parseColor("#0F1115"))

                client = _BridgeClient(self.handle)
                wv.setWebViewClient(client)
                self._client = client          # 保引用防 GC

                self.webview = wv
                activity.addContentView(wv, LayoutParams(-1, -1))
                print("[bridge] WebView 已挂载")

                if on_ready:
                    on_ready()
            except Exception:
                traceback.print_exc()

        self._run_on_ui(_do)

    def _run_on_ui(self, fn):
        def _w():
            try:
                self.activity.runOnUiThread(_JavaRunnable(fn))
            except Exception:
                traceback.print_exc()
        threading.Thread(target=_w, daemon=True).start()

    # ---------- 加载 HTML ----------
    def load_html(self, html):
        """
        用 loadDataWithBaseURL 注入页面内容（最稳，无需外部文件）。
        基地址用 file:/// 方便未来加载本地图片/字体。
        """
        def _do():
            try:
                self.webview.loadDataWithBaseURL(
                    "file:///android_asset/",
                    html,
                    "text/html",
                    "utf-8",
                    None)
                print("[bridge] HTML 已注入 (%d 字符)" % len(html))
            except Exception:
                traceback.print_exc()

        self._run_on_ui(_do)
        # 页面渲染需要一点时间；随后告诉网页"桥接是通的"，
        # 避免网页误判成电脑浏览器预览而降级为模拟回复
        self._arm_bridge_hello()

    def _arm_bridge_hello(self):
        """注入后分几次尝试通知网页，确保脚本已执行"""
        def _worker():
            time.sleep(1.2)
            for i in range(6):
                try:
                    self.eval_js(
                        "if(window.__bridgeAlive__){window.__bridgeAlive__();}")
                    print("[bridge] 已通知网页桥接就绪 (第 %d 次)" % (i + 1))
                except Exception:
                    traceback.print_exc()
                time.sleep(1.0)

        threading.Thread(target=_worker, daemon=True).start()

    # ---------- Python -> JS ----------
    def eval_js(self, code):
        if not self.webview:
            print("[bridge] eval_js: WebView 未就绪")
            return

        def _do():
            try:
                self.webview.evaluateJavascript(code, None)
            except Exception:
                try:
                    self.webview.loadUrl("javascript:" + code)
                except Exception:
                    traceback.print_exc()

        self._run_on_ui(_do)

    def js(self, fn, *args):
        payload = ",".join(json.dumps(a, ensure_ascii=False) for a in args)
        self.eval_js("window.%s(%s);" % (fn, payload))

    # ---------- 常用封装 ----------
    def ai_chunk(self, text):
        self.js("onAIChunk", text)

    def ai_done(self, meta=None):
        self.js("onAIDone", meta or {})

    def status(self, state, text=""):
        self.js("onStatus", state, text)

    def toast(self, text):
        self.js("onToast", text)

    def rec_start(self):
        self.js("onRecordingStart")

    def rec_stop(self):
        self.js("onRecordingStop")

    # ---------- 分发 ----------
    def handle(self, action, data):
        print("[bridge] JS ->", action, data)
        b = self.backend
        if b is None:
            return
        try:
            if action == "send":
                b.on_send(data.get("text", ""))
            elif action == "interrupt":
                b.on_interrupt()
            elif action == "start_record":
                b.on_start_record()
            elif action == "stop_record":
                b.on_stop_record()
            elif action == "save_settings":
                b.on_save_settings(data)
                self.toast("设置已保存")
            elif action == "clear_chat":
                b.on_clear_chat()
            elif action == "get_settings":
                self.js("onSettings", b.get_settings())
            elif action == "get_conversations":
                self.js("onConversations", b.get_conversations())
            elif action == "ready":
                self.js("onStatus", "idle", "DeepSeek")
                self.js("onSettings", b.get_settings())
            else:
                print("[bridge] 未知 action:", action)
        except Exception:
            traceback.print_exc()
            self.toast("操作出错")
