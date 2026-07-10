# PlantUML 时序图生成规范

给定代码（diff、文件或仓库），为每个入口方法/函数生成完整的 PlantUML 时序图。

## 一、识别链路

### 1.1 判断项目类型

- **后端项目**（存在 `pom.xml`、`build.gradle`、`*.java`）：链路入口 = Facade / Controller / Handler 的**每个公开方法**
- **前端项目**（存在 `package.json`，不存在 `pom.xml`/`build.gradle`）：链路入口 = 页面组件 / 自定义 hooks / API 请求函数 / 路由处理函数 / 事件处理器

### 1.2 粒度要求

- 以**单个方法/函数**为单位，不是类/文件级别
- 一个类有 N 个需要分析的方法 = N 条链路 = N 张图
- 结构高度相似的方法（如多个 delete 逻辑几乎一样）可归并为一张通用图，但必须在输出中显式声明归并关系

### 1.3 输出链路清单

画图前先列出所有链路：

| 序号 | 所属模块 | 方法/函数名 | 操作类型 | 独立画图 | 归并到 |
|------|---------|------------|---------|---------|-------|

统计行：`共 N 条链路，独立图 M 张，归并图 K 张，合计 M+K 张`

## 二、先写文字逻辑，后画图

**严格禁止跳过文字描述直接画图。**

对每条链路，先用文字完整描述执行逻辑，必须覆盖：

1. 方法入口：谁调用、传入什么参数
2. 执行步骤：按代码顺序逐步描述
3. **每一个**条件分支（if/else/switch）：条件的业务含义 + 各分支逻辑
4. **每一个**异常处理（try/catch）：捕获什么、怎么处理
5. **每一个**提前返回（return/throw）：触发条件、返回什么
6. 最终返回：正常流程的返回结果

写完后回到代码逐行比对，确认无遗漏分支，再画图。

## 三、PlantUML 生成规范

### 3.1 参与者声明（必须显式声明，附中文角色名）

```
participant RealClassName as "中文角色名\n(职责说明)"
```

后端典型参与者：

```
actor Caller as "调用方\n(上游服务)"
participant Controller as "控制层\n(XxxController)"
participant Service as "业务服务\n(XxxServiceImpl)"
participant Repository as "数据访问层\n(XxxMapper)"
participant Cache as "缓存服务\n(Redis)"
participant MQ as "消息队列\n(MetaQ)"
participant ExternalAPI as "外部服务\n(服务说明)"
database DB as "数据库\n(MySQL)"
```

前端典型参与者：

```
actor User as "用户\n(页面操作)"
participant Page as "页面组件\n(XxxPage.tsx)"
participant Hook as "业务Hook\n(useXxx)"
participant Store as "状态管理\n(Redux/Zustand)"
participant API as "API请求层\n(api/xxx.ts)"
participant BFF as "BFF服务\n(后端接口)"
participant Storage as "本地存储\n(localStorage)"
```

**禁止**只写英文类名不加中文说明。

### 3.2 箭头标注（中文动作描述优先）

```
A -> B : 中文动作描述\n(methodName)
```

- 禁止只写 `methodName(param1, param2)`
- 必须让读者先理解"在做什么"，括号里附方法名作为代码索引

### 3.3 条件分支（必须用中文写业务含义）

```
alt 订单状态为已支付（status == PAID）
  A -> B : 执行退款流程
else 订单未支付
  A -> B : 直接关闭订单
end
```

- `alt` 后必须是中文业务含义，代码表达式可附在括号里
- 禁止写 `alt status == PAID`

### 3.4 流程控制关键字

| 场景 | 语法 | 说明 |
|------|------|------|
| 条件分支 | `alt 条件 / else 条件 / end` | 每个 if/else 都要画 |
| 可选步骤 | `opt 条件说明` | 可能执行也可能不执行 |
| 循环 | `loop 循环条件` | for/while |
| 提前退出 | `break 退出条件` | 提前 return/throw |

### 3.5 阶段分隔

```
== 参数校验 ==
...
== 核心处理 ==
...
== 结果返回 ==
```

按业务阶段切分，阶段名用中文。

### 3.6 注释标注

```
note right of Service
  这里需要加锁防止并发重复提交
  lockKey = "order:" + orderId
end note
```

- 在关键步骤旁标注**为什么要做这步**、数据怎么流转
- 可以引用代码变量/方法名，但必须附中文解释
- 禁止只贴代码不解释

### 3.7 语法兼容性（强制）

**禁止使用以下语法**（渲染环境不兼容会导致图片生成失败）：

- `[->` `[-->` `<-]` `<--]`（外部参与者 boundary 语法）
- `?->` `->?`（未广泛支持的语法）

所有交互对象必须用 `participant` 或 `actor` 显式声明后再使用。表示外部系统时：

```
participant ExternalSystem as "外部系统\n(说明)"
```

### 3.8 总原则优先级

1. **完整性第一**：不漏任何一个分支、异常、提前返回
2. **可读性第二**：中文标注让非开发人员也能看懂
3. **兼容性第三**：只使用广泛支持的基础语法

## 四、自检清单

每张图画完后逐项检查：

- [ ] 文字描述中的每个条件分支是否都用 `alt/opt/break` 画了？
- [ ] 每个异常处理（try/catch）是否都体现了？
- [ ] 每个提前返回是否都画了？
- [ ] 参与者是否都有中文角色名和职责说明？
- [ ] 箭头标注是否都有中文动作描述？
- [ ] alt 条件是否用中文写清了业务含义？
- [ ] note 注释是否解释了关键步骤的业务原因（不是只贴代码）？
- [ ] 是否使用了 `== 阶段名 ==` 分隔业务阶段？
- [ ] 是否存在 `[->` `<-]` `?->` 等不兼容语法？
- [ ] 图的数量是否 >= 链路清单中的预期数量？

**任一项不通过，必须修正后再输出。**
