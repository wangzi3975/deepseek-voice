[app]
title = DSV探针
package.name = dsvprobe
package.domain = org.dsvprobe
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.1

# 只保留最核心的依赖，去掉一切可能出问题的东西
requirements = python3,kivy==2.3.1

orientation = landscape, portrait, landscape-reverse, portrait-reverse
fullscreen = 0
p4a.branch = v2024.01.21

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.minapi = 21
android.api = 31
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
