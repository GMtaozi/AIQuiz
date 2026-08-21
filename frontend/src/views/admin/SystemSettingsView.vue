<template>
  <div class="system-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>系统设置</h3>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="settings-tabs">
        <!-- 1. 基础设置标签页 -->
        <el-tab-pane label="基础设置" name="basic">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>基础设置</span>
            </template>
            <el-form :model="basicSettings" label-width="140px" class="settings-form">
              <el-form-item label="系统名称">
                <el-input v-model="basicSettings.systemName" placeholder="请输入系统名称" style="width: 400px" />
              </el-form-item>

              <el-form-item label="系统Logo">
                <el-upload
                  class="logo-uploader"
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="handleLogoChange"
                >
                  <img v-if="basicSettings.logoUrl" :src="basicSettings.logoUrl" class="logo-preview" />
                  <el-icon v-else class="logo-uploader-icon"><Plus /></el-icon>
                </el-upload>
                <span class="upload-tip">支持PNG、JPG格式，建议尺寸200x60px</span>
              </el-form-item>

              <el-form-item label="系统公告">
                <el-input
                  v-model="basicSettings.announcement"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入系统公告内容"
                  style="width: 600px"
                />
              </el-form-item>

              <el-form-item label="登录页背景">
                <el-upload
                  class="bg-uploader"
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="handleBgChange"
                >
                  <img v-if="basicSettings.loginBgUrl" :src="basicSettings.loginBgUrl" class="bg-preview" />
                  <div v-else class="bg-placeholder">
                    <el-icon><Plus /></el-icon>
                    <span>上传背景图片</span>
                  </div>
                </el-upload>
                <span class="upload-tip">建议尺寸1920x1080px，支持PNG、JPG格式</span>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveBasicSettings">保存设置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <!-- 2. 考试种类管理标签页 -->
        <el-tab-pane label="考试种类" name="examCategory">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <div class="card-header">
                <span>考试种类管理</span>
                <el-button type="primary" @click="showExamCategoryDialog()">新增种类</el-button>
              </div>
            </template>

            <el-table :data="examCategories" stripe style="width: 100%">
              <el-table-column prop="name" label="种类名称" width="200" />
              <el-table-column prop="code" label="代码" width="150" />
              <el-table-column prop="description" label="描述" min-width="300" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'info'">
                    {{ row.status === 1 ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" size="small" link @click="showExamCategoryDialog(row)">编辑</el-button>
                  <el-button type="danger" size="small" link @click="deleteExamCategory(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 新增/编辑考试种类弹窗 -->
          <el-dialog
            v-model="examCategoryDialogVisible"
            :title="isEditExamCategory ? '编辑考试种类' : '新增考试种类'"
            width="500px"
          >
            <el-form :model="examCategoryForm" :rules="examCategoryRules" ref="examCategoryFormRef" label-width="100px">
              <el-form-item label="种类名称" prop="name">
                <el-input v-model="examCategoryForm.name" placeholder="请输入种类名称，如：软考、司法鉴定" @input="generateCategoryCode" />
              </el-form-item>
              <el-form-item label="代码" prop="code">
                <el-input v-model="examCategoryForm.code" placeholder="请输入种类代码" />
                <span class="form-tip">自动从名称生成，也可手动修改</span>
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="examCategoryForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch v-model="examCategoryForm.status" :active-value="1" :inactive-value="0" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="examCategoryDialogVisible = false">取消</el-button>
              <el-button type="primary" @click="submitExamCategory">确定</el-button>
            </template>
          </el-dialog>
        </el-tab-pane>

        <!-- 3. 考试科目管理标签页 -->
        <el-tab-pane label="考试科目" name="examType">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <div class="card-header">
                <span>考试科目管理</span>
                <el-button type="primary" @click="showExamTypeDialog()">新增科目</el-button>
              </div>
            </template>

            <!-- 按考试种类分组的层级显示 -->
            <div class="category-groups">
              <div v-for="group in groupedExamTypes" :key="group.category.id" class="category-group">
                <div class="group-header">
                  <el-icon><Folder /></el-icon>
                  <span class="group-title">{{ group.category.name }}</span>
                  <el-tag size="small" type="info">{{ group.examTypes.length }} 个科目</el-tag>
                </div>
                <el-table :data="group.examTypes" stripe style="width: 100%">
                  <el-table-column prop="name" label="科目名称" width="180" />
                  <el-table-column prop="code" label="代码" width="120" />
                  <el-table-column prop="level" label="级别" width="100">
                    <template #default="{ row }">
                      {{ row.level || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="duration" label="时长" width="80">
                    <template #default="{ row }">
                      {{ row.duration }}分钟
                    </template>
                  </el-table-column>
                  <el-table-column prop="total_score" label="总分" width="80" />
                  <el-table-column prop="passing_score" label="及格分" width="80" />
                  <el-table-column prop="status" label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 1 ? 'success' : 'info'">
                        {{ row.status === 1 ? '启用' : '禁用' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="150" fixed="right">
                    <template #default="{ row }">
                      <el-button type="primary" size="small" link @click="showExamTypeDialog(row)">编辑</el-button>
                      <el-button type="danger" size="small" link @click="deleteExamType(row.id)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-if="groupedExamTypes.length === 0" description="暂无考试科目数据" />
            </div>
          </el-card>

          <!-- 新增/编辑考试科目弹窗 -->
          <el-dialog
            v-model="examTypeDialogVisible"
            :title="isEditExamType ? '编辑考试科目' : '新增考试科目'"
            width="600px"
          >
            <el-form :model="examTypeForm" :rules="examTypeRules" ref="examTypeFormRef" label-width="100px">
              <el-form-item label="所属种类" prop="category_id">
                <el-select v-model="examTypeForm.category_id" placeholder="请选择考试种类" style="width: 100%">
                  <el-option v-for="cat in examCategories" :key="cat.id" :label="cat.name" :value="cat.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="科目名称" prop="name">
                <el-input v-model="examTypeForm.name" placeholder="请输入科目名称，如：网络管理员" @input="generateExamTypeCode" />
              </el-form-item>
              <el-form-item label="代码" prop="code">
                <el-input v-model="examTypeForm.code" placeholder="请输入科目代码" />
                <span class="form-tip">自动从名称生成，也可手动修改</span>
              </el-form-item>
              <el-form-item label="级别">
                <el-select v-model="examTypeForm.level" placeholder="请选择级别" style="width: 100%">
                  <el-option label="初级" value="初级" />
                  <el-option label="中级" value="中级" />
                  <el-option label="高级" value="高级" />
                </el-select>
              </el-form-item>
              <el-form-item label="考试时长">
                <el-input-number v-model="examTypeForm.duration" :min="1" :max="600" />
                <span style="margin-left: 8px">分钟</span>
              </el-form-item>
              <el-form-item label="总分">
                <el-input-number v-model="examTypeForm.total_score" :min="0" :max="1000" />
              </el-form-item>
              <el-form-item label="及格分数">
                <el-input-number v-model="examTypeForm.passing_score" :min="0" :max="1000" />
              </el-form-item>
              <el-form-item label="支持的题型">
                <el-checkbox-group v-model="examTypeForm.question_types">
                  <el-checkbox value="choice">单选题</el-checkbox>
                  <el-checkbox value="multiple">多选题</el-checkbox>
                  <el-checkbox value="judge">判断题</el-checkbox>
                  <el-checkbox value="fill">填空题</el-checkbox>
                  <el-checkbox value="essay">简答题</el-checkbox>
                </el-checkbox-group>
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="examTypeForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch v-model="examTypeForm.status" :active-value="1" :inactive-value="0" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="examTypeDialogVisible = false">取消</el-button>
              <el-button type="primary" @click="submitExamType">确定</el-button>
            </template>
          </el-dialog>
        </el-tab-pane>

        <!-- 3. 用户管理标签页 -->
        <el-tab-pane label="用户管理" name="user">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <div class="card-header">
                <span>用户管理</span>
                <el-button type="primary" @click="showUserDialog()">新建用户</el-button>
              </div>
            </template>

            <el-table :data="users" stripe style="width: 100%">
              <el-table-column label="头像" width="70">
                <template #default="{ row }">
                  <el-avatar :size="40" :src="row.avatar">
                    {{ row.name?.charAt(0) }}
                  </el-avatar>
                </template>
              </el-table-column>
              <el-table-column prop="username" label="用户名" width="120" />
              <el-table-column prop="name" label="姓名" width="100" />
              <el-table-column prop="role" label="角色" width="120">
                <template #default="{ row }">
                  <el-tag :type="getRoleTagType(row.role)">{{ getRoleName(row.role) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="phone" label="手机" width="130" />
              <el-table-column prop="email" label="邮箱" width="180" />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-switch v-model="row.status" @change="toggleUserStatus(row)" />
                </template>
              </el-table-column>
              <el-table-column prop="lastLogin" label="最后登录" width="160">
                <template #default="{ row }">
                  {{ row.lastLogin || '从未登录' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="{ row }">
                  <el-button link size="small" @click="showUserDialog(row)">编辑</el-button>
                  <el-button link size="small" @click="resetUserPassword(row)">重置密码</el-button>
                  <el-button link size="small" @click="changeUserRole(row)">切换角色</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              v-model:current-page="userPagination.page"
              v-model:page-size="userPagination.pageSize"
              :total="userPagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              @size-change="fetchUsers"
              @current-change="fetchUsers"
              style="margin-top: 20px; text-align: right"
            />
          </el-card>

          <!-- 新建/编辑用户弹窗 -->
          <el-dialog
            v-model="userDialogVisible"
            :title="isEditUser ? '编辑用户' : '新建用户'"
            width="500px"
          >
            <el-form :model="userForm" :rules="userRules" ref="userFormRef" label-width="100px">
              <el-form-item label="用户名" prop="username">
                <el-input v-model="userForm.username" placeholder="请输入用户名" :disabled="isEditUser" />
              </el-form-item>
              <el-form-item label="姓名" prop="name">
                <el-input v-model="userForm.name" placeholder="请输入姓名" />
              </el-form-item>
              <el-form-item label="角色" prop="role">
                <el-select v-model="userForm.role" placeholder="请选择角色" style="width: 100%">
                  <el-option label="管理员" value="admin" />
                  <el-option label="题库编辑" value="editor" />
                  <el-option label="审核员" value="reviewer" />
                </el-select>
              </el-form-item>
              <el-form-item label="手机" prop="phone">
                <el-input v-model="userForm.phone" placeholder="请输入手机号" />
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="userForm.email" placeholder="请输入邮箱" />
              </el-form-item>
              <el-form-item v-if="!isEditUser" label="密码" prop="password">
                <el-input v-model="userForm.password" type="password" placeholder="请输入密码" show-password />
              </el-form-item>
              <el-form-item label="状态">
                <el-switch v-model="userForm.status" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="userDialogVisible = false">取消</el-button>
              <el-button type="primary" @click="submitUser">确定</el-button>
            </template>
          </el-dialog>

          <!-- 角色切换弹窗 -->
          <el-dialog v-model="roleDialogVisible" title="切换角色" width="400px">
            <el-form label-width="80px">
              <el-form-item label="当前用户">
                <span>{{ currentUser?.name }}</span>
              </el-form-item>
              <el-form-item label="选择角色">
                <el-select v-model="newRole" placeholder="请选择角色" style="width: 100%">
                  <el-option label="管理员" value="admin" />
                  <el-option label="题库编辑" value="editor" />
                  <el-option label="审核员" value="reviewer" />
                </el-select>
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="roleDialogVisible = false">取消</el-button>
              <el-button type="primary" @click="submitRoleChange">确定</el-button>
            </template>
          </el-dialog>
        </el-tab-pane>

        <!-- 4. 考试规则标签页 - 预留功能，暂不显示
        <el-tab-pane label="考试规则" name="examRules">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>考试规则设置</span>
            </template>
            <el-form :model="examRules" label-width="160px" class="settings-form">
              <el-divider content-position="left">题目顺序</el-divider>

              <el-form-item label="题目随机顺序">
                <el-switch v-model="examRules.randomQuestionOrder" />
                <span class="form-tip">开启后，考生每次考试的题目顺序将随机打乱</span>
              </el-form-item>

              <el-form-item label="选项随机顺序">
                <el-switch v-model="examRules.randomOptionOrder" />
                <span class="form-tip">开启后，考生每次考试的选项顺序将随机打乱</span>
              </el-form-item>

              <el-divider content-position="left">考试限制</el-divider>

              <el-form-item label="允许回看答案">
                <el-switch v-model="examRules.allowReviewAnswer" />
                <span class="form-tip">开启后，考生可以在考试过程中查看已作答的答案</span>
              </el-form-item>

              <el-form-item label="切屏次数限制">
                <el-input-number v-model="examRules.maxScreenSwitch" :min="0" :max="100" />
                <span class="form-tip">超出次数后将强制交卷，0表示不限制</span>
              </el-form-item>

              <el-divider content-position="left">评分设置</el-divider>

              <el-form-item label="及格分数比例">
                <el-input-number v-model="examRules.passScoreRatio" :min="0" :max="100" :precision="0" />
                <span class="form-tip">百分比，如60表示及格分为总分的60%</span>
              </el-form-item>

              <el-form-item label="成绩显示配置">
                <el-checkbox-group v-model="examRules.scoreDisplay">
                  <el-checkbox value="score">显示分数</el-checkbox>
                  <el-checkbox value="rank">显示排名</el-checkbox>
                  <el-checkbox value="correctRate">显示正确率</el-checkbox>
                  <el-checkbox value="answerTime">显示答题时间</el-checkbox>
                </el-checkbox-group>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveExamRules">保存设置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>
        -->

        <!-- 5. 通知设置标签页 (暂时隐藏，需要邮件服务器和短信接口)
        <el-tab-pane label="通知设置" name="notification">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>通知设置</span>
            </template>

            <el-tabs v-model="notificationSubTab" class="nested-tabs">
              <el-tab-pane label="邮件配置" name="email">
                <el-form :model="notificationSettings.email" label-width="140px" class="settings-form">
                  <el-form-item label="启用邮件通知">
                    <el-switch v-model="notificationSettings.email.enabled" />
                  </el-form-item>
                  <el-form-item label="SMTP服务器">
                    <el-input v-model="notificationSettings.email.smtpHost" placeholder="smtp.example.com" style="width: 300px" />
                  </el-form-item>
                  <el-form-item label="SMTP端口">
                    <el-input-number v-model="notificationSettings.email.smtpPort" :min="1" :max="65535" style="width: 150px" />
                  </el-form-item>
                  <el-form-item label="发件人邮箱">
                    <el-input v-model="notificationSettings.email.fromEmail" placeholder="noreply@example.com" style="width: 300px" />
                  </el-form-item>
                  <el-form-item label="邮箱密码">
                    <el-input v-model="notificationSettings.email.password" type="password" placeholder="请输入邮箱密码" show-password style="width: 300px" />
                  </el-form-item>
                  <el-form-item label="使用SSL">
                    <el-switch v-model="notificationSettings.email.useSSL" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" @click="saveEmailSettings">保存设置</el-button>
                    <el-button @click="testEmailNotification">发送测试邮件</el-button>
                  </el-form-item>
                </el-form>
              </el-tab-pane>

              <el-tab-pane label="短信配置" name="sms">
                <el-form :model="notificationSettings.sms" label-width="140px" class="settings-form">
                  <el-form-item label="启用短信通知">
                    <el-switch v-model="notificationSettings.sms.enabled" />
                  </el-form-item>
                  <el-form-item label="短信服务商">
                    <el-select v-model="notificationSettings.sms.provider" placeholder="请选择服务商" style="width: 300px">
                      <el-option label="阿里云短信" value="aliyun" />
                      <el-option label="腾讯云短信" value="tencent" />
                      <el-option label="华为云短信" value="huawei" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="AccessKey ID">
                    <el-input v-model="notificationSettings.sms.accessKeyId" placeholder="请输入AccessKey ID" style="width: 300px" />
                  </el-form-item>
                  <el-form-item label="AccessKey Secret">
                    <el-input v-model="notificationSettings.sms.accessKeySecret" type="password" placeholder="请输入AccessKey Secret" show-password style="width: 300px" />
                  </el-form-item>
                  <el-form-item label="签名名称">
                    <el-input v-model="notificationSettings.sms.signName" placeholder="请输入短信签名" style="width: 300px" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" @click="saveSmsSettings">保存设置</el-button>
                    <el-button @click="testSmsNotification">发送测试短信</el-button>
                  </el-form-item>
                </el-form>
              </el-tab-pane>

              <el-tab-pane label="消息模板" name="templates">
                <el-form :model="notificationSettings.templates" label-width="140px" class="settings-form">
                  <el-divider content-position="left">审核结果通知模板</el-divider>
                  <el-form-item label="模板标题">
                    <el-input v-model="notificationSettings.templates.review.title" placeholder="审核结果通知" style="width: 400px" />
                  </el-form-item>
                  <el-form-item label="模板内容">
                    <el-input
                      v-model="notificationSettings.templates.review.content"
                      type="textarea"
                      :rows="4"
                      placeholder="尊敬的{username}，您的{type}已通过审核。"
                      style="width: 600px"
                    />
                  </el-form-item>
                  <el-form-item label="可用变量">
                    <span class="var-hint">{username} - 用户名, {type} - 内容类型, {result} - 审核结果, {time} - 时间</span>
                  </el-form-item>

                  <el-divider content-position="left">成绩发布通知模板</el-divider>
                  <el-form-item label="模板标题">
                    <el-input v-model="notificationSettings.templates.score.title" placeholder="成绩发布通知" style="width: 400px" />
                  </el-form-item>
                  <el-form-item label="模板内容">
                    <el-input
                      v-model="notificationSettings.templates.score.content"
                      type="textarea"
                      :rows="4"
                      placeholder="尊敬的{username}，您的考试成绩已发布，总分{score}分。"
                      style="width: 600px"
                    />
                  </el-form-item>
                  <el-form-item label="可用变量">
                    <span class="var-hint">{username} - 用户名, {examName} - 考试名称, {score} - 分数, {rank} - 排名</span>
                  </el-form-item>

                  <el-form-item>
                    <el-button type="primary" @click="saveTemplates">保存模板</el-button>
                  </el-form-item>
                </el-form>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </el-tab-pane>
        -->

        <!-- 6. 安全设置标签页 -->
        <el-tab-pane label="安全设置" name="security">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>安全设置</span>
            </template>
            <el-form :model="securitySettings" label-width="160px" class="settings-form">
              <el-divider content-position="left">登录安全</el-divider>

              <el-form-item label="登录失败锁定">
                <el-switch v-model="securitySettings.loginLockEnabled" />
                <span class="form-tip">启用后，连续登录失败将锁定账户</span>
              </el-form-item>

              <el-form-item v-if="securitySettings.loginLockEnabled" label="失败次数限制">
                <el-input-number v-model="securitySettings.maxLoginAttempts" :min="3" :max="10" />
                <span class="form-tip">连续失败达到此次数将锁定账户</span>
              </el-form-item>

              <el-form-item v-if="securitySettings.loginLockEnabled" label="锁定时长">
                <el-input-number v-model="securitySettings.lockDuration" :min="1" :max="1440" />
                <span class="form-tip">账户锁定时长，单位：分钟</span>
              </el-form-item>

              <el-divider content-position="left">密码安全</el-divider>

              <el-form-item label="密码强度要求">
                <el-switch v-model="securitySettings.passwordStrengthEnabled" />
              </el-form-item>

              <el-form-item v-if="securitySettings.passwordStrengthEnabled" label="密码规则">
                <el-checkbox-group v-model="securitySettings.passwordRules">
                  <el-checkbox value="length">至少8位</el-checkbox>
                  <el-checkbox value="uppercase">包含大写字母</el-checkbox>
                  <el-checkbox value="lowercase">包含小写字母</el-checkbox>
                  <el-checkbox value="number">包含数字</el-checkbox>
                  <el-checkbox value="special">包含特殊字符</el-checkbox>
                </el-checkbox-group>
              </el-form-item>

              <el-divider content-position="left">会话管理</el-divider>

              <el-form-item label="会话超时时间">
                <el-input-number v-model="securitySettings.sessionTimeout" :min="5" :max="480" />
                <span class="form-tip">用户无操作超时时间，单位：分钟</span>
              </el-form-item>

              <!-- IP白名单功能暂时隐藏
              <el-divider content-position="left">访问控制</el-divider>

              <el-form-item label="IP白名单">
                <el-input
                  v-model="securitySettings.ipWhitelist"
                  type="textarea"
                  :rows="4"
                  placeholder="每行一个IP地址，支持CIDR格式，如：192.168.1.1&#10;10.0.0.0/8"
                  style="width: 400px"
                />
              </el-form-item>
              -->

              <el-divider content-position="left">审计日志</el-divider>

              <el-form-item label="操作日志">
                <el-switch v-model="securitySettings.operationLogEnabled" />
                <span class="form-tip">启用后将记录所有用户的操作日志</span>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveSecuritySettings">保存设置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <!-- 密码重置申请管理 -->
        <el-tab-pane label="密码重置" name="passwordReset">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <div class="card-header">
                <span>密码重置申请</span>
                <el-button @click="loadPasswordResetRequests" :loading="resetLoading">刷新</el-button>
              </div>
            </template>
            <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
              显示用户提交的密码重置申请。处理后将新密码告知用户。
            </el-alert>

            <el-table :data="passwordResetRequests" stripe style="width: 100%" v-loading="resetLoading">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="username" label="用户名" width="150" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 0 ? 'warning' : 'success'">
                    {{ row.status === 0 ? '待处理' : '已处理' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="申请时间" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column prop="processed_at" label="处理时间" width="180">
                <template #default="{ row }">
                  {{ row.processed_at ? formatDateTime(row.processed_at) : '-' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="{ row }">
                  <div v-if="row.status === 0">
                    <el-button type="primary" size="small" @click="showResetDialog(row)">处理</el-button>
                  </div>
                  <el-button v-else type="danger" size="small" @click="deleteResetRequest(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <!-- 密码重置对话框 -->
        <el-dialog v-model="resetDialogVisible" title="重置用户密码" width="400px">
          <el-form :model="resetForm" label-width="80px">
            <el-form-item label="用户名">
              <el-input v-model="resetForm.username" disabled />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="resetForm.newPassword" type="password" placeholder="请输入新密码（至少8位）" show-password />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="resetDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitPasswordReset">确认重置</el-button>
          </template>
        </el-dialog>

        <!-- 7. 角色权限标签页 -->
        <el-tab-pane label="角色权限" name="rolePermissions">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>角色菜单权限配置</span>
            </template>
            <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
              配置各角色可访问的菜单模块。修改后立即生效。
            </el-alert>

            <el-form :model="rolePermissionsForm" label-width="100px" class="settings-form">
              <el-form-item label="管理员">
                <div class="permission-grid">
                  <el-checkbox-group v-model="rolePermissionsForm.role1">
                    <el-checkbox value="ai-question">AI出题</el-checkbox>
                    <el-checkbox value="audit">试题审核</el-checkbox>
                    <el-checkbox value="auto-paper">智能组卷</el-checkbox>
                    <el-checkbox value="question-bank">题库管理</el-checkbox>
                    <el-checkbox value="paper-management">试卷管理</el-checkbox>
                    <el-checkbox value="knowledge">知识点管理</el-checkbox>
                    <el-checkbox value="settings">系统设置</el-checkbox>
                    <el-checkbox value="user-permission">用户权限</el-checkbox>
                  </el-checkbox-group>
                </div>
              </el-form-item>

              <el-form-item label="题库编辑">
                <div class="permission-grid">
                  <el-checkbox-group v-model="rolePermissionsForm.role2">
                    <el-checkbox value="ai-question">AI出题</el-checkbox>
                    <el-checkbox value="audit">试题审核</el-checkbox>
                    <el-checkbox value="auto-paper">智能组卷</el-checkbox>
                    <el-checkbox value="question-bank">题库管理</el-checkbox>
                    <el-checkbox value="paper-management">试卷管理</el-checkbox>
                    <el-checkbox value="knowledge">知识点管理</el-checkbox>
                  </el-checkbox-group>
                </div>
              </el-form-item>

              <el-form-item label="审核员">
                <div class="permission-grid">
                  <el-checkbox-group v-model="rolePermissionsForm.role3">
                    <el-checkbox value="audit">试题审核</el-checkbox>
                    <el-checkbox value="question-bank">题库管理</el-checkbox>
                  </el-checkbox-group>
                </div>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveRolePermissions">保存配置</el-button>
                <el-button @click="loadRolePermissions">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <!-- 8. AI配置标签页 -->
        <el-tab-pane label="AI配置" name="ai">
          <el-card shadow="never" class="tab-content-card">
            <template #header>
              <span>AI配置</span>
            </template>
            <el-form :model="aiSettings" label-width="140px" class="settings-form">
              <el-divider content-position="left">模型配置</el-divider>

              <el-form-item label="服务商">
                <el-select v-model="aiSettings.provider" @change="handleProviderChange" placeholder="请选择服务商" style="width: 200px">
                  <el-option v-for="p in providerList" :key="p.key" :label="p.name" :value="p.key" />
                </el-select>
              </el-form-item>

              <el-form-item label="模型">
                <el-select v-model="aiSettings.model" placeholder="请先选择服务商" style="width: 300px">
                  <el-option v-for="m in currentProviderModels" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>

              <el-form-item label="API密钥">
                <div style="display: flex; align-items: center; gap: 8px; width: 400px">
                  <el-input
                    v-model="aiSettings.apiKey"
                    :type="apiKeyVisible ? 'text' : 'password'"
                    :placeholder="apiKeyConfigured ? '****（已配置，可修改或清除）' : '请输入API密钥'"
                    show-password
                    style="flex: 1"
                  />
                  <el-button
                    v-if="apiKeyConfigured"
                    type="danger"
                    :icon="Delete"
                    circle
                    size="small"
                    title="清除API密钥"
                    @click="clearApiKey"
                  />
                </div>
              </el-form-item>

              <el-form-item label="API地址">
                <el-input
                  v-model="aiSettings.apiUrl"
                  placeholder="留空使用默认值"
                  style="width: 400px"
                />
                <span class="form-tip">如使用代理或自定义端点，请填写完整地址</span>
              </el-form-item>

              <el-form-item label="超时时间">
                <el-input-number v-model="aiSettings.timeout" :min="10" :max="300" />
                <span class="form-tip">超时时间，单位：秒</span>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveAiSettings">保存配置</el-button>
                <el-button @click="testAiConnection">测试连接</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Folder, Delete } from '@element-plus/icons-vue'
import { useSystemSettings } from '@/composables/useSystemSettings'

const {
  // Tab state
  activeTab,
  notificationSubTab,
  // Password reset
  passwordResetRequests,
  resetLoading,
  resetDialogVisible,
  resetForm,
  loadPasswordResetRequests,
  approveReset,
  rejectReset,
  // Basic settings
  basicSettings,
  handleLogoChange,
  handleBgChange,
  saveBasicSettings,
  // Exam categories
  examCategories,
  examCategoryDialogVisible,
  isEditExamCategory,
  loading,
  examCategoryFormRef,
  examCategoryForm,
  examCategoryRules,
  fetchExamCategories,
  showExamCategoryDialog,
  submitExamCategory,
  deleteExamCategory,
  getCategoryName,
  generateCategoryCode,
  generateCode,
  // Exam types
  examTypes,
  examTypeDialogVisible,
  isEditExamType,
  examTypeFormRef,
  examTypeForm,
  examTypeRules,
  groupedExamTypes,
  fetchExamTypes,
  showExamTypeDialog,
  submitExamType,
  deleteExamType,
  generateExamTypeCode,
  // Subjects
  subjects,
  getQuestionTypeName,
  // Users
  users,
  userPagination,
  userDialogVisible,
  roleDialogVisible,
  isEditUser,
  userFormRef,
  currentUser,
  newRole,
  userForm,
  userRules,
  fetchUsers,
  showUserDialog,
  submitUser,
  resetUserPassword,
  changeUserRole,
  submitRoleChange,
  toggleUserStatus,
  getRoleName,
  getRoleTagType,
  // Exam rules
  examRules,
  saveExamRules,
  // Notification settings
  notificationSettings,
  saveEmailSettings,
  saveSmsSettings,
  saveTemplates,
  testEmailNotification,
  testSmsNotification,
  // Security settings
  securitySettings,
  saveSecuritySettings,
  // AI settings
  AI_PROVIDER_MODELS,
  aiSettings,
  currentProviderModels,
  handleProviderChange,
  loadAiProviders,
  providerList,
  saveAiSettings,
  testAiConnection,
  apiKeyVisible,
  apiKeyConfigured,
  clearApiKey,
  // Role permissions
  rolePermissionsForm,
  loadRolePermissions,
  saveRolePermissions,
  // Initialization
  initializeSystemSettings,
  // Password reset actions
  showResetDialog,
  submitPasswordReset,
  deleteResetRequest,
  formatDateTime
} = useSystemSettings()

// Initialize
onMounted(async () => {
  await initializeSystemSettings()
})
</script>


<style scoped>
.system-settings {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.settings-tabs {
  margin-top: 0;
}

.tab-content-card {
  margin-bottom: 20px;
}

/* 考试种类分组样式 */
.category-groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.category-group {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.group-header .el-icon {
  font-size: 18px;
  color: #409eff;
}

.group-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.category-group .el-table {
  border-top: none;
}

.permission-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
}

.permission-grid .el-checkbox {
  min-width: 120px;
}

.form-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.upload-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.var-hint {
  color: #909399;
  font-size: 12px;
}

/* Logo上传样式 */
.logo-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s;
  width: 120px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-uploader:hover {
  border-color: #409eff;
}

.logo-preview {
  width: 120px;
  height: 60px;
  object-fit: contain;
}

.logo-uploader-icon {
  font-size: 28px;
  color: #8c939d;
}

/* 背景上传样式 */
.bg-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s;
  width: 320px;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bg-uploader:hover {
  border-color: #409eff;
}

.bg-preview {
  width: 320px;
  height: 180px;
  object-fit: cover;
}

.bg-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8c939d;
}

.bg-placeholder span {
  margin-top: 8px;
  font-size: 12px;
}

/* 嵌套标签页样式 */
.nested-tabs {
  margin-top: 0;
}

:deep(.el-tabs__nav-wrap) {
  background-color: #f5f7fa;
  border-radius: 4px;
  padding: 0 12px;
}

:deep(.el-tabs__item) {
  height: 40px;
  line-height: 40px;
}

:deep(.el-tabs__header) {
  margin-bottom: 0;
}

:deep(.el-divider--horizontal) {
  margin: 24px 0 16px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
