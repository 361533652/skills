# 模板：计时通关 + 纪录排行

场景：起点/终点装置方块计时，通关结算耗时、存读点次数、所用武器，维护排行榜与金币奖励。

## 协议设计

| 项目 | 设计 |
|---|---|
| 信号 | 无（按钮触发）；每帧心跳 `S_Update=969` 用于同步计时 |
| 同步值 | `State<idx>` 1待机/2计时中/3暂停；`Time_Real<idx>` 实时耗时；`numsb<idx>` 存读点文本 |
| player.user | `time_start` 开始时刻；`numStorage`/`numBack`；`Weapon` 记录所用武器 |

## 文件与结构

- `Set.lua`：`Score`（及格线）、起点/终点坐标、`Switch_Timer`
- `Game_Fun.lua`：`SyncF` 类、时间格式化、`Record_Rank`/`Update_Record`
- `game.lua`：按钮 `OnUse`、`OnPlayerConnect` 初始化、`OnPlayerSignal(969)` 同步
- `UI_Fun.lua`：`UI_Timer`/`UI_Win` 控件
- `ui.lua`：`Sync.*:OnSync` 刷新

## 核心代码骨架

```lua
-- ===== Set.lua =====
Score = 1000000 -- 及格线(耗时折算分)

-- ===== Game_Fun.lua =====
-- 双端各定义一份 SyncF(独立 Lua 状态)
SyncF = {}
function SyncF:Create(o, player)
    o = o or {}
    setmetatable(o, self); self.__index = self
    o.Time_Real = Game.SyncValue:Create('Time_Real' .. tostring(player.index))
    o.State     = Game.SyncValue:Create('State' .. tostring(player.index))
    o.numsb     = Game.SyncValue:Create('numsb' .. tostring(player.index))
    return o
end
function SyncF:Initialize()
    self.Time_Real.value = 0
    self.State.value = 1
    self.numsb.value = ''
end
-- 时间格式化(时.分.秒.毫秒)
function transform_1(n)
    local hours = math.floor(n / 3600)
    local minutes = math.floor(n / 60) - hours * 60
    local seconds = math.floor(n) - (hours * 3600 + minutes * 60)
    local _, a = math.modf(n)
    return string.format('%02d.%02d.%02d.%02d', hours, minutes, seconds, math.floor(a * 100))
end

-- ===== game.lua =====
if Switch_Timer == 1 then
    button1 = Game.EntityBlock.Create({x = 起点坐标})
    button2 = Game.EntityBlock.Create({x = 终点坐标})
end
Sync = {}; Record = {}; numrecord = 0

function Game.Rule:OnPlayerConnect(player)
    player.user['time_start'] = 0
    player.user.numStorage = 0; player.user.numBack = 0
    Sync[player.index] = SyncF:Create(nil, player)
    Sync[player.index]:Initialize()
end

-- 开始按钮
if Switch_Timer == 1 then
    function button1:OnUse(player)
        Sync[player.index].State.value = 2
        player.user['time_start'] = Game.GetTime()
        player.user.numStorage = 0; player.user.numBack = 0
    end
    -- 结束按钮
    function button2:OnUse(player)
        if Sync[player.index].State.value == 2 then
            numrecord = numrecord + 1
            Record[numrecord] = {
                Time = Game.GetTime() - player.user['time_start'],
                player = player,
                numStorage = player.user.numStorage,
                numBack = player.user.numBack,
                Weapon = player.user.Weapon,
            }
            print('||耗时 ' .. transform_1(Record[numrecord].Time) .. '||')
            Time_Win.value = Record[numrecord].Time   -- 广播给 UI
            Sync[player.index].State.value = 1
        end
    end
end

-- 每帧同步耗时(UI 每帧发 969，这里按 1 秒节流)
function Game.Rule:OnPlayerSignal(player, signal)
    if signal == 969 and Sync[player.index].State.value == 2 then
        if Game.GetTime() - player.user['time_dy'] >= 1 then
            Sync[player.index].Time_Real.value =
                Game.GetTime() - player.user['time_start']
            player.user['time_dy'] = Game.GetTime()
        end
    end
end
```

## 注意

- 按钮对象只在 `Switch_Timer == 1` 时创建，其 `OnUse` 也需在同一 if 内定义。
- 排行榜排序用冒泡排序（数据量小），注意 `Record[i].player` 判空。
- 金币奖励写在结算分支：`if 折算耗时 <= Score then ... end`。
