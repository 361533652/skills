# CSO Studio Lua API 完整参考（汉化版）

> 本文件是 `cso-lua-dev` Skill 的完整 API 参考，对应扩展 `library/` 下的
> `game.lua` / `ui.lua` / `common.lua` / `alias.lua` / `__Doc.lua` 定义。
> 所有注释已汉化，签名与官方一致。编写脚本前先在此查 API，再写代码。

## 0. 通用类型（alias.lua）

```lua
---@class position   -- 方块坐标
---@field x integer
---@field y integer
---@field z integer

---@class velocity   -- 实体速度
---@field x number
---@field y number
---@field z number

---@class eventArg   -- 装置方块事件参数
---@field action "text"|"signal"|"use"|"touch"|"reset"|"password"
---@field value? string|boolean
---@field target? Game.Player

---@class screensize
---@field width integer
---@field height integer

---@alias RGB  { r: integer, g: integer, b: integer }
---@alias RGBA { r: integer, g: integer, b: integer, a: integer }

---@class UI.BoxSetArg   -- UI.Box:Set 参数
---@field x? integer
---@field y? integer
---@field width? integer
---@field height? integer
---@field r? integer
---@field g? integer
---@field b? integer
---@field a? integer

---@class UI.TextSetArg  -- UI.Text:Set 参数
---@field text? string
---@field font? "small"|"medium"|"large"|"verylarge"
---@field align? "left"|"center"|"right"
---@field x? integer
---@field y? integer
---@field width? integer
---@field height? integer
---@field r? integer
---@field g? integer
---@field b? integer
---@field a? integer
```

---

## 1. Common 模块（双端均可）

### 1.1 武器枚举 `Common.WEAPON`

```lua
Common.WEAPON = {
  P228=1, Scout=3, XM1014=5, MAC10=7, AUG=8, DualBeretta=10, FiveSeven=11,
  UMP45=12, SG550Commando=13, Galil=14, FAMAS=15, USP45=16, Glock18C=17,
  AWP=18, MP5=19, M249=20, M3=21, M4A1=22, TMP=23, G3SG1=24,
  DesertEagle50C=26, SG552=27, AK47=28, P90=30, SCAR=31, USAS12=39,
  QBB95=41, MG3=45, DualMP7A1=48, AK47Custom=50, DesertEagle50CGold=56,
  WinchesterM1887=58, M134Minigun=59, F2000=60, WinchesterM1887Gold=63,
  LightningAR1=65, M24=66, DualInfinity=67, DualInfinityCustom=70,
  QBB95AdditionalMag=73, MP7A1ExtendedMag=74, SawedOffM79=75,
  DualInfinityFinal=78, Crossbow=83, USAS12CAMO=88, DoubleBarrelShotgun=90,
  KrissSuperV=95, TAR21=102, BarrettM95=103, DualKriss=105, AN94=107,
  M16A4=108, P90Lapin=110, Volcano=111, MG36=115, Salamander=118,
  LightningSG1=126, Tempest=135, BlackDragonCannon=144, TMPDragon=145,
  MK48=147, FNFNC=160, L85A2=161, AKM=163, HK416=165, LightningAR2=168,
  Ethereal=169, M32MGL=170, BALROGVII=172, OICW=183, TripleBarrelShotgun=192,
  Ripper=193, K3=197, Needler=200, SKULL4=201, BALROGXI=203, AK74U=204,
  PlasmaGun=207, Leviathan=209, UTS15PinkGold=217, CompoundBow=221,
  ARX160=222, GaeBolg=233, Cyclone=235, SPAS12Maverick=239, Aeolis=241,
  PetrolBoomer=249, RailCannon=257, Eruptor=258, Slasher=259, RPG7=275,
  Guillotine=277, CrossbowAdvance=279, FireVulcan=281, JackHammer=284,
  Coilgun=295, DualUZI=302, LaserMinigun=303, M4A1DarkKnight=306,
  AK47Paladin=307, AttackM950=318, MagnumDrill=319,
  DesertEagleCrimsonHunter=329, FlameJackhammer=337, SG552Lycanthrope=338,
  BroadDivine=339, PythonDesperado=373, CHARGER7=377, BOUNCER=381,
  StunRifle=385, DualBerettaGunslinger=395, M249Phoenix=397,
  StarChaserAR=398, M32MGLVenom=400, MG3CSOGSEdition=417,
  ThunderGhostWalker=431, Stinger=432, InfinityLaserFist=440,
  ShiningHeartRod=449,
}
```

