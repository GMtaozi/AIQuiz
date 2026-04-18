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
                  type="linkarea"
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
                <el-input v-model="examCategoryForm.description" type="linkarea" :rows="3" placeholder="请输入描述" />
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
                <el-input v-model="examTypeForm.description" type="linkarea" :rows="2" placeholder="请输入描述" />
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
              style="margin-top: 20px; link-align: right"
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
                      type="linkarea"
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
                      type="linkarea"
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
                  type="linkarea"
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
              </el-form-item>

              <el-form-item label="题库编辑">
                <el-checkbox-group v-model="rolePermissionsForm.role2">
                  <el-checkbox value="ai-question">AI出题</el-checkbox>
                  <el-checkbox value="audit">试题审核</el-checkbox>
                  <el-checkbox value="auto-paper">智能组卷</el-checkbox>
                  <el-checkbox value="question-bank">题库管理</el-checkbox>
                  <el-checkbox value="paper-management">试卷管理</el-checkbox>
                  <el-checkbox value="knowledge">知识点管理</el-checkbox>
                </el-checkbox-group>
              </el-form-item>

              <el-form-item label="审核员">
                <el-checkbox-group v-model="rolePermissionsForm.role3">
                  <el-checkbox value="audit">试题审核</el-checkbox>
                  <el-checkbox value="question-bank">题库管理</el-checkbox>
                </el-checkbox-group>
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
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Anthropic Claude" value="anthropic" />
                  <el-option label="智谱AI (GLM)" value="zhipu" />
                  <el-option label="阿里云 (Qwen)" value="qwen" />
                  <el-option label="MiniMax" value="minimax" />
                  <el-option label="百度文心一言" value="baidu" />
                  <el-option label="Google Gemini" value="gemini" />
                </el-select>
              </el-form-item>

              <el-form-item label="模型">
                <el-select v-model="aiSettings.model" placeholder="请先选择服务商" style="width: 300px">
                  <el-option v-for="m in currentProviderModels" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>

              <el-form-item label="API密钥">
                <el-input
                  v-model="aiSettings.apiKey"
                  type="password"
                  placeholder="请输入API密钥"
                  show-password
                  style="width: 400px"
                />
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
import { Plus, Folder } from '@element-plus/icons-vue'
import { systemAPI } from '@/api'

// 当前激活的标签页
const activeTab = ref('basic')
const notificationSubTab = ref('email')

// ============ 密码重置申请 ============
const passwordResetRequests = ref([])
const resetLoading = ref(false)
const resetDialogVisible = ref(false)
const resetForm = reactive({
  requestId: null,
  username: '',
  newPassword: ''
})

// ============ 1. 基础设置 ============
const basicSettings = reactive({
  systemName: '智题 AIQuiz',
  logoUrl: '',
  announcement: '欢迎使用智题 AIQuiz，祝您工作顺利！',
  loginBgUrl: ''
})

const handleLogoChange = (file) => {
  const url = URL.createObjectURL(file.raw)
  basicSettings.logoUrl = url
}

const handleBgChange = (file) => {
  const url = URL.createObjectURL(file.raw)
  basicSettings.loginBgUrl = url
}

const saveBasicSettings = () => {
  ElMessage.success('基础设置保存成功')
}

// ============ 2. 考试种类管理 ============
const examCategories = ref([])

const examCategoryDialogVisible = ref(false)
const isEditExamCategory = ref(false)
const loading = ref(false)
const examCategoryFormRef = ref(null)

const examCategoryForm = reactive({
  id: null,
  name: '',
  code: '',
  description: '',
  status: 1
})

const examCategoryRules = {
  name: [{ required: true, message: '请输入种类名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入种类代码', trigger: 'blur' }]
}

// 获取考试种类列表
const fetchExamCategories = async () => {
  try {
    const res = await systemAPI.getExamCategories()
    examCategories.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试种类失败:', e)
  }
}

const showExamCategoryDialog = (row = null) => {
  if (row) {
    isEditExamCategory.value = true
    Object.assign(examCategoryForm, {
      id: row.id,
      name: row.name,
      code: row.code,
      description: row.description || '',
      status: row.status
    })
  } else {
    isEditExamCategory.value = false
    Object.assign(examCategoryForm, {
      id: null,
      name: '',
      code: '',
      description: '',
      status: 1
    })
  }
  examCategoryDialogVisible.value = true
}

