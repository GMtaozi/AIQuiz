import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API module
vi.mock('@/api', () => ({
  adminAPI: {
    getQuestions: vi.fn(),
    createQuestion: vi.fn(),
    updateQuestion: vi.fn(),
    deleteQuestion: vi.fn(),
    batchDeleteQuestions: vi.fn(),
    batchUpdateQuestionStatus: vi.fn(),
    exportQuestions: vi.fn()
  },
  systemAPI: {
    getExamCategories: vi.fn(),
    getExamTypes: vi.fn()
  },
  questionBankAPI: {
    previewImport: vi.fn(),
    importQuestions: vi.fn(),
    checkSimilarity: vi.fn()
  }
}))

// Mock element-plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  },
  ElMessageBox: {
    confirm: vi.fn().mockResolvedValue(undefined)
  }
}))

import {
  loading,
  searchKeyword,
  questionList,
  selectedQuestions,
  categoryOptions,
  examTypeOptions,
  loadingCategories,
  loadingExamTypes,
  questionDialogVisible,
  previewDialogVisible,
  importDialogVisible,
  exportDialogVisible,
  isEdit,
  submitLoading,
  currentQuestion,
  importTab,
  importFormat,
  importText,
  importing,
  importProgress,
  importedCount,
  totalCount,
  importResult,
  uploadRef,
  selectedFile,
  importCategoryId,
  importSubjectId,
  previewResult,
  exportForm,
  pagination,
  filterForm,
  questionForm,
  formRules,
  importProgressStatus,
  filteredExamTypeOptions,
  handleCategoryChange,
  fetchCategories,
  fetchExamTypes,
  fetchQuestionList,
  handleSearch,
  handleSizeChange,
  handlePageChange,
  handleSelectionChange,
  handleStatusChange,
  handleBatchCommand,
  handleBatchDelete,
  handleBatchStatusChange,
  openQuestionDialog,
  editQuestion,
  resetQuestionForm,
  submitQuestionForm,
  deleteQuestion,
  previewQuestion,
  addOption,
  removeOption,
  showImportDialog,
  handlePreview,
  resetPreview,
  handleFileChange,
  downloadTemplate,
  startImport,
  showExportDialog,
  startExport,
  getTypeName,
  getDifficultyType,
  getDifficultyName,
  getStatusName,
  getStatusTagType,
  getExamTypeName,
  getCategoryName,
  formatDate,
  escapeHtml,
  renderMarkdown,
  isCorrectAnswer,
  formatAnswer,
  useQuestionBank
} from '@/composables/useQuestionBank'

import { adminAPI, systemAPI, questionBankAPI } from '@/api'

