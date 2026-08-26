---
name: cso-lua-dev
description: "CSO Studio（反恐精英 Online 工作室）Lua 脚本开发规范。用户要写/改 CSO 地图脚本（连跳图、闯关图、生化玩法、计时器、存点、自定义功能）或询问 Game/UI/Common API 用法时触发。强制按 project.json 双端结构产出、先设计信号协议再写代码、包含全部 API 参考与性能规范。"
version: 0.1.0
---

# CSO Studio Lua 脚本开发规范（cso-lua-dev）

为 CSO Studio（《反恐精英 Online》工作室模式）编写地图玩法脚本，或修改/扩展现有脚本（如连跳图、闯关图、生化玩法）。本 Skill 提供**完整 API 参考**、**双端架构模型**、**功能开发工作流**与**性能规范**，帮助作者把想法落地为可运行的 Lua 脚本。

**产物结构一律以 `project.json` 为准**，任何实现都必须按该契约拆分到 Game / UI 两侧文件中。

## 何时使用

**触发条件：** 用户提到 CSO Studio / CSO Lua / csolua 脚本、地图玩法开发、连跳图、闯关图、计时器、存点读点、暂停、脚本检测、管理员指令、自定义功能、或询问 `Game.` / `UI.` / `Common.` API 用法时触发。

## 一、基础认知：三个模块与双环境

### 1.1 三个 API 模块各自的职责

| 模块 | 运行位置 | 职责 | 典型用途 |
|---|---|---|---|
| `Game` | **服务端**（房间服务器） | 游戏规则、实体（玩家/怪物/武器/装置方块）、状态机、存档 | 计时/规则/胜负、生成实体、改血量速度、反外挂、记录 |
| `UI` | **客户端**（每个玩家本地） | 按键/聊天/帧事件采集、屏幕 UI（Box/Text）、本地同步值 | 监听按键、显示计时/地速/公告、发送信号给服务器 |
| `Common` | 双端均可 | 全局武器参数、商店/背包/存档开关等杂项 | 武器统一参数、开启武器背包、全局选项 |

**判断功能该放哪一侧：**
- 需要"游戏世界"状态（位置、血量、武器、规则、对所有玩家生效）→ `Game` 侧
- 需要"单机输入/屏幕显示"（按键、聊天、UI 控件、只给本玩家看）→ `UI` 侧
- 双端都要的状态 → 通过**同步值桥**打通（见第二章）

### 1.2 project.json 契约（必须遵守）

`project.json` 声明两侧的加载文件列表与顺序：

```json
{
  "game": ["Set.lua", "Game_Fun.lua", "game.lua", "Set_common.lua"],
  "ui":   ["UI_Fun.lua", "ui.lua", "Set_common.lua"]
}
```

约定（参考社区惯例，产物按此组织）：

| 文件 | 侧 | 职责 |
|---|---|---|
| `Set.lua` | game | **配置**：功能开关、坐标、名单、可调参数（作者改这里，不碰逻辑） |
| `Game_Fun.lua` | game | **函数库**：纯函数与辅助（时间格式化、排序、检测、指令处理），不注册事件 |
| `game.lua` | game | **事件接线**：`Game.Rule`/按钮/实体的事件回调 + 顶层初始化 |
| `UI_Fun.lua` | ui | **函数库**：UI 控件类、聊天解析、格式函数 |
| `ui.lua` | ui | **事件接线**：`UI.Event` 回调 + 顶层初始化 |
| `Set_common.lua` | 双端 | 双端共用的初始化（如 Common 开关、全局表） |

- 两个环境是**完全独立的 Lua 状态**：`game.lua` 里定义的全局变量在 `ui.lua` **不存在**，反之亦然。双端共享数据只能走**信号**或**同名同步值**。
- 每个玩家在 UI 侧运行一份自己的 `ui.lua`；Game 侧只有一份。

## 二、双端通信模型（架构核心）

CSO Studio 的脚本本质上是一个**双端异步消息系统**，所有跨端功能都建立在这两条通道上：

### 2.1 上行：客户端 → 服务器（指令）