> `Common.WEAPON` 文档中没有的武器，可直接把 `InGameID` 整数传给 API
> （完整 ID 参考表见 `library/__Doc.lua` 的 `__Doc.WeaponId`，或
> `data/weapon_trans_20260208.csv` 的 `InGameID` 列）。

### 1.2 函数

```lua
---获取指定武器的 WeaponOption 类（API 文档没有的武器值可传 InGameID 整数）
---@param weaponid Common.WEAPON|integer
---@return Common.WeaponOption
Common.GetWeaponOption(weaponid)

---开启武器背包功能
Common.UseWeaponInven(value: boolean)

---设置保存当前装备中的武器
Common.SetSaveCurrentWeapons(value: boolean)

---设置保存武器背包内容（需先开启 UseWeaponInven）
Common.SetSaveWeaponInven(value: boolean)

---自动执行存档信息加载
Common.SetAutoLoad(value: boolean)

---禁用武器配件功能
Common.DisableWeaponParts(value: boolean)

---禁用武器强化功能
Common.DisableWeaponEnhance(value: boolean)

---游戏开始时不给默认武器
Common.DontGiveDefaultItems(value: boolean)

---击杀队友也按正常击杀处理（不判团队击杀）
Common.DontCheckTeamKill(value: boolean)

---商店使用剧情商店窗口
Common.UseScenarioBuymenu(value: boolean)

---购买枪支需要花钱
Common.SetNeedMoney(value: boolean)

---开枪时用新形态绘制枪口特效（不适用 Scale）
Common.UseAdvancedMuzzle(value: boolean)

---修改开枪时枪口特效大小
Common.SetMuzzleScale(value: number)

---修改被击中时血液特效大小
Common.SetBloodScale(value: number)

---修改子弹命中墙壁等时特效大小
Common.SetGunsparkScale(value: number)

---修改命中判定框大小
Common.SetHitboxScale(value: number)

---鼠标悬停实体(怪物等)时显示轮廓线（仅玩家处于
---Game.Player:SetThirdPersonFixedView 等第三人称模式时生效）
Common.SetMouseoverOutline(value: boolean, color: RGB)

---统一所有主武器单个弹匣价格
Common.SetUnitedPrimaryAmmoPrice(price: integer)

---统一所有副武器单个弹匣价格
Common.SetUnitedSecondaryAmmoPrice(price: integer)

---设置商店武器列表（需开启 UseScenarioBuymenu）
Common.SetBuymenuWeaponList(list: integer[])
```

### 1.3 `Common.WeaponOption` 类

```lua
---@class Common.WeaponOption
---@field weaponid Common.WEAPON|integer  所指武器种类
---@field user table<string, any>         可存任意数据的表
---@field price integer                   武器购买价（需 SetNeedMoney）
---@field damage number                   伤害倍率（与 Game.Weapon 一起用为乘算）
---@field penetration number              穿透力倍率
---@field rangemod number                 距离伤害衰减率倍率
---@field cycletime number                射速倍率
---@field reloadtime number               装填速度倍率
---@field accuracy number                 精准度倍率
---@field spread number                   移动时精准度下降程度倍率

---设置子弹颜色
Common.WeaponOption:SetBulletColor(color: RGB)
```

---

## 2. Game 模块（服务端）

### 2.1 枚举

