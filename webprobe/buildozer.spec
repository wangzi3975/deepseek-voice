[app]

title = 网页探针
package.name = webprobe
package.domain = org.dsvwebprobe
version = 0.1

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,htm,css,js,json,txt

icon.filename = %(source.dir)s/app_icon.png

# 用 sdl2 引导启动（保证 Python 能跑起来）
# 但界面不在 SDL2 里画，而是把 Android 原生 WebView 盖上去
requirements = python3,kivy==2.3.1,pyjnius,android

orientation = portrait
fullscreen = 0

p4a.branch = v2024.01.21

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

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
