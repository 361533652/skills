---
name: background-automation
description: 在窗口处于后台、被遮挡或最小化时操作它——基于 WGC 合成器截图 + PostMessage 消息投递 + OpenCV 模板匹配，不抢焦点、不劫持鼠标。适合游戏日常、后台软件自动化、以及"边用电脑边让它干活"的场景。用户说"帮我在后台点这个""不要抢我鼠标""游戏挂在后台自动跑"时使用。
---

# 后台窗口自动化

**核心价值：目标窗口不需要在前台，你的鼠标键盘也不受影响。**

和 `desktop-control` 的区别：

| | desktop-control | 本技能 |
|---|---|---|
| 截后台窗口 | ❌ 遮挡即黑屏 | ✅ WGC 从合成器取帧 |
| 点击 | 移动真实鼠标 | ✅ 消息合成，不动光标 |
| 输入 | 真实键盘 | ✅ 消息合成 |
| 能否边用电脑边跑 | ❌ 会打断你 | ✅ 完全不影响 |

---

## 环境要求

```powershell
# 先定位 python（别写死版本号，见下节）
$py = (Get-Command python -EA SilentlyContinue).Source
$bg = "<base-directory>\scripts\bgauto.py"
& $py $bg deps              # 检查依赖
& $py $bg deps --install    # 自动安装缺失依赖
```

### Python 解释器怎么定位

**不要写死具体版本路径**，换机器就失效。按顺序找：

```powershell
# 1. 优先 PATH 里的 python（排除 WindowsApps 的商店别名）
$py = (Get-Command python -EA SilentlyContinue).Source
if (-not $py -or $py -like '*WindowsApps*') {
  # 2. py launcher 的真实解释器
  $py = & py -c "import sys;print(sys.executable)" 2>$null
}
# 3. 常见安装目录兜底
if (-not (Test-Path $py)) {
  foreach ($c in @("C:\Python314\python.exe","C:\Python313\python.exe",
                   "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe")) {
    if (Test-Path $c) { $py = $c; break }
  }
}
```

`desktop-control` 的 `dsh-ctl.ps1` 里已实现同样逻辑（`Resolve-Python` 函数），可参考。

### 依赖清单

| 包 | 体积 | 作用 | 缺失后果 |
|---|---|---|---|
| `windows-capture` | 224 KB | WGC 后台截图 | 降级到 PrintWindow（GPU 窗口会黑） |
| `opencv-python` | ~40 MB | 模板匹配 | `find` 不可用 |
| `numpy` | ~15 MB | 图像数组 | 全部图像功能不可用 |

全部有预编译轮子，`pip install` 无需编译。

### 平台支持矩阵

| 平台 | 后台截图 | 后台输入 | 说明 |
|---|---|---|---|
| **Windows 10 1803+** | ✅ WGC | ✅ PostMessage | 完整支持 |
| **Windows 11** | ✅ WGC | ✅ PostMessage | 完整支持（建议，实测平台） |
| Windows 7/8 | ❌ 无 WGC | ⚠️ 可用 | 只能用 PrintWindow，GPU 窗口会黑 |
| Linux | ❌ | ❌ | 需换 X11/PipeWire，本工具不支持 |
| macOS | ❌ | ❌ | 需换 CGWindowList，本工具不支持 |

**判断能否用**：先跑 `deps`，如果 `windows-capture` 装不上或导入失败，说明平台不满足。

### 依赖缺失时的降级行为

工具**不会因为缺依赖就崩**，而是逐级降级并明确告知：

```
缺 numpy           → 所有图像功能报错退出，窗口操作仍可用
缺 opencv          → find/grab/clickfind 不可用，capture/click/key 可用
缺 windows-capture → 自动降级 PrintWindow，后台 GPU 窗口会返回全黑并被判定失败
```

每个失败都给出**具体的安装命令**，不会静默失败。

---

## 11 个命令

```powershell
& $py $bg deps                              # 依赖自检/安装
& $py $bg list [--filter 关键词]            # 列出窗口
& $py $bg capture --title T --out F.png     # 后台截图
& $py $bg grab --title T --box X,Y,W,H --out TPL.png   # 截图并裁模板
& $py $bg geom --title T                    # 显示坐标映射
& $py $bg calibrate --title T               # 实测校验映射
& $py $bg find --title T --template TPL.png # 找元素→客户区坐标
& $py $bg click --title T --x N --y N       # 后台点击
& $py $bg key --title T --key F             # 后台按键
& $py $bg type --title T --text "内容"      # 后台输入文字
& $py $bg clickfind --title T --template TPL.png   # 找到即点
```