const submitExamCategory = async () => {
  try {
    await examCategoryFormRef.value.validate()
    const data = {
      name: examCategoryForm.name,
      code: examCategoryForm.code,
      description: examCategoryForm.description,
      status: examCategoryForm.status
    }
    if (isEditExamCategory.value) {
      await systemAPI.updateExamCategory(examCategoryForm.id, data)
      ElMessage.success('考试种类更新成功')
    } else {
      await systemAPI.createExamCategory(data)
      ElMessage.success('考试种类添加成功')
    }
    examCategoryDialogVisible.value = false
    fetchExamCategories()
  } catch (error) {
    console.error('提交失败:', error)
  }
}

const deleteExamCategory = (id) => {
  ElMessageBox.confirm('确定要删除该考试种类吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await systemAPI.deleteExamCategory(id)
      ElMessage.success('删除成功')
      fetchExamCategories()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const getCategoryName = (categoryId) => {
  const cat = examCategories.value.find(c => c.id === categoryId)
  return cat ? cat.name : '-'
}

// 自动生成代码
const generateCategoryCode = () => {
  if (!isEditExamCategory.value && examCategoryForm.name) {
    examCategoryForm.code = generateCode(examCategoryForm.name)
  }
}

const generateExamTypeCode = () => {
  if (!isEditExamType.value && examTypeForm.name) {
    examTypeForm.code = generateCode(examTypeForm.name)
  }
}

// 生成代码的辅助函数：将中文/英文名称转换为大写字母数字组合
const generateCode = (name) => {
  if (!name) return ''
  // 移除非字母数字字符
  let code = name.replace(/[^\w\u4e00-\u9fa5]/g, '')
  // 如果是纯中文，转换为拼音首字母
  if (/^[\u4e00-\u9fa5]+$/.test(name)) {
    code = name.split('').map(char => charToPinyin(char)).filter(Boolean).join('')
  } else {
    // 英文混合，只保留字母数字
    code = code.replace(/[^\w]/g, '').toUpperCase()
  }
  return code || name.toUpperCase().replace(/[^\w]/g, '')
}

// 汉字转拼音首字母（扩展映射表）
const charToPinyin = (char) => {
  const pinyinMap = {
    // 考试种类相关
    '软': 'R', '考': 'K', '司': 'S', '法': 'F', '鉴': 'J', '定': 'D',
    '司': 'S', '法': 'F', '鉴': 'J', '定': 'D', '教': 'J', '育': 'Y',
    // 考试科目相关
    '网': 'W', '络': 'L', '管': 'G', '理': 'L', '员': 'Y', '工': 'G',
    '程': 'C', '师': 'S', '规': 'G', '划': 'H', '设': 'S', '计': 'J',
    '基': 'J', '础': 'C', '专': 'Z', '业': 'Y', '初': 'C', '级': 'J',
    '中': 'Z', '高': 'G', '律': 'L', '法': 'F', '规': 'G', '则': 'Z',
    '度': 'D', '理': 'L', '论': 'L', '实': 'S', '务': 'W', '鉴': 'J',
    '别': 'B', '会': 'H', '计': 'K', '审': 'S', '计': 'J', '财': 'C',
    '务': 'W', '税': 'S', '务': 'W', '银': 'Y', '行': 'H', '经': 'J',
    '济': 'J', '贸': 'M', '易': 'Y', '保': 'B', '险': 'X', '金': 'J',
    '融': 'R', '投': 'T', '资': 'Z', '房': 'F', '产': 'C', '筑': 'Z',
    '医': 'Y', '疗': 'L', '卫': 'W', '生': 'S', '文': 'W', '化': 'H',
    '教': 'J', '师': 'S', '资': 'Z', '源': 'Y', '人': 'R', '力': 'L',
    '行': 'X', '政': 'X', '公': 'G', '共': 'G', '安': 'A', '全': 'Q',
    '质': 'Z', '量': 'L', '检': 'J', '测': 'C', '食': 'S', '品': 'P',
    '环': 'H', '境': 'J', '化': 'H', '电': 'D', '子': 'Z', '商': 'S',
    '务': 'W', '物': 'W', '流': 'L', '输': 'S', '运': 'Y', '园': 'Y',
    '林': 'L', '农': 'N', '业': 'Y', '机': 'J', '械': 'X', '电': 'D',
    '力': 'L', '水': 'S', '利': 'L', '铁': 'T', '路': 'L', '航': 'H',
    '空': 'K', '航': 'H', '天': 'T', '信': 'X', '息': 'X', '通': 'T'
  }
  return pinyinMap[char] || ''
}

// ============ 3. 考试科目管理 ============
// 按考试种类分组的考试科目
const groupedExamTypes = computed(() => {
  const groups = []
  for (const cat of examCategories.value) {
    const examTypesInCat = examTypes.value.filter(et => et.category_id === cat.id)
    groups.push({
      category: cat,
      examTypes: examTypesInCat
    })
  }
  return groups
})

const examTypes = ref([])

const examTypeDialogVisible = ref(false)
const isEditExamType = ref(false)
const examTypeFormRef = ref(null)

const examTypeForm = reactive({
  id: null,
  category_id: null,
  name: '',
  code: '',
  level: '',
  duration: 120,
  total_score: 100,
  passing_score: 60,
  question_types: [],
  description: '',
  status: 1
})

const examTypeRules = {
  category_id: [{ required: true, message: '请选择考试种类', trigger: 'change' }],
  name: [{ required: true, message: '请输入科目名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入科目代码', trigger: 'blur' }]
}

// 获取考试科目列表
const fetchExamTypes = async () => {
  try {
    const res = await systemAPI.getExamTypes()
    examTypes.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  }
}

const showExamTypeDialog = (row = null) => {
  if (row) {
    isEditExamType.value = true
    Object.assign(examTypeForm, {
      id: row.id,
      category_id: row.category_id,
      name: row.name,
      code: row.code,
      level: row.level || '',
      duration: row.duration,
      total_score: row.total_score,
      passing_score: row.passing_score,
      question_types: row.question_types || [],
      description: row.description || '',
      status: row.status
    })
  } else {
    isEditExamType.value = false
    Object.assign(examTypeForm, {
      id: null,
      category_id: null,
      name: '',
      code: '',
      level: '',
      duration: 120,
      total_score: 100,
      passing_score: 60,
      question_types: [],
      description: '',
      status: 1
    })
  }
  examTypeDialogVisible.value = true
}

const submitExamType = async () => {
  try {
    await examTypeFormRef.value.validate()
    const data = {
      category_id: examTypeForm.category_id,
      name: examTypeForm.name,
      code: examTypeForm.code,
      level: examTypeForm.level || null,
      duration: examTypeForm.duration,
      total_score: examTypeForm.total_score,
      passing_score: examTypeForm.passing_score,
      question_types: examTypeForm.question_types,
      description: examTypeForm.description,
      status: examTypeForm.status
    }
    if (isEditExamType.value) {
      await systemAPI.updateExamType(examTypeForm.id, data)
      ElMessage.success('考试科目更新成功')
    } else {
      await systemAPI.createExamType(data)
      ElMessage.success('考试科目添加成功')
    }
    examTypeDialogVisible.value = false
    fetchExamTypes()
  } catch (error) {
    console.error('提交失败:', error)
  }
}

const deleteExamType = (id) => {
  ElMessageBox.confirm('确定要删除该考试科目吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await systemAPI.deleteExamType(id)
      ElMessage.success('删除成功')
      fetchExamTypes()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ============ 3. 科目管理 ============
const subjects = ref([])

const getQuestionTypeName = (type) => {
  const map = {
    choice: '单选题',
    multiple: '多选题',
    short_answer: '简答题',
    judge: '判断题',
    fill: '填空题'
  }
  return map[type] || type
}

// ============ 3. 用户管理 ============
const users = ref([
  { id: 1, username: 'admin', name: '管理员', role: 'admin', phone: '13800138000', email: 'admin@example.com', status: true, lastLogin: '2026-04-14 10:30:00', avatar: '' },
  { id: 2, username: 'editor1', name: '题库编辑', role: 'editor', phone: '13800138001', email: 'editor@example.com', status: true, lastLogin: '2026-04-13 15:20:00', avatar: '' },
  { id: 3, username: 'reviewer1', name: '审核员', role: 'reviewer', phone: '13800138002', email: 'reviewer@example.com', status: true, lastLogin: '2026-04-12 09:15:00', avatar: '' },
  { id: 4, username: 'operator2', name: '题库编辑2', role: 'editor', phone: '13800138003', email: 'operator2@example.com', status: false, lastLogin: '2026-04-10 14:00:00', avatar: '' }
])

const userPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 4
})

const userDialogVisible = ref(false)
const roleDialogVisible = ref(false)
const isEditUser = ref(false)
const userFormRef = ref(null)
const currentUser = ref(null)
const newRole = ref('')

const userForm = reactive({
  id: null,
  username: '',
  name: '',
  role: 'editor',
  phone: '',
  email: '',
  password: '',
  status: true
})

const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const fetchUsers = async () => {
  try {
    loading.value = true
    const res = await systemAPI.getUsers()
    users.value = (res.data?.items || res.data || []).map(u => ({
      id: u.id,
      username: u.username,
      name: u.real_name || u.username,
      role: u.role === 1 ? 'admin' : u.role === 2 ? 'editor' : 'reviewer',
      phone: u.phone || '',
      email: u.email,
      status: u.status === 1,
      lastLogin: u.last_login || ''
    }))
  } catch (err) {
    console.error('获取用户列表失败:', err)
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const showUserDialog = (row = null) => {
  if (row) {
    isEditUser.value = true
    Object.assign(userForm, row)
    userForm.password = ''
  } else {
    isEditUser.value = false
    Object.assign(userForm, {
      id: null,
      username: '',
      name: '',
      role: 'editor',
      phone: '',
      email: '',
      password: '',
      status: true
    })
  }
  userDialogVisible.value = true
}

const submitUser = async () => {
  try {
    await userFormRef.value.validate()
    // 将角色字符串转换为整数
    const roleMap = { 'admin': 1, 'editor': 2, 'reviewer': 3 }
    const userData = {
      username: userForm.username,
      real_name: userForm.name,
      role: typeof userForm.role === 'string' ? (roleMap[userForm.role] || userForm.role) : userForm.role,
      phone: userForm.phone || null,
      email: userForm.email,
      status: userForm.status ? 1 : 0
    }
    if (isEditUser.value) {
      await systemAPI.updateUser(userForm.id, userData)
      const index = users.value.findIndex(item => item.id === userForm.id)
      if (index !== -1) {
        users.value[index] = { ...users.value[index], ...userForm }
      }
      ElMessage.success('用户更新成功')
    } else {
      userData.password = userForm.password
      const res = await systemAPI.createUser(userData)
      users.value.push({ ...userForm, id: res.id, lastLogin: '', avatar: '' })
      ElMessage.success('用户创建成功')
    }
    userDialogVisible.value = false
  } catch (error) {
    ElMessage.error(isEditUser.value ? '用户更新失败' : '用户创建失败')
  }
}

const resetUserPassword = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要重置用户"${row.name}"的密码吗？`, '提示', {
      type: 'warning'
    })
    await systemAPI.resetPassword(row.id)
    ElMessage.success('密码已重置为默认密码')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置密码失败')
    }
  }
}

const changeUserRole = (row) => {
  currentUser.value = row
  newRole.value = row.role
  roleDialogVisible.value = true
}

const submitRoleChange = async () => {
  if (newRole.value) {
    try {
      const roleMap = { 'admin': 1, 'editor': 2, 'reviewer': 3 }
      // 转换为整数：支持 'admin'/'editor'/'reviewer' 和 '1'/'2'/'3' 格式
      let roleInt
      if (typeof newRole.value === 'string') {
        roleInt = roleMap[newRole.value]
        if (roleInt === undefined) {
          roleInt = parseInt(newRole.value, 10)
        }
      } else {
        roleInt = newRole.value
      }
      await systemAPI.changeRole(currentUser.value.id, roleInt)
      const user = users.value.find(item => item.id === currentUser.value.id)
      if (user) {
        user.role = newRole.value
      }
      ElMessage.success('角色切换成功')
    } catch (error) {
      ElMessage.error('角色切换失败')
    }
  }
  roleDialogVisible.value = false
}

const toggleUserStatus = (row) => {
  ElMessage.success(`用户"${row.name}"已${row.status ? '启用' : '禁用'}`)
}

const getRoleName = (role) => {
  const map = {
    admin: '管理员',
    editor: '题库编辑',
    reviewer: '审核员'
  }
  return map[role] || role
}

const getRoleTagType = (role) => {
  const map = {
    admin: 'warning',
    editor: 'success',
    reviewer: 'info'
  }
  return map[role] || 'info'
}

// ============ 4. 考试规则 ============
const examRules = reactive({
  randomQuestionOrder: true,
  randomOptionOrder: true,
  allowReviewAnswer: false,
  maxScreenSwitch: 5,
  passScoreRatio: 60,
  scoreDisplay: ['score', 'correctRate']
})

const saveExamRules = () => {
  ElMessage.success('考试规则保存成功')
}

// ============ 5. 通知设置 ============
const notificationSettings = reactive({
  email: {
    enabled: true,
    smtpHost: 'smtp.example.com',
    smtpPort: 465,
    fromEmail: 'noreply@example.com',
    password: '',
    useSSL: true
  },
  sms: {
    enabled: false,
    provider: 'aliyun',
    accessKeyId: '',
    accessKeySecret: '',
    signName: ''
  },
  templates: {
    review: {
      title: '审核结果通知',
      content: '尊敬的{username}，您的{type}已通过审核。'
    },
    score: {
      title: '成绩发布通知',
      content: '尊敬的{username}，您的考试成绩已发布，总分{score}分。'
    }
  }
})

const saveEmailSettings = () => {
  ElMessage.success('邮件配置保存成功')
}

const saveSmsSettings = () => {
  ElMessage.success('短信配置保存成功')
}

const saveTemplates = () => {
  ElMessage.success('消息模板保存成功')
}

const testEmailNotification = () => {
  ElMessage.success('测试邮件已发送，请查收')
}

const testSmsNotification = () => {
  ElMessage.success('测试短信已发送，请查收')
}

// ============ 6. 安全设置 ============
const securitySettings = reactive({
  loginLockEnabled: true,
  maxLoginAttempts: 5,
  lockDuration: 30,
  passwordStrengthEnabled: true,
  passwordRules: ['length', 'number'],
  sessionTimeout: 120,
  ipWhitelist: '',
  operationLogEnabled: true
})

const saveSecuritySettings = async () => {
  try {
    // 构建更新数据
    const settingsToUpdate = [
      { key: 'login_lock_enabled', value: securitySettings.loginLockEnabled },
      { key: 'login_lock_count', value: securitySettings.maxLoginAttempts },
      { key: 'login_lock_duration', value: securitySettings.lockDuration },
      { key: 'password_strength_enabled', value: securitySettings.passwordStrengthEnabled },
      { key: 'password_require_uppercase', value: securitySettings.passwordRules.includes('uppercase') },
      { key: 'password_require_lowercase', value: securitySettings.passwordRules.includes('lowercase') },
      { key: 'password_require_digit', value: securitySettings.passwordRules.includes('number') },
      { key: 'password_require_special', value: securitySettings.passwordRules.includes('special') },
      { key: 'session_timeout', value: securitySettings.sessionTimeout },
      { key: 'operation_log_enabled', value: securitySettings.operationLogEnabled }
    ]

    await systemAPI.updateSettings(settingsToUpdate)
    ElMessage.success('安全设置保存成功')
  } catch (error) {
    console.error('保存安全设置失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ 7. AI配置 ============
// AI服务商模型映射
const AI_PROVIDER_MODELS = {
  openai: ['gpt-4o-2024-11-20', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
  anthropic: ['claude-opus-4-20251120', 'claude-sonnet-4-20251120', 'claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus-latest', 'claude-3-sonnet-latest', 'claude-3-haiku-latest'],
  zhipu: ['glm-4-plus', 'glm-4-flash', 'glm-4-long', 'glm-4-alltools', 'glm-4', 'glm-3-turbo'],
  qwen: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-max-long上下文'],
  minimax: ['MiniMax-M2.7', 'abab6.5s-chat', 'abab6-chat'],
  baidu: ['ernie-4.0-8k-latest', 'ernie-4.0-8k', 'ernie-4.0-turbo-8k-latest', 'ernie-3.5-8k-latest', 'ernie-3.5-8k'],
  gemini: ['gemini-2.0-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-flash-8b']
}

const aiSettings = reactive({
  provider: 'minimax',
  model: 'MiniMax-M2.7',
  apiKey: '',
  apiUrl: '',
  timeout: 120
})

// 根据选择的服务商获取模型列表
const currentProviderModels = computed(() => {
  return AI_PROVIDER_MODELS[aiSettings.provider] || []
})

// 当服务商变化时，重置模型选择
const handleProviderChange = () => {
  const models = AI_PROVIDER_MODELS[aiSettings.provider] || []
  aiSettings.model = models[0] || ''
}

const saveAiSettings = async () => {
  try {
    await systemAPI.updateAiConfig({
      provider: aiSettings.provider,
      model: aiSettings.model,
      api_key: aiSettings.apiKey,
      api_url: aiSettings.apiUrl,
      timeout: aiSettings.timeout
    })
    ElMessage.success('AI配置保存成功')
  } catch (error) {
    console.error('保存AI配置失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

const testAiConnection = async () => {
  try {
    ElMessage.info('正在测试AI连接...')
    const result = await systemAPI.testAiConnection()
    if (result.success) {
      ElMessage.success('AI连接测试成功！')
    } else {
      ElMessage.error('AI连接测试失败：' + result.message)
    }
  } catch (error) {
    console.error('测试AI连接失败:', error)
    ElMessage.error('测试连接失败，请稍后重试')
  }
}

onMounted(async () => {
  // 初始化加载数据
  fetchUsers()
  fetchExamCategories()
  fetchExamTypes()
  // 加载角色权限配置
  loadRolePermissions()
  // 加载AI配置
  try {
    const res = await systemAPI.getAiConfig()
    if (res.data) {
      aiSettings.provider = res.data.provider
      aiSettings.model = res.data.model
      aiSettings.apiUrl = res.data.api_url || ''
      aiSettings.timeout = res.data.timeout
      // API密钥不返回，只显示已配置的提示
      if (res.data.provider) {
        aiSettings.apiKey = ''
      }
    }
  } catch (error) {
    console.error('加载AI配置失败:', error)
  }
})

// ============ 8. 角色权限配置 ============
const rolePermissionsForm = reactive({
  role1: [],
  role2: [],
  role3: []
})

const loadRolePermissions = async () => {
  try {
    const res = await systemAPI.getRolePermissions()
    if (res.data && res.data.length) {
      res.data.forEach(item => {
        if (item.role === 1) rolePermissionsForm.role1 = item.permissions || []
        if (item.role === 2) rolePermissionsForm.role2 = item.permissions || []
        if (item.role === 3) rolePermissionsForm.role3 = item.permissions || []
      })
    }
  } catch (error) {
    console.error('加载角色权限失败:', error)
  }
}

const saveRolePermissions = async () => {
  try {
    await systemAPI.updateRolePermissions(1, rolePermissionsForm.role1)
    await systemAPI.updateRolePermissions(2, rolePermissionsForm.role2)
    await systemAPI.updateRolePermissions(3, rolePermissionsForm.role3)
    ElMessage.success('角色权限配置已保存')
  } catch (error) {
    console.error('保存角色权限失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  }
}

// ============ 密码重置申请管理 ============
const loadPasswordResetRequests = async () => {
  resetLoading.value = true
  try {
    const res = await systemAPI.getPasswordResetRequests({ status: undefined })
    passwordResetRequests.value = res.data?.items || []
  } catch (error) {
    console.error('加载密码重置申请失败:', error)
    ElMessage.error('加载失败')
  } finally {
    resetLoading.value = false
  }
}

const showResetDialog = (row) => {
  resetForm.requestId = row.id
  resetForm.username = row.username
  resetForm.newPassword = ''
  resetDialogVisible.value = true
}

const submitPasswordReset = async () => {
  if (!resetForm.newPassword || resetForm.newPassword.length < 8) {
    ElMessage.warning('密码长度至少8位')
    return
  }
  try {
    await systemAPI.processPasswordResetRequest(resetForm.requestId, {
      new_password: resetForm.newPassword
    })
    ElMessage.success('密码已重置，请告知用户新密码')
    resetDialogVisible.value = false
    loadPasswordResetRequests()
  } catch (error) {
    console.error('重置密码失败:', error)
    ElMessage.error(error.message || '重置失败')
  }
}

const deleteResetRequest = async (id) => {
  try {
    await systemAPI.deletePasswordResetRequest(id)
    ElMessage.success('申请记录已删除')
    loadPasswordResetRequests()
  } catch (error) {
    console.error('删除申请记录失败:', error)
    ElMessage.error('删除失败')
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}

// 切换到密码重置标签页时自动加载
watch(activeTab, (newTab) => {
  if (newTab === 'passwordReset' && passwordResetRequests.value.length === 0) {
    loadPasswordResetRequests()
  }
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

.settings-form {
  max-width: 800px;
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
