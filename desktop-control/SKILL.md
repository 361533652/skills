---
name: desktop-control
description: 直接操作 Windows 桌面——截屏、找窗口、点击、输入中文、按快捷键、读剪贴板、读控件树。用户说"看看屏幕上是什么""帮我点一下""在那个窗口里输入""操作某个软件""自动化这个界面"时使用，不要要求用户截图。
---

# Windows 桌面操控

用户让你"看屏幕""点这里""在那个窗口输入"时用这个。**自己截，别要用户截图。**

## 工具位置

```
%USERPROFILE%\.dsh\tools\ctl.cmd
```

包装器 `ctl.cmd` + 实际逻辑 `dsh-ctl.ps1`，两者放在同一目录。用 `pwsh` 调用，PowerShell 风格参数：

```powershell
$c = "$env:USERPROFILE\.dsh\tools\ctl.cmd"
& $c -Action windows
```

**只调 `.cmd`，不要直接跑 `.ps1`**（会被执行策略拦截：`AuthorizationManager 检查失败`）。

> 首次使用前确认工具存在：`Test-Path "$env:USERPROFILE\.dsh\tools\ctl.cmd"`。
> 这是本机专用工具，不在本仓库内——仓库只放技能说明，不含可执行脚本。

## 动作表

| 目的 | 命令 |
|---|---|
| 列出可见窗口（pid/标题/坐标/是否前台） | `& $c -Action windows` |
| 全屏截图 | `& $c -Action shot -Out E:\path\shot.png` |
| 截单窗口 | `& $c -Action shot -ProcId 1234 -Out ...` |
| 截屏幕区域 | `& $c -Action shot -X 100 -Y 200 -W 800 -H 600 -Out ...` |
| 读控件树（拿精确坐标） | `& $c -Action tree -ProcId 1234 -Limit 60` |
| 读控件文本 | `& $c -Action text -ProcId 1234 -Limit 20` |
| 点击（自动激活窗口） | `& $c -Action click -ProcId 1234 -X 300 -Y 400 [-Double]` |
| 输入文本（支持中文） | `& $c -Action type -ProcId 1234 -Text "你好"` |
| 快捷键（逗号分隔） | `& $c -Action keys -ProcId 1234 -Text "ctrl+s,enter,alt+f4"` |
| 激活窗口 | `& $c -Action focus -ProcId 1234` |
| 启动程序 | `& $c -Action launch -App notepad -AppArgs "C:\a.txt"` |
| 剪贴板 | `& $c -Action clip` / `& $c -Action clip -Set -Text "..."` |
| 虚拟屏幕范围 | `& $c -Action cursor` |

键名：`ctrl alt shift win`、单字母、`f1-f12`、`enter tab esc space backspace delete home end left up right down pgup pgdn`。

## 标准循环

1. `windows` 找目标 pid
2. `shot` 看当前状态（用 `read_image` 打开）
3. 要精确坐标就 `tree`，取控件 `x,y wxh` 算中心
4. `click` / `type` / `keys` 执行
5. **再截图或读剪贴板验证**

**永远验证，不要假设点成功了。**

## 硬性规则

- **不抢用户正在用的前台窗口。** 必须先确认目标不是用户正在打字的那个；会切走时先说一声。用完把焦点还回去。
- **破坏性操作先问。** 删除、发送、支付、关闭未保存文档、改系统设置——即使审批是 never，也要先问。
- **优先非 GUI 路径。** 能命令行/API/文件读写完成的，绝不点界面。GUI 是最后手段。

## 踩过的坑（都实际发生过）

### 1. 截图是缩放的，不能用来估坐标

窗口截图 1919px 宽，但实际屏幕是 2560 物理像素。按截图比例算坐标，点了两次都点偏（一次点到广告，一次点到输入框边缘）。

**必须读 UIA 的 `BoundingRectangle` 拿真实屏幕坐标。** 截图只用于确认视觉状态。

### 2. 浏览器和 QQ 用 GDI 截窗口是全黑

Chromium（Edge/QQ）走 D3D 合成，`BitBlt` 截窗口得到 5 KB 的纯黑图。
- **浏览器**：截屏幕区域，不能截窗口句柄。窗口被遮挡就看不见了。
- **QQ**：可用 `PrintWindow` + flags=2 (`PW_RENDERFULLCONTENT`)，后台也能截到内容。

### 3. `SetCursorPos` 瞬移不触发拖拽

直接跳到下一点，应用只当单击。画图里只留一个小点。
**必须按下后插值移动**，每点停 6-15ms。

### 4. 杀进程前必须核验身份

按 `E:\dsh\*` 粗筛会把 **DSH Desktop 自己**列进去（我误伤过一次）。`-match` 默认不区分大小写，`dsh` 会匹配 `DSH`。
**杀前重新查一次，同时校验 PID 和可执行文件绝对路径。**

### 5. 命令行的查询命令会把自己匹配进去

查"有没有 watchdog 进程"时，查询命令本身带 `watchdog` 字样，结果把自己列出来了。匹配 `-File` 参数，排除 `-Command`。

### 6. 现代 UWP 应用文本框在 UIA 里是 Pane 不是 Edit

新版记事本、设置的输入区读不到内容。这时直接截图看，或者 `keys ctrl+a,ctrl+c` 再读剪贴板。

### 7. 中文输入走 SendInput Unicode

不依赖输入法，直接可用。别试图用 `WM_CHAR` 给 Electron 应用发中文。

## 坐标系

主屏 2560×1440 从 (0,0) 开始；副屏从 x=2560 开始且 **y 为负（-67）**。
截图前先 `cursor` 确认虚拟屏幕范围。