```
UI 侧: UI.Signal(信号整数)          -- 任意时刻发送
Game 侧: function Game.Rule:OnPlayerSignal(player, signal)  -- 收到
```

- 信号是**整数**，需要自建协议表（常量命名，如 `S_Pause = 737`）。
- 信号既来自按键/聊天（UI 主动），也来自每帧心跳（见 2.3）。
- 服务器处理完要反馈 → 走下行同步值。

### 2.2 下行：服务器 → 客户端（数据/状态）

```
Game 侧: Game.SyncValue:Create('Time_Real2').value = 12.5
UI 侧:   UI.SyncValue:Create('Time_Real2')  -- 同名即关联
         function 同步值:OnSync() ... end    -- 值变化时回调
```

- **同名即同步**：`Game.SyncValue:Create('xxx')` 与 `UI.SyncValue:Create('xxx')` 使用完全相同的字符串就自动双向同步。
- 每玩家独立的同步值要带玩家标识：`'Time_Real' .. player.index`。
- UI 侧收到 `OnSync` 后更新界面（计时文本、公告、遮罩）。

### 2.3 每帧心跳模式（帧驱动）

```
UI.Event:OnUpdate(time)  -- 每帧触发
  -> 采集按键状态/清理临时状态
  -> UI.Signal(S_Update)  -- 每帧发给服务器
Game.Rule:OnPlayerSignal(player, S_Update)
  -> 每帧逻辑（锁血、地速、区域检测…）
```

- 这是"连跳图"类脚本的常见骨架，但**每帧全量逻辑是性能热点**，必须遵守第四章的优化规范。
- 替代方案：服务器侧可用 `Game.Rule:OnUpdate(time)`（约 0.1s 周期）做低频逻辑，不必全部走帧信号。

### 2.4 推荐的数据/状态组织

- **玩家私有数据**：存在 `player.user`（`table<string, any>`，服务器侧，随玩家存在）。如 `player.user.N_Storage`、`player.user.pause`。
- **按玩家状态机**：用同步值存状态，如 `State = 1 待机 / 2 计时中 / 3 暂停`，所有功能围绕状态机分支。
- **全局常量**：在各自侧的顶层集中定义（信号码、坐标、开关）。
- **跨玩家共享的服务器数据**：服务器内存表（如 `Record`、`players`）+ 同步值广播给 UI。

## 三、完整工作流（门禁驱动，强制）

本 Skill 是**门禁（Gate）驱动流程**：每个阶段都有强制的放行检查，**不通过禁止进入下一阶段**。作者信息不足时**必须提问**，禁止用假设补全需求或跳过协议直接写码。

### 门禁总览

| 门禁 | 名称 | 位置 | 放行条件 | 不通过的处理 |
|---|---|---|---|---|
| Gate 0 | 触发门禁 | 进入本 Skill 时 | 任务是 CSO Studio 脚本开发/修改/API 咨询 | 非相关任务 → 不套用本流程，直接说明 |
| Gate 1 | 需求门禁 | 阶段 0 结束 | 落点/交互/跨端/对象/性能 5 项全部明确 | **必须提问**，不写代码 |
| Gate 2 | 协议门禁 | 阶段 1 结束 | 信号表、同步值、user 字段、状态机已输出 | **禁止编码**，先补协议 |
| Gate 3 | 结构门禁 | 阶段 2 结束 | 按 project.json 分文件产出、API 符号全部存在 | 重构至符合结构 |
| Gate 4 | 交付门禁 | 阶段 3 结束 | 自检清单**全部**通过 | 修正后重新交付 |

### 阶段 0：需求澄清 —— 门禁 Gate 1

**目标：** 确定功能落点、交互方式与边界。
**动作：** 逐项确认下表；任何一项没有明确答案，**必须向作者提问**，禁止自行假设。

