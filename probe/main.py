#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek语音助手 —— 启动探针版
这个版本只有一个目的：证明程序到底能不能跑起来。
它不联网、不读配置、不建界面，只做三件事：
  1. 用最原始的方式（sys.stdout / 文件）记录每一步
  2. 尝试写入你能看得见的 /sdcard/Download
  3. 显示一个最简单的界面，证明 Kivy 能工作
如果连这个都闪退，那就是手机系统拦截，跟代码无关。
"""

import sys, os, time, traceback

# ============================================================
# 第 0 步：在 import 任何东西之前，先写一个"活着"的标记。
# 用最笨的办法：把所有可能能写的目录都试一遍，绝不 break。
# ============================================================
_BOOT_TXT = []
def _probe(msg):
    _BOOT_TXT.append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
    try:
        print("DSVPROBE|" + msg, flush=True)
    except Exception:
        pass

_probe("0. 探针脚本开始执行")
_probe("Python 版本: " + sys.version.replace("\n", " "))

# 环境变量全量 dump
_env_lines = []
for _k in sorted(os.environ.keys()):
    try:
        _env_lines.append("  %s = %s" % (_k, os.environ[_k]))
    except Exception:
        pass
_probe("环境变量共 %d 个" % len(_env_lines))

def _write_everywhere(fname, text):
    """往所有可能的目录写，一个成功不算成功，全都要试。"""
    done = []
    dirs = []
    # 1. 明确的公共目录（你能看见的）
    for d in ("/sdcard/Download", "/storage/emulated/0/Download",
              "/sdcard", "/storage/emulated/0",
              "/storage/emulated/0/Android/data/org.deepseekvoice.deepseekvoice/files"):
        dirs.append(d)
    # 2. app 私有目录（你看不见，但一定能写）
    for e in ("ANDROID_PRIVATE", "ANDROID_APP_PATH", "ANDROID_ARGUMENT"):
        p = os.environ.get(e)
        if p:
            dirs.append(p)
    # 3. 脚本所在目录、临时目录
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    dirs.append("/data/local/tmp")
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
                f.write(text)
            done.append(fp)
        except Exception as ex:
            done.append("  [失败] %s : %s" % (d, ex))
    return done

_probe("1. 开始写启动探针文件")

_body = "\n".join(_BOOT_TXT) + "\n\n----- 环境变量 -----\n" + "\n".join(_env_lines)

_written = _write_everywhere("探针_程序已启动.txt", _body)
_probe("2. 探针文件写入结果:")
for _w in _written:
    _probe("     " + str(_w))

# ============================================================
# 第 1 步：导入 Kivy（这是最容易崩的一步）
# ============================================================
_probe("3. 准备导入 Kivy")
try:
    from kivy.app import App
    from kivy.uix.label import Label
    from kivy.core.window import Window
    from kivy.utils import platform as _kplatform
    _probe("4. Kivy 导入成功, platform=" + repr(_kplatform))
except Exception:
    _err = "Kivy 导入失败！\n\n" + traceback.format_exc()
    _probe("4. Kivy 导入失败")
    _write_everywhere("探针_Kivy导入失败.txt", _err)
    raise

# ============================================================
# 第 2 步：最简单界面
# ============================================================
class ProbeApp(App):
    def build(self):
        _probe("5. build() 被调用")
        _write_everywhere("探针_界面已构建.txt",
                          "\n".join(_BOOT_TXT) + "\n\n>>> 到这里说明程序完全正常 <<<\n")
        try:
            return Label(
                text="DeepSeek语音助手\n\n启动探针 v1\n\n"
                     "如果你看到这句话，\n说明程序本身没问题！\n\n"
                     "请把「下载」文件夹里的\n探针_*.txt 发给我",
                font_size="22sp",
                halign="center",
                valign="middle",
            )
        except Exception:
            _probe("5b. Label 构建失败")
            _write_everywhere("探针_界面构建失败.txt", traceback.format_exc())
            raise

    def on_start(self):
        _probe("6. on_start() 被调用 —— 程序完整启动成功！")
        _write_everywhere("探针_启动成功.txt",
                          "\n".join(_BOOT_TXT) + "\n\n>>> 完美！程序完全正常 <<<\n")

_probe("7. 准备调用 run()")
try:
    ProbeApp().run()
except Exception:
    _probe("7b. run() 崩溃")
    _write_everywhere("探针_run崩溃.txt", traceback.format_exc())
    raise
_probe("8. run() 正常结束")