```lua
---队伍
Game.TEAM = { UNASSIGNED=0, TR=1, CT=2, SPECTATOR=3 }
-- UNASSIGNED 未分配 / TR 恐怖分子 / CT 反恐精英 / SPECTATOR 旁观者

---玩家模型（类）
Game.MODEL = {
  DEFAULT=0,        -- 进入时选择的职业
  SEAL=1,           -- 海豹六队
  GSG9=2, GIGN=3, SAS=4,
  SPETSNAZ=5,       -- 阿尔法特种部队
  GUERILLA=6,       -- 游击队
  PHOENIX=7,        -- 凤凰战士
  ELITE=8,          -- 精英特工
  ARCTIC=9,         -- 北极复仇者
  MILITIA=10,       -- 民兵
  HERO=11,          -- 男英雄
  HEROINE=12,       -- 女英雄
  NORMAL_ZOMBIE=13, -- 普通僵尸
  LIGHT_ZOMBIE=14,  -- 轻型僵尸
  HEAVY_ZOMBIE=15,  -- 重装僵尸
  PHYCHO_ZOMBIE=16, -- 疯狂僵尸
  VOODOO_ZOMBIE=17, -- 巫毒僵尸
  DEIMOS_ZOMBIE=18, GANYMEDE_ZOMBIE=19, STAMPER_ZOMBIE=20,
  BANSHEE_ZOMBIE=21, VENOMGUARD_ZOMBIE=22, STINGFINGER_ZOMBIE=23,
  METATRON_ZOMBIE=24, LILITH_ZOMBIE=25, CHASER_ZOMBIE=26,
  BLOTTER_ZOMBIE=27, RUSTYWING_ZOMBIE=28, AKSHA_ZOMBIE=29,
  SOLDIER_ZOMBIE=30,
  -- 宿主变体（31~48，模型 + 31）：
  NORMAL_ZOMBIE_HOST=31, LIGHT_ZOMBIE_HOST=32, HEAVY_ZOMBIE_HOST=33,
  PHYCHO_ZOMBIE_HOST=34, VOODOO_ZOMBIE_HOST=35, DEIMOS_ZOMBIE_HOST=36,
  GANYMEDE_ZOMBIE_HOST=37, STAMPER_ZOMBIE_HOST=38, BANSHEE_ZOMBIE_HOST=39,
  VENOMGUARD_ZOMBIE_HOST=40, STINGFINGER_ZOMBIE_HOST=41,
  METATRON_ZOMBIE_HOST=42, LILITH_ZOMBIE_HOST=43, CHASER_ZOMBIE_HOST=44,
  BLOTTER_ZOMBIE_HOST=45, RUSTYWING_ZOMBIE_HOST=46, AKSHA_ZOMBIE_HOST=47,
  SOLDIER_ZOMBIE_HOST=48,
}

---武器类型
Game.WEAPONTYPE = {
  NONE=0, KNIFE=1, PISTOL=2, GRENADE=3, SUBMACHINEGUN=4, SHOTGUN=5,
  MACHINEGUN=6, RIFLE=7, SNIPERRIFLE=8, EQUIPMENT=9,
}

---玩家命中判定部位
Game.HITBOX = { HEAD=1, CHEST=2, STOMACH=3, LEFTARM=4, RIGHTARM=5, LEFTLEG=6, RIGHTLEG=7 }

---实体类型
Game.ENTITYTYPE = { ENTITY=0, MONSTER=1, PLAYER=2 }

---怪物类型
Game.MONSTERTYPE = {
  NORMAL0=246, NORMAL1=200, NORMAL2=201, NORMAL3=202, NORMAL4=203,
  NORMAL5=204, NORMAL6=205,          -- 普通僵尸 LV.0~6
  RUNNER0=247, RUNNER1=206, RUNNER2=207, RUNNER3=208, RUNNER4=209,
  RUNNER5=210, RUNNER6=211,          -- 跑者僵尸 LV.0~6
  HEAVY1=244, HEAVY2=245,            -- 重甲僵尸 LV.1~2
  GHOST=1284,                        -- 布袋幽灵
  PUMPKIN=1285,                      -- 南瓜头稻草人
  PUMPKINHEAD=1286,                  -- 南瓜头
  A101AR=1477,                       -- A101AR
  A104RL=1478,                       -- A104RL
}

---实体渲染特效
Game.RENDERFX = { NONE=0, GLOWSHELL=18 }

---武器颜色
Game.WEAPONCOLOR = {
  NONE=0, GREEN=1, WHITE=2, RED=3, BLUE=4, YELLOW=5, ORANGE=6,
}

---第三人称固定视角的射线检测平面
Game.THIRDPERSON_FIXED_PLANE = { GROUND=0, XY=1, XZ=2, YZ=3 }
```

