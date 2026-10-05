# -*- coding: utf-8 -*-
"""
DSV WebProbe v1 —— 浏览器套壳最小验证包
目的：验证「用手机自带浏览器内核显示界面」这条路能不能在荣耀 Play7T 上跑通。
不含任何业务功能，只有一个测试页面。
"""

import os
import sys
import traceback
from datetime import datetime

# ============================================================
# 0. 最早期崩溃日志：在任何危险导入之前先落地
# ============================================================

def _write_everywhere(fname, text):
    """写到所有可能的位置，不中断。手机文件管理器里能看到的最好。"""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = u"[%s]\n%s\n" % (stamp, text)
    done = []
    dirs = [
        "/sdcard/Download",
        "/storage/emulated/0/Download",
        "/storage/emulated/0/Documents",
        "/sdcard",
        "/storage/emulated/0",
        "/data/local/tmp",
    ]
    for e in ("ANDROID_PRIVATE", "ANDROID_APP_PATH", "ANDROID_ARGUMENT"):
        p = os.environ.get(e)
        if p:
            dirs.append(p)
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    dirs.append("/tmp")

    for d in dirs:
        try:
            if not d:
                continue
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
            fp = os.path.join(d, fname)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(body)
            done.append("OK  " + fp)
        except Exception as ex:
            done.append("ERR %s : %r" % (d, ex))
    return done


def _log(stage, extra=""):
    try:
        _write_everywhere("网页探针_启动阶段.txt",
                          u"当前阶段：%s\n%s" % (stage, extra))
    except Exception:
        pass


try:
    _log(u"00.脚本开始执行",
         u"Python=%s\nargv=%r\ncwd=%s" % (sys.version, sys.argv, os.getcwd()))
except Exception:
    pass


# ============================================================
# 1. 全局异常钩子 —— 任何崩溃都留证据
# ============================================================

def _hook(exc_type, exc_value, exc_tb):
    try:
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _write_everywhere("网页探针_崩溃日志.txt", tb)
        _log(u"99.发生未捕获异常", tb)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _hook
_log(u"01.全局异常钩子已挂载")


# ============================================================
# 2. Kivy + WebView 导入
# ============================================================

_log(u"02.准备导入 Kivy")

try:
    from kivy.app import App
    from kivy.uix.widget import Widget
    _log(u"03.Kivy 导入成功")
except Exception:
    _write_everywhere("网页探针_崩溃日志.txt", traceback.format_exc())
    raise

# WebView 组件（关键）：优先用 kivy 官方的，其次用 android 的
WEBVIEW_KIND = None
try:
    from kivy.uix.webview import WebView
    WEBVIEW_KIND = "kivy.uix.webview"
    _log(u"04.WebView 导入成功", WEBVIEW_KIND)
except Exception as e1:
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        WEBVIEW_KIND = "jnius+android.webkit.WebView"
        _log(u"04.WebView 导入成功(jnius)", str(e1))
    except Exception as e2:
        _log(u"04.WebView 全部导入失败",
             u"kivy方式: %r\njnius方式: %r" % (e1, e2))


# ============================================================
# 3. 测试页面 HTML
# ============================================================

