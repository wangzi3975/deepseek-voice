[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.5c

# 【纯 32 位版 C】只打 armeabi-v7a
# 如果你的手机是"纯 32 位系统"，这个包最匹配
requirements = python3,kivy==2.1.0,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

orientation = landscape, portrait, landscape-reverse, portrait-reverse
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

p4a.branch = v2022.12.20

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.minapi = 21
android.api = 27
# 【只打 32 位】匹配纯 32 位系统
android.archs = armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