### 2.2 顶层函数

```lua
---查找指定坐标位置的玩家（与区域方块同判定，但只取 1 名玩家）
---@return Game.Player|nil
Game.FindPlayerAt(position)

---获取当前游戏时间
Game.GetTime()  -- @return number

---触发脚本触发器方块
Game.SetTrigger(name: string, value: boolean)

---获取脚本创建的实体
Game.GetEntity(index: integer)  -- @return Game.Entity|nil

---获取随机整数 / 随机实数
Game.RandomInt(min: integer, max: integer)    -- @return integer
Game.RandomFloat(min: number, max: number)    -- @return number

---获取影响本次脚本调用块的玩家/怪物实体
Game.GetTriggerEntity()  -- @return Game.Entity|nil

---获取调用当前函数的脚本调用块
Game.GetScriptCaller()   -- @return Game.EntityBlock|nil

---下一个 OnUpdate 后杀死所有怪物
Game.KillAllMonsters()
```

### 2.3 `Game.Entity`（玩家与怪物的父类）

```lua
---@class Game.Entity
---@field index integer      实体索引
---@field user table<string, any>  可存任意数据的表
---@field health integer     生命值（读写）
---@field maxhealth integer  最大生命值（读写）
---@field armor integer      护甲（读写）
---@field maxarmor integer   最大护甲（读写）
---@field position position  所在方块坐标（读写）
---@field velocity velocity  速度（读写）

Game.Entity:GetEntityType()        -- @return Game.ENTITYTYPE
Game.Entity:IsMonster()            -- @return boolean
Game.Entity:IsPlayer()             -- @return boolean
Game.Entity:ToMonster()            -- @return Game.Monster|nil
Game.Entity:ToPlayer()             -- @return Game.Player|nil
Game.Entity:ShowOverheadDamage(damage: number, playerIndex: integer)
                                   -- 头顶显示伤害；playerIndex=0 对所有人显示
Game.Entity:SetRenderFX(fx: Game.RENDERFX|integer)
Game.Entity:SetRenderColor(color: RGB)
```

### 2.4 `Game.EntityBlock`（工作室装置方块）

```lua
---@class Game.EntityBlock
---@field id integer          装置方块 id
---@field position position   装置方块坐标
---@field onoff boolean       当前 On/Off 状态
---@field OnUse fun(self, player: Game.Player|nil)  玩家使用时回调
---@field OnTouch fun(self, player: Game.Player|nil) 玩家碰到区域装置时回调

Game.EntityBlock.Create(position)      -- @return Game.EntityBlock|nil
Game.EntityBlock:Event(arg: eventArg, index?: integer)  -- 触发装置事件
Game.EntityBlock:OnUse(player)         -- 使用回调（也可自己实现）
Game.EntityBlock:OnTouch(player)       -- 触碰回调（踏板块也在此）
```

### 2.5 `Game.Rule`（游戏规则）

