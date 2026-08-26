# 模板：管理员指令 + 信号协议

场景：聊天命令（如 `stop 3`、`coin 5`、`give 2`）→ 服务器执行管理操作；含权限分级。

## 协议设计

| 项目 | 设计 |
|---|---|
| 上行 | 聊天 `UI.Event:OnChat` → 解析 → `UI.Signal(基数 + 玩家索引)` |
| 下行 | 同步值广播（如 `stopA`、`drop`）；`Game.Player:Signal` 单发 |
| 权限 | `player.user.permission` = `admin` / `normal` / `ban`（连接时从名单判定） |

**信号编码惯例（区间段）：** 用 `基数 + 玩家索引` 编码目标玩家，服务器按区间解析：

```lua
S_stopA  = 1000000  -- stop 区间
S_coin   = 1001000  -- coin 区间
S_give   = 1002000  -- give 区间
S_take   = 1003000  -- take 区间
S_to     = 1004000  -- to 区间
S_get    = 1005000  -- get 区间
S_kill   = 1006000  -- kill 区间
S_rp     = 1007000  -- rp 区间
S_drop   = 1008000  -- drop 区间
S_promote= 1009000  -- promote 区间
S_id     = 8821     -- 查玩家 id
S_f1     = 8822     -- 友伤开关
S_f2     = 8823     -- 敌伤开关
```

## 核心代码骨架

```lua
-- ===== Set.lua（名单配置）=====
Administrator = {'LMH蓝渊'}   -- 高级管理员(可 getweapon 等)
administrator = {'Jay丶CeLng'} -- 普通管理员

-- ===== game.lua（连接时判定权限）=====
function Game.Rule:OnPlayerConnect(player)
    for _, v in ipairs(administrator) do
        if v == player.name then player.user.permission = 'admin'; break end
    end
    if player.user.permission == nil then player.user.permission = 'normal' end
    -- 权限同步给 UI(UI 侧据此显示管理菜单)
    Identity[player.index] = Game.SyncValue:Create('p' .. tostring(player.index))
    Identity[player.index].value = player.user.permission
end

-- ===== Game_Fun.lua（服务器执行）=====
function AdminSignal(player, signal)
    -- 查玩家 id 列表
    if signal == S_id then
        for i, p in pairs(players) do
            if p ~= nil then print(string.format('%-5s', p.index) .. p.name) end
        end
    end
    -- 禁止移动: stop <idx> → 1000000+idx
    if signal > S_stopA and signal < S_coin then
        stopA.value = signal - S_stopA   -- 同步给对应 UI → StopPlayerControl
    end
    -- 发放金币: coin <idx>
    if signal > S_coin and signal < S_give then
        local p = Game.Player:Create(signal - S_coin)
        if p ~= nil and players[p.index] ~= nil then p.coin = p.coin + 1000 end
    end
    -- 处死 / 复活 / 拉回 / 传送同理(按区间)
    if signal > S_kill and signal < S_rp then
        local p = Game.Player:Create(signal - S_kill)
        if p ~= nil and players[p.index] ~= nil then p:Kill() end
    end
    if signal > S_rp and signal < S_drop then
        local p = Game.Player:Create(signal - S_rp)
        if p ~= nil and players[p.index] ~= nil then p:Respawn() end
    end
end

-- ===== game.lua（信号入口，权限校验在 UI 侧 + 服务器侧双保险）=====
function Game.Rule:OnPlayerSignal(player, signal)
    if player.user.permission == 'admin' then AdminSignal(player, signal) end
end
```

```lua
-- ===== UI_Fun.lua（聊天解析 → 信号）=====
function AdminOrder(msg)
    -- 精确匹配用长度校验, 避免子串误匹配
    if msg == 'id' then UI.Signal(S_id) end
    if msg == 'f1' then UI.Signal(S_f1) end
    if msg == 'f2' then UI.Signal(S_f2) end
    local function numAfter(prefix, base)
        if string.sub(msg, 1, #prefix) == prefix then
            local n = tonumber(string.sub(msg, #prefix + 1))
            if n ~= nil then UI.Signal(base + n) end
        end
    end
    numAfter('stop ', S_stopA)
    numAfter('coin ', S_coin)
    numAfter('give ', S_give)
    numAfter('take ', S_take)
    numAfter('to ', S_to)
    numAfter('get ', S_get)
    numAfter('kill ', S_kill)
    numAfter('rp ', S_rp)
    numAfter('drop ', S_drop)
    numAfter('promote ', S_promote)
end

-- ===== ui.lua（聊天入口 + 权限门控）=====
function UI.Event:OnChat(msg)
    if Identity.value == 'admin' then
        AdminOrder(msg)
    end
    -- 普通玩家指令也走这里(如 help)
end
```

## 注意

- 信号编码用**区间 + 索引**，服务器只做一次区间判断即可定位操作，避免几十个 if。
- **权限双端校验**：UI 侧决定"是否发指令"，服务器侧再校验一次（防伪造信号）。
- 字符串解析统一用 `tonumber` + 前缀匹配，替代 `string.find` 的子串误匹配问题。
- 涉及"强制掉线/踢人"等危险操作，务必只给最高权限，且服务器侧二次确认。
