[app]

title = DeepSeek语音助手
package.name = deepseekwebui
package.domain = org.dsvwebui
version = 1.0

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,htm,css,js,json,txt,ttf

icon.filename = %(source.dir)s/app_icon.png

# 核心依赖：kivy 只用来起 Python 环境，界面走 Android 原生 WebView
requirements = python3,kivy==2.3.1,pyjnius,android,requests,urllib3,certifi,chardet,idna

orientation = portrait
fullscreen = 0

p4a.branch = v2024.01.21

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,RECORD_AUDIO

android.minapi = 21
android.api = 31
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk
android.presplash_color = #0F1115

[buildozer]
log_level = 2
warn_on_root = 1