```lua
---@class Game.Rule
---@field name string            规则名（读写，用途不明）
---@field desc string            规则说明（读写，用途不明）
---@field user table<string, any> 任意数据表
---@field respawnable boolean    玩家可重生（读写）
---@field respawnTime number     重生时间秒（读写）
---@field enemyfire boolean      敌队伤害开关（读写）
---@field friendlyfire boolean   友军伤害开关（读写）
---@field breakable boolean      玩家可破坏地图（读写）

-- 事件回调（在 game.lua 中定义，游戏引擎调用）：
Game.Rule:OnPlayerConnect(player)                 -- 玩家连接
Game.Rule:OnPlayerDisconnect(player)              -- 玩家断开
Game.Rule:OnRoundStart()                          -- 回合开始
Game.Rule:OnRoundStartFinished()                  -- 回合开始流程全部结束（地图初始化放这里）
Game.Rule:OnPlayerSpawn(player)                   -- 玩家出生
Game.Rule:OnPlayerJoiningSpawn(player)            -- 选完职业后首次出生
Game.Rule:OnPlayerKilled(victim, killer)          -- 玩家死亡 (killer 可为 nil)
Game.Rule:OnKilled(victim: Game.Entity, killer: Game.Entity|nil)
                                                  -- 玩家或怪物死亡
Game.Rule:OnPlayerSignal(player, signal)          -- 收到 UI.Signal
Game.Rule:OnUpdate(time)                          -- 约 0.1s 一次
Game.Rule:OnPlayerAttack(victim, attacker, damage, weapontype, hitbox) -> integer?
                                                  -- 玩家被攻击；返回实际伤害
Game.Rule:OnTakeDamage(victim, attacker, damage, weapontype, hitbox) -> integer?
                                                  -- 玩家/怪物被攻击；返回实际伤害
Game.Rule:CanBuyWeapon(player, weaponid, weapon) -> boolean?
Game.Rule:CanHaveWeaponInHand(player, weaponid, weapon) -> boolean?
Game.Rule:OnGetWeapon(player, weaponid, weapon)   -- 获得武器
Game.Rule:OnReload(player, weapon, time)          -- 开始装填
Game.Rule:OnReloadFinished(player, weapon)        -- 装填结束
Game.Rule:OnSwitchWeapon(player)                  -- 切换武器
Game.Rule:PostFireWeapon(player, weapon, time)    -- 开火后
Game.Rule:OnGameSave(player)                      -- 保存玩家存档
Game.Rule:OnLoadGameSave(player)                  -- 加载玩家存档
Game.Rule:OnClearGameSave(player)                 -- 清除玩家存档

-- 方法：
Game.Rule:Win(team: Game.TEAM|integer, exit?: boolean)  -- 指定队伍胜利；无 exit 则胜利后结束游戏
Game.Rule:Respawn()        -- 强制所有玩家重生（※复活选角色中的玩家会随机选角色）
Game.Rule:CanSave()        -- 当前地图可否存档（有分组才 true）
Game.Rule:SetGameSave(name: string, value: any)   -- 写分组数据（※2026.04.08 起分组功能不可用）
Game.Rule:GetGameSave(name: string)               -- 读分组数据
```

### 2.6 `Game.Monster`

```lua
---@class Game.Monster : Game.Entity
---@field type Game.MONSTERTYPE|integer  怪物种类
---@field damage integer  怪物伤害实际值
---@field speed number    移动速度倍率
---@field viewDistance number 视野距离实际值
---@field coin integer    击杀获得金币
---@field applyKnockback boolean 是否受击退
---@field canJump boolean 能否跳跃
---@field checkAngle boolean 视野角度实际值

Game.Monster:Create(monstertype, position)
    -- @return Game.Monster|nil；坐标被占用会就近尝试(z 固定)，全不可则 nil
Game.Monster:AttackPlayer(player)   -- 命令攻击玩家（※BOSS 除外）
Game.Monster:AttackTo(position)     -- 移动到该坐标，途中遇敌转攻击
Game.Monster:MoveTo(position)       -- 移动到该坐标，途中不攻击
Game.Monster:Hold(hold: boolean)    -- 原地待命，攻击范围内有敌则攻击
Game.Monster:Stop(stop: boolean)    -- 原地待命，攻击范围内也不攻击
```

