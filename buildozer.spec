[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.1
# Kivy 用 Git URL 强制指定，绕过 p4a 内置 recipe 的旧版本缓存
requirements = python3,kivy==https://github.com/kivy/kivy/archive/refs/tags/2.3.1.zip,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow
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

# 使用 p4a 的 develop 分支，获得对新版 Python / Kivy 的兼容修复
p4a.branch = develop
