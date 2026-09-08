import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API module
vi.mock('@/api', () => ({
  adminAPI: {
    getPapers: vi.fn(),
    getPaperById: vi.fn(),
    createPaper: vi.fn(),
    updatePaper: vi.fn(),
    deletePaper: vi.fn()
  },
  systemAPI: {
    getExamCategories: vi.fn(),
    getExamTypes: vi.fn()
  },
  paperAPI: {
    getPaperAnalysis: vi.fn(),
    checkSimilarity: vi.fn(),
    getPaperVersions: vi.fn(),
    getPaperVersion: vi.fn(),
    restorePaperVersion: vi.fn()
  },
  api: {
    post: vi.fn()
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
  loadingCategories,
  loadingSubjects,
  paperList,
  selectedRows,
  searchKeyword,
  paperDialogVisible,
  previewDialogVisible,
  isEdit,
  saveLoading,
  currentEditId,
  previewPaperData,
  analysisDialogVisible,
  analysisData,
  analysisSuggestions,
  versionDialogVisible,
  versionDetailDialogVisible,
  versionList,
  versionDetail,
  currentVersionPaperId,
  versionPagination,
  similarityDialogVisible,
  similarityLoading,
  similarityData,
  similarityThreshold,
  pagination,
  filterForm,
  categoryOptions,
  subjectOptions,
  paperForm,
  formRules,
  filteredSubjectOptions,
  dialogFilteredSubjects,
  formatDate,
  getSubjectName,
  getStatusName,
  getStatusTagType,
  getQuestionTypeName,
  getCorrectAnswerLabels,
  fetchCategories,
  fetchSubjects,
  fetchPaperList,
  handleSearch,
  handleSizeChange,
  handlePageChange,
  handleCategoryChange,
  handleDialogCategoryChange,
  handleSelectionChange,
  openPaperDialog,
  editPaper,
  resetPaperForm,
  savePaper,
  previewPaper,
  analyzePaper,
  generateAnalysisSuggestions,
  getTypeStatsTable,
  getTypeColor,
  getCoverageClass,
  getKnowledgePointStatsTable,
  getDiscriminationType,
  getPassRateColor,
  getQualityScoreColor,
  getMasteryType,
  getMasteryLabel,
  showVersionHistory,
  fetchVersions,
  showVersionDetail,
  restoreVersion,
  handleVersionPageChange,
  showSimilarityCheck,
  runSimilarityCheck,
  getSimilarityType,
  getSimilarityLevel,
  handleRowCommand,
  publishPaper,
  archivePaper,
  deletePaper,
  handleBatchCommand,
  exportWord,
  exportPdf,
  usePaperManagement
} from '@/composables/usePaperManagement'

import { adminAPI, systemAPI, paperAPI } from '@/api'

describe('usePaperManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset state
    loading.value = false
    paperList.value = []
    selectedRows.value = []
    searchKeyword.value = ''
    paperDialogVisible.value = false
    previewDialogVisible.value = false
    isEdit.value = false
    saveLoading.value = false
    currentEditId.value = null
    previewPaperData.value = null
    analysisDialogVisible.value = false
    analysisData.value = null
    analysisSuggestions.value = []
    versionDialogVisible.value = false
    versionList.value = []
    versionDetail.value = null
    currentVersionPaperId.value = null
    versionPagination.page = 1
    versionPagination.pageSize = 20
    versionPagination.total = 0
    similarityDialogVisible.value = false
    similarityLoading.value = false
    similarityData.value = null
    similarityThreshold.value = 0.7
    pagination.page = 1
    pagination.pageSize = 20
    pagination.total = 0
    filterForm.categoryId = null
    filterForm.subjectId = null
    filterForm.status = null
    categoryOptions.value = []
    subjectOptions.value = []
    paperForm.title = ''
    paperForm.categoryId = null
    paperForm.subjectId = null
    paperForm.totalTime = 120
    paperForm.totalScore = 100
    paperForm.passingScore = 60
    paperForm.description = ''
  })

  describe('Initialization State', () => {
    it('should have correct initial state', () => {
      expect(loading.value).toBe(false)
      expect(paperList.value).toEqual([])
      expect(selectedRows.value).toEqual([])
      expect(searchKeyword.value).toBe('')
      expect(paperDialogVisible.value).toBe(false)
      expect(previewDialogVisible.value).toBe(false)
      expect(isEdit.value).toBe(false)
      expect(saveLoading.value).toBe(false)
      expect(currentEditId.value).toBeNull()
      expect(previewPaperData.value).toBeNull()
      expect(analysisDialogVisible.value).toBe(false)
      expect(analysisData.value).toBeNull()
      expect(analysisSuggestions.value).toEqual([])
      expect(versionDialogVisible.value).toBe(false)
      expect(versionList.value).toEqual([])
      expect(versionDetail.value).toBeNull()
      expect(currentVersionPaperId.value).toBeNull()
      expect(similarityDialogVisible.value).toBe(false)
      expect(similarityLoading.value).toBe(false)
      expect(similarityData.value).toBeNull()
      expect(similarityThreshold.value).toBe(0.7)
    })

    it('should have correct initial pagination', () => {
      expect(pagination.page).toBe(1)
      expect(pagination.pageSize).toBe(20)
      expect(pagination.total).toBe(0)
    })

    it('should have correct initial filter form', () => {
      expect(filterForm.categoryId).toBeNull()
      expect(filterForm.subjectId).toBeNull()
      expect(filterForm.status).toBeNull()
    })

    it('should have correct initial paper form', () => {
      expect(paperForm.title).toBe('')
      expect(paperForm.categoryId).toBeNull()
      expect(paperForm.subjectId).toBeNull()
      expect(paperForm.totalTime).toBe(120)
      expect(paperForm.totalScore).toBe(100)
      expect(paperForm.passingScore).toBe(60)
      expect(paperForm.description).toBe('')
    })
  })

  describe('Utility Functions', () => {
    describe('formatDate', () => {
      it('should format date correctly', () => {
        const result = formatDate('2024-01-15T10:30:00')
        expect(result).toBe('2024-01-15 10:30:00')
      })

      it('should return "-" for null date', () => {
        expect(formatDate(null)).toBe('-')
      })

      it('should return "-" for undefined date', () => {
        expect(formatDate(undefined)).toBe('-')
      })
    })

    describe('getSubjectName', () => {
      it('should return subject name for valid id', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 1, subject_id: 2 }
        ]
        expect(getSubjectName(1)).toBe('Math')
        expect(getSubjectName(2)).toBe('English')
      })

      it('should return empty string for invalid id', () => {
        subjectOptions.value = [{ id: 1, name: 'Math', category_id: 1, subject_id: 1 }]
        expect(getSubjectName(999)).toBe('')
      })
    })

    describe('getStatusName', () => {
      it('should return correct status names', () => {
        expect(getStatusName(0)).toBe('草稿')
        expect(getStatusName(1)).toBe('已发布')
        expect(getStatusName(2)).toBe('已归档')
      })

      it('should return "草稿" for unknown status', () => {
        expect(getStatusName(999)).toBe('草稿')
      })
    })

    describe('getStatusTagType', () => {
      it('should return correct tag types', () => {
        expect(getStatusTagType(0)).toBe('info')
        expect(getStatusTagType(1)).toBe('success')
        expect(getStatusTagType(2)).toBe('warning')
      })

      it('should return "info" for unknown status', () => {
        expect(getStatusTagType(999)).toBe('info')
      })
    })

    describe('getQuestionTypeName', () => {
      it('should return correct question type names', () => {
        expect(getQuestionTypeName('single_choice')).toBe('单选题')
        expect(getQuestionTypeName('multiple_choice')).toBe('多选题')
        expect(getQuestionTypeName('true_false')).toBe('判断题')
        expect(getQuestionTypeName('essay')).toBe('简答题')
      })

      it('should return original type for unknown type', () => {
        expect(getQuestionTypeName('unknown')).toBe('unknown')
      })
    })

    describe('getCorrectAnswerLabels', () => {
      it('should return correct answer labels', () => {
        const options = [
          { is_correct: true, option_label: 'A' },
          { is_correct: false, option_label: 'B' },
          { is_correct: true, option_label: 'C' }
        ]
        expect(getCorrectAnswerLabels(options)).toBe('A, C')
      })

      it('should return empty string for empty options', () => {
        expect(getCorrectAnswerLabels([])).toBe('')
      })

      it('should return empty string for null options', () => {
        expect(getCorrectAnswerLabels(null as any)).toBe('')
      })
    })
  })

  describe('Computed Properties', () => {
    describe('filteredSubjectOptions', () => {
      it('should return all subjects when no category selected', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        filterForm.categoryId = null
        expect(filteredSubjectOptions.value.length).toBe(2)
      })

      it('should return filtered subjects when category selected', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        filterForm.categoryId = 1
        expect(filteredSubjectOptions.value.length).toBe(1)
        expect(filteredSubjectOptions.value[0].name).toBe('Math')
      })
    })

    describe('dialogFilteredSubjects', () => {
      it('should return all subjects when no category selected in dialog', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        paperForm.categoryId = null
        expect(dialogFilteredSubjects.value.length).toBe(2)
      })

      it('should return filtered subjects when category selected in dialog', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 },
          { id: 2, name: 'English', category_id: 2, subject_id: 2 }
        ]
        paperForm.categoryId = 1
        expect(dialogFilteredSubjects.value.length).toBe(1)
        expect(dialogFilteredSubjects.value[0].name).toBe('Math')
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

    describe('fetchSubjects', () => {
      it('should fetch subjects successfully', async () => {
        const mockSubjects = [{ id: 1, name: 'Subject 1', category_id: 1, subject_id: 1 }]
        vi.mocked(systemAPI.getExamTypes).mockResolvedValue({
          data: { items: mockSubjects }
        } as any)

        await fetchSubjects()

        expect(subjectOptions.value).toEqual(mockSubjects)
        expect(loadingSubjects.value).toBe(false)
      })

      it('should handle fetch subjects error', async () => {
        vi.mocked(systemAPI.getExamTypes).mockRejectedValue(new Error('Network error'))

        await fetchSubjects()

        expect(subjectOptions.value).toEqual([])
        expect(loadingSubjects.value).toBe(false)
      })
    })

    describe('fetchPaperList', () => {
      it('should fetch paper list successfully', async () => {
        const mockPapers = [{ id: 1, title: 'Paper 1', status: 1 }]
        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: mockPapers, total: 1 }
        } as any)

        await fetchPaperList()

        expect(paperList.value).toEqual(mockPapers)
        expect(pagination.total).toBe(1)
        expect(loading.value).toBe(false)
      })

      it('should handle fetch paper list error', async () => {
        vi.mocked(adminAPI.getPapers).mockRejectedValue(new Error('Network error'))

        await fetchPaperList()

        expect(paperList.value).toEqual([])
        expect(loading.value).toBe(false)
      })

      it('should pass correct params with filters', async () => {
        filterForm.categoryId = 1
        filterForm.subjectId = 2
        filterForm.status = 1
        searchKeyword.value = 'test'
        pagination.page = 2
        pagination.pageSize = 10

        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        await fetchPaperList()

        expect(adminAPI.getPapers).toHaveBeenCalledWith({
          page: 2,
          page_size: 10,
          category_id: 1,
          subject_id: 2,
          status: 1,
          keyword: 'test'
        })
      })
    })
  })

  describe('Handler Functions', () => {
    describe('handleSearch', () => {
      it('should reset page to 1 and fetch paper list', async () => {
        pagination.page = 3
        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleSearch()

        expect(pagination.page).toBe(1)
      })
    })

    describe('handleSizeChange', () => {
      it('should reset page to 1 and fetch paper list', () => {
        pagination.page = 3
        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleSizeChange()

        expect(pagination.page).toBe(1)
      })
    })

    describe('handlePageChange', () => {
      it('should fetch paper list', () => {
        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handlePageChange()

        expect(adminAPI.getPapers).toHaveBeenCalled()
      })
    })

    describe('handleCategoryChange', () => {
      it('should reset subjectId and fetch paper list', () => {
        filterForm.subjectId = 2
        vi.mocked(adminAPI.getPapers).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleCategoryChange()

        expect(filterForm.subjectId).toBeNull()
      })
    })

    describe('handleDialogCategoryChange', () => {
      it('should reset paperForm subjectId', () => {
        paperForm.subjectId = 2

        handleDialogCategoryChange()

        expect(paperForm.subjectId).toBeNull()
      })
    })

    describe('handleSelectionChange', () => {
      it('should update selectedRows', () => {
        const rows = [{ id: 1, title: 'Paper 1' }] as any

        handleSelectionChange(rows)

        expect(selectedRows.value).toEqual(rows)
      })
    })
  })

  describe('Dialog Operations', () => {
    describe('openPaperDialog', () => {
      it('should open dialog in create mode', () => {
        isEdit.value = true
        currentEditId.value = 1

        openPaperDialog()

        expect(isEdit.value).toBe(false)
        expect(currentEditId.value).toBeNull()
        expect(paperDialogVisible.value).toBe(true)
      })
    })

    describe('editPaper', () => {
      it('should open dialog in edit mode with paper data', () => {
        subjectOptions.value = [
          { id: 1, name: 'Math', category_id: 1, subject_id: 1 }
        ]
        const row = {
          id: 1,
          title: 'Test Paper',
          subject_id: 1,
          total_time: 90,
          total_score: 100,
          passing_score: 60,
          description: 'Test description',
          status: 1
        } as any

        editPaper(row)

        expect(isEdit.value).toBe(true)
        expect(currentEditId.value).toBe(1)
        expect(paperForm.title).toBe('Test Paper')
        expect(paperForm.categoryId).toBe(1)
        expect(paperForm.subjectId).toBe(1)
        expect(paperForm.totalTime).toBe(90)
        expect(paperForm.totalScore).toBe(100)
        expect(paperForm.passingScore).toBe(60)
        expect(paperForm.description).toBe('Test description')
        expect(paperDialogVisible.value).toBe(true)
      })
    })

    describe('resetPaperForm', () => {
      it('should reset paper form to initial values', () => {
        paperForm.title = 'Test'
        paperForm.categoryId = 1
        paperForm.subjectId = 2
        paperForm.totalTime = 90
        paperForm.totalScore = 80
        paperForm.passingScore = 50
        paperForm.description = 'Test'

        resetPaperForm()

        expect(paperForm.title).toBe('')
        expect(paperForm.categoryId).toBeNull()
        expect(paperForm.subjectId).toBeNull()
        expect(paperForm.totalTime).toBe(120)
        expect(paperForm.totalScore).toBe(100)
        expect(paperForm.passingScore).toBe(60)
        expect(paperForm.description).toBe('')
      })
    })
  })

  describe('Preview Functions', () => {
    describe('previewPaper', () => {
      it('should fetch paper detail and open preview dialog', async () => {
        const mockPaperData = { id: 1, title: 'Paper 1', questions: [] }
        vi.mocked(adminAPI.getPaperById).mockResolvedValue({
          data: mockPaperData
        } as any)

        await previewPaper({ id: 1 } as any)

        expect(previewPaperData.value).toEqual(mockPaperData)
        expect(previewDialogVisible.value).toBe(true)
      })

      it('should handle preview error', async () => {
        vi.mocked(adminAPI.getPaperById).mockRejectedValue(new Error('Network error'))

        await previewPaper({ id: 1 } as any)

        expect(previewPaperData.value).toBeNull()
        expect(previewDialogVisible.value).toBe(false)
      })
    })
  })

  describe('Analysis Functions', () => {
    describe('generateAnalysisSuggestions', () => {
      it('should generate suggestions for low coverage rate', () => {
        const data = {
          coverage_rate: 50,
          difficulty_distribution: { easy: 30, medium: 50, hard: 20 },
          type_stats: { single_choice: { count: 10, score: 20 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.length).toBeGreaterThan(0)
        expect(suggestions[0]).toContain('50%')
      })

      it('should generate suggestions for high easy percentage', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 70, medium: 20, hard: 10 },
          type_stats: { single_choice: { count: 10, score: 20 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('简单题目占比过高'))).toBe(true)
      })

      it('should generate suggestions for high hard percentage', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 20, medium: 20, hard: 60 },
          type_stats: { single_choice: { count: 10, score: 20 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('困难题目占比过高'))).toBe(true)
      })

      it('should generate suggestions for high choice percentage', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: {
            single_choice: { count: 8, score: 16 },
            multiple_choice: { count: 2, score: 4 }
          },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('客观题（选择题）占比过高'))).toBe(true)
      })

      it('should generate suggestions for estimated time exceeding total time', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: { single_choice: { count: 5, score: 10 } },
          total_questions: 10,
          estimated_time: 150,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('预估完成时间'))).toBe(true)
      })

      it('should generate suggestions for low discrimination index', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: { single_choice: { count: 5, score: 10 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 3,
          predicted_pass_rate: 70,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('区分度较低'))).toBe(true)
      })

      it('should generate suggestions for low predicted pass rate', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: { single_choice: { count: 5, score: 10 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 40,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('预估通过率偏低'))).toBe(true)
      })

      it('should generate suggestions for high predicted pass rate', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: { single_choice: { count: 5, score: 10 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 95,
          quality_score: 80
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('预估通过率偏高'))).toBe(true)
      })

      it('should generate suggestions for low quality score', () => {
        const data = {
          coverage_rate: 80,
          difficulty_distribution: { easy: 30, medium: 40, hard: 30 },
          type_stats: { single_choice: { count: 5, score: 10 } },
          total_questions: 10,
          estimated_time: 60,
          total_time: 120,
          discrimination_index: 7,
          predicted_pass_rate: 70,
          quality_score: 50
        }

        const suggestions = generateAnalysisSuggestions(data as any)

        expect(suggestions.some(s => s.includes('试卷综合质量分较低'))).toBe(true)
      })
    })

    describe('getTypeStatsTable', () => {
      it('should return type stats table', () => {
        const typeStats = {
          single_choice: { count: 5, score: 10 },
          multiple_choice: { count: 3, score: 6 }
        }

        const result = getTypeStatsTable(typeStats)

        expect(result.length).toBe(2)
        expect(result[0].type).toBe('单选题')
        expect(result[0].count).toBe(5)
        expect(result[0].score).toBe(10)
        expect(result[0].percentage).toBe(63)
      })

      it('should return empty array for null typeStats', () => {
        expect(getTypeStatsTable(null as any)).toEqual([])
      })
    })

    describe('getTypeColor', () => {
      it('should return correct colors', () => {
        expect(getTypeColor('单选题')).toBe('#409eff')
        expect(getTypeColor('多选题')).toBe('#67c23a')
        expect(getTypeColor('判断题')).toBe('#e6a23c')
        expect(getTypeColor('简答题')).toBe('#f56c6c')
      })

      it('should return default color for unknown type', () => {
        expect(getTypeColor('unknown')).toBe('#909399')
      })
    })

    describe('getCoverageClass', () => {
      it('should return "coverage-good" for rate >= 80', () => {
        expect(getCoverageClass(80)).toBe('coverage-good')
        expect(getCoverageClass(90)).toBe('coverage-good')
      })

      it('should return "coverage-medium" for rate >= 60 and < 80', () => {
        expect(getCoverageClass(60)).toBe('coverage-medium')
        expect(getCoverageClass(70)).toBe('coverage-medium')
      })

      it('should return "coverage-poor" for rate < 60', () => {
        expect(getCoverageClass(50)).toBe('coverage-poor')
        expect(getCoverageClass(0)).toBe('coverage-poor')
      })
    })

    describe('getDiscriminationType', () => {
      it('should return "success" for value >= 8', () => {
        expect(getDiscriminationType(8)).toBe('success')
        expect(getDiscriminationType(10)).toBe('success')
      })

      it('should return "warning" for value >= 5 and < 8', () => {
        expect(getDiscriminationType(5)).toBe('warning')
        expect(getDiscriminationType(7)).toBe('warning')
      })

      it('should return "danger" for value < 5', () => {
        expect(getDiscriminationType(4)).toBe('danger')
        expect(getDiscriminationType(0)).toBe('danger')
      })

      it('should return "info" for null value', () => {
        expect(getDiscriminationType(null)).toBe('info')
      })
    })

    describe('getPassRateColor', () => {
      it('should return green for value >= 75', () => {
        expect(getPassRateColor(75)).toBe('#67c23a')
        expect(getPassRateColor(100)).toBe('#67c23a')
      })

      it('should return yellow for value >= 50 and < 75', () => {
        expect(getPassRateColor(50)).toBe('#e6a23c')
        expect(getPassRateColor(70)).toBe('#e6a23c')
      })

      it('should return red for value < 50', () => {
        expect(getPassRateColor(49)).toBe('#f56c6c')
        expect(getPassRateColor(0)).toBe('#f56c6c')
      })

      it('should return gray for null value', () => {
        expect(getPassRateColor(null)).toBe('#909399')
      })
    })

    describe('getQualityScoreColor', () => {
      it('should return green for value >= 80', () => {
        expect(getQualityScoreColor(80)).toBe('#67c23a')
        expect(getQualityScoreColor(100)).toBe('#67c23a')
      })

      it('should return yellow for value >= 60 and < 80', () => {
        expect(getQualityScoreColor(60)).toBe('#e6a23c')
        expect(getQualityScoreColor(70)).toBe('#e6a23c')
      })

      it('should return red for value < 60', () => {
        expect(getQualityScoreColor(59)).toBe('#f56c6c')
        expect(getQualityScoreColor(0)).toBe('#f56c6c')
      })

      it('should return gray for null value', () => {
        expect(getQualityScoreColor(null)).toBe('#909399')
      })
    })

    describe('getMasteryType', () => {
      it('should return correct types', () => {
        expect(getMasteryType('high')).toBe('success')
        expect(getMasteryType('medium')).toBe('warning')
        expect(getMasteryType('low')).toBe('danger')
      })

      it('should return "info" for unknown level', () => {
        expect(getMasteryType('unknown')).toBe('info')
      })
    })

    describe('getMasteryLabel', () => {
      it('should return correct labels', () => {
        expect(getMasteryLabel('high')).toBe('掌握良好')
        expect(getMasteryLabel('medium')).toBe('一般')
        expect(getMasteryLabel('low')).toBe('待加强')
      })

      it('should return original level for unknown level', () => {
        expect(getMasteryLabel('unknown')).toBe('unknown')
      })
    })
  })

  describe('Version Management', () => {
    describe('showVersionHistory', () => {
      it('should set current version paper id and open dialog', async () => {
        vi.mocked(paperAPI.getPaperVersions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        await showVersionHistory({ id: 1 } as any)

        expect(currentVersionPaperId.value).toBe(1)
        expect(versionDialogVisible.value).toBe(true)
      })
    })

    describe('fetchVersions', () => {
      it('should fetch versions successfully', async () => {
        const mockVersions = [{ id: 1, version_number: 1, title: 'V1' }]
        vi.mocked(paperAPI.getPaperVersions).mockResolvedValue({
          data: { items: mockVersions, total: 1 }
        } as any)

        await fetchVersions(1)

        expect(versionList.value).toEqual(mockVersions)
        expect(versionPagination.total).toBe(1)
      })

      it('should handle fetch versions error', async () => {
        vi.mocked(paperAPI.getPaperVersions).mockRejectedValue(new Error('Network error'))

        await fetchVersions(1)

        expect(versionList.value).toEqual([])
        expect(versionPagination.total).toBe(0)
      })
    })

    describe('showVersionDetail', () => {
      it('should fetch version detail and open dialog', async () => {
        currentVersionPaperId.value = 1
        const mockVersionDetail = { id: 1, version_number: 1, title: 'V1' }
        vi.mocked(paperAPI.getPaperVersion).mockResolvedValue({
          data: mockVersionDetail
        } as any)

        await showVersionDetail({ id: 1, version_number: 1 } as any)

        expect(versionDetail.value).toEqual(mockVersionDetail)
        expect(versionDetailDialogVisible.value).toBe(true)
      })
    })

    describe('handleVersionPageChange', () => {
      it('should fetch versions for current paper id', async () => {
        currentVersionPaperId.value = 1
        vi.mocked(paperAPI.getPaperVersions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        handleVersionPageChange()

        expect(paperAPI.getPaperVersions).toHaveBeenCalledWith(1, {
          page: versionPagination.page,
          page_size: versionPagination.pageSize
        })
      })

      it('should not fetch if no current paper id', () => {
        currentVersionPaperId.value = null

        handleVersionPageChange()

        expect(paperAPI.getPaperVersions).not.toHaveBeenCalled()
      })
    })
  })

  describe('Similarity Check', () => {
    describe('showSimilarityCheck', () => {
      it('should reset similarity data and open dialog', () => {
        similarityData.value = { similar_pairs_count: 1 } as any
        similarityThreshold.value = 0.5

        showSimilarityCheck({ id: 1 } as any)

        expect(similarityData.value).toBeNull()
        expect(similarityThreshold.value).toBe(0.7)
        expect(similarityDialogVisible.value).toBe(true)
      })
    })

    describe('runSimilarityCheck', () => {
      it('should run similarity check successfully', async () => {
        previewPaperData.value = { id: 1, title: 'Paper 1' } as any
        vi.mocked(paperAPI.checkSimilarity).mockResolvedValue({
          data: { similar_pairs_count: 0, similar_pairs: [] }
        } as any)

        await runSimilarityCheck()

        expect(similarityData.value).toEqual({ similar_pairs_count: 0, similar_pairs: [] })
        expect(similarityLoading.value).toBe(false)
      })

      it('should not run if no preview paper data', async () => {
        previewPaperData.value = null

        await runSimilarityCheck()

        expect(paperAPI.checkSimilarity).not.toHaveBeenCalled()
      })

      it('should handle similarity check error', async () => {
        previewPaperData.value = { id: 1, title: 'Paper 1' } as any
        vi.mocked(paperAPI.checkSimilarity).mockRejectedValue(new Error('Network error'))

        await runSimilarityCheck()

        expect(similarityLoading.value).toBe(false)
      })
    })

    describe('getSimilarityType', () => {
      it('should return "danger" for score >= 0.9', () => {
        expect(getSimilarityType(0.9)).toBe('danger')
        expect(getSimilarityType(1.0)).toBe('danger')
      })

      it('should return "warning" for score >= 0.8 and < 0.9', () => {
        expect(getSimilarityType(0.8)).toBe('warning')
        expect(getSimilarityType(0.85)).toBe('warning')
      })

      it('should return "info" for score < 0.8', () => {
        expect(getSimilarityType(0.7)).toBe('info')
        expect(getSimilarityType(0.5)).toBe('info')
      })
    })

    describe('getSimilarityLevel', () => {
      it('should return "高度相似" for score >= 0.9', () => {
        expect(getSimilarityLevel(0.9)).toBe('高度相似')
        expect(getSimilarityLevel(1.0)).toBe('高度相似')
      })

      it('should return "中度相似" for score >= 0.8 and < 0.9', () => {
        expect(getSimilarityLevel(0.8)).toBe('中度相似')
        expect(getSimilarityLevel(0.85)).toBe('中度相似')
      })

      it('should return "轻度相似" for score < 0.8', () => {
        expect(getSimilarityLevel(0.7)).toBe('轻度相似')
        expect(getSimilarityLevel(0.5)).toBe('轻度相似')
      })
    })
  })

  describe('Row Operations', () => {
    describe('handleRowCommand', () => {
      it('should handle analyze command', async () => {
        vi.mocked(paperAPI.getPaperAnalysis).mockResolvedValue({
          data: {
            total_questions: 10,
            total_score: 100,
            estimated_time: 60,
            coverage_rate: 80,
            difficulty_distribution: { easy: 30, medium: 50, hard: 20 },
            type_stats: { single_choice: { count: 10, score: 20 } },
            difficulty_stats: { easy: 3, medium: 5, hard: 2 },
            discrimination_index: 7,
            predicted_pass_rate: 70,
            quality_score: 80,
            total_time: 120
          }
        } as any)

        await handleRowCommand('analyze', { id: 1 } as any)

        expect(analysisDialogVisible.value).toBe(true)
      })

      it('should handle version command', async () => {
        vi.mocked(paperAPI.getPaperVersions).mockResolvedValue({
          data: { items: [], total: 0 }
        } as any)

        await handleRowCommand('version', { id: 1 } as any)

        expect(versionDialogVisible.value).toBe(true)
      })

      it('should handle similarity command', () => {
        handleRowCommand('similarity', { id: 1 } as any)

        expect(similarityDialogVisible.value).toBe(true)
      })
    })
  })

  describe('Batch Operations', () => {
    describe('handleBatchCommand', () => {
      it('should show warning if no rows selected', () => {
        selectedRows.value = []

        handleBatchCommand('publish')

        expect(adminAPI.updatePaper).not.toHaveBeenCalled()
      })
    })
  })

  describe('Composable', () => {
    it('should return all required properties and methods', () => {
      const composable = usePaperManagement()

      expect(composable).toHaveProperty('loading')
      expect(composable).toHaveProperty('paperList')
      expect(composable).toHaveProperty('selectedRows')
      expect(composable).toHaveProperty('searchKeyword')
      expect(composable).toHaveProperty('paperDialogVisible')
      expect(composable).toHaveProperty('previewDialogVisible')
      expect(composable).toHaveProperty('isEdit')
      expect(composable).toHaveProperty('saveLoading')
      expect(composable).toHaveProperty('currentEditId')
      expect(composable).toHaveProperty('previewPaperData')
      expect(composable).toHaveProperty('analysisDialogVisible')
      expect(composable).toHaveProperty('analysisData')
      expect(composable).toHaveProperty('analysisSuggestions')
      expect(composable).toHaveProperty('versionDialogVisible')
      expect(composable).toHaveProperty('versionList')
      expect(composable).toHaveProperty('versionDetail')
      expect(composable).toHaveProperty('currentVersionPaperId')
      expect(composable).toHaveProperty('versionPagination')
      expect(composable).toHaveProperty('similarityDialogVisible')
      expect(composable).toHaveProperty('similarityLoading')
      expect(composable).toHaveProperty('similarityData')
      expect(composable).toHaveProperty('similarityThreshold')
      expect(composable).toHaveProperty('pagination')
      expect(composable).toHaveProperty('filterForm')
      expect(composable).toHaveProperty('categoryOptions')
      expect(composable).toHaveProperty('subjectOptions')
      expect(composable).toHaveProperty('paperForm')
      expect(composable).toHaveProperty('formRules')
      expect(composable).toHaveProperty('filteredSubjectOptions')
      expect(composable).toHaveProperty('dialogFilteredSubjects')
      expect(composable).toHaveProperty('formatDate')
      expect(composable).toHaveProperty('getSubjectName')
      expect(composable).toHaveProperty('getStatusName')
      expect(composable).toHaveProperty('getStatusTagType')
      expect(composable).toHaveProperty('getQuestionTypeName')
      expect(composable).toHaveProperty('getCorrectAnswerLabels')
      expect(composable).toHaveProperty('fetchCategories')
      expect(composable).toHaveProperty('fetchSubjects')
      expect(composable).toHaveProperty('fetchPaperList')
      expect(composable).toHaveProperty('handleSearch')
      expect(composable).toHaveProperty('handleSizeChange')
      expect(composable).toHaveProperty('handlePageChange')
      expect(composable).toHaveProperty('handleCategoryChange')
      expect(composable).toHaveProperty('handleDialogCategoryChange')
      expect(composable).toHaveProperty('handleSelectionChange')
      expect(composable).toHaveProperty('openPaperDialog')
      expect(composable).toHaveProperty('editPaper')
      expect(composable).toHaveProperty('resetPaperForm')
      expect(composable).toHaveProperty('savePaper')
      expect(composable).toHaveProperty('previewPaper')
      expect(composable).toHaveProperty('analyzePaper')
      expect(composable).toHaveProperty('generateAnalysisSuggestions')
      expect(composable).toHaveProperty('getTypeStatsTable')
      expect(composable).toHaveProperty('getTypeColor')
      expect(composable).toHaveProperty('getCoverageClass')
      expect(composable).toHaveProperty('getKnowledgePointStatsTable')
      expect(composable).toHaveProperty('getDiscriminationType')
      expect(composable).toHaveProperty('getPassRateColor')
      expect(composable).toHaveProperty('getQualityScoreColor')
      expect(composable).toHaveProperty('getMasteryType')
      expect(composable).toHaveProperty('getMasteryLabel')
      expect(composable).toHaveProperty('showVersionHistory')
      expect(composable).toHaveProperty('fetchVersions')
      expect(composable).toHaveProperty('showVersionDetail')
      expect(composable).toHaveProperty('restoreVersion')
      expect(composable).toHaveProperty('handleVersionPageChange')
      expect(composable).toHaveProperty('showSimilarityCheck')
      expect(composable).toHaveProperty('runSimilarityCheck')
      expect(composable).toHaveProperty('getSimilarityType')
      expect(composable).toHaveProperty('getSimilarityLevel')
      expect(composable).toHaveProperty('handleRowCommand')
      expect(composable).toHaveProperty('publishPaper')
      expect(composable).toHaveProperty('archivePaper')
      expect(composable).toHaveProperty('deletePaper')
      expect(composable).toHaveProperty('handleBatchCommand')
      expect(composable).toHaveProperty('exportWord')
      expect(composable).toHaveProperty('exportPdf')
    })
  })
})