### 2.7 `Game.Player`

```lua
---@class Game.Player : Game.Entity
---@field name string           昵称
---@field death integer         死亡次数
---@field team Game.TEAM|integer 队伍（读写）
---@field coin integer          工作室货币（0~10 亿）
---@field model Game.MODEL|integer 当前职业/模型（改僵尸模型会自动卸掉所有武器且无法拾取）
---@field flinch number         硬直倍率（0.0~1.0，默认 1.0，乘算）
---@field knockback number      击退倍率（0.0~3.0，默认 1.0，乘算）
---@field maxspeed number       最大速度倍率（0.0~10.0，默认 1.0，受引擎上限约束）
---@field gravity number        重力倍率（0.0~10.0，默认 1.0，受引擎上限约束）
---@field infiniteclip boolean  弹匣无限（官方无说明，疑似不生效）
---@field OnSpawn fun(self)     出生回调
---@field OnKilled fun(self, killer: Game.Player|nil) 死亡回调
---@field OnAssist fun(self, victim, killer)          助攻回调

Game.Player.Create(index: integer)  -- @return Game.Player|nil；索引从 1 开始
Game.Player:Respawn()               -- 重生
Game.Player:Kill()                  -- 死亡（※有护甲不会一枪死）
Game.Player:Win(exit?: boolean)     -- 胜利；无 exit 则胜利后结束游戏
Game.Player:ShowBuymenu()           -- 显示收藏武器购买菜单
Game.Player:RemoveWeapon()          -- 移除全部武器
Game.Player:SetGameSave(name, value: number|string|boolean)  -- 写玩家存档
Game.Player:GetGameSave(name)       -- @return number|string|boolean|nil
Game.Player:SetFirstPersonView()    -- 第一人称
Game.Player:SetThirdPersonView(minDist, maxDist)  -- 第三人称
Game.Player:SetThirdPersonFixedView(yaw, pitch, minDist, maxDist)
    -- 第三人称固定角度（鼠标指针 + 射线瞄准模式）
Game.Player:SetThirdPersonFixedPlane(plane: Game.THIRDPERSON_FIXED_PLANE)
    -- 固定视角射线平面；GROUND/XY 适合俯视玩法，XZ/YZ 适合横版玩法
Game.Player:ShowWeaponInven()       -- 显示武器背包
Game.Player:ToggleWeaponInven()     -- 开关武器背包
Game.Player:Signal(signal: integer) -- 给该玩家发信号（UI.Event.OnSignal 收到）
Game.Player:SetLevelUI(level: integer, expRate: number)
    -- 显示等级/经验条 UI；expRate 0.0~1.0
Game.Player:SetBuymenuLockedUI(weaponid, uiLocked: boolean, level?: integer)
Game.Player:SetWeaponInvenLockedUI(weaponid, uiLocked: boolean, level?: integer)
Game.Player:GetPrimaryWeapon()      -- @return Game.Weapon|nil
Game.Player:GetSecondaryWeapon()    -- @return Game.Weapon|nil
Game.Player:GetWeaponInvenList()    -- @return Game.Weapon[]（需 UseWeaponInven）
```

### 2.8 `Game.SyncValue` / `Game.Weapon`

