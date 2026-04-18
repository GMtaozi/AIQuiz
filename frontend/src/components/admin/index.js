// AI考试系统 - 管理组件导出
// 按需导出管理后台通用组件

// 布局组件
export { default as AdminLayout } from './layout/AdminLayout.vue'
export { default as AdminHeader } from './layout/AdminHeader.vue'
export { default as AdminSidebar } from './layout/AdminSidebar.vue'

// 通用组件
export { default as DataTable } from './common/DataTable.vue'
export { default as SearchFilter } from './common/SearchFilter.vue'
export { default as Pagination } from './common/Pagination.vue'
export { default as ConfirmDialog } from './common/ConfirmDialog.vue'
export { default as StatusBadge } from './common/StatusBadge.vue'

// 业务组件
export { default as UserManage } from './business/UserManage.vue'
export { default as ExamManage } from './business/ExamManage.vue'
export { default as QuestionManage } from './business/QuestionManage.vue'
export { default as ScoreManage } from './business/ScoreManage.vue'