| 问题 | 作用 | 缺失时的处理 |
|---|---|---|
| 功能是"游戏世界"行为还是"单机输入/显示"？ | 决定 Game / UI 侧 | 提问 |
| 交互方式：按键 / 聊天 / 地图装置 / 自动触发？ | 决定入口 | 提问 |
| 需要跨端显示或同步吗？ | 决定是否用同步值 | 提问 |
| 对谁生效：单玩家 / 全体 / 指定玩家？ | 决定索引与权限 | 提问 |
| 性能敏感吗（每帧检测类）？ | 决定实现策略 | 按性能敏感处理 |

**输出：** 功能落点结论（Game / UI / 双端）+ 交互入口清单 + 作用对象。
**门禁 Gate 1：** 5 项全部明确 → 放行进入阶段 1；否则停在提问态，不进入阶段 1。

### 阶段 1：协议设计 —— 门禁 Gate 2

**目标：** 先定协议，再写代码（双端脚本最容易出错的就是两侧不一致）。
**动作：** 按顺序产出四件套：

1. **信号表**：列出每个 `UI.Signal(N)` 的用途与编码，检查无冲突、两侧常量一致。
2. **同步值清单**：`Game/UI.SyncValue:Create('名字')`，标注读写方（Game 写 / UI 读，或反之）。
3. **player.user 字段规划**：字段名 + 类型 + 初始化位置（应列出 `OnPlayerConnect` 里的初始化行）。
4. **状态机**（状态驱动类功能必需）：状态迁移图（如 待机→计时中→暂停），注明每个状态下的功能开关。

**输出：** 协议设计文档（可直接对照实现）。
**门禁 Gate 2：** 信号表无冲突、同步值两侧同名、user 字段已规划、状态机已定 → 放行；任一缺失 → 补齐后再编码，禁止带协议缺口进入阶段 2。

### 阶段 2：实现与接线 —— 门禁 Gate 3

**目标：** 按 project.json 契约分文件产出，每个文件职责单一。
**动作：**

1. 新增可调参数 → `Set.lua`（加开关/坐标/名单，注释说明）。
2. 纯函数/检测/格式化 → `Game_Fun.lua` 或 `UI_Fun.lua`。
3. 事件回调与初始化 → `game.lua` / `ui.lua`。
4. 双端公共初始化 → `Set_common.lua`。
5. 双端都要引用的辅助类（如 `SyncF`）→ **两侧各定义一份**（独立 Lua 状态）。

**门禁 Gate 3：** 产物结构符合 project.json 约定；代码里引用的每个 `Game.` / `UI.` / `Common.` 符号都已在 `api-reference.md` 中核对存在；无未定义全局变量 → 放行；否则修复后进入阶段 3。

### 阶段 3：交付自检 —— 门禁 Gate 4

**目标：** 交付前逐项核对，**全部通过才允许交付**。
**动作：** 逐项检查并记录结果：

- [ ] 代码引用的每个 `Game.` / `UI.` / `Common.` 符号都在 API 参考中存在？
- [ ] 信号码与同步值名字在两侧完全一致？
- [ ] `player.user` 字段已在 `OnPlayerConnect` 初始化？
- [ ] 每帧执行的逻辑做到最简（第四章性能规范）？
- [ ] 回调内没有嵌套定义函数？
- [ ] 没有引用未定义的全局变量？
- [ ] 危险操作（如对不存在武器 ID 调 `Common.GetWeaponOption`）有 `pcall` 或判空保护？
- [ ] 与阶段 1 协议一致（信号表/同步值/状态机无漂移）？

**门禁 Gate 4：** 全部勾选 → 交付并附"实现说明 + 协议对照"；任一未通过 → 修正后重新走阶段 3，**禁止带未通过项交付**。

## 四、编码规范与性能（重要）

### 4.1 性能：区域/碰撞类检测

**反例（性能差，来自真实案例）：** 每帧对每个玩家执行多次函数嵌套、内部定义子函数、用全局计数器跨玩家计数、频繁 `math.sqrt`。