HTML = u"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>网页探针</title>
<style>
 * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
 body { margin:0; padding:0; background:#0f1115; color:#e8eaed;
        font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }
 .wrap { padding:22px 18px 40px; }
 h1 { font-size:26px; margin:6px 0 4px; color:#4ea1ff; }
 .sub { font-size:15px; color:#9aa0a6; margin-bottom:22px; }
 .ok { background:#123d1e; border:2px solid #2ecc71; border-radius:14px;
       padding:18px; font-size:19px; line-height:1.7; margin-bottom:16px; }
 .ok b { color:#2ecc71; font-size:22px; }
 .card { background:#1a1d23; border-radius:14px; padding:16px 18px;
         margin-bottom:14px; font-size:15px; line-height:1.9; }
 .k { color:#8ab4f8; }
 .v { color:#fdd663; word-break:break-all; }
 button { width:100%; padding:16px; font-size:18px; border:0; border-radius:12px;
          background:#4ea1ff; color:#fff; font-weight:600; margin-top:8px; }
 button:active { background:#2d7fd3; }
 #out { margin-top:14px; font-size:16px; color:#81c995; min-height:30px;
        line-height:1.7; }
</style></head>
<body><div class="wrap">
  <h1>手机支持这条路</h1>
  <div class="sub">DSV WebProbe v1 · 浏览器套壳验证</div>

  <div class="ok">
    <b>你看到这个页面了</b><br>
    说明你的手机<br>能用「浏览器套壳」显示界面。
  </div>

  <div class="card">
    <div><span class="k">当前时间：</span><span class="v" id="t">读取中…</span></div>
    <div><span class="k">屏幕宽度：</span><span class="v" id="w">读取中…</span></div>
    <div><span class="k">浏览器内核：</span><span class="v" id="ua">读取中…</span></div>
  </div>

  <button onclick="ping()">点我测试交互</button>
  <div id="out"></div>
</div>
<script>
  document.getElementById('t').textContent = new Date().toLocaleString('zh-CN');
  document.getElementById('w').textContent = window.innerWidth + ' px';
  var u = navigator.userAgent;
  var m = u.match(/Chrome\\/[0-9.]+/);
  document.getElementById('ua').textContent = m ? m[0] : u.slice(0, 60);
  function ping() {
    var o = document.getElementById('out');
    o.textContent = '按钮生效了 · ' + new Date().toLocaleTimeString('zh-CN');
  }
</script>
</body></html>"""


# ============================================================
# 4. 界面
# ============================================================

if WEBVIEW_KIND == "kivy.uix.webview":
    class ProbeRoot(Widget):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.wv = WebView()
            self.wv.load_html_string(HTML, "")
            self.add_widget(self.wv)
            self.bind(size=self._rs, pos=self._rp)
            _log(u"05.build 完成(kivy webview)")

        def _rs(self, *a):
            self.wv.size = self.size

        def _rp(self, *a):
            self.wv.pos = self.pos

else:
    # jnius 直连 Android WebView
    class ProbeRoot(Widget):
        def __init__(self, **kw):
            super().__init__(**kw)
            _log(u"05.build 开始(jnius webview)")
            self._android_create()

        def _android_create(self):
            try:
                from android.runnable import run_on_ui_thread
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                WebViewCls = autoclass("android.webkit.WebView")
                LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
                activity = PythonActivity.mActivity

                webview = WebViewCls(activity)
                webview.getSettings().setJavaScriptEnabled(True)
                webview.getSettings().setDomStorageEnabled(True)
                webview.setBackgroundColor(0xFF0F1115)
                webview.loadDataWithBaseURL("", HTML, "text/html", "utf-8", "")

                self._wv = webview

                @run_on_ui_thread
                def add():
                    try:
                        activity.addContentView(webview, LayoutParams(-1, -1))
                        _log(u"06.WebView 已挂到界面")
                    except Exception:
                        _write_everywhere("网页探针_崩溃日志.txt",
                                          traceback.format_exc())
                add()
                _log(u"05.build 完成(jnius webview)")
            except Exception:
                _write_everywhere("网页探针_崩溃日志.txt", traceback.format_exc())
                _log(u"05.build 失败(jnius webview)", traceback.format_exc())


class WebProbeApp(App):
    def build(self):
        _log(u"07.build() 被调用")
        self.title = "网页探针"
        return ProbeRoot()

    def on_start(self):
        _log(u"08.on_start() 被调用 —— 程序已成功启动！")
        try:
            _write_everywhere(
                "★程序已启动★.txt",
                u"恭喜！DSV WebProbe 在你的手机上成功启动了。\n"
                u"这说明「浏览器套壳」这条路可行。\n"
                u"时间：%s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

    def on_stop(self):
        _log(u"09.on_stop() 被调用 —— 程序正常退出")


if __name__ == "__main__":
    _log(u"10.准备调用 run()")
    try:
        WebProbeApp().run()
    except Exception:
        _write_everywhere("网页探针_崩溃日志.txt", traceback.format_exc())
        raise
