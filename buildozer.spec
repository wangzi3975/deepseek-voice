[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.1
# Kivy 2.3.1：配方(recipe)会把版本号拼进下载地址，这里只写版本号，不要写完整 URL
requirements = python3,kivy==2.3.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

[android]
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
# 关键：固定用 p4a 的稳定分支(master)，它内置 Python 3.11.5，与 Kivy 2.3.x 完全兼容。
# 绝不能用 develop 分支——那里的 python3 配方是 Python 3.14，Kivy 的 C 扩展编译不过。
p4a.branch = master
