---
name: AIQuiz
description: AI 智能题库系统设计规范
colors:
  primary: "#165DFF"
  primary-hover: "#4080FF"
  primary-light: "#E8F3FF"
  primary-dark: "#0D47A1"
  success: "#67C23A"
  warning: "#E6A23C"
  danger: "#F56C6C"
  info: "#909399"
  text-primary: "#303133"
  text-regular: "#606266"
  text-secondary: "#909399"
  text-placeholder: "#C0C4CC"
  border-base: "#DCDFE6"
  border-light: "#E4E7ED"
  border-lighter: "#EBEEF5"
  border-extra-light: "#F2F6FC"
  bg-page: "#F5F7FA"
  bg-base: "#FFFFFF"
typography:
  display:
    fontFamily: "Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
  title:
    fontFamily: "Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "2px"
  base: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  base: "16px"
  lg: "20px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.base}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
    rounded: "{rounded.base}"
    padding: "8px 16px"
  card:
    backgroundColor: "{colors.bg-base}"
    rounded: "{rounded.lg}"
    padding: "{spacing.base}"
---

# Design System: AIQuiz

## 1. Overview

**Creative North Star: "The Quiet Command Center"**

这是一个面向教育教研人员的效率工具，不是营销展示页。设计目标是让高频操作路径最短，状态一目了然，减少认知负担。界面应像一本整理得井井有条的工作手册：专业、可信赖、不张扬。

**Key Characteristics:**
- 信息密度适中，表格和列表优先
- 操作反馈即时且明确
- 状态区分清晰（草稿/已发布/已归档）
- 批量操作入口显眼但不打扰
- 深色侧边栏 + 浅色内容区，降低长时间使用视觉疲劳

## 2. Colors

