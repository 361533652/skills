# engineering-thinking

资深软件工程师推理框架——让 AI 编码智能体像资深工程师那样"先诊断、再动手"。

## 解决什么问题

AI 编码智能体最常见的失败模式：

1. **过早修改**：看到报错就改，不理解系统就动手
2. **浅层修复**：加空判断压制 NPE，不追根因
3. **编辑循环**：改→失败→改→失败，每轮都离根因更远

本 Skill 通过强制 10 阶段工作流 + 置信度门禁 + 防循环协议解决这些问题。

## 工作流

```
观察 → 理解 → 定位 → 上下文 → 假设 → 取证 → 计划 → 修改 → 验证 → 审查
```

## 触发条件

修 bug、重构、实现功能、代码审查、排查问题等非平凡代码改动时自动触发。

## 文件结构

```
engineering-thinking/
├── SKILL.md                          # 主文件：工作流 + 分流 + 执行约束
├── README.md
└── references/
    ├── workflow.md                   # 10 阶段完整定义
    ├── investigation.md              # 调查技巧 + 根因概率评分
    ├── planning.md                   # 修改计划模板
    ├── code-modification.md          # 代码修改原则
    ├── verification.md               # 验证阶段
    ├── anti-loop.md                  # 防循环协议
    ├── architecture.md               # 架构思维
    └── dev-conventions.md            # 开发规范
```

## 版本

0.1.0