```lua
---@class Game.SyncValue
---@field name string  名字
---@field value string|number|boolean  值（读写）
Game.SyncValue:Create(name)  -- 同名即与 UI.SyncValue 同步；已存在则取回

---@class Game.Weapon
---@field user table<string, any>
---@field weaponid Common.WEAPON|integer  武器种类
---@field color Game.WEAPONCOLOR|integer  颜色（读写）
---@field damage number       伤害倍率
---@field speed number        移动速度倍率
---@field knockback number    击退倍率
---@field flinch number       硬直倍率
---@field criticalrate number 暴击概率
---@field criticaldamage number 暴击伤害倍率（0~100）
---@field bloodsucking number 吸血比例（0~100）
---@field infiniteclip boolean 无限弹匣

Game.Weapon.CreateAndDrop(weaponid, position)  -- @return Game.Weapon|nil；掉落在地上
Game.Weapon:GetWeaponType()    -- @return Game.WEAPONTYPE|integer
Game.Weapon:AddClip1(clip: integer)  -- 补充第一种弹匣
```

---

## 3. UI 模块（客户端）

### 3.1 按键枚举 `UI.KEY`

```lua
UI.KEY = {
  NUM1=0, NUM2=1, NUM3=2, NUM4=3, NUM5=4, NUM6=5, NUM7=6, NUM8=7,
  NUM9=8, NUM0=9,
  A=10, B=11, C=12, D=13, E=14, F=15, G=16, H=17, I=18, J=19, K=20,
  L=21, M=22, N=23, O=24, P=25, Q=26, R=27, S=28, T=29, U=30, V=31,
  W=32, X=33, Y=34, Z=35,
  SHIFT=36, SPACE=37, ENTER=38,
  UP=39, DOWN=40, LEFT=41, RIGHT=42,
  MOUSE1=43, MOUSE2=44,
}
```

### 3.2 顶层函数

```lua
UI.ScreenSize()          -- @return screensize {width, height}
UI.PlayerIndex()         -- @return integer 本地玩家索引（同 Game.Entity.index）
UI.GetTime()             -- @return number 客户端时间
UI.Signal(signal: integer)  -- 发信号给服务器（Game.Rule:OnPlayerSignal 收到）
UI.StopPlayerControl(stop: boolean)
    -- 一段时间内禁止移动与攻击；玩家死亡时重置；0~60 秒
```

### 3.3 `UI.SyncValue`

```lua
---@class UI.SyncValue
---@field name string
---@field value number|string|boolean
---@field OnSync fun(self)  同步值变化时回调
UI.SyncValue:Create(name)  -- 与 Game.SyncValue 同名即同步
    -- ex) Game.SyncValue:Create("round") 与 UI.SyncValue:Create("round")
    --     在 Game 修改后，UI 可通过 OnSync 收到
```

### 3.4 `UI.Box` / `UI.Text`

```lua
---矩形 UI 对象（同时最多 1024 个）
UI.Box.Create()            -- @return UI.Box|nil（超限返回 nil）
UI.Box:Show() / Hide() / IsVisible()
UI.Box:Set(arg: UI.BoxSetArg)   -- 改属性（x,y,width,height,r,g,b,a）
UI.Box:Get()                   -- @return UI.BoxSetArg

---文本 UI 对象（同时最多 1024 个；font: small/medium/large/verylarge；align: left/center/right）
UI.Text.Create()           -- @return UI.Text|nil
UI.Text:Show() / Hide() / IsVisible()
UI.Text:Set(setArg: UI.TextSetArg)
UI.Text:Get()              -- @return UI.TextSetArg
```

### 3.5 `UI.Event` 回调（在 ui.lua 中定义）

```lua
UI.Event:OnRoundStart()                        -- 回合开始
UI.Event:OnSpawn()                             -- 本地玩家出生
UI.Event:OnKilled()                            -- 本地玩家死亡
UI.Event:OnInput(inputs: UI.KEY)               -- 按住期间持续触发（inputs 为按键状态数组）
UI.Event:OnUpdate(time: number)                -- 每帧触发（time 为当前游戏时间）
UI.Event:OnChat(text: string)                  -- 玩家发聊天
UI.Event:OnSignal(signal: integer)             -- 收到服务器 signal（Game.Player:Signal 发出）
UI.Event:OnKeyDown(inputs: UI.KEY)             -- 按下瞬间
UI.Event:OnKeyUp(inputs: UI.KEY)               -- 松开瞬间
```

