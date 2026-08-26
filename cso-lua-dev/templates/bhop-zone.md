# 模板：连跳区域检测（性能优化版）

场景：连跳/滑坡区域判定 —— 落地后未及时起跳、原地连跳、掉出区域时自动回点。
本模板针对常见"每帧全局计数器 + 嵌套函数 + 反复构造表"的**差实现**给出规范写法。

## 与差实现的对比（性能关键）

| 问题（差实现） | 规范做法 |
|---|---|
| 全局计数器 `areaCounter` 跨玩家共享 → 多人互相干扰 | 计数器/状态全部放 `player.user` |
| 函数内嵌套 `function isDown/isIn` → 每次调用重新定义 | 纯函数提升为顶层 |
| 每帧重复构造区域表/多次 `math` | 区域常量定义一次，距离用平方比较 |
| 无法区分玩家与区域 | 区域带 `id`，状态按区域记录 |

## 协议设计

| 项目 | 设计 |
|---|---|
| 信号 | `969` 每帧心跳（UI 发，Game 处理） |
| player.user | `last_land_t` 上次落地时刻；`last_land_x/y` 上次落点；`zone_state` 当前区域状态 |

## 区域配置（Set.lua）

```lua
-- 每个区域: {x1,y1,z1, x2,y2,z2, 回点x,回点y,回点z, 类型}
-- 类型 "bhop" 连跳区(落地后必须起跳) / "slide" 滑坡区(落地立即回点)
JumpZones = {
  { -3, -30, 27, -30, -3, 92, -5, -31, 28, "bhop" },
  -- 可继续添加
}
```

## 检测实现（Game_Fun.lua）

```lua
-- 判断点是否在盒内(含边界收缩 0.5 的容差由调用方决定)
local function pointInBox(px, py, pz, x1, y1, z1, x2, y2, z2)
    local minx, maxx = math.min(x1, x2), math.max(x1, x2)
    local miny, maxy = math.min(y1, y2), math.max(y1, y2)
    local minz, maxz = math.min(z1, z2), math.max(z1, z2)
    return px >= minx and px <= maxx
       and py >= miny and py <= maxy
       and pz >= minz and pz <= maxz
end

-- 距离平方(避免 sqrt)
local function dist2(ax, ay, bx, by)
    local dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy
end

-- 每帧连跳检测: 状态全在 player.user, 无全局计数器
function JumpCheck(player)
    local u = player.user
    local pos = player.position

    -- 粗筛: 先按包围盒快速排除, 命中再细判
    for id, zone in ipairs(JumpZones) do
        local x1, y1, z1, x2, y2, z2 = zone[1], zone[2], zone[3], zone[4], zone[5], zone[6]
        local bx, by, bz = zone[7], zone[8], zone[9]
        local kind = zone[10]

        if pointInBox(pos.x, pos.y, pos.z, x1, y1, z1, x2, y2, z2) then
            -- 滑坡区: 落地立即回点
            if kind == "slide" and player.velocity.z == 0 then
                player.position = {x = bx, y = by, z = bz}
                player.velocity = {x = 0, y = 0, z = 0}
                return true
            end
            -- 连跳区: 需要"落地-起跳"节奏
            if kind == "bhop" then
                local t = Game.GetTime()
                local landing = player.velocity.z == 0
                if landing then
                    -- 刚落地: 检查与上次落点的间距与间隔
                    if u.last_land_x then
                        local d2 = dist2(pos.x, pos.y, u.last_land_x, u.last_land_y)
                        local dt = t - u.last_land_t
                        -- 原地连跳(落点几乎重合) 或 落地滞留过久(断连跳)
                        if d2 <= MinJumpDist2 or dt > 0.1 then
                            player.position = {x = bx, y = by, z = bz}
                            player.velocity = {x = 0, y = 0, z = 0}
                            u.last_land_x, u.last_land_y, u.last_land_t = nil, nil, nil
                            return true
                        end
                    end
                    -- 正常连跳: 记录本次落点
                    u.last_land_x, u.last_land_y, u.last_land_t = pos.x, pos.y, t
                end
            end
            return true -- 在区域内, 结束遍历
        end
    end
    -- 不在任何区域: 清理落点状态
    u.last_land_x, u.last_land_y, u.last_land_t = nil, nil, nil
    return false
end
```

```lua
-- ===== game.lua（接线：只在该玩家有效状态时检测）=====
MinJumpDist2 = 1 -- 最小落点间距平方(可配置)

function Game.Rule:OnPlayerSignal(player, signal)
    if signal == 969 then
        -- 锁血/其它每帧逻辑...
        if Switch_JpArea == 1 then
            -- 暂停/作弊状态跳过检测
            if not (player.user.pause or player.user[1] or player.user[2]) then
                JumpCheck(player)
            end
        end
    end
end
```

## 注意

- **不要**用全局变量记录任何玩家状态；多人时全部用 `player.user`。
- 区域数据是常量表，不要在每帧里重新构造。
- 粗筛先行：`pointInBox` 是最便宜的判断，命中后才算距离/时间。
- 落点状态在离开区域时清理，避免残留误判。
- 需要支持"悬空后传送回该区域起点再继续"等更复杂的规则时，在 `kind` 分支里扩展。
