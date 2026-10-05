[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.4

requirements = python3,kivy==2.3.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

# 横竖屏双模式：四个方向全部列出
# （不用 all 简写——部分 buildozer 版本的合法值列表里没有 "all"，会直接报错退出）
orientation = landscape, portrait, landscape-reverse, portrait-reverse

fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

p4a.branch = v2024.01.21

# ============================================================
# 【关键】android.* 配置必须写在 [app] 段内（buildozer 1.6+ 的读取方式），
# 写在 [android] 段会被整段忽略（旧写法已废弃）。
# ============================================================

# 网络 + 存储权限（缺 INTERNET 会联网即被杀）
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 最低兼容 Android 5.0（API 21）—— 覆盖绝大多数在用安卓机
android.minapi = 21

# 编译目标 API 31（Android 12），与历史可正常运行版本一致
android.api = 31

# ============================================================
# 【全架构适配】
# 荣耀 Play7T（天玑6020）等机型 CPU 虽是 64 位，但系统运行在 32 位模式。
# 只打 arm64-v8a 会被系统"接受安装"却在启动时找不到匹配原生库而闪退。
# 同时打出 32 位与 64 位两套库，覆盖全部主流安卓设备。
# ============================================================
android.archs = arm64-v8a, armeabi-v7a

android.accept_sdk_license = True
android.allow_backup = True

# release 构建产出 apk（默认 aab 无法直接安装到手机）
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