**目标窗口定位**：`--title` 子串匹配 / `--class-name` / `--pid` / `--exact` 精确匹配。

---

## 标准工作流

```powershell
# 1. 找到窗口
& $py $bg list --filter "原神"

# 2. 后台截一张，确认坐标映射
& $py $bg geom --title "原神"
#   window 1920x1023  client 1904x964  capture 1906x1016
#   client offset in capture: (1, 51)

# 3. 从截图里裁出按钮，存成模板（只需做一次）
& $py $bg grab --title "原神" --box 1200,900,180,60 --out buttons\claim.png

# 4. 以后每次：找到就点
& $py $bg clickfind --title "原神" --template buttons\claim.png
```

---

## 三个必须知道的机制

### 1. WGC 截的是"窗口视觉边界"，不是客户区

实测数据（1920×1023 的 Win11 记事本）：

```
window rect   1920x1023     ← GetWindowRect，含不可见的缩放边框
client area   1904x964      ← 真正的可用区域
WGC capture   1906x1016     ← 视觉边界，边框被去掉了
client offset (1, 51)       ← 客户区在截图中起点：左 1，上 51（标题栏高）
```

**偏移量不是常数**，随窗口标题栏、边框样式、DPI 变化。所以：

- `find` 返回的坐标**已经自动换算成客户区坐标**，可以直接喂给 `click`
- `geom` 可查当前映射
- `calibrate` 会实测校验（需要窗口在屏幕上）

**如果把截图坐标直接当客户区坐标用，点击会偏移几十像素，静默点错位置。** 这是最容易踩的坑。

### 2. 按键必须发给子控件，不能发顶层窗口

实测对比（同一个记事本）：

| 投递目标 | 结果 |
|---|---|
| `WM_CHAR` → 顶层窗口 | ❌ 文字丢失 |
| `WM_CHAR` → Edit 子控件 | ✅ 成功 |
| `WM_KEYDOWN` → Edit 子控件 | ✅ 成功 |

工具会自动 `find_input_child()` 递归找 `Edit` / `RichEdit` / `TextField` / `Scintilla` 类控件。
找不到时会警告并退回顶层窗口（可能失败）。

### 3. 焦点不会被抢走

6 次对照实验，含/不含 `WM_ACTIVATE` 合成激活，结果全部 `focus_stolen = False`。

**但有个例外**：极少数程序（游戏）内部会主动抢回焦点，那时需要额外处理——见下方"游戏特殊处理"。

---

## 健壮性设计（重要）

### 依赖缺失不崩，给出安装命令

```powershell
& $py $bg deps
#   MISSING windows-capture (windows_capture)
#   install with:
#     python -m pip install windows-capture
```

任何模块缺失只影响对应功能，其余命令照常工作。

### 截图三级降级

```
WGC（首选，后台可用）
  ↓ 失败（窗口刚创建 / 不支持）
PrintWindow + PW_RENDERFULLCONTENT（后台部分可用）
  ↓ 输出全黑则判定失败
明确报错，不返回黑图冒充成功
```

**黑图检测**：PrintWindow 对 GPU 窗口常返回纯黑，工具会算像素均值，`< 2.0` 判定失败并换下一个后端。

### WGC 启动失败自动重试

刚创建的窗口会报：

```
Failed to convert item to `GraphicsCaptureItem`
```

工具内置 4 次重试，每次退避 0.3–2.0 秒。实测这个错误几乎总能靠重试解决。

### 模板匹配三重策略

同一个按钮在不同分辨率、游戏内缩放比例下像素尺寸不同，游戏画面还会持续变化。
`template_match` 依次尝试**三种方法 × 七个尺度**，取最高分：

| 方法 | 适用 | 说明 |
|---|---|---|
| **原图匹配** `TM_CCOEFF_NORMED` | 静态 UI、窗口、菜单 | 最准，score 通常 1.000 |
| **边缘匹配** `Canny` + 匹配 | 游戏实时 3D 画面 | 忽略光照与粒子动画，只看轮廓 |
| **模糊匹配** `GaussianBlur` + 匹配 | 带发光/渐变的 UI 面板 | 抵抗柔光和过渡 |

返回结果里带 `method` 字段，可以看出是哪一路命中的。

**阈值建议**：

| 场景 | threshold |
|---|---|
| 静态 UI 按钮、窗口控件 | 0.85–0.95 |
| 游戏 UI（实时渲染） | 0.70–0.85 |
| 有大量粒子/闪光 | 0.60–0.75 |
| 同色系容易误匹配 | 0.92+ |

### 实测数据（本机验证）

用虚幻引擎游戏「二重螺旋」实测：

