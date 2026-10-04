# DeepSeek语音助手 —— 完整打包包

## 这个包是干什么的

这是**可以直接上传 GitHub 打包 APK 的完整项目**。
代码版本：main.py 4396 行（含粘贴功能 + 本次新增的 4 项功能）。

### 本次更新（新增功能）

1. **思考时按钮自动锁定**：AI 思考/回答期间，图片、语音、发送按钮自动变灰不可点，
   避免重复发送；回答结束后自动恢复。
2. **实时打断按钮**：思考/回答期间底部出现红色 ■ 按钮，点一下就立即中断
   AI 输出，同时停止语音朗读。
3. **语音输入按钮**：底部新增 🎤 麦克风按钮，安卓上调用系统语音识别，
   识别结果自动写入输入框。
4. **后台生图（不阻塞对话）**：点顶部「AI」→ 输入描述 → 开始生成，
   弹窗立即关闭，生图在后台进行，**期间可以继续聊天**，完成后图片
   自动插入消息区。

---

## 目录结构

```
DeepSeekVoice_完整包/
├── main.py                              ← 主程序（4055行，已含粘贴功能）
├── buildozer.spec                       ← 打包配置（已修：补 plyer/pillow）
├── personas.json                        ← 角色数据
├── .github/
│   └── workflows/
│       └── build.yml                    ← 云编译配置（已修：Python 3.9）
├── .gitignore                           ← 防止 Key 泄露
├── icon/
│   └── app_icon.png                     ← App 图标（512×512）
└── assets/
    └── avatars/
        └── DeepSeek 鲸鱼娘.png           ← 角色立绘
```

---

## 已修复的 4 个问题

### 1. buildozer.spec 缺 plyer —— 致命
代码里用了 `from plyer import filechooser`（选相册/选图功能），
但原配置没写这个依赖。装到手机上一点"选图"就崩溃。
**已加入 requirements。**

### 2. workflow 用 Python 3.11 —— 致命
pyjnius 在 Python 3.11 下有已知编译错误：
```
jnius.c:54433:5: error: expression is not assignable
       ++Py_REFCNT(o);
```
**已改为 Python 3.9。**

### 3. cython 未锁版本 —— 严重
新版 Cython 编译 pyjnius 会失败。
**已锁 cython==0.29.33。**

### 4. main.py 版本不一致 —— 严重
原项目里根目录 main.py 是 4055 行（带粘贴功能），
_release/main.py 是 3913 行（旧）。
**本包统一用 4055 行最新版。**

---

## 怎么用

### 第1步：上传 GitHub

1. 打开 https://github.com/new 建一个**私有**仓库
2. 把本包**全部文件**上传（先按 Ctrl+H 显示隐藏文件，
   确保 `.github` 和 `.gitignore` 也传上去）
3. 提交

### 第2步：等云编译

上传后 GitHub Actions 自动开始跑，约 25~40 分钟。
在仓库的 Actions 页面看进度。

### 第3步：下载 APK

构建完成后，进 Actions 那条记录，底部 Artifacts
下载 `deepseek-voice-apk`，解压得到 `app-debug.apk`。

### 第4步：装到手机

传到手机 → 点击安装 → 允许"未知来源" → 完成。
首次打开进设置页填 API Key。

---

## 需要的 API Key

| 填到哪 | 去哪申请 | 花钱吗 |
|--------|----------|--------|
| DeepSeek API Key | https://platform.deepseek.com/ | 要充值，10元起 |
| 搜索 API Key | https://open.bochaai.com/ | 有免费额度 |
| 图像识别 API Key | https://open.bigmodel.cn/ | flash版免费 |
| 图片生成 API Key | https://open.bigmodel.cn/ | 同上，一个Key填两个框 |

---

## 重要提醒

1. **本包里没有 config.json**（里面存API Key），放心上传。
2. 千万不要把运行后生成的 config.json 传到 GitHub。
3. `.gitignore` 已经帮你屏蔽了 config.json、sessions.json、
   Bug日志.txt 等敏感/运行时文件。