describe('useQuestionBank', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset state
    loading.value = false
    searchKeyword.value = ''
    questionList.value = []
    selectedQuestions.value = []
    categoryOptions.value = []
    examTypeOptions.value = []
    loadingCategories.value = false
    loadingExamTypes.value = false
    questionDialogVisible.value = false
    previewDialogVisible.value = false
    importDialogVisible.value = false
    exportDialogVisible.value = false
    isEdit.value = false
    submitLoading.value = false
    currentQuestion.value = null
    importTab.value = 'excel'
    importFormat.value = 'excel'
    importText.value = ''
    importing.value = false
    importProgress.value = 0
    importedCount.value = 0
    totalCount.value = 0
    importResult.value = null
    uploadRef.value = null
    selectedFile.value = null
    importCategoryId.value = null
    importSubjectId.value = null
    previewResult.value = null
    exportForm.format = 'excel'
    exportForm.scope = 'filtered'
    exportForm.fields = ['content', 'type', 'difficulty', 'answer']
    pagination.page = 1
    pagination.pageSize = 20
    pagination.total = 0
    filterForm.categoryId = null
    filterForm.examTypeId = null
    filterForm.questionType = ''
    filterForm.difficulty = ''
    filterForm.status = null
    questionForm.id = null
    questionForm.type = 'single'
    questionForm.difficulty = 'medium'
    questionForm.score = 5
    questionForm.content = ''
    questionForm.options = [
      { content: '' },
      { content: '' },
      { content: '' },
      { content: '' }
    ]
    questionForm.correctAnswer = 0
    questionForm.judgeAnswer = true
    questionForm.knowledgePointIds = []
    questionForm.explanation = ''
  })

  describe('Initialization State', () => {
    it('should have correct initial state', () => {
      expect(loading.value).toBe(false)
      expect(searchKeyword.value).toBe('')
      expect(questionList.value).toEqual([])
      expect(selectedQuestions.value).toEqual([])
      expect(categoryOptions.value).toEqual([])
      expect(examTypeOptions.value).toEqual([])
      expect(loadingCategories.value).toBe(false)
      expect(loadingExamTypes.value).toBe(false)
      expect(questionDialogVisible.value).toBe(false)
      expect(previewDialogVisible.value).toBe(false)
      expect(importDialogVisible.value).toBe(false)
      expect(exportDialogVisible.value).toBe(false)
      expect(isEdit.value).toBe(false)
      expect(submitLoading.value).toBe(false)
      expect(currentQuestion.value).toBeNull()
    })

    it('should have correct initial pagination', () => {
      expect(pagination.page).toBe(1)
      expect(pagination.pageSize).toBe(20)
      expect(pagination.total).toBe(0)
    })

    it('should have correct initial filter form', () => {
      expect(filterForm.categoryId).toBeNull()
      expect(filterForm.examTypeId).toBeNull()
      expect(filterForm.questionType).toBe('')
      expect(filterForm.difficulty).toBe('')
      expect(filterForm.status).toBeNull()
    })

    it('should have correct initial question form', () => {
      expect(questionForm.id).toBeNull()
      expect(questionForm.type).toBe('single')
      expect(questionForm.difficulty).toBe('medium')
      expect(questionForm.score).toBe(5)
      expect(questionForm.content).toBe('')
      expect(questionForm.options.length).toBe(4)
      expect(questionForm.correctAnswer).toBe(0)
      expect(questionForm.judgeAnswer).toBe(true)
      expect(questionForm.knowledgePointIds).toEqual([])
      expect(questionForm.explanation).toBe('')
    })
  })

  describe('Utility Functions', () => {
    describe('getTypeName', () => {
      it('should return correct type names', () => {
        expect(getTypeName('single')).toBe('单选题')
        expect(getTypeName('single_choice')).toBe('单选题')
        expect(getTypeName('multiple')).toBe('多选题')
        expect(getTypeName('multiple_choice')).toBe('多选题')
        expect(getTypeName('judge')).toBe('判断题')
        expect(getTypeName('true_false')).toBe('判断题')
        expect(getTypeName('short_answer')).toBe('简答题')
        expect(getTypeName('essay')).toBe('简答题')
      })

      it('should return original type for unknown type', () => {
        expect(getTypeName('unknown')).toBe('unknown')
      })
    })

    describe('getDifficultyType', () => {
      it('should return correct difficulty types for numbers', () => {
        expect(getDifficultyType(1)).toBe('success')
        expect(getDifficultyType(2)).toBe('success')
        expect(getDifficultyType(3)).toBe('warning')
        expect(getDifficultyType(4)).toBe('danger')
        expect(getDifficultyType(5)).toBe('danger')
      })

      it('should return correct difficulty types for strings', () => {
        expect(getDifficultyType('easy')).toBe('success')
        expect(getDifficultyType('medium')).toBe('warning')
        expect(getDifficultyType('hard')).toBe('danger')
      })

      it('should return "info" for unknown difficulty', () => {
        expect(getDifficultyType('unknown')).toBe('info')
      })
    })

    describe('getDifficultyName', () => {
      it('should return correct difficulty names for numbers', () => {
        expect(getDifficultyName(1)).toBe('简单')
        expect(getDifficultyName(2)).toBe('简单')
        expect(getDifficultyName(3)).toBe('中等')
        expect(getDifficultyName(4)).toBe('困难')
        expect(getDifficultyName(5)).toBe('困难')
      })

      it('should return correct difficulty names for strings', () => {
        expect(getDifficultyName('easy')).toBe('简单')
        expect(getDifficultyName('medium')).toBe('中等')
        expect(getDifficultyName('hard')).toBe('困难')
      })

      it('should return original difficulty for unknown difficulty', () => {
        expect(getDifficultyName('unknown')).toBe('unknown')
      })
    })

    describe('getStatusName', () => {
      it('should return correct status names', () => {
        expect(getStatusName(0)).toBe('禁用')
        expect(getStatusName(1)).toBe('启用')
        expect(getStatusName(2)).toBe('待启用')
      })

      it('should return "启用" for unknown status', () => {
        expect(getStatusName(999)).toBe('启用')
      })
    })

    describe('getStatusTagType', () => {
      it('should return correct tag types', () => {
        expect(getStatusTagType(0)).toBe('danger')
        expect(getStatusTagType(1)).toBe('success')
        expect(getStatusTagType(2)).toBe('warning')
      })

      it('should return "info" for unknown status', () => {
        expect(getStatusTagType(999)).toBe('info')
      })
    })

    describe('getExamTypeName', () => {
      it('should return exam type name for valid id', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', subject_id: 1, category_id: 1 },
          { id: 2, name: 'English', subject_id: 2, category_id: 1 }
        ]
        expect(getExamTypeName(1)).toBe('Math')
        expect(getExamTypeName(2)).toBe('English')
      })

      it('should return empty string for invalid id', () => {
        examTypeOptions.value = [{ id: 1, name: 'Math', subject_id: 1, category_id: 1 }]
        expect(getExamTypeName(999)).toBe('')
      })

      it('should return empty string for null id', () => {
        expect(getExamTypeName(null)).toBe('')
      })
    })

    describe('getCategoryName', () => {
      it('should return category name for valid id', () => {
        categoryOptions.value = [
          { id: 1, name: 'Category 1' },
          { id: 2, name: 'Category 2' }
        ]
        expect(getCategoryName(1)).toBe('Category 1')
        expect(getCategoryName(2)).toBe('Category 2')
      })

      it('should return empty string for invalid id', () => {
        categoryOptions.value = [{ id: 1, name: 'Category 1' }]
        expect(getCategoryName(999)).toBe('')
      })

      it('should return empty string for null id', () => {
        expect(getCategoryName(null)).toBe('')
      })
    })

    describe('formatDate', () => {
      it('should format date correctly', () => {
        const result = formatDate('2024-01-15T10:30:00')
        expect(result).toBe('2024-01-15')
      })

      it('should return "-" for null date', () => {
        expect(formatDate(null)).toBe('-')
      })

      it('should return "-" for undefined date', () => {
        expect(formatDate(undefined)).toBe('-')
      })
    })

    describe('escapeHtml', () => {
      it('should escape HTML special characters', () => {
        expect(escapeHtml('<script>alert("xss")</script>')).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;')
      })

      it('should return empty string for null', () => {
        expect(escapeHtml(null)).toBe('')
      })

      it('should return empty string for undefined', () => {
        expect(escapeHtml(undefined)).toBe('')
      })
    })

    describe('renderMarkdown', () => {
      it('should render bold markdown', () => {
        expect(renderMarkdown('**bold**')).toBe('<strong>bold</strong>')
      })

      it('should render italic markdown', () => {
        expect(renderMarkdown('*italic*')).toBe('<em>italic</em>')
      })

      it('should render code markdown', () => {
        expect(renderMarkdown('`code`')).toBe('<code>code</code>')
      })

      it('should escape HTML before rendering markdown', () => {
        expect(renderMarkdown('**<script>**')).toBe('<strong>&lt;script&gt;</strong>')
      })

      it('should return empty string for null content', () => {
        expect(renderMarkdown(null)).toBe('')
      })
    })

    describe('isCorrectAnswer', () => {
      it('should return true for correct answer', () => {
        currentQuestion.value = { answer: 'A' }
        expect(isCorrectAnswer(0)).toBe(true)
      })

      it('should return false for incorrect answer', () => {
        currentQuestion.value = { answer: 'B' }
        expect(isCorrectAnswer(0)).toBe(false)
      })

      it('should handle array answer', () => {
        currentQuestion.value = { answer: ['A', 'C'] }
        expect(isCorrectAnswer(0)).toBe(true)
        expect(isCorrectAnswer(2)).toBe(true)
        expect(isCorrectAnswer(1)).toBe(false)
      })

      it('should return false when no current question', () => {
        currentQuestion.value = null
        expect(isCorrectAnswer(0)).toBe(false)
      })
    })

    describe('formatAnswer', () => {
      it('should format array answer', () => {
        expect(formatAnswer(['A', 'C'])).toBe('A, C')
      })

      it('should format string answer', () => {
        expect(formatAnswer('A')).toBe('A')
      })

      it('should return "-" for null answer', () => {
        expect(formatAnswer(null)).toBe('-')
      })
    })
  })

  describe('Computed Properties', () => {
    describe('importProgressStatus', () => {
      it('should return "success" when progress is 100', () => {
        importProgress.value = 100
        expect(importProgressStatus.value).toBe('success')
      })

      it('should return undefined when progress is not 100', () => {
        importProgress.value = 50
        expect(importProgressStatus.value).toBeUndefined()
      })
    })

    describe('filteredExamTypeOptions', () => {
      it('should return all exam types when no category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        filterForm.categoryId = null
        expect(filteredExamTypeOptions.value.length).toBe(2)
      })

      it('should return filtered exam types when category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        filterForm.categoryId = 1
        expect(filteredExamTypeOptions.value.length).toBe(1)
        expect(filteredExamTypeOptions.value[0].name).toBe('Math')
      })
    })
  })

  describe('API Functions', () => {
    describe('fetchCategories', () => {
      it('should fetch categories successfully', async () => {
        const mockCategories = [{ id: 1, name: 'Category 1' }]
        vi.mocked(systemAPI.getExamCategories).mockResolvedValue({
          data: { items: mockCategories }
        } as any)

        await fetchCategories()

        expect(categoryOptions.value).toEqual(mockCategories)
        expect(loadingCategories.value).toBe(false)
      })

      it('should handle fetch categories error', async () => {
        vi.mocked(systemAPI.getExamCategories).mockRejectedValue(new Error('Network error'))

        await fetchCategories()

        expect(categoryOptions.value).toEqual([])
        expect(loadingCategories.value).toBe(false)
      })
    })

    describe('fetchExamTypes', () => {
      it('should fetch exam types successfully', async () => {
        const mockExamTypes = [{ id: 1, name: 'Math', category_id: 1, subject_id: 1 }]
        vi.mocked(systemAPI.getExamTypes).mockResolvedValue({
          data: { items: mockExamTypes }
        } as any)

        await fetchExamTypes()

        expect(examTypeOptions.value).toEqual(mockExamTypes)
        expect(loadingExamTypes.value).toBe(false)
      })

      it('should handle fetch exam types error', async () => {
        vi.mocked(systemAPI.getExamTypes).mockRejectedValue(new Error('Network error'))

        await fetchExamTypes()

        expect(examTypeOptions.value).toEqual([])
        expect(loadingExamTypes.value).toBe(false)
      })
    })

    describe('fetchQuestionList', () => {
      it('should fetch question list successfully', async () => {
        const mockQuestions = [
          { id: 1, content: 'Question 1', status: 1, created_at: '2024-01-01' }
        ]
        vi.mocked(adminAPI.getQuestions).mockResolvedValue({
          data: { items: mockQuestions, total: 1 }
        } as any)

        await fetchQuestionList()

        expect(questionList.value.length).toBe(1)
        expect(questionList.value[0].createTime).toBe('2024-01-01')
        expect(pagination.total).toBe(1)
        expect(loading.value).toBe(false)
      })

      it('should handle fetch question list error', async () => {
        vi.mocked(adminAPI.getQuestions).mockRejectedValue(new Error('Network error'))

        await fetchQuestionList()

        expect(loading.value).toBe(false)
      })

      it('should pass correct params with filters', async () => {
        filterForm.categoryId = 1
        filterForm.examTypeId = 2
        filterForm.questionType = 'single'
        filterForm.difficulty = 'medium'
        filterForm.status = 1
        searchKeyword.value = 'test'
        pagination.page = 2
        pagination.pageSize = 10

        vi.mocked(adminAPI.getQuestions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        await fetchQuestionList()

        expect(adminAPI.getQuestions).toHaveBeenCalledWith({
          page: 2,
          page_size: 10,
          keyword: 'test',
          question_type: 'single_choice',
          difficulty: 3,
          category_id: 1,
          subject_id: 2,
          status: 1
        })
      })
    })
  })

  describe('Handler Functions', () => {
    describe('handleSearch', () => {
      it('should reset page to 1 and fetch question list', () => {
        pagination.page = 3
        vi.mocked(adminAPI.getQuestions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleSearch()

        expect(pagination.page).toBe(1)
      })
    })

    describe('handleSizeChange', () => {
      it('should update page size and fetch question list', () => {
        vi.mocked(adminAPI.getQuestions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleSizeChange(50)

        expect(pagination.pageSize).toBe(50)
      })
    })

    describe('handlePageChange', () => {
      it('should update page and fetch question list', () => {
        vi.mocked(adminAPI.getQuestions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handlePageChange(3)

        expect(pagination.page).toBe(3)
      })
    })

    describe('handleSelectionChange', () => {
      it('should update selected questions', () => {
        const selection = [{ id: 1, content: 'Question 1' }] as any

        handleSelectionChange(selection)

        expect(selectedQuestions.value).toEqual(selection)
      })
    })

    describe('handleStatusChange', () => {
      it('should update question status successfully', async () => {
        vi.mocked(adminAPI.updateQuestion).mockResolvedValue({} as any)

        await handleStatusChange({ id: 1, status: 1 } as any)

        expect(adminAPI.updateQuestion).toHaveBeenCalledWith(1, { status: 1 })
      })

      it('should handle status update error', async () => {
        vi.mocked(adminAPI.updateQuestion).mockRejectedValue(new Error('Network error'))

        await handleStatusChange({ id: 1, status: 1 } as any)

        expect(adminAPI.updateQuestion).toHaveBeenCalled()
      })
    })

    describe('handleCategoryChange', () => {
      it('should reset examTypeId', () => {
        filterForm.examTypeId = 2

        handleCategoryChange()

        expect(filterForm.examTypeId).toBeNull()
      })
    })
  })

  describe('Dialog Operations', () => {
    describe('openQuestionDialog', () => {
      it('should open dialog in create mode', () => {
        isEdit.value = true

        openQuestionDialog()

        expect(isEdit.value).toBe(false)
        expect(questionDialogVisible.value).toBe(true)
      })
    })

    describe('editQuestion', () => {
      it('should open dialog in edit mode with question data', () => {
        const row = {
          id: 1,
          question_type: 'single_choice',
          difficulty: 3,
          score: 5,
          content: 'Test question',
          options: [{ option_content: 'Option A' }],
          answer: 'A',
          meta: { knowledge_point_ids: [1, 2] },
          explanation: 'Test explanation'
        } as any

        editQuestion(row)

        expect(isEdit.value).toBe(true)
        expect(questionForm.id).toBe(1)
        expect(questionForm.type).toBe('single')
        expect(questionForm.difficulty).toBe('medium')
        expect(questionForm.score).toBe(5)
        expect(questionForm.content).toBe('Test question')
        expect(questionForm.options.length).toBe(1)
        expect(questionForm.correctAnswer).toBe('A')
        expect(questionForm.knowledgePointIds).toEqual([1, 2])
        expect(questionForm.explanation).toBe('Test explanation')
        expect(questionDialogVisible.value).toBe(true)
      })
    })

    describe('resetQuestionForm', () => {
      it('should reset question form to initial values', () => {
        questionForm.id = 1
        questionForm.type = 'multiple'
        questionForm.difficulty = 'hard'
        questionForm.score = 10
        questionForm.content = 'Test'
        questionForm.options = [{ content: 'A' }]
        questionForm.correctAnswer = 1
        questionForm.judgeAnswer = false
        questionForm.knowledgePointIds = [1]
        questionForm.explanation = 'Test'

        resetQuestionForm()

        expect(questionForm.id).toBeNull()
        expect(questionForm.type).toBe('single')
        expect(questionForm.difficulty).toBe('medium')
        expect(questionForm.score).toBe(5)
        expect(questionForm.content).toBe('')
        expect(questionForm.options.length).toBe(4)
        expect(questionForm.correctAnswer).toBe(0)
        expect(questionForm.judgeAnswer).toBe(true)
        expect(questionForm.knowledgePointIds).toEqual([])
        expect(questionForm.explanation).toBe('')
      })
    })
  })

  describe('Option Operations', () => {
    describe('addOption', () => {
      it('should add option when less than 6', () => {
        questionForm.options = [{ content: 'A' }, { content: 'B' }]

        addOption()

        expect(questionForm.options.length).toBe(3)
      })

      it('should not add option when 6 or more', () => {
        questionForm.options = [
          { content: 'A' },
          { content: 'B' },
          { content: 'C' },
          { content: 'D' },
          { content: 'E' },
          { content: 'F' }
        ]

        addOption()

        expect(questionForm.options.length).toBe(6)
      })
    })

    describe('removeOption', () => {
      it('should remove option at index', () => {
        questionForm.options = [
          { content: 'A' },
          { content: 'B' },
          { content: 'C' }
        ]

        removeOption(1)

        expect(questionForm.options.length).toBe(2)
        expect(questionForm.options[0].content).toBe('A')
        expect(questionForm.options[1].content).toBe('C')
      })

      it('should adjust correctAnswer if needed', () => {
        questionForm.options = [
          { content: 'A' },
          { content: 'B' },
          { content: 'C' }
        ]
        questionForm.correctAnswer = 2

        removeOption(1)

        expect(questionForm.correctAnswer).toBe(1)
      })
    })
  })

  describe('Import Functions', () => {
    describe('showImportDialog', () => {
      it('should open import dialog and reset state', () => {
        importResult.value = { success: 1, failed: 0 } as any
        previewResult.value = { questions: [] } as any
        importProgress.value = 50
        importedCount.value = 5

        showImportDialog()

        expect(importDialogVisible.value).toBe(true)
        expect(importResult.value).toBeNull()
        expect(previewResult.value).toBeNull()
        expect(importProgress.value).toBe(0)
        expect(importedCount.value).toBe(0)
      })
    })

    describe('handleFileChange', () => {
      it('should set selected file and format for excel', () => {
        const file = new File(['test'], 'test.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
        const fileObj = { raw: file, name: 'test.xlsx' }

        handleFileChange(fileObj as any)

        expect(selectedFile.value).toBeInstanceOf(File)
        expect(importFormat.value).toBe('excel')
      })

      it('should set selected file and format for word', () => {
        const file = new File(['test'], 'test.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
        const fileObj = { raw: file, name: 'test.docx' }

        handleFileChange(fileObj as any)

        expect(selectedFile.value).toBeInstanceOf(File)
        expect(importFormat.value).toBe('word')
      })
    })

    describe('resetPreview', () => {
      it('should reset preview state', () => {
        previewResult.value = { questions: [] } as any
        selectedFile.value = new File(['test'], 'test.xlsx')
        uploadRef.value = { clearFiles: vi.fn() }

        resetPreview()

        expect(previewResult.value).toBeNull()
        expect(selectedFile.value).toBeNull()
        expect(uploadRef.value.clearFiles).toHaveBeenCalled()
      })
    })
  })

  describe('Export Functions', () => {
    describe('showExportDialog', () => {
      it('should open export dialog', () => {
        showExportDialog()

        expect(exportDialogVisible.value).toBe(true)
      })
    })
  })

  describe('Batch Operations', () => {
    describe('handleBatchCommand', () => {
      it('should handle import command', () => {
        handleBatchCommand('import')

        expect(importDialogVisible.value).toBe(true)
      })

      it('should show warning for delete with no selection', () => {
        selectedQuestions.value = []

        handleBatchCommand('delete')

        expect(adminAPI.batchDeleteQuestions).not.toHaveBeenCalled()
      })

      it('should show warning for export with no selection', () => {
        selectedQuestions.value = []

        handleBatchCommand('export')

        expect(exportDialogVisible.value).toBe(false)
      })

      it('should show warning for status with no selection', () => {
        selectedQuestions.value = []

        handleBatchCommand('status')

        expect(adminAPI.batchUpdateQuestionStatus).not.toHaveBeenCalled()
      })
    })
  })

  describe('Similarity Check', () => {
    let composable: ReturnType<typeof useQuestionBank>

    beforeEach(() => {
      composable = useQuestionBank()
    })

    describe('showSimilarityCheck', () => {
      it('should reset similarity data and open dialog', () => {
        composable.similarityData.value = { similar_pairs_count: 1 } as any
        composable.similarityThreshold.value = 0.5

        composable.showSimilarityCheck()

        expect(composable.similarityData.value).toBeNull()
        expect(composable.similarityThreshold.value).toBe(0.7)
        expect(composable.similarityDialogVisible.value).toBe(true)
      })
    })

    describe('runSimilarityCheck', () => {
      it('should run similarity check successfully', async () => {
        filterForm.examTypeId = 1
        filterForm.questionType = 'single'
        composable.similarityThreshold.value = 0.8
        vi.mocked(questionBankAPI.checkSimilarity).mockResolvedValue({
          data: { similar_pairs_count: 0, similar_pairs: [] }
        } as any)

        await composable.runSimilarityCheck()

        expect(composable.similarityData.value).toEqual({ similar_pairs_count: 0, similar_pairs: [] })
        expect(composable.similarityLoading.value).toBe(false)
      })

      it('should handle similarity check error', async () => {
        vi.mocked(questionBankAPI.checkSimilarity).mockRejectedValue(new Error('Network error'))

        await composable.runSimilarityCheck()

        expect(composable.similarityLoading.value).toBe(false)
      })
    })

    describe('getSimilarityType', () => {
      it('should return "danger" for score >= 0.9', () => {
        expect(composable.getSimilarityType(0.9)).toBe('danger')
        expect(composable.getSimilarityType(1.0)).toBe('danger')
      })

      it('should return "warning" for score >= 0.8 and < 0.9', () => {
        expect(composable.getSimilarityType(0.8)).toBe('warning')
        expect(composable.getSimilarityType(0.85)).toBe('warning')
      })

      it('should return "info" for score < 0.8', () => {
        expect(composable.getSimilarityType(0.7)).toBe('info')
        expect(composable.getSimilarityType(0.5)).toBe('info')
      })
    })

    describe('getSimilarityLevel', () => {
      it('should return "高度相似" for score >= 0.9', () => {
        expect(composable.getSimilarityLevel(0.9)).toBe('高度相似')
        expect(composable.getSimilarityLevel(1.0)).toBe('高度相似')
      })

      it('should return "中度相似" for score >= 0.8 and < 0.9', () => {
        expect(composable.getSimilarityLevel(0.8)).toBe('中度相似')
        expect(composable.getSimilarityLevel(0.85)).toBe('中度相似')
      })

      it('should return "轻度相似" for score < 0.8', () => {
        expect(composable.getSimilarityLevel(0.7)).toBe('轻度相似')
        expect(composable.getSimilarityLevel(0.5)).toBe('轻度相似')
      })
    })
  })

  describe('Composable', () => {
    it('should return all required properties and methods', () => {
      const composable = useQuestionBank()

      expect(composable).toHaveProperty('loading')
      expect(composable).toHaveProperty('searchKeyword')
      expect(composable).toHaveProperty('questionList')
      expect(composable).toHaveProperty('selectedQuestions')
      expect(composable).toHaveProperty('categoryOptions')
      expect(composable).toHaveProperty('examTypeOptions')
      expect(composable).toHaveProperty('loadingCategories')
      expect(composable).toHaveProperty('loadingExamTypes')
      expect(composable).toHaveProperty('questionDialogVisible')
      expect(composable).toHaveProperty('previewDialogVisible')
      expect(composable).toHaveProperty('importDialogVisible')
      expect(composable).toHaveProperty('exportDialogVisible')
      expect(composable).toHaveProperty('isEdit')
      expect(composable).toHaveProperty('submitLoading')
      expect(composable).toHaveProperty('currentQuestion')
      expect(composable).toHaveProperty('importTab')
      expect(composable).toHaveProperty('importFormat')
      expect(composable).toHaveProperty('importText')
      expect(composable).toHaveProperty('importing')
      expect(composable).toHaveProperty('importProgress')
      expect(composable).toHaveProperty('importedCount')
      expect(composable).toHaveProperty('totalCount')
      expect(composable).toHaveProperty('importResult')
      expect(composable).toHaveProperty('uploadRef')
      expect(composable).toHaveProperty('selectedFile')
      expect(composable).toHaveProperty('importCategoryId')
      expect(composable).toHaveProperty('importSubjectId')
      expect(composable).toHaveProperty('previewResult')
      expect(composable).toHaveProperty('exportForm')
      expect(composable).toHaveProperty('pagination')
      expect(composable).toHaveProperty('filterForm')
      expect(composable).toHaveProperty('questionForm')
      expect(composable).toHaveProperty('formRules')
      expect(composable).toHaveProperty('importProgressStatus')
      expect(composable).toHaveProperty('filteredExamTypeOptions')
      expect(composable).toHaveProperty('handleCategoryChange')
      expect(composable).toHaveProperty('fetchCategories')
      expect(composable).toHaveProperty('fetchExamTypes')
      expect(composable).toHaveProperty('fetchQuestionList')
      expect(composable).toHaveProperty('handleSearch')
      expect(composable).toHaveProperty('handleSizeChange')
      expect(composable).toHaveProperty('handlePageChange')
      expect(composable).toHaveProperty('handleSelectionChange')
      expect(composable).toHaveProperty('handleStatusChange')
      expect(composable).toHaveProperty('handleBatchCommand')
      expect(composable).toHaveProperty('handleBatchDelete')
      expect(composable).toHaveProperty('handleBatchStatusChange')
      expect(composable).toHaveProperty('openQuestionDialog')
      expect(composable).toHaveProperty('editQuestion')
      expect(composable).toHaveProperty('resetQuestionForm')
      expect(composable).toHaveProperty('submitQuestionForm')
      expect(composable).toHaveProperty('deleteQuestion')
      expect(composable).toHaveProperty('showImportDialog')
      expect(composable).toHaveProperty('handlePreview')
      expect(composable).toHaveProperty('resetPreview')
      expect(composable).toHaveProperty('handleFileChange')
      expect(composable).toHaveProperty('downloadTemplate')
      expect(composable).toHaveProperty('startImport')
      expect(composable).toHaveProperty('showExportDialog')
      expect(composable).toHaveProperty('startExport')
      expect(composable).toHaveProperty('getTypeName')
      expect(composable).toHaveProperty('getDifficultyType')
      expect(composable).toHaveProperty('getDifficultyName')
      expect(composable).toHaveProperty('getStatusName')
      expect(composable).toHaveProperty('getStatusTagType')
      expect(composable).toHaveProperty('getExamTypeName')
      expect(composable).toHaveProperty('getCategoryName')
      expect(composable).toHaveProperty('formatDate')
      expect(composable).toHaveProperty('renderMarkdown')
      expect(composable).toHaveProperty('isCorrectAnswer')
      expect(composable).toHaveProperty('formatAnswer')
      expect(composable).toHaveProperty('similarityDialogVisible')
      expect(composable).toHaveProperty('similarityLoading')
      expect(composable).toHaveProperty('similarityData')
      expect(composable).toHaveProperty('similarityThreshold')
      expect(composable).toHaveProperty('showSimilarityCheck')
      expect(composable).toHaveProperty('runSimilarityCheck')
      expect(composable).toHaveProperty('getSimilarityType')
      expect(composable).toHaveProperty('getSimilarityLevel')
    })
  })
})
