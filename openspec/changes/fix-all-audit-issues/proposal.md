## Why

系统上线前终审发现了多个P0（致命）和P1（严重）问题，必须修复后才能正式商用。主要问题包括：异步任务线程安全隐患、MiniMax Group ID缺失、前端越权风险、AI配置混乱、SQL注入风险、试卷分数计算错误等。

## What Changes

### 致命问题修复 (P0)
1. **异步任务线程安全重构** - 重构AI出题异步任务执行逻辑，使用ThreadPoolExecutor替代asyncio.new_event_loop()，避免高并发下服务崩溃
2. **MiniMax Group ID支持** - 在API调用中添加group_id参数，确保AI出题功能可用
3. **前端权限拦截** - 在API层统一添加权限检查，防止越权访问

### 严重问题修复 (P1)
4. **AI配置加载优化** - 明确配置优先级（环境变量 > 数据库 > 默认值），消除双重加载混乱
5. **SQL注入防护加固** - 对keyword搜索添加特殊字符转义
6. **试卷分数计算修复** - 使用题型配置分数替代硬编码默认值
7. **导出权限校验** - 将导出接口改为需要teacher/admin权限

### 一般问题修复 (P2)
8. **字体路径优化** - 增加多路径回退机制，解决Linux环境中文乱码
9. **难度映射统一** - 抽取为常量文件集中管理
10. **错误处理统一** - 规范化异常传播机制
11. **邮箱枚举防护** - 忘记密码接口统一返回成功信息

### 体验优化 (P3)
12. **批量导入进度优化** - 实现真实进度更新
13. **忘记密码表单修复** - 绑定正确字段

### 合规补充
14. **法律文案完善** - 添加用户协议、隐私政策、免责声明页面及链接

## Capabilities

### New Capabilities
- `legal-pages`: 登录注册页面法律文本（用户协议、隐私政策、免责声明）

### Modified Capabilities
- `ai-question-generation`: AI出题模块 - 添加Group ID支持、优化异步执行
- `auto-paper-generation`: 智能组卷模块 - 修复分数计算
- `authentication`: 认证模块 - 邮箱枚举防护
- `system-security`: 系统安全 - SQL注入防护、前端权限拦截

## Impact

### 后端受影响文件
- `app/routers/ai_templates.py` - 异步任务线程安全
- `app/services/ai_provider.py` - Group ID、配置加载
- `app/routers/questions.py` - SQL注入防护、导出权限
- `app/routers/papers.py` - 分数计算修复
- `app/routers/auth.py` - 邮箱枚举防护
- `app/config.py` - Group ID配置项

### 前端受影响文件
- `src/api/index.js` - 权限拦截
- `src/views/admin/LoginView.vue` - 忘记密码表单、法律文本
- `src/views/admin/RegisterView.vue` - 法律文本
- 新增法律页面组件

### 配置变更
- 环境变量新增 `MINIMAX_GROUP_ID`（可选，兼容无Group ID的API Key）
