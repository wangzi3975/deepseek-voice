[app]
title = DeepSeek语音助手
package.name = deepseekvoice
package.domain = org.deepseekvoice
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_dirs = _release,_shots,bin,.buildozer,__pycache__,logs,saved
version = 0.4

requirements = python3,kivy==2.3.1,requests,pyjnius,android,urllib3,certifi,chardet,idna,plyer,pillow

# 横竖屏双模式：all 会展开为 landscape / portrait / landscape-reverse /
# portrait-reverse，即四种方向全部支持，跟随手机旋转自动切换。
orientation = all
fullscreen = 0
icon.filename = %(source.dir)s/icon/app_icon.png

p4a.branch = v2024.01.21

# ============================================================
# 【关键】android.* 配置必须写在 [app] 段内（buildozer 1.6+ 的读取方式），
# 写在 [android] 段会被整段忽略。
# ============================================================

# 网络 + 存储权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 与可正常启动的历史版本一致
android.api = 31
android.minapi = 21

# ============================================================
# 【本次核心改动】全架构适配
#
# 荣耀 Play7T（天玑6020）等机型虽然 CPU 是 64 位，但系统运行在 32 位模式下。
# 只打 arm64-v8a 的包会被系统"接受安装"却在启动时因为找不到匹配的原生库
# 而立刻闪退（表现为点开瞬间退出）。
#
# 同时打出 32 位(armeabi-v7a) 与 64 位(arm64-v8a) 两套库，
# 无论手机运行在哪种模式下都能加载对应版本。
# ============================================================
android.archs = arm64-v8a, armeabi-v7a

android.accept_sdk_license = True
android.allow_backup = True

# release 构建产出 apk（默认 aab 无法直接安装）
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