---

## 4. `__Doc` 参考表（仅查表用，勿直接引用）

`library/__Doc.lua` 里的 `__Doc` 表是**说明用参考表**：脚本里不要直接写
`__Doc.MonsterId.NormalZombie1`，请查表得到整数后直接传整数：

```lua
-- 错误：Game.Monster:Create(__Doc.MonsterId.NormalZombie1, {x=1,y=1,z=1})
-- 正确：Game.Monster:Create(200, {x=1,y=1,z=1})
```

VS Code 中输入 `__DocWeapon` / `__DocMonster` / `__DocRenderFX` 可插入对应表。

### 4.1 `__Doc.MonsterId`（怪物 ID 参考）

```lua
NormalZombie1=200 .. NormalZombie6=205   -- 普通僵尸 LV.1~6
RunnerZombie1=206 .. RunnerZombie6=211   -- 跑者僵尸 LV.1~6
NormalZombieA=244 / NormalZombieB=245    -- 重装A / 重装B
NormalZombie0=246 / RunnerZombie0=247    -- 普通 / 跑者 LV.0
Mushroom1=248 / Mushroom2=249 / Mushroom3=250
Slime1=251 / Slime2=687
ChinaMonster1=688 / ChinaMonster2=689    -- 中国士兵1/2
Snowman=763                              -- 雪人
MinionRed=940 / MinionBlue=941           -- 小兵(红/蓝)
HooliganMelee1=1097 / HooliganThrow1=1098 -- 暴徒(近战/远程)
HooliganMelee3=1284 / HooliganMelee4=1285 -- 幽灵 / 南瓜
Mushroom=1286                            -- 南瓜头
BossProtoPhobos=1289                     -- 原型福波斯
A101AR=1477 / A104RL=1478                -- 远程枪械 / 远程火箭
ShelterNormal=1520 / RunnerZombieK1=1521 -- 庇护所普通 / 自爆僵尸
GasTurret=1509                           -- 瓦斯炮塔
NormalZombieK1=1650 .. RunnerZombieK4=1653 -- 王国王僵尸 / 平民僵尸(男1男2女1)
BossAmpSuit=1950 / BossTitan=1951        -- 疯狂机械师 / 堕落泰坦
```

### 4.2 `__Doc.RENDERFX`（渲染特效 ID 参考）

```lua
NONE=0, PULSESLOW=1, PULSEFAST=2, PULSESLOWWIDE=3, PULSEFASTWIDE=4,
FADESLOW=5, FADEFAST=6, SOLIDSLOW=7, SOLIDFAST=8, STROBESLOW=9,
STROBEFAST=10, STROBEFASTER=11, FLICKERSLOW=12, FLICKERFAST=13,
NODISSIPATION=14, DISTORT=15, HOLOGRAM=16, DEADPLAYER=17, EXPLODE=18,
GLOWSHELL=19, CLAMPMINSCALE=20, LIGHTMULTIPLIER=21, FULLCOLOR=22,
DAYLIGHTFULLCOLOR=23
-- 除 22/23 外参考《半条命》RENDERFX
```

### 4.3 `__Doc.WeaponId`

完整武器 ID 参考表（400+ 条目，`library/__Doc.lua` 第 19~831 行）：
`Common.WEAPON` 中没有的武器，从该表查 `InGameID` 整数直接使用。
常用代表值：`P228=1, Scout=3, XM1014=5, MAC10=7, AUG=8, DualBeretta=10,
FiveSeven=11, UMP45=12, SG550Commando=13, Galil=14, FAMAS=15, USP45=16,
Glock18C=17, AWP=18, MP5=19, M249=20, M3=21, M4A1=22, TMP=23, G3SG1=24,
DesertEagle50C=26, SG552=27, AK47=28, P90=30, SCAR=31, ...`
