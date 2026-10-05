[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.5a

# 【保守版 A】用最老最稳的组合，最大化兼容性
# Kivy 2.1.0 = 2021 年稳定版，对国产芯片兼容性远好于 2.3.x
requirements = python3,kivy==2.1.0,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

orientation = landscape, portrait, landscape-reverse, portrait-reverse
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

# 老的 p4a 分支，配 Kivy 2.1.0
p4a.branch = v2022.12.20

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.minapi = 21
# 【关键】目标 API 降到 27（安卓 8.1）—— 兼容性最好的档位
android.api = 27
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