**规范做法：**
- 状态（计数器、上次落点、时间戳）一律放 `player.user.*`，**禁止用全局变量跨玩家共享**。
- 距离比较用**平方**避免 `math.sqrt`：`dx*dx + dy*dy <= dist*dist`。
- 粗筛优先：先做包围盒快速排除，再做精确判断；能提前 `return` 就提前。
- 区域数据写成常量表（`Set.lua`），不要在函数体内重复构造表。
- 每帧只做必要计算；能 0.1s 一次的就别每帧做（用 `Game.Rule:OnUpdate`）。

### 4.2 结构

- **禁止在事件回调/函数内部 `function` 定义另一个函数**（每次调用都重新定义，且依赖调用顺序）。把嵌套函数提升为顶层，或做成方法/闭包工厂。
- 顶层初始化（同步值、按钮、全局表）放在文件开头集中完成。
- 按 `project.json` 分文件，不把所有逻辑塞进 `game.lua`。

### 4.3 健壮性

- 引用 API 前确认符号存在（对照第五章）。
- 用 `pcall` 包裹"可能对无效 ID 操作"的调用（如 `Common.GetWeaponOption(不存在ID)`）。
- 枚举值用常量（`Game.TEAM.CT`），不要写裸数字。
- 字符串比较注意 `string.find` 的子串误匹配：精确匹配用 `#msg == #'help'` 之类长度校验。

## 五、API 速查（常用；完整参考见 api-reference.md）

> 完整 API（含全部枚举、字段、事件回调签名、`__Doc` 参考表）在 **`api-reference.md`**，需要时加载。以下是最高频的速查。

### 5.1 服务器事件回调（game.lua 里定义）

| 回调 | 时机 | 常用签名 |
|---|---|---|
| `Game.Rule:OnPlayerSignal(player, signal)` | UI 发信号 | 信号分发中枢 |
| `Game.Rule:OnPlayerConnect(player)` / `OnPlayerDisconnect(player)` | 进出房 | 初始化/清理 `player.user` |
| `Game.Rule:OnPlayerSpawn(player)` / `OnPlayerJoiningSpawn(player)` | 复活 / 首次出生 | 重置、视角 |
| `Game.Rule:OnPlayerKilled(victim, killer)` | 玩家死亡 | |
| `Game.Rule:OnUpdate(time)` | 约 0.1s | 低频服务器逻辑 |
| `Game.Rule:OnGameSave(player)` / `OnLoadGameSave(player)` / `OnClearGameSave(player)` | 存档 | `player:SetGameSave/GetGameSave` |
| `Game.Rule:OnGetWeapon(player, weaponid, weapon)` | 获得武器 | 反外挂/改武器 |
| `Game.Rule:OnSwitchWeapon(player)` / `PostFireWeapon(player, weapon, time)` | 切枪/开火后 | |
| `button:OnUse(player)` / `button:OnTouch(player)` | 使用/触碰装置方块 | 计时开始/结束 |

### 5.2 客户端事件回调（ui.lua 里定义）

| 回调 | 时机 | 常用签名 |
|---|---|---|
| `UI.Event:OnInput(inputs)` | 按键**持续** | `inputs[UI.KEY.W] == true` |
| `UI.Event:OnKeyDown(inputs)` / `OnKeyUp(inputs)` | 按键按下/松开 | 单次触发 |
| `UI.Event:OnChat(text)` | 聊天 | 解析文字命令 |
| `UI.Event:OnUpdate(time)` | 每帧 | 帧驱动、`UI.Signal` |
| `UI.Event:OnSpawn()` | 本地玩家复活 | 重置 UI |
| `UI.Event:OnSignal(signal)` | 服务器发来 signal | 下行指令 |
| `SyncValue:OnSync()` | 同步值变化 | 刷新界面 |

### 5.3 高频函数速查