| 项目 | 结果 |
|---|---|
| WGC 截取 2560×1440 实时 3D 场景 | ✅ 成功，画面完整（角色、UI、粒子都在） |
| 窗口/客户区/截图尺寸 | 三者完全一致，offset = (0,0) |
| 静态 UI 元素匹配（Lv.80 文字） | ✅ **score = 1.000** |
| 战斗场景中同一元素匹配 | ⚠️ score 降到 0.703（画面在动） |
| 后台点击投递 | ✅ 成功，`focus_stolen = False` |
| 两张连续截图的差异 | **95.4% 像素不同**（战斗动画+镜头移动） |

**这就是游戏场景的核心难点：画面永远在变。** 应对方式：

1. **只匹配稳定 UI**（血条、按钮、固定图标），不要匹配角色或场景
2. **降低阈值到 0.7**，配合"连续 2-3 帧都命中才确认"
3. **优先用边缘匹配**，它对光照变化免疫
4. **模板裁得越小越稳**（一个小按钮比一大块界面稳定得多）

### 中文路径安全

`cv2.imwrite` 在部分构建下对中文路径静默失败。`save_image()` 检测失败后自动改用 `PIL` 保存。

### 退出码约定

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 执行失败（截图失败、点击投递失败） |
| 2 | 未命中（窗口找不到 / 模板匹配低于阈值） |

脚本可以据此决定是否重试，**不会把失败当成功**。

---

## 游戏特殊处理（原神这类）

### 什么时候模板匹配不够

原神有两类操作，性质完全不同：

| 操作 | 能否 PostMessage | 说明 |
|---|---|---|
| 点 UI 按钮（领奖、邮件、派遣） | ✅ **能** | 纯界面交互 |
| 角色移动 / 转向 | ❌ **不能** | 游戏用 Raw Input 读原始鼠标增量，消息合成无效 |

**移动/转向必须真实输入**，参考 OKGI 的做法：

```python
# 1. 屏蔽用户输入，防止互相打架
user32.BlockInput(True)
# 2. 存光标位置
pos = win32api.GetCursorPos()
# 3. SendInput 相对移动（Raw Input 才认）
SendInput(1, pointer(INPUT(0, MOUSEINPUT(dx, dy, 0, 1, 0, None))), sizeof(INPUT))
# 4. 还原光标
win32api.SetCursorPos(pos)
# 5. 解除屏蔽
user32.BlockInput(False)
```

**这段时间你的鼠标会被锁住**——这是无法避免的代价，必须在使用前告知用户。

### 自适应分辨率

不要硬编码坐标。正确做法：

```powershell
# 相对坐标：按窗口尺寸比例
# 例如"屏幕中心偏下 20%" →
#   x = client_w * 0.5
#   y = client_h * 0.8
```

配合 `find --template` 更稳：模板匹配自带尺度搜索，分辨率变了也能命中。

---

## 常见问题

### `Failed to convert item to GraphicsCaptureItem`

窗口刚创建，合成表面没好。工具会自动重试；手动重试也能成功。

### 截图全黑

WGC 失败降级到了 PrintWindow，而 PrintWindow 对 GPU 合成窗口无用。
检查窗口是否真的存在、是否已最小化到托盘。

### 点击没反应

按顺序排查：

1. `geom` 看坐标映射是否合理
2. `calibrate` 实测校验（需窗口可见）
3. 目标窗口是否接受了 `WM_ACTIVATE`（有些程序要求先激活）
4. 坐标是**客户区**坐标，不是屏幕坐标，也不是截图坐标

### 输入文字没进去

1. 看 `type` 输出的 `input child detected` 是否非 0
2. 若为 `none`，说明该程序没有标准 Edit 控件（游戏、Qt 自绘界面）
3. 这类情况只能用真实键盘

### 窗口找不到

```powershell
& $py $bg list    # 看真实标题
```

注意：标题可能带不可见字符（如 Telegram 的 `‎` LTR 标记），用 `--pid` 更稳。

---

## 边界与诚实说明

**能做到**：
- 后台截图任意窗口（遮挡、最小化、副屏）
- 后台点击 UI 元素，不抢焦点
- 后台输入文字（有标准输入控件的程序）
- 模板匹配定位，支持分辨率缩放

**做不到**：
- **游戏内角色移动/转向**（需真实输入，会锁鼠标）
- **操作 DirectInput 独占模式全屏游戏**（消息合成无效）
- **Linux / macOS**（WGC 是 Windows API）
- **永远保证不抢焦点**（个别程序会主动抢回）

**不要承诺百分之百**。这套技术对常规桌面应用很稳，对游戏是"UI 部分能做，操作部分受限"。
