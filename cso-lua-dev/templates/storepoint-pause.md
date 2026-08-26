# 模板：存点 / 读点 + 暂停

场景：数字键存点、回当前点、回上一点；暂停/继续计时并补偿时间、暂停点还原。

## 协议设计

| 项目 | 设计 |
|---|---|
| 信号 | `5` 存点；`6` 回当前点；`7` 回上一点；`737` 暂停/继续 |
| 同步值 | `State<idx>`（3=暂停）；`numsb<idx>` 存读点文本 |
| player.user | `StoragePoint{x,y,z}` 坐标栈；`N_Storage` 栈指针；`numStorage`/`numBack`；`time_pause`/`position_pause` |

## 核心代码骨架

```lua
-- ===== Game_Fun.lua =====
function StorePoint(player, signal)
    -- 必须落地且非暂停才响应
    if player.velocity.z ~= 0 or Sync[player.index].State.value == 3 then
        return
    end
    local u = player.user
    local px, py, pz = player.position.x, player.position.y, player.position.z

    -- 存点(信号5)：禁止在同一个点重复存
    if signal == 5 then
        local last = u.StoragePointx[u.N_Storage]
        if not (px == last and py == u.StoragePointy[u.N_Storage]
                and pz == u.StoragePointz[u.N_Storage]) then
            u.N_Storage = u.N_Storage + 1
            u.StoragePointx[u.N_Storage] = px
            u.StoragePointy[u.N_Storage] = py
            u.StoragePointz[u.N_Storage] = pz
            u.numStorage = u.numStorage + 1
            Sync[player.index].numsb.value =
                '存点:' .. u.numStorage .. ' 读点:' .. u.numBack
        end
    -- 回当前点(信号6)
    elseif signal == 6 and u.N_Storage > 0 then
        player.velocity = {x = 0, y = 0, z = 0}
        player.position = {x = u.StoragePointx[u.N_Storage],
                           y = u.StoragePointy[u.N_Storage],
                           z = u.StoragePointz[u.N_Storage]}
        u.numBack = u.numBack + 1
        Sync[player.index].numsb.value =
            '存点:' .. u.numStorage .. ' 读点:' .. u.numBack
    -- 回上一点(信号7)
    elseif signal == 7 and u.N_Storage > 1 then
        u.N_Storage = u.N_Storage - 1
        player.velocity = {x = 0, y = 0, z = 0}
        player.position = {x = u.StoragePointx[u.N_Storage],
                           y = u.StoragePointy[u.N_Storage],
                           z = u.StoragePointz[u.N_Storage]}
        u.numBack = u.numBack + 1
        Sync[player.index].numsb.value =
            '存点:' .. u.numStorage .. ' 读点:' .. u.numBack
    end
end

-- 暂停(信号737)：暂停记录位置，继续时还原并补偿暂停时长
function Pause(player, signal)
    if signal ~= 737 or player.velocity.z ~= 0 then return end
    local u = player.user
    local state = Sync[player.index].State.value
    if state == 2 then
        u.pause = true
        u['time_pause'] = Game.GetTime()
        u['position_pause'] = {x = player.position.x,
                               y = player.position.y,
                               z = player.position.z}
        Sync[player.index].State.value = 3
    elseif state == 3 then
        u.pause = false
        -- 时间补偿：开始时刻 + 暂停时长
        u['time_start'] = u['time_start'] + Game.GetTime() - u['time_pause']
        player.position = u['position_pause']
        player.velocity = {x = 0, y = 0, z = 0}
        Sync[player.index].State.value = 2
    end
end
```

```lua
-- ===== game.lua =====
function Game.Rule:OnPlayerSignal(player, signal)
    if Switch_StorePoint == 1 then StorePoint(player, signal) end
    if Switch_Pause == 1 then Pause(player, signal) end
end

-- ===== ui.lua（防连发 + 发信号）=====
time_5, time_6, time_7, time_9 = 0, 0, 0, 0
function UI.Event:OnInput(inputs)
    local t = UI.GetTime()
    if inputs[UI.KEY.NUM4] and t - time_5 > 0.05 then UI.Signal(5); time_5 = t end
    if inputs[UI.KEY.NUM5] and t - time_6 > 0.05 then UI.Signal(6); time_6 = t end
    if inputs[UI.KEY.NUM7] and t - time_7 > 0.05 then UI.Signal(7); time_7 = t end
    if inputs[UI.KEY.NUM9] and t - time_9 > 0.05 then UI.Signal(737); time_9 = t end
end
```

## 注意

- `StoragePoint` 系列表在 `OnPlayerConnect` 里初始化（`u.StoragePointx = {}` 等），否则首次存点报错。
- 暂停必须做**时间补偿**，否则暂停期间计时器继续走。
- 回点前先清速度，避免传送后惯性飞出。
- 防连发阈值 0.05s（20 次/秒），防止按住按键连发信号。
