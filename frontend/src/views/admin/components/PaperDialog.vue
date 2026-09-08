<template>
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
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import {
  paperDialogVisible,
  isEdit,
  saveLoading,
  paperForm,
  formRules,
  categoryOptions,
  dialogFilteredSubjects,
  handleDialogCategoryChange,
  resetPaperForm,
  savePaper,
  paperFormRef
} from '@/composables/usePaperManagement'

const handleCancel = () => {
  paperDialogVisible.value = false
  resetPaperForm()
}

const handleSave = async () => {
  await savePaper()
}
</script>

<style scoped>
/* No additional styles needed - uses Element Plus defaults */
</style>