**Primary Blue (#165DFF)** 作为唯一强调色，承担 10% 以内的交互元素。其余界面以中性色为主，保持克制。

### Primary
- **Primary Blue** (#165DFF): 主要操作按钮、链接、选中状态、重要高亮
- **Primary Light** (#E8F3FF): 浅底色用于选中行、标签背景、轻量提示
- **Primary Dark** (#0D47A1): 悬停态、深色强调

### Functional
- **Success Green** (#67C23A): 成功状态、通过、启用
- **Warning Amber** (#E6A23C): 警告、待审核、提醒
- **Danger Red** (#F56C6C): 删除、驳回、错误
- **Info Gray** (#909399): 禁用、次要信息、占位

### Neutral
- **Text Primary** (#303133): 标题、正文
- **Text Regular** (#606266): 正文、表单内容
- **Text Secondary** (#909399): 辅助文字、时间戳
- **Text Placeholder** (#C0C4CC): 输入占位
- **Border Base** (#DCDFE6): 输入框、表格边框
- **Border Light** (#E4E7ED): 分隔线、次要边框
- **Border Lighter** (#EBEEF5): 卡片边框、区块分隔
- **Background Page** (#F5F7FA): 页面底色
- **Background Base** (#FFFFFF): 卡片、表格、表单底色

### Named Rules

**The Restraint Rule.** Primary blue 仅用于需要用户操作或需要关注的元素上。大面积中性色保持界面干净，让内容本身成为焦点。

## 3. Typography

**Body Font:** Source Han Sans SC / PingFang SC / Microsoft YaHei (with system-ui fallback)

**Character:** 专业、清晰、中文优化。无衬线字体确保小字号下的可读性。

### Hierarchy
- **Display** (600, 20px, 1.4): 页面标题、弹窗标题
- **Title** (600, 16px, 1.4): 卡片标题、区块标题
- **Body** (400, 14px, 1.5): 正文、表格内容、表单
- **Label** (400, 13px, 1.4): 辅助说明、时间戳、次要信息

### Named Rules

**The Density Rule.** 默认字号 14px，行高 1.5。数据表格和列表可适当收紧密集显示，但正文不小于 13px，确保长时间阅读不疲劳。

## 4. Elevation

**Flat with tonal separation.** 系统不使用投影创造层级，而是通过背景色差和边框来区分区块。表格、卡片、页面背景通过 #F5F7FA 与 #FFFFFF 的对比自然分层。

### Shadow Vocabulary (sparingly)
- **Ambient** (`0 2px 4px rgba(0,0,0,0.1)`): 仅用于下拉菜单、弹窗等浮动元素
- 其余组件保持扁平，依赖边框和背景色区分

### Named Rules

**The Flat-First Rule.** 默认无阴影。只有需要明确"浮起"语义的元素（下拉、弹窗、日期选择器）才使用极轻阴影。

## 5. Components

### Buttons
- **Shape:** 圆角 4px（`rounded-base`）
- **Primary:** 蓝底白字 (#165DFF)，8px 16px padding，用于主要操作
- **Hover:** 略亮蓝 (#4080FF)，过渡 0.2s
- **Danger:** 红底白字 (#F56C6C)，用于删除、驳回等破坏性操作
- **Ghost/Link:** 无背景，蓝色文字，用于表格行内操作
- **Loading:** 按钮内显示 Loading 图标，文案缩短或隐藏

### Chips / Tags
- **Style:** 浅底色 + 深色文字，圆角 12px（pill 形）
- **Status variants:** Success/Warning/Danger/Info 对应不同背景色
- **Size:** small，高度约 24px

### Cards / Containers
- **Corner Style:** 8px（`rounded-lg`）
- **Background:** #FFFFFF
- **Border:** 1px solid #EBEEF5
- **Shadow:** 无（扁平）
- **Internal Padding:** 16px（`spacing-base`）

### Inputs / Fields
- **Style:** 1px solid #DCDFE6 边框，#FFFFFF 背景
- **Height:** 32px（小）/ 40px（标准）
- **Focus:** 边框变蓝 (#165DFF)，可配合轻量外发光
- **Error:** 边框变红，下方或右侧显示错误信息
- **Disabled:** 背景 #F5F7FA，文字 #C0C4CC

### Navigation
- **Sidebar:** 深色背景 (#001529)，白色文字，当前项高亮
- **Active state:** 左侧 2px 蓝色指示条或整行浅蓝背景
- **Hover:** 浅色背景过渡
- **Header:** 白色背景，阴影分隔，包含面包屑和用户信息

### Tables
- **Header:** 浅灰背景 (#F5F7FA)，深色文字，无底部边框或极浅边框
- **Row:** 白色背景，hover 时 #F5F7FA
- **Border:** 仅水平分隔线，垂直方向依赖列宽和留白
- **Selection:** 选中行 #F5F7FA 或极浅蓝背景

## 6. Do's and Don'ts

### Do:
- **Do** 保持主操作按钮使用 Primary Blue (#165DFF)，次要操作用 Ghost 样式
- **Do** 表格和列表优先使用水平分隔线，减少垂直边框
- **Do** 状态标签使用彩色背景 + 白色/深色文字，保持 pill 形状
- **Do** 删除、归档等不可逆操作使用红色确认框，文案明确说明后果
- **Do** 批量操作入口放在工具栏，与单条操作区分层级

### Don't:
- **Don't** 使用 border-left 或 border-right 大于 1px 的彩色边条作为卡片或列表项的装饰
- **Don't** 使用 gradient text（background-clip: text + gradient）
- **Don't** 大面积使用 Primary Blue，保持它在 10% 以内
- **Don't** 使用玻璃态效果（backdrop-filter blur）作为默认卡片样式
- **Don't** 在每个页面都放 hero 区域或大标题，管理后台不需要
- **Don't** 使用 em dash（—）在文案中，用逗号、冒号或括号替代
- **Don't** 深色模式下使用紫色渐变或霓虹色（如果未来支持深色模式）
