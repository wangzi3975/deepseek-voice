[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.2

# Kivy 2.3.1：配方(recipe)会把版本号拼进下载地址，这里只写版本号，不要写完整 URL
requirements = python3,kivy==2.3.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

# 锁定 python-for-android 到 v2024.01.21 稳定版（内置 Python 3.11.5）。
# master/develop 分支内置 Python 3.14，pip 与 p4a 不兼容
# (ImportError: BuildDependencyInstallError)，且 Kivy 的 C 扩展编译不过。
p4a.branch = v2024.01.21

# ============================================================
# 【关键】以下 android.* 配置必须写在 [app] 段内！
# buildozer 1.6+ 的读取方式是 config.get('app', 'android.xxx')，
# 放在 [android] 段会被完全忽略（旧版写法），导致：
#   - 权限为空(没有 INTERNET) -> App 启动即崩
#   - minapi 回退默认 21
#   - archs 回退默认双架构(编出多余的 32 位库)
# 这正是之前"点开就闪退"的根因。
# ============================================================

# 网络权限（没有 INTERNET 时 App 一联网就被系统杀掉）
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES

# 编译 SDK 33：满足 Android 13 / HarmonyOS 4 的要求
android.api = 33
android.minapi = 24

# 只编 64 位，避免华为等纯 64 位机型加载到 32 位库而崩溃
android.archs = arm64-v8a

# 系统会自动接受 SDK 许可
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
