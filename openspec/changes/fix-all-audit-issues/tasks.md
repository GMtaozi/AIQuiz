## 1. P0 致命问题修复

- [x] 1.1 重构 ai_templates.py 异步任务执行逻辑，使用 asyncio.run() 替代 asyncio.new_event_loop()
- [x] 1.2 在 config.py 添加 MINIMAX_GROUP_ID 配置项（已完成）
- [x] 1.3 在 ai_provider.py 的 _call_minimax 中添加 group_id 参数
- [x] 1.4 在 src/stores/auth.js 添加 hasPermission 权限检查函数

## 2. P1 严重问题修复

- [x] 2.1 重构 ai_provider.py 配置加载，明确优先级（环境变量 > 数据库 > 默认值）
- [x] 2.2 在 questions.py 的 keyword 搜索添加特殊字符转义（% 和 _）
- [x] 2.3 修复 papers.py 第1181行分数计算（代码已正确使用 type_scores）
- [x] 2.4 将 questions.py 导出接口改为 require_teacher_or_admin 权限

## 3. P2 一般问题修复

- [x] 3.1 优化 papers.py 字体路径检测，添加跨平台字体路径（Windows/macOS/Linux）
- [x] 3.2 在前端创建 constants.js 统一管理难度和题型映射常量
- [x] 3.3 统一 hybrid_question_generator.py 的错误处理规范化（无异常捕获需修复）
- [x] 3.4 修复 auth.py 忘记密码接口，统一返回成功信息防枚举

## 4. P3 体验优化

- [ ] 4.1 优化批量导入进度显示（需后端支持才能实现真实进度）
- [x] 4.2 修复 LoginView.vue 忘记密码表单字段绑定（email 而非 username）

## 5. 合规补充

- [x] 5.1 在 LoginView.vue 登录页面添加免责声明、用户协议和隐私政策
- [x] 5.2 在 RegisterView.vue 注册页面添加用户协议和隐私政策链接
- [x] 5.3 在 LoginView.vue 和 RegisterView.vue 添加法律文本弹窗
- [x] 5.4 在 papers.py 导出功能添加版权水印到页脚

## 6. 测试验证

- [ ] 6.1 验证异步任务在高并发下稳定运行
- [ ] 6.2 验证 AI 出题功能正常调用 MiniMax API
- [ ] 6.3 验证权限拦截器正常工作
- [ ] 6.4 验证 SQL 注入防护生效
- [ ] 6.5 验证导出分数计算准确
- [ ] 6.6 验证 Word/PDF 中文显示正常
