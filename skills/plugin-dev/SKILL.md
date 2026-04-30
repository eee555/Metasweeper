---
name: plugin-dev
description: >-
    Meta-Minesweeper 插件系统开发专家。当你需要创建插件、编写插件代码、了解插件架构、调试插件问题、
    使用 BasePlugin API、订阅事件、发送指令、跨线程 GUI、配置系统、插件模板，或用户提到
    "插件"、"plugin"、"创建插件"、"开发插件"、"插件开发"、"plugin_dev"、"baseplugin"、
    "插件管理器"、"plugin manager"、"插件模板"、"plugins 目录" 时使用此 skill。
    涵盖架构概览 (architecture.md)、创建流程 (creating.md)、渐进式知识体系 (level-1 ~ level-6)、
    问题诊断 (troubleshooting.md)、最佳实践 (best-practices.md)、代码模板 (assets/templates/)
    和 CLI 工具 (scripts/create_plugin.py)。
---

# Meta-Minesweeper 插件开发助手

你是一个专业的 Meta-Minesweeper 插件开发助手，熟悉插件系统的架构、API 和最佳实践。

## 何时使用本 Skill

**必须调用本 skill 的场景：**

- 创建/生成/脚手架一个新的插件
- **编写或修改任何插件代码** — 生成代码前必须先读取相关 references 和模板，确保 API 用法、继承关系、线程安全、导入路径等完全符合项目规范，禁止凭记忆编写
- 解答插件架构、API、事件系统、跨线程 GUI、配置系统等问题
- 排查插件加载失败、事件未触发、GUI 崩溃、导入错误等故障
- 查找插件模板代码或插件开发规范

**不需要调用的场景：**

- 项目中与插件系统无关的通用 Python 编程问题

## 知识体系索引

按需读取以下文件，不要一次性全部读取：

## 场景化指南

### 1. 创建新插件

**读取文件**:

- [references/creating.md](references/creating.md) - 交互流程指导

### 2. 订阅游戏事件

**读取文件**:

- [references/level-2-events.md](references/level-2-events.md) - 事件订阅/过滤机制

### 3. 发送指令控制主进程

**读取文件**:

- [references/level-4-control.md](references/level-4-control.md) - 发送指令控制主进程

### 4. 跨线程 GUI 操作

**读取文件**:

- [references/level-3-threading.md](references/level-3-threading.md) - 跨线程 GUI 安全

### 5. 使用配置系统

**读取文件**:

- [references/level-6-config.md](references/level-6-config.md) - 配置系统
  **参考模板**:
- [assets/templates/with-config.py](assets/templates/with-config.py)

### 6. 服务注册与发现

**读取文件**:

- [references/level-5-service.md](references/level-5-service.md) - 服务注册/发现

### 7. 了解整体架构

**读取文件**:

- [references/architecture.md](references/architecture.md) - 架构概览

### 8. 排查插件问题

**读取文件**:

- [references/troubleshooting.md](references/troubleshooting.md) - 问题诊断
  **聚焦问题**: 文件位置、命名规则、基类继承、线程安全、导入依赖

### 9. 代码规范与调试

**读取文件**:

- [references/best-practices.md](references/best-practices.md) - 代码规范/性能/调试
