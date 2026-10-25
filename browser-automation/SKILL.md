---
name: browser-automation
description: 通过 CDP 协议直接驱动浏览器——按页面文字定位元素、点击、填表、读页面内容、后台截图，完全不碰鼠标键盘。用户要操作网页、登录态应用、或 Chromium 系 Electron 软件（VS Code、Discord）时说"在浏览器里点一下""帮我填这个表单""抓这个页面的内容"时使用。
---

# 浏览器自动化（CDP）

比截屏和 UI Automation 都强：**按文本直接定位 DOM 元素，坐标由浏览器自己算，永不点偏。**

## 工具

```
scripts\cdp.py
```

依赖 `websocket-client`（已装）。用 `C:\Python314\python.exe` 跑。

```powershell
$py  = "C:\Python314\python.exe"
$cdp = "scripts\cdp.py"
& $py $cdp open        # 启动带调试端口的 Edge
```

## 命令

| 目的 | 命令 |
|---|---|
| 启动调试实例 | `& $py $cdp open` |
| 列出标签页 | `& $py $cdp targets` |
| 按文字找元素 → 坐标 | `& $py $cdp find "番剧"` |
| **按文字点击** | `& $py $cdp click "登录"` |
| 填输入框 | `& $py $cdp type "占位符文字" "要填的内容"` |
| 读页面全文 | `& $py $cdp text` |
| 执行 JS | `& $py $cdp eval "document.title"` |
| 导航 | `& $py $cdp nav "https://..."` |
| 后台截图 | `& $py $cdp shot out.png` |
| 关闭 | `& $py $cdp close` |

**`find` 输出**：`100,62  <SPAN> w=28 h=22  "番剧"`

## 关键：必须带这两个启动参数

```powershell
--remote-debugging-port=9222
--remote-allow-origins=*        ← 少了这个，WS 握手直接 403
```

新版 Chromium（Edge 156+）会拒绝没有 allow-list 的 WebSocket 连接，报：

```
Rejected an incoming WebSocket connection from the http://localhost origin
```

`cdp.py open` 已经带上了。

## 独立 profile，不干扰你的日常浏览器

`open` 用的是 `%LOCALAPPDATA%\cdp-automation-profile`，**和你日常 Edge 的会话完全隔离**。好处是不影响你正常上网，代价是那个实例**没有你的登录态**。

需要登录态时，先在里面手动登录一次（profile 会保留 cookie）。

## 踩过的坑

### 1. 合成点击会被 SPA 吞掉

`el.click()` 对 B 站（SPAPP）、React Router 这类**无效**——事件被拦截，页面不跳转。

**必须用 CDP 原生鼠标事件**：

```python
sess.send('Input.dispatchMouseEvent', {'type':'mousePressed', 'x':x,'y':y, 'button':'left'})
sess.send('Input.dispatchMouseEvent', {'type':'mouseReleased','x':x,'y':y, 'button':'left'})
```

这是浏览器内部事件，页面无法拒绝。`cdp.py click` 已用这个。

### 2. 同一个词在页面上出现多次

「番剧」在顶部导航、内容区卡片、页脚都有。取错了就点错地方。

排序策略（已内置）：
1. 视口内完整可见的优先
2. 从上到下（`top` 小的优先）
3. 面积小的优先（叶子节点，不是包裹容器）

`find` 会输出候选数量，例如 `(3 candidates)`。

### 3. 隐藏元素会返回 w=0 h=0

响应式页面常有隐藏副本。**过滤条件**：宽高 ≥ 2px、`display≠none`、`visibility≠hidden`、`opacity≠0`，且跳过 `IMG/SVG/CANVAS`（它们没有文字）。

### 4. 按"自身文本"匹配，不要用 innerText

`innerText` 会把所有子元素的文字都算进去，导致匹配到巨大的外层容器。
用**直接子文本节点**拼接（`childNodes` 里 `nodeType===3` 的），才能拿到真正的叶子。

## 决策：什么时候用 CDP，什么时候不用

| 场景 | 用什么 |
|---|---|
| 网页操作（点击/填表/抓取） | **CDP** |
| Electron 应用（VS Code / Discord） | 可能可用，需试探 |
| 原生 Windows 程序 | 用 `desktop-control` 的 UIA |
| 游戏 / Canvas | 用 `screen-ocr` |

## 注意

- **破坏性操作先问**：提交、发布、购买、删除。
- CDP 实例是**独立 profile**，不会带你的登录态，别误以为已登录。
- 用完 `& $py $cdp close` 关掉，别留后台进程。
