[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.3

requirements = python3,kivy==2.3.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

p4a.branch = v2024.01.21

# ============================================================
# 【关键】android.* 配置必须写在 [app] 段内（buildozer 1.6+ 的读取方式），
# 写在 [android] 段会被整段忽略。
#
# 本次采取"最大兼容"策略：API 级别与曾经能正常启动的版本保持一致，
# 只修正权限缺失这一项。
# ============================================================

# 网络 + 存储权限（无 INTERNET 时联网会被系统拒绝）
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 与可正常启动的历史版本一致，避免新系统策略差异
android.api = 31
android.minapi = 21

android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
