---
name: screen-ocr
description: 用 OCR 从屏幕像素里找文字并返回坐标——适用于没有 UI Automation 树、也没有 DOM 的界面（游戏、Canvas 渲染、远程桌面、Java/Qt 自绘窗口、截图里的文字）。用户说"从画面里找这个按钮""读一下这个界面上的字""这个软件抓不到控件"时使用。
---

# 屏幕 OCR 定位

**这是最后手段。** 有 UIA 或用得上 CDP 时，都不要用它。

## 前置检查

```powershell
Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe"
Test-Path "C:\Program Files\Tesseract-OCR\tessdata\chi_sim.traineddata"
```

没装就：`winget install UB-Mannheim.TesseractOCR`，中文包需单独下：

```
https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata
→ 放到 C:\Program Files\Tesseract-OCR\tessdata\
```

## 工具

```
scripts\ocr.py
```

```powershell
$py  = "C:\Python314\python.exe"
$ocr = "scripts\ocr.py"

& $py $ocr find "确认"                       # 全屏找文字 → 坐标
& $py $ocr find "确认" --min-conf 80        # 更严格
& $py $ocr find "确认" --region 0,0,1200,800 # 限定区域
& $py $ocr dump                             # 全屏所有文字+坐标
& $py $ocr read shot.png                    # 识别已有图片
```

**输出**：`1240,850  conf=93  w=60 h=24  "确认"`

也可以统一走 `desktop-control` 技能里的 `ctl.cmd`：
```powershell
& "<skills>\desktop-control\scripts\ctl.cmd" -Action find -Text "确认"
```
它会**先查 UIA，查不到再自动降级到 OCR**。

## 中文参数必须走 base64

**PowerShell 5.1 传中文 argv 给原生 exe 会乱码**——`番剧` 到了 Python 那边变成 `锟斤拷`。

`ctl.cmd` 的 `find` 已经用 base64 传递（纯 ASCII 过线，Python 端 decode）。
自己直接调 `ocr.py` 时，用 `find-b64 <base64>`：

```powershell
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("确认"))
& $py $ocr find-b64 $b64
```

## 精度的真相（重要）

**实测结论：这个方案能定位，但准确率不稳定。**

能用的部分：
- 大字号、清晰、纯色背景的文字：`conf` 90+，坐标准确
- 已验证：`登录`、`套餐`、`账单`、标签页标题，坐标误差在几像素内
- 放大后识别率显著提升（`run_ocr` 按图像尺寸自适应放大 2-4 倍）

不稳定的部分：
- **小字号中文容易错字**：「番剧索引」可能被识别成「HRS」
- **复杂排版会串行**：同一个词在页面多处时，分组可能出错
- **低对比度/抗锯齿文字**：`conf` 掉到 60 以下，不可信

**因此：`conf < 80` 的命中，不要直接拿去点击。** 先裁出该区域重识别验证。

## 正确的使用姿势

```
1. find 拿到坐标 + conf
2. conf >= 85 → 可信，裁剪该区域再 read 一次确认文字一致
3. conf < 85  → 剪出区域，单独 OCR（区域小可以放很大倍率）
4. 点击前：截图记录点击位置前后对比，确认发生了预期变化
```

区域越小、放大倍率越高，准确率越好。**全屏 OCR 是最差的做法**，`--region` 才是正道。

## 踩过的坑

### 1. 手写 PNG 编码会崩

用 `ctypes` + `zlib` 手工拼 PNG，在双屏 5120×1600 上直接挂掉。
**改用 `PIL.ImageGrab.grab(all_screens=True)`**，一行搞定。

### 2. `WinRT OCR`（Windows 自带）在 PowerShell 5.1 里没法用

`Windows.Media.Ocr` 引擎能创建（支持 `zh-Hans-CN`），但 `IAsyncOperation` 的状态读不出来：

```
Status after wait: (空)
```

PowerShell 5.1 对接 WinRT 有已知缺陷。**用 Tesseract，别折腾 WinRT。**

### 3. PowerShell 参数里的中文会乱码

见上面「中文参数必须走 base64」。

### 4. OCR 会匹配到"别处的同名文字"

搜「番剧」可能命中聊天记录、另一个窗口、副屏内容。
**必须传 `--region` 限定范围**，或先移动到目标窗口再截。

## 什么时候**不要**用

| 情况 | 用什么 |
|---|---|
| 有 UIA 控件树 | `desktop-control` 的 `tree` |
| 是网页 | `browser-automation` 的 CDP |
| 是原生 Windows 程序 | 优先 UIA |
| 是游戏/Canvas | **才用它** |

**先花 200ms 跑一次 `tree`，能出结果就别用 OCR。**
