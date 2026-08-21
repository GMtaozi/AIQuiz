<template>
  <div class="paper-management-view">
    <!-- 顶部操作栏 -->
    <div class="operation-bar">
      <div class="left-operations">
        <el-select v-model="filterForm.categoryId" placeholder="考试种类" clearable class="filter-select" :loading="loadingCategories" @change="handleCategoryChange">
          <el-option
            v-for="item in categoryOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>

        <el-select v-model="filterForm.subjectId" placeholder="考试科目" clearable class="filter-select" :loading="loadingSubjects" :disabled="!filterForm.categoryId">
          <el-option
            v-for="item in filteredSubjectOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>

        <el-select v-model="filterForm.status" placeholder="状态" clearable class="filter-select">
          <el-option label="草稿" :value="0" />
          <el-option label="已发布" :value="1" />
          <el-option label="已归档" :value="2" />
        </el-select>

        <el-input
          v-model="searchKeyword"
          placeholder="搜索试卷..."
          class="search-input"
          clearable
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>

      <div class="right-operations">
        <el-dropdown @command="handleBatchCommand" trigger="click">
          <el-button>
            批量操作 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="publish">批量发布</el-dropdown-item>
              <el-dropdown-item command="archive">批量归档</el-dropdown-item>
              <el-dropdown-item command="delete">批量归档</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 试卷列表表格 -->
    <div class="table-container">
      <el-empty v-if="!loading && paperList.length === 0" description="暂无试卷数据" :image-size="80" />
      <el-table
        v-else
        ref="tableRef"
        :data="paperList"
        stripe
        style="width: 100%"
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column label="序号" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="试卷标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="考试科目" width="120">
          <template #default="{ row }">
            {{ getSubjectName(row.subject_id) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="total_time" label="时长(分钟)" width="100" />
        <el-table-column prop="total_score" label="总分" width="80" />
        <el-table-column prop="passing_score" label="及格分" width="80" />
        <el-table-column label="题目数" width="80">
          <template #default="{ row }">
            {{ row.config?.actual_question_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button link size="small" @click="previewPaper(row)">预览</el-button>
              <el-button link size="small" @click="editPaper(row)">编辑</el-button>
              <el-button link size="small" v-if="row.status === 0" @click="publishPaper(row)">发布</el-button>
              <el-button link size="small" v-if="row.status === 1" @click="archivePaper(row)">归档</el-button>
              <el-dropdown @command="(cmd) => handleRowCommand(cmd, row)">
                <el-button link size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="analyze">分析</el-dropdown-item>
                    <el-dropdown-item command="version">版本历史</el-dropdown-item>
                    <el-dropdown-item command="similarity">查重</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 新建/编辑试卷弹窗 -->
    <el-dialog
      v-model="paperDialogVisible"
      :title="isEdit ? '编辑试卷' : '新建试卷'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="paperForm" :rules="formRules" ref="paperFormRef" label-width="100px">
        <el-form-item label="试卷标题" prop="title">
          <el-input v-model="paperForm.title" placeholder="请输入试卷标题" />
        </el-form-item>

        <el-form-item label="考试种类" prop="categoryId">
          <el-select v-model="paperForm.categoryId" placeholder="请选择考试种类" style="width: 100%" @change="handleDialogCategoryChange">
            <el-option
              v-for="item in categoryOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="考试科目" prop="subjectId">
          <el-select v-model="paperForm.subjectId" placeholder="请选择考试科目" style="width: 100%" :disabled="!paperForm.categoryId">
            <el-option
              v-for="item in dialogFilteredSubjects"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="时长(分钟)" prop="totalTime">
              <el-input-number v-model="paperForm.totalTime" :min="1" :max="300" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="总分" prop="totalScore">
              <el-input-number v-model="paperForm.totalScore" :min="1" :max="500" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="及格分" prop="passingScore">
              <el-input-number v-model="paperForm.passingScore" :min="0" :max="paperForm.totalScore" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="paperForm.description" type="textarea" :rows="3" placeholder="请输入试卷描述" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="paperDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePaper" :loading="saveLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 试卷预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      title="试卷预览"
      width="800px"
    >
      <div class="paper-preview" v-if="previewPaperData">
        <div class="preview-header">
          <h2>{{ previewPaperData.title }}</h2>
          <div class="preview-info">
            <span>科目：{{ getSubjectName(previewPaperData.subject_id) }}</span>
            <span>时长：{{ previewPaperData.total_time }}分钟</span>
            <span>总分：{{ previewPaperData.total_score }}</span>
            <span>及格：{{ previewPaperData.passing_score }}</span>
          </div>
        </div>
        <div class="preview-questions">
          <div v-for="(item, index) in previewPaperData.questions" :key="item.id" class="preview-question-item">
            <div class="question-header">
              <span class="question-index">{{ index + 1 }}.</span>
              <span class="question-type">[{{ getQuestionTypeName(item.question.question_type) }}]</span>
              <span class="question-score">({{ item.score }}分)</span>
            </div>
            <div class="question-content">{{ item.question.content }}</div>
            <!-- 选择题选项显示（单选题、多选题） -->
            <div v-if="item.question.options && item.question.options.length > 0" class="question-options">
              <div v-for="(opt, optIdx) in item.question.options" :key="opt.id" class="option-item">
                <span class="option-label">{{ opt.option_label }}.</span>
                <span>{{ opt.option_content }}</span>
                <span v-if="opt.is_correct" class="correct-badge">✓</span>
              </div>
            </div>
            <!-- 判断题答案 -->
            <div v-if="item.question.question_type === 'true_false'" class="true-false-answer">
              <span class="answer-label">答案：</span>
              <span>{{ item.question.answer === 'true' || item.question.answer === 'T' ? '正确' : '错误' }}</span>
            </div>
            <!-- 简答题答案 -->
            <div v-if="item.question.question_type === 'essay'" class="essay-answer">
              <span class="answer-label">参考答案：</span>
              <span>{{ item.question.answer }}</span>
            </div>
            <!-- 答案显示（选择题单独显示答案标签） -->
            <div v-if="item.question.options && item.question.options.length > 0" class="choice-answer">
              <span class="answer-label">正确答案：</span>
              <span>{{ getCorrectAnswerLabels(item.question.options) }}</span>
            </div>
            <!-- 解析 -->
            <div v-if="item.question.explanation" class="question-explanation">
              <span class="explanation-label">解析：</span>
              <span>{{ item.question.explanation }}</span>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportWord">导出Word</el-button>
        <el-button type="primary" @click="exportPdf">导出PDF</el-button>
      </template>
    </el-dialog>

    <!-- 试卷分析弹窗 -->
    <el-dialog
      v-model="analysisDialogVisible"
      title="试卷分析报告"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="analysisData" class="analysis-container">
        <!-- 基本信息 -->
        <div class="analysis-section">
          <h4>基本信息</h4>
          <div class="info-cards">
            <el-card class="info-card">
              <div class="info-value">{{ analysisData.total_questions }}</div>
              <div class="info-label">题目数量</div>
            </el-card>
            <el-card class="info-card">
              <div class="info-value">{{ analysisData.total_score }}</div>
              <div class="info-label">总分</div>
            </el-card>
            <el-card class="info-card">
              <div class="info-value">{{ analysisData.estimated_time }}分钟</div>
              <div class="info-label">预估完成时间</div>
            </el-card>
            <el-card class="info-card">
              <div class="info-value" :class="getCoverageClass(analysisData.coverage_rate)">
                {{ analysisData.coverage_rate }}%
              </div>
              <div class="info-label">知识点覆盖率</div>
            </el-card>
          </div>
        </div>

        <!-- 题型统计 -->
        <div class="analysis-section">
          <h4>题型统计</h4>
          <el-table :data="getTypeStatsTable(analysisData.type_stats)" stripe style="width: 100%">
            <el-table-column prop="type" label="题型" width="120">
              <template #default="{ row }">{{ row.type }}</template>
            </el-table-column>
            <el-table-column prop="count" label="题数" width="80" />
            <el-table-column prop="score" label="分值" width="80" />
            <el-table-column label="占比">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.percentage"
                  :stroke-width="12"
                  :color="getTypeColor(row.type)"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 难度分布 -->
        <div class="analysis-section">
          <h4>难度分布</h4>
          <div class="difficulty-bars">
            <div class="difficulty-item">
              <span class="difficulty-label">简单</span>
              <div class="difficulty-bar-wrapper">
                <el-progress
                  :percentage="analysisData.difficulty_distribution.easy"
                  :stroke-width="16"
                  color="#67c23a"
                  :show-text="true"
                />
              </div>
              <span class="difficulty-count">{{ analysisData.difficulty_stats.easy }}题</span>
            </div>
            <div class="difficulty-item">
              <span class="difficulty-label">中等</span>
              <div class="difficulty-bar-wrapper">
                <el-progress
                  :percentage="analysisData.difficulty_distribution.medium"
                  :stroke-width="16"
                  color="#e6a23c"
                  :show-text="true"
                />
              </div>
              <span class="difficulty-count">{{ analysisData.difficulty_stats.medium }}题</span>
            </div>
            <div class="difficulty-item">
              <span class="difficulty-label">困难</span>
              <div class="difficulty-bar-wrapper">
                <el-progress
                  :percentage="analysisData.difficulty_distribution.hard"
                  :stroke-width="16"
                  color="#f56c6c"
                  :show-text="true"
                />
              </div>
              <span class="difficulty-count">{{ analysisData.difficulty_stats.hard }}题</span>
            </div>
          </div>
        </div>

        <!-- 知识点覆盖 -->
        <div class="analysis-section">
          <h4>知识点覆盖情况</h4>
          <div class="knowledge-coverage">
            <div class="coverage-summary">
              <span>已配置知识点：{{ analysisData.selected_knowledge_points?.length || 0 }}个</span>
              <span>实际覆盖：{{ analysisData.covered_knowledge_points?.length || 0 }}个</span>
              <span>覆盖率：{{ analysisData.coverage_rate }}%</span>
            </div>
            <div v-if="analysisData.knowledge_point_stats && Object.keys(analysisData.knowledge_point_stats).length > 0" class="knowledge-table">
              <el-table :data="getKnowledgePointStatsTable(analysisData.knowledge_point_stats)" stripe style="width: 100%">
                <el-table-column prop="kp_id" label="知识点ID" width="100" />
                <el-table-column prop="count" label="题目数" width="100" />
                <el-table-column prop="score" label="总分" width="100" />
                <el-table-column label="覆盖状态" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.covered ? 'success' : 'danger'" size="small">
                      {{ row.covered ? '已覆盖' : '未覆盖' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-alert v-else type="info" :closable="false" style="margin-top: 12px;">
              该试卷未配置知识点覆盖范围，或题目未关联知识点
            </el-alert>
          </div>
        </div>

        <!-- 高级分析指标 -->
        <div class="analysis-section">
          <h4>高级分析</h4>
          <div class="advanced-metrics">
            <div class="metric-card">
              <div class="metric-label">区分度</div>
              <div class="metric-value">
                <el-tag :type="getDiscriminationType(analysisData.discrimination_index)" size="large">
                  {{ analysisData.discrimination_index ?? '-' }}
                </el-tag>
              </div>
              <div class="metric-desc">越高越能区分学生水平</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">预估通过率</div>
              <div class="metric-value">
                <el-progress
                  :percentage="analysisData.predicted_pass_rate || 0"
                  :stroke-width="18"
                  :color="getPassRateColor(analysisData.predicted_pass_rate)"
                />
              </div>
              <div class="metric-desc">基于难度分布估算</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">综合质量分</div>
              <div class="metric-value">
                <el-progress
                  :percentage="analysisData.quality_score || 0"
                  :stroke-width="18"
                  :color="getQualityScoreColor(analysisData.quality_score)"
                />
              </div>
              <div class="metric-desc">覆盖率、难度、区分度综合评估</div>
            </div>
          </div>

          <!-- 知识点掌握度 -->
          <div v-if="analysisData.knowledge_mastery && analysisData.knowledge_mastery.length > 0" class="knowledge-mastery">
            <h5 style="margin-top: 16px;">知识点掌握度</h5>
            <el-table :data="analysisData.knowledge_mastery" stripe style="width: 100%">
              <el-table-column prop="knowledge_point_id" label="知识点ID" width="120" />
              <el-table-column prop="count" label="题目数" width="100" />
              <el-table-column prop="score" label="总分" width="100" />
              <el-table-column prop="avg_difficulty" label="平均难度" width="120">
                <template #default="{ row }">
                  <el-rate
                    :model-value="row.avg_difficulty"
                    disabled
                    :max="5"
                    :colors="['#67c23a', '#e6a23c', '#f56c6c']"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="mastery_level" label="掌握度" width="120">
                <template #default="{ row }">
                  <el-tag :type="getMasteryType(row.mastery_level)" size="small">
                    {{ getMasteryLabel(row.mastery_level) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 分析建议 -->
        <div class="analysis-section" v-if="analysisSuggestions.length > 0">
          <h4>优化建议</h4>
          <div class="suggestions">
            <div v-for="(suggestion, index) in analysisSuggestions" :key="index" class="suggestion-item">
              <el-icon class="suggestion-icon"><Warning /></el-icon>
              <span>{{ suggestion }}</span>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="analysisDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportWord">导出Word</el-button>
        <el-button type="primary" @click="exportPdf">导出PDF</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史弹窗 -->
    <el-dialog
      v-model="versionDialogVisible"
      title="版本历史"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="currentVersionPaperId">
        <el-table :data="versionList" stripe style="width: 100%">
          <el-table-column prop="version_number" label="版本号" width="100" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="change_log" label="变更说明" min-width="200" show-overflow-tooltip />
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link size="small" @click="showVersionDetail(row)">详情</el-button>
              <el-button link size="small" type="warning" @click="restoreVersion(row)">回滚</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-container" style="margin-top: 16px; justify-content: flex-end;">
          <el-pagination
            v-model:current-page="versionPagination.page"
            v-model:page-size="versionPagination.pageSize"
            :total="versionPagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="handleVersionPageChange"
            @current-change="handleVersionPageChange"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="versionDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 版本详情弹窗 -->
    <el-dialog
      v-model="versionDetailDialogVisible"
      :title="`版本 ${versionDetail?.version_number || ''} 详情`"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="versionDetail" class="version-detail">
        <div class="version-info">
          <p><strong>标题：</strong>{{ versionDetail.title }}</p>
          <p v-if="versionDetail.description"><strong>描述：</strong>{{ versionDetail.description }}</p>
          <p><strong>变更日志：</strong>{{ versionDetail.change_log || '无' }}</p>
          <p><strong>创建时间：</strong>{{ formatDate(versionDetail.created_at) }}</p>
        </div>

        <div class="version-questions" v-if="versionDetail.questions_snapshot && versionDetail.questions_snapshot.length > 0">
          <h4>题目列表（{{ versionDetail.questions_snapshot.length }}题）</h4>
          <el-table :data="versionDetail.questions_snapshot" stripe style="width: 100%">
            <el-table-column prop="order" label="序号" width="80" />
            <el-table-column prop="question_id" label="题目ID" width="120" />
            <el-table-column prop="score" label="分值" width="100" />
          </el-table>
        </div>
        <el-alert v-else type="info" :closable="false">该版本无题目数据</el-alert>
      </div>
      <template #footer>
        <el-button @click="versionDetailDialogVisible = false">关闭</el-button>
        <el-button type="warning" @click="restoreVersion(versionDetail)">回滚到此版本</el-button>
      </template>
    </el-dialog>

    <!-- 相似度检测弹窗 -->
    <el-dialog
      v-model="similarityDialogVisible"
      title="题目相似度检测"
      width="1000px"
      :close-on-click-modal="false"
    >
      <div v-if="similarityData">
        <div class="similarity-summary">
          <span>检测试卷：{{ previewPaperData?.title }}</span>
          <span>检测题目数：{{ similarityData.total_checked }} 题</span>
          <span>发现相似对：<strong :style="{color: similarityData.similar_pairs_count > 0 ? '#f56c6c' : '#67c23a'}">{{ similarityData.similar_pairs_count }}</strong> 对</span>
        </div>

        <el-alert v-if="similarityData.message" type="info" :closable="false" style="margin-bottom: 16px;">
          {{ similarityData.message }}
        </el-alert>

        <el-table v-if="similarityData.similar_pairs.length > 0" :data="similarityData.similar_pairs" stripe style="width: 100%">
          <el-table-column label="相似度" width="120">
            <template #default="{ row }">
              <el-tag :type="getSimilarityType(row.similarity_score)" size="large">
                {{ Math.round(row.similarity_score * 100) }}%
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="相似等级" width="120">
            <template #default="{ row }">
              <el-tag :type="getSimilarityType(row.similarity_score)" size="small">
                {{ getSimilarityLevel(row.similarity_score) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="question_type" label="题型" width="120">
            <template #default="{ row }">
              {{ getQuestionTypeName(row.question_type) }}
            </template>
          </el-table-column>
          <el-table-column label="题目A" min-width="250" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="similarity-content">
                <span class="similarity-id">#{{ row.question_a_id }}</span>
                <span>{{ row.question_a_content }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="题目B" min-width="250" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="similarity-content">
                <span class="similarity-id">#{{ row.question_b_id }}</span>
                <span>{{ row.question_b_content }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="similarity_reason" label="相似原因" min-width="180" show-overflow-tooltip />
        </el-table>

        <el-empty v-else description="未发现相似题目" :image-size="80" />
      </div>
      <div v-else class="similarity-empty">
        <p>点击下方按钮开始检测试卷中的相似题目</p>
        <div class="similarity-config">
          <span>相似度阈值：</span>
          <el-slider v-model="similarityThreshold" :min="0" :max="1" :step="0.1" style="width: 300px;" />
          <span>{{ Math.round(similarityThreshold * 100) }}%</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="similarityDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="runSimilarityCheck" :loading="similarityLoading">
          {{ similarityData ? '重新检测' : '开始检测' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, ArrowDown, Warning } from '@element-plus/icons-vue'
import { adminAPI, systemAPI, paperAPI, api } from '@/api'

// 工具函数
const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 状态
const loading = ref(false)
const loadingCategories = ref(false)
const loadingSubjects = ref(false)
const paperList = ref([])
const selectedRows = ref([])
const searchKeyword = ref('')
const paperDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const isEdit = ref(false)
const saveLoading = ref(false)
const currentEditId = ref(null)
const previewPaperData = ref(null)
const tableRef = ref(null)
const paperFormRef = ref(null)

// 试卷分析
const analysisDialogVisible = ref(false)
const analysisData = ref(null)
const analysisSuggestions = ref([])

// 版本管理
const versionDialogVisible = ref(false)
const versionDetailDialogVisible = ref(false)
const versionList = ref([])
const versionDetail = ref(null)
const currentVersionPaperId = ref(null)
const versionPagination = reactive({ page: 1, pageSize: 20, total: 0 })

// 相似度检测
const similarityDialogVisible = ref(false)
const similarityLoading = ref(false)
const similarityData = ref(null)
const similarityThreshold = ref(0.7)

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 筛选表单
const filterForm = reactive({
  categoryId: null,
  subjectId: null,
  status: null
})

// 考试种类选项
const categoryOptions = ref([])

// 考试科目选项
const subjectOptions = ref([])

// 计算属性：按考试种类筛选考试科目
const filteredSubjectOptions = computed(() => {
  if (!filterForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === filterForm.categoryId)
})

// 弹窗内的考试科目（过滤用）
const dialogFilteredSubjects = computed(() => {
  if (!paperForm.categoryId) return subjectOptions.value
  return subjectOptions.value.filter(s => s.category_id === paperForm.categoryId)
})

// 试卷表单
const paperForm = reactive({
  title: '',
  categoryId: null,
  subjectId: null,
  totalTime: 120,
  totalScore: 100,
  passingScore: 60,
  description: ''
})

// 表单验证规则
const formRules = {
  title: [{ required: true, message: '请输入试卷标题', trigger: 'blur' }],
  categoryId: [{ required: true, message: '请选择考试种类', trigger: 'change' }],
  subjectId: [{ required: true, message: '请选择考试科目', trigger: 'change' }],
  totalTime: [{ required: true, message: '请输入时长', trigger: 'blur' }],
  totalScore: [{ required: true, message: '请输入总分', trigger: 'blur' }],
  passingScore: [{ required: true, message: '请输入及格分', trigger: 'blur' }]
}

// 挂载时获取数据
onMounted(() => {
  fetchCategories()
  fetchSubjects()
  fetchPaperList()
})

// 获取考试种类
const fetchCategories = async () => {
  loadingCategories.value = true
  try {
    const res = await systemAPI.getExamCategories()
    categoryOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试种类失败:', e)
  } finally {
    loadingCategories.value = false
  }
}

// 获取考试科目
const fetchSubjects = async () => {
  loadingSubjects.value = true
  try {
    const res = await systemAPI.getExamTypes()
    subjectOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取考试科目失败:', e)
  } finally {
    loadingSubjects.value = false
  }
}

// 获取试卷列表
const fetchPaperList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filterForm.categoryId) params.category_id = filterForm.categoryId
    if (filterForm.subjectId) params.subject_id = filterForm.subjectId
    if (filterForm.status !== null) params.status = filterForm.status
    if (searchKeyword.value) params.keyword = searchKeyword.value

    const res = await adminAPI.getPapers(params)
    paperList.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取试卷列表失败:', e)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  fetchPaperList()
}

// 分页变化
const handleSizeChange = () => {
  pagination.page = 1
  fetchPaperList()
}

const handlePageChange = () => {
  fetchPaperList()
}

// 考试种类变化
const handleCategoryChange = () => {
  filterForm.subjectId = null
  fetchPaperList()
}

// 弹窗内考试种类变化
const handleDialogCategoryChange = () => {
  paperForm.subjectId = null
}

// 获取科目名称
const getSubjectName = (subjectId) => {
  // exam_types.subject_id 对应 subjects.id
  const subject = subjectOptions.value.find(s => s.subject_id === subjectId)
  return subject?.name || ''
}

// 状态名称
const getStatusName = (status) => {
  const map = { 0: '草稿', 1: '已发布', 2: '已归档' }
  return map[status] ?? '草稿'
}

// 状态标签类型
const getStatusTagType = (status) => {
  const map = { 0: 'info', 1: 'success', 2: 'warning' }
  return map[status] ?? 'info'
}

// 题型名称
const getQuestionTypeName = (type) => {
  const map = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'essay': '简答题'
  }
  return map[type] || type
}

// 获取选择题正确答案标签
const getCorrectAnswerLabels = (options) => {
  if (!options || options.length === 0) return ''
  const correctLabels = options.filter(opt => opt.is_correct).map(opt => opt.option_label)
  return correctLabels.join(', ')
}

// 表格选择变化
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 打开新建弹窗
const openPaperDialog = () => {
  isEdit.value = false
  currentEditId.value = null
  resetPaperForm()
  paperDialogVisible.value = true
}

// 编辑试卷
const editPaper = (row) => {
  isEdit.value = true
  currentEditId.value = row.id
  paperForm.title = row.title
  // 根据subject_id反推category_id（需要遍历）
  const subject = subjectOptions.value.find(s => s.id === row.subject_id)
  paperForm.categoryId = subject?.category_id || null
  paperForm.subjectId = row.subject_id
  paperForm.totalTime = row.total_time
  paperForm.totalScore = row.total_score
  paperForm.passingScore = row.passing_score
  paperForm.description = row.description || ''
  paperDialogVisible.value = true
}

// 行内更多操作
const handleRowCommand = (command, row) => {
  if (command === 'analyze') {
    analyzePaper(row)
  } else if (command === 'version') {
    showVersionHistory(row)
  } else if (command === 'similarity') {
    showSimilarityCheck(row)
  }
}

// 重置表单
const resetPaperForm = () => {
  paperForm.title = ''
  paperForm.categoryId = null
  paperForm.subjectId = null
  paperForm.totalTime = 120
  paperForm.totalScore = 100
  paperForm.passingScore = 60
  paperForm.description = ''
}

// 保存试卷
const savePaper = async () => {
  try {
    await paperFormRef.value.validate()
  } catch {
    return
  }

  saveLoading.value = true
  try {
    const data = {
      title: paperForm.title,
      subject_id: paperForm.subjectId,
      total_time: paperForm.totalTime,
      total_score: paperForm.totalScore,
      passing_score: paperForm.passingScore,
      description: paperForm.description,
      paper_type: 1,
      questions: []
    }

    if (isEdit.value) {
      await adminAPI.updatePaper(currentEditId.value, data)
      ElMessage.success('试卷更新成功')
    } else {
      await adminAPI.createPaper(data)
      ElMessage.success('试卷创建成功')
    }

    paperDialogVisible.value = false
    fetchPaperList()
  } catch (e) {
    console.error('保存试卷失败:', e)
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    saveLoading.value = false
  }
}

// 预览试卷
const previewPaper = async (row) => {
  try {
    const res = await adminAPI.getPaperById(row.id)
    previewPaperData.value = res.data
    previewDialogVisible.value = true
  } catch (e) {
    console.error('获取试卷详情失败:', e)
    ElMessage.error('获取试卷详情失败')
  }
}

// 分析试卷
const analyzePaper = async (row) => {
  try {
    const res = await paperAPI.getPaperAnalysis(row.id)
    analysisData.value = res.data
    analysisSuggestions.value = generateAnalysisSuggestions(res.data)
    analysisDialogVisible.value = true
  } catch (e) {
    console.error('获取试卷分析失败:', e)
    ElMessage.error('获取试卷分析失败')
  }
}

// 版本管理
const showVersionHistory = async (row) => {
  currentVersionPaperId.value = row.id
  versionDialogVisible.value = true
  await fetchVersions(row.id)
}

const fetchVersions = async (paperId) => {
  versionList.value = []
  versionPagination.total = 0
  try {
    const res = await paperAPI.getPaperVersions(paperId, { page: versionPagination.page, page_size: versionPagination.pageSize })
    versionList.value = res.data?.items || []
    versionPagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取版本历史失败:', e)
    ElMessage.error('获取版本历史失败')
  }
}

const showVersionDetail = async (version) => {
  try {
    const res = await paperAPI.getPaperVersion(currentVersionPaperId.value, version.id)
    versionDetail.value = res.data
    versionDetailDialogVisible.value = true
  } catch (e) {
    console.error('获取版本详情失败:', e)
    ElMessage.error('获取版本详情失败')
  }
}

const restoreVersion = async (version) => {
  try {
    await ElMessageBox.confirm(`确定要回滚到版本 ${version.version_number} 吗？当前版本将被覆盖。`, '确认回滚', { type: 'warning' })
    await paperAPI.restorePaperVersion(currentVersionPaperId.value, version.id)
    ElMessage.success(`已回滚到版本 ${version.version_number}`)
    versionDetailDialogVisible.value = false
    await fetchVersions(currentVersionPaperId.value)
  } catch (e) {
    if (e !== 'cancel') {
      console.error('回滚失败:', e)
      ElMessage.error('回滚失败')
    }
  }
}

const handleVersionPageChange = () => {
  fetchVersions(currentVersionPaperId.value)
}

// 相似度检测
const showSimilarityCheck = (row) => {
  similarityData.value = null
  similarityThreshold.value = 0.7
  similarityDialogVisible.value = true
}

const runSimilarityCheck = async () => {
  if (!previewPaperData.value) return
  similarityLoading.value = true
  try {
    const res = await paperAPI.checkSimilarity(previewPaperData.value.id, {
      threshold: similarityThreshold.value
    })
    similarityData.value = res.data
    if (similarityData.value.similar_pairs_count === 0) {
      ElMessage.success('未发现相似题目')
    } else {
      ElMessage.warning(`发现 ${similarityData.value.similar_pairs_count} 对相似题目`)
    }
  } catch (e) {
    console.error('相似度检测失败:', e)
    ElMessage.error('相似度检测失败')
  } finally {
    similarityLoading.value = false
  }
}

const getSimilarityType = (score) => {
  if (score >= 0.9) return 'danger'
  if (score >= 0.8) return 'warning'
  return 'info'
}

const getSimilarityLevel = (score) => {
  if (score >= 0.9) return '高度相似'
  if (score >= 0.8) return '中度相似'
  return '轻度相似'
}

// 生成分析建议
const generateAnalysisSuggestions = (data) => {
  const suggestions = []

  // 知识点覆盖率建议
  if (data.coverage_rate < 60) {
    suggestions.push(`知识点覆盖率仅${data.coverage_rate}%，建议补充更多知识点以确保考核全面性`)
  } else if (data.coverage_rate < 80) {
    suggestions.push(`知识点覆盖率为${data.coverage_rate}%，覆盖率良好，可考虑补充部分未覆盖知识点`)
  }

  // 难度分布建议
  const easyPercent = data.difficulty_distribution.easy || 0
  const hardPercent = data.difficulty_distribution.hard || 0

  if (easyPercent > 60) {
    suggestions.push('简单题目占比过高，建议增加中等和困难题目以提升试卷区分度')
  } else if (hardPercent > 50) {
    suggestions.push('困难题目占比过高，建议适当增加简单和中等题目，避免试卷过于困难')
  }

  // 题型分布建议
  const typeStats = data.type_stats || {}
  const totalQuestions = data.total_questions || 0

  if (totalQuestions > 0) {
    const choiceQuestions = (typeStats.single_choice?.count || 0) + (typeStats.multiple_choice?.count || 0)
    const choicePercent = choiceQuestions / totalQuestions * 100

    if (choicePercent > 80) {
      suggestions.push('客观题（选择题）占比过高，建议增加主观题（如简答题）以考察综合能力')
    }
  }

  // 预估时间建议
  if (data.estimated_time > data.total_time) {
    suggestions.push(`预估完成时间（${data.estimated_time}分钟）超过试卷设定时长（${data.total_time}分钟），建议适当减少题量或增加时长`)
  }

  // 高级指标建议
  if (data.discrimination_index != null && data.discrimination_index < 5) {
    suggestions.push(`区分度较低（${data.discrimination_index}/10），建议调整难度分布，增加中高难度题目比例`)
  }

  if (data.predicted_pass_rate != null && data.predicted_pass_rate < 50) {
    suggestions.push(`预估通过率偏低（${data.predicted_pass_rate}%），建议适当降低难度或增加基础题`)
  } else if (data.predicted_pass_rate != null && data.predicted_pass_rate > 90) {
    suggestions.push(`预估通过率偏高（${data.predicted_pass_rate}%），建议适当提升难度以更好区分学生水平`)
  }

  if (data.quality_score != null && data.quality_score < 60) {
    suggestions.push(`试卷综合质量分较低（${data.quality_score}/100），建议优化知识点覆盖、难度分布和题型配比`)
  }

  return suggestions
}

// 分析数据格式化辅助函数
const getTypeStatsTable = (typeStats) => {
  if (!typeStats) return []
  const total = Object.values(typeStats).reduce((sum, item) => sum + (item.count || 0), 0)
  return Object.entries(typeStats).map(([type, stats]) => ({
    type: getQuestionTypeName(type),
    count: stats.count || 0,
    score: stats.score || 0,
    percentage: total > 0 ? Math.round((stats.count / total) * 100) : 0
  }))
}

const getTypeColor = (type) => {
  const map = {
    '单选题': '#409eff',
    '多选题': '#67c23a',
    '判断题': '#e6a23c',
    '简答题': '#f56c6c'
  }
  return map[type] || '#909399'
}

const getCoverageClass = (rate) => {
  if (rate >= 80) return 'coverage-good'
  if (rate >= 60) return 'coverage-medium'
  return 'coverage-poor'
}

const getKnowledgePointStatsTable = (kpStats) => {
  if (!kpStats) return []
  return Object.entries(kpStats).map(([kpId, stats]) => ({
    kp_id: kpId,
    count: stats.count || 0,
    score: stats.score || 0,
    covered: (stats.count || 0) > 0
  }))
}

const getDiscriminationType = (value) => {
  if (value == null) return 'info'
  if (value >= 8) return 'success'
  if (value >= 5) return 'warning'
  return 'danger'
}

const getPassRateColor = (value) => {
  if (value == null) return '#909399'
  if (value >= 75) return '#67c23a'
  if (value >= 50) return '#e6a23c'
  return '#f56c6c'
}

const getQualityScoreColor = (value) => {
  if (value == null) return '#909399'
  if (value >= 80) return '#67c23a'
  if (value >= 60) return '#e6a23c'
  return '#f56c6c'
}

const getMasteryType = (level) => {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[level] || 'info'
}

const getMasteryLabel = (level) => {
  const map = { high: '掌握良好', medium: '一般', low: '待加强' }
  return map[level] || level
}

// 发布试卷
const publishPaper = (row) => {
  ElMessageBox.confirm('确定要发布这份试卷吗？', '确认发布', { type: 'info' })
    .then(async () => {
      try {
        await adminAPI.updatePaper(row.id, { status: 1 })
        ElMessage.success('试卷发布成功')
        fetchPaperList()
      } catch (e) {
        console.error('发布失败:', e)
        ElMessage.error('发布失败')
      }
    })
    .catch(() => {})
}

// 归档试卷
const archivePaper = (row) => {
  ElMessageBox.confirm('确定要归档这份试卷吗？', '确认归档', { type: 'info' })
    .then(async () => {
      try {
        await adminAPI.updatePaper(row.id, { status: 2 })
        ElMessage.success('试卷归档成功')
        fetchPaperList()
      } catch (e) {
        console.error('归档失败:', e)
        ElMessage.error('归档失败')
      }
    })
    .catch(() => {})
}

// 归档试卷
const deletePaper = (row) => {
  ElMessageBox.confirm(`确定要归档试卷"${row.title}"吗？`, '确认归档', { type: 'warning' })
    .then(async () => {
      try {
        await adminAPI.deletePaper(Number(row.id))
        ElMessage.success('归档成功')
        fetchPaperList()
      } catch (e) {
        console.error('归档失败:', e)
        ElMessage.error('归档失败')
      }
    })
    .catch(() => {})
}

// 批量操作
const handleBatchCommand = (command) => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要操作的试卷')
    return
  }

  const ids = selectedRows.value.map(r => r.id)

  if (command === 'publish') {
    ElMessageBox.confirm(`确定要发布选中的 ${ids.length} 份试卷吗？`, '批量发布', { type: 'info' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.updatePaper(id, { status: 1 })
          }
          ElMessage.success('批量发布成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量发布失败')
        }
      })
      .catch(() => {})
  } else if (command === 'archive') {
    ElMessageBox.confirm(`确定要归档选中的 ${ids.length} 份试卷吗？`, '批量归档', { type: 'info' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.updatePaper(id, { status: 2 })
          }
          ElMessage.success('批量归档成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量归档失败')
        }
      })
      .catch(() => {})
  } else if (command === 'delete') {
    ElMessageBox.confirm(`确定要归档选中的 ${ids.length} 份试卷吗？`, '批量归档', { type: 'warning' })
      .then(async () => {
        try {
          for (const id of ids) {
            await adminAPI.deletePaper(Number(id))
          }
          ElMessage.success('批量归档成功')
          fetchPaperList()
        } catch (e) {
          ElMessage.error('批量归档失败')
        }
      })
      .catch(() => {})
  }
}

// 导出Word
const exportWord = async () => {
  if (!previewPaperData.value) return
  try {
    ElMessage.info('正在导出Word文档...')
    const response = await api.post(`/papers/export`, {
      paper_id: previewPaperData.value.id,
      format: 'word'
    }, {
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${previewPaperData.value.title || '试卷'}.docx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败，请稍后重试')
  }
}

// 导出PDF
const exportPdf = async () => {
  if (!previewPaperData.value) return
  try {
    ElMessage.info('正在导出PDF文档...')
    const response = await api.post(`/papers/export`, {
      paper_id: previewPaperData.value.id,
      format: 'pdf'
    }, {
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${previewPaperData.value.title || '试卷'}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败，请稍后重试')
  }
}
</script>

<style scoped>
.paper-management-view {
  padding: 0;
}

.operation-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.left-operations {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 160px;
}

.filter-select {
  width: 140px;
}

.right-operations {
  display: flex;
  gap: 12px;
}

.table-container {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.operation-buttons {
  display: flex;
  gap: 8px;
}

.delete-btn {
  color: #f56c6c;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.paper-preview {
  max-height: 60vh;
  overflow-y: auto;
}

.preview-header {
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e4e7ed;
}

.preview-header h2 {
  margin: 0 0 12px 0;
  color: #303133;
}

.preview-info {
  display: flex;
  justify-content: center;
  gap: 24px;
  color: #606266;
  font-size: 14px;
}

.preview-questions {
  padding: 0 8px;
}

.preview-question-item {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.question-header {
  margin-bottom: 8px;
  font-size: 14px;
  color: #409eff;
}

.question-index {
  font-weight: 600;
  margin-right: 4px;
}

.question-type {
  margin-right: 8px;
}

.question-score {
  color: #67c23a;
}

.question-content {
  color: #303133;
  line-height: 1.6;
  margin-bottom: 12px;
}

.question-options {
  margin-top: 12px;
  padding-left: 20px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  line-height: 1.6;
}

.option-label {
  font-weight: 500;
  color: #409eff;
}

.correct-badge {
  color: #67c23a;
  font-size: 12px;
  margin-left: 8px;
}

.true-false-answer,
.essay-answer,
.choice-answer,
.question-explanation {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
}

.choice-answer {
  background: #f0f9ff;
  border: 1px solid #409eff;
  color: #303133;
}

.question-explanation {
  background: #f5f7fa;
  color: #606266;
  line-height: 1.6;
}

.answer-label {
  color: #67c23a;
  font-weight: 500;
}

.explanation-label {
  color: #909eff;
  font-weight: 500;
}

/* Analysis styles */
.analysis-container {
  max-height: 65vh;
  overflow-y: auto;
}

.analysis-section {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.analysis-section:last-child {
  border-bottom: none;
}

.analysis-section h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #303133;
  font-weight: 600;
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.info-card {
  text-align: center;
  padding: 16px;
}

.info-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.info-label {
  font-size: 13px;
  color: #909399;
}

.coverage-good {
  color: #67c23a;
}

.coverage-medium {
  color: #e6a23c;
}

.coverage-poor {
  color: #f56c6c;
}

.difficulty-bars {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.difficulty-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.difficulty-label {
  width: 60px;
  font-size: 14px;
  color: #606266;
}

.difficulty-bar-wrapper {
  flex: 1;
}

.difficulty-count {
  width: 80px;
  text-align: right;
  font-size: 14px;
  color: #606266;
}

.coverage-summary {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
  color: #606266;
}

.knowledge-table {
  margin-top: 12px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  background: #fdf6ec;
  border-left: 4px solid #e6a23c;
  border-radius: 4px;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.suggestion-icon {
  color: #e6a23c;
  margin-top: 2px;
}

.advanced-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.metric-card {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.metric-value {
  margin-bottom: 8px;
}

.metric-desc {
  font-size: 12px;
  color: #909399;
}

.knowledge-mastery {
  margin-top: 16px;
}

.similarity-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
}

.similarity-summary span:last-child {
  font-weight: 600;
}

.similarity-empty {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.similarity-config {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
  font-size: 14px;
  color: #606266;
}

.similarity-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.similarity-id {
  font-size: 12px;
  color: #909399;
}
</style>