```lua
-- Game 侧
Game.GetTime()                          -- 服务器时间(秒)
Game.EntityBlock.Create({x,y,z})        -- 创建装置方块(按钮)
Game.SyncValue:Create('name')           -- 同步值
Game.Player:Create(index)               -- 按索引取玩家
player.position / player.velocity       -- 坐标/速度(表, 可整体赋值)
player:Kill() / player:Respawn() / player:RemoveWeapon()
player:SetFirstPersonView() / SetThirdPersonView(min,max)
player:SetThirdPersonFixedView(yaw,pitch,minDist,maxDist)
player:SetThirdPersonFixedPlane(Game.THIRDPERSON_FIXED_PLANE.XY)
player:SetGameSave('k', v) / player:GetGameSave('k')
Game.Weapon.CreateAndDrop(Common.WEAPON.AWP, {x,y,z})

-- UI 侧
UI.Signal(N)                            -- 发信号给服务器
UI.ScreenSize()                         -- {width, height}
UI.GetTime()                            -- 客户端时间
UI.PlayerIndex()                        -- 本地玩家索引
UI.StopPlayerControl(true/false)        -- 禁/允移动攻击
UI.Box.Create() / UI.Text.Create()      -- UI 控件
UI.Box:Set({x,y,width,height,r,g,b,a})  -- 属性(同 Text:Set 加 text/font/align)
UI.SyncValue:Create('name')             -- 与 Game 同名即同步
```

### 5.4 常用枚举速查

```lua
Game.TEAM.UNASSIGNED / TR / CT / SPECTATOR
Game.WEAPONTYPE.NONE/KNIFE/PISTOL/GRENADE/SUBMACHINEGUN/SHOTGUN/MACHINEGUN/RIFLE/SNIPERRIFLE/EQUIPMENT
Game.ENTITYTYPE.ENTITY / MONSTER / PLAYER
Game.RENDERFX.NONE / GLOWSHELL
Game.WEAPONCOLOR.NONE/GREEN/WHITE/RED/BLUE/YELLOW/ORANGE
Common.WEAPON.USP45 / Glock18C / Scout / AWP / M249 / FAMAS / P90 / AK47 / M4A1 / ...
UI.KEY.W/A/S/D/SHIFT/SPACE/ENTER/UP/DOWN/LEFT/RIGHT/MOUSE1/MOUSE2/NUM0..NUM9/B/V/...
```

## 六、参考案例（ISWhiteFirJump）

已有案例 `ISWhiteFirJump`（白杉连跳图）可作为**结构参考**，但其实现**并非规范**。取长弃短：

**可借鉴（好的模式）：**
- 信号协议表集中定义（`S_Pause=737`、`S_Update=969`…）+ 聊天/按键 → 信号 → 服务器分发的完整链路。
- 同名同步值桥（`Time_Real`/`State`/`numsb` 按玩家索引命名）+ `OnSync` 刷新 UI。
- 玩家状态机（1 待机 / 2 计时中 / 3 暂停）驱动存点/暂停/回点。
- 双端各一份 `SyncF` 辅助类封装同步值。

**不规范的实现（编写新代码时避免）：**
- ❌ 连跳检测用**全局计数器** `areaCounter` 跨玩家计数 → 多人互相干扰（应放 `player.user`）。
- ❌ 在 `StorePoint` 函数内部 `function PlayerModel` 嵌套定义 → 依赖调用顺序、开关关闭即报错。
- ❌ `Inn()` 恒返回 `true`，实际靠内部定义的全局 `isDown/isIn` 生效 → 脆弱。
- ❌ 引用未定义全局（`PostFireWeapon` 里传 `weaponid`、`UI.PlayerIndex(index)` 传 `index`）→ 恰好"能跑"但错误。
- ❌ 每帧信号 969 里做全套重型逻辑 → 人多时性能差。

## 七、模板索引（templates/）

按需加载对应模板，套用其结构再改参数：

| 模板 | 场景 | 文件 |
|---|---|---|
| 计时通关 + 纪录排行 | 起点/终点按钮计时、结算、排行榜 | `templates/timer-and-record.md` |
| 存点/读点 + 暂停 | 数字键存点回点、暂停补偿时间 | `templates/storepoint-pause.md` |
| 连跳区域检测（性能优化版） | 连跳/滑坡区域判定与回点 | `templates/bhop-zone.md` |
| 管理员指令 + 信号协议 | 聊天命令 → 信号 → 服务器执行 | `templates/admin-signal.md` |
