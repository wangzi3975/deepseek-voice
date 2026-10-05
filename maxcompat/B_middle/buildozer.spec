[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.5b

# 【折中版 B】Kivy 2.2.1 + p4a v2023.09.15
# 比 A 新一点，比当前 2.3.1 老一点，中间路线
requirements = python3,kivy==2.2.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

orientation = landscape, portrait, landscape-reverse, portrait-reverse
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

p4a.branch = v2023.09.16

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.minapi = 21
android.api = 30
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
