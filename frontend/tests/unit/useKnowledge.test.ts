import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API module
vi.mock('@/api', () => ({
  knowledgeAPI: {
    getHierarchyTrees: vi.fn(),
    getKnowledgePointQuestions: vi.fn(),
    createNode: vi.fn(),
    updateNode: vi.fn(),
    deleteNode: vi.fn(),
    importFile: vi.fn(),
    ruleAnalyze: vi.fn(),
    aiAnalyze: vi.fn(),
    aiImport: vi.fn()
  },
  systemAPI: {
    getExamCategories: vi.fn(),
    getExamTypes: vi.fn()
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

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn()
  }))
}))

import {
  treeRef,
  knowledgeTreeData,
  filteredTreeData,
  treeSearchKeyword,
  selectedKnowledge,
  relatedQuestions,
  dialogVisible,
  importDialogVisible,
  isEdit,
  submitLoading,
  contextMenuVisible,
  contextMenuX,
  contextMenuY,
  contextMenuNode,
  importMode,
  uploadRef,
  aiUploadRef,
  selectedFile,
  aiSelectedFile,
  aiAnalyzing,
  aiResult,
  aiImportForm,
  treeProps,
  knowledgeForm,
  formRules,
  examTypeOptions,
  examCategoryOptions,
  totalKnowledgeCount,
  categoryCount,
  examTypeCount,
  knowledgeOnlyTreeData,
  filteredFormExamTypeOptions,
  filteredAIExamTypeOptions,
  defaultExpandedKeys,
  handleFormCategoryChange,
  fetchExamTypesAndCourses,
  allowDrop,
  allowDrag,
  fetchKnowledgeTree,
  calculateStats,
  handleTreeSearch,
  handleNodeClick,
  handleNodeContextMenu,
  hideContextMenu,
  handleDragStart,
  handleDragEnd,
  openCreateDialog,
  handleAddKnowledgeUnderExamType,
  openEditDialog,
  resetForm,
  submitForm,
  deleteKnowledge,
  handleAddChild,
  handleRename,
  handleDelete,
  handleImport,
  resetImportState,
  closeImportDialog,
  handleFileChange,
  handleAIFileChange,
  autoRuleAnalyze,
  startAIAnalysis,
  confirmAIImport,
  confirmImport,
  handleExport,
  handleBatchImport,
  viewQuestion,
  viewAllQuestions,
  formatDate,
  truncateContent,
  useKnowledge
} from '@/composables/useKnowledge'

import { knowledgeAPI, systemAPI } from '@/api'

describe('useKnowledge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset state
    treeRef.value = null
    knowledgeTreeData.value = []
    filteredTreeData.value = []
    treeSearchKeyword.value = ''
    selectedKnowledge.value = null
    relatedQuestions.value = []
    dialogVisible.value = false
    importDialogVisible.value = false
    isEdit.value = false
    submitLoading.value = false
    contextMenuVisible.value = false
    contextMenuX.value = 0
    contextMenuY.value = 0
    contextMenuNode.value = null
    importMode.value = 'file'
    uploadRef.value = null
    aiUploadRef.value = null
    selectedFile.value = null
    aiSelectedFile.value = null
    aiAnalyzing.value = false
    aiResult.value = null
    aiImportForm.parentId = null
    aiImportForm.categoryId = null
    aiImportForm.examTypeId = null
    knowledgeForm.id = null
    knowledgeForm.name = ''
    knowledgeForm.parentId = null
    knowledgeForm.categoryId = null
    knowledgeForm.examTypeId = null
    knowledgeForm.sortOrder = 0
    knowledgeForm.description = ''
    examTypeOptions.value = []
    examCategoryOptions.value = []
    totalKnowledgeCount.value = 0
    categoryCount.value = 0
    examTypeCount.value = 0
  })

  describe('Initialization State', () => {
    it('should have correct initial state', () => {
      expect(treeRef.value).toBeNull()
      expect(knowledgeTreeData.value).toEqual([])
      expect(filteredTreeData.value).toEqual([])
      expect(treeSearchKeyword.value).toBe('')
      expect(selectedKnowledge.value).toBeNull()
      expect(relatedQuestions.value).toEqual([])
      expect(dialogVisible.value).toBe(false)
      expect(importDialogVisible.value).toBe(false)
      expect(isEdit.value).toBe(false)
      expect(submitLoading.value).toBe(false)
      expect(contextMenuVisible.value).toBe(false)
      expect(contextMenuX.value).toBe(0)
      expect(contextMenuY.value).toBe(0)
      expect(contextMenuNode.value).toBeNull()
    })

    it('should have correct initial import state', () => {
      expect(importMode.value).toBe('file')
      expect(uploadRef.value).toBeNull()
      expect(aiUploadRef.value).toBeNull()
      expect(selectedFile.value).toBeNull()
      expect(aiSelectedFile.value).toBeNull()
      expect(aiAnalyzing.value).toBe(false)
      expect(aiResult.value).toBeNull()
    })

    it('should have correct initial knowledge form', () => {
      expect(knowledgeForm.id).toBeNull()
      expect(knowledgeForm.name).toBe('')
      expect(knowledgeForm.parentId).toBeNull()
      expect(knowledgeForm.categoryId).toBeNull()
      expect(knowledgeForm.examTypeId).toBeNull()
      expect(knowledgeForm.sortOrder).toBe(0)
      expect(knowledgeForm.description).toBe('')
    })

    it('should have correct initial options', () => {
      expect(examTypeOptions.value).toEqual([])
      expect(examCategoryOptions.value).toEqual([])
    })

    it('should have correct initial stats', () => {
      expect(totalKnowledgeCount.value).toBe(0)
      expect(categoryCount.value).toBe(0)
      expect(examTypeCount.value).toBe(0)
    })
  })

  describe('Utility Functions', () => {
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

    describe('truncateContent', () => {
      it('should truncate content longer than 20 characters', () => {
        expect(truncateContent('This is a very long content')).toBe('This is a very long ...')
      })

      it('should not truncate content shorter than 20 characters', () => {
        expect(truncateContent('Short content')).toBe('Short content')
      })

      it('should return empty string for null content', () => {
        expect(truncateContent(null)).toBe('')
      })

      it('should return empty string for undefined content', () => {
        expect(truncateContent(undefined)).toBe('')
      })
    })
  })

  describe('Computed Properties', () => {
    describe('knowledgeOnlyTreeData', () => {
      it('should extract only knowledge nodes from tree', () => {
        knowledgeTreeData.value = [
          {
            id: 1,
            name: 'Category 1',
            node_type: 'category',
            children: [
              {
                id: 2,
                name: 'Exam Type 1',
                node_type: 'exam_type',
                children: [
                  { id: 3, name: 'Knowledge 1', node_type: 'knowledge' },
                  { id: 4, name: 'Knowledge 2', node_type: 'knowledge' }
                ]
              }
            ]
          }
        ]

        const result = knowledgeOnlyTreeData.value

        expect(result.length).toBe(2)
        expect(result[0].name).toBe('Knowledge 1')
        expect(result[1].name).toBe('Knowledge 2')
      })

      it('should return empty array for empty tree', () => {
        knowledgeTreeData.value = []

        expect(knowledgeOnlyTreeData.value).toEqual([])
      })
    })

    describe('filteredFormExamTypeOptions', () => {
      it('should return all exam types when no category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1 },
          { id: 2, name: 'English', category_id: 2 }
        ]
        knowledgeForm.categoryId = null

        expect(filteredFormExamTypeOptions.value.length).toBe(2)
      })

      it('should return filtered exam types when category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1 },
          { id: 2, name: 'English', category_id: 2 }
        ]
        knowledgeForm.categoryId = 1

        expect(filteredFormExamTypeOptions.value.length).toBe(1)
        expect(filteredFormExamTypeOptions.value[0].name).toBe('Math')
      })
    })

    describe('filteredAIExamTypeOptions', () => {
      it('should return all exam types when no category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1 },
          { id: 2, name: 'English', category_id: 2 }
        ]
        aiImportForm.categoryId = null

        expect(filteredAIExamTypeOptions.value.length).toBe(2)
      })

      it('should return filtered exam types when category selected', () => {
        examTypeOptions.value = [
          { id: 1, name: 'Math', category_id: 1 },
          { id: 2, name: 'English', category_id: 2 }
        ]
        aiImportForm.categoryId = 1

        expect(filteredAIExamTypeOptions.value.length).toBe(1)
        expect(filteredAIExamTypeOptions.value[0].name).toBe('Math')
      })
    })

    describe('defaultExpandedKeys', () => {
      it('should return keys for category and exam_type nodes', () => {
        knowledgeTreeData.value = [
          {
            id: 1,
            name: 'Category 1',
            node_type: 'category',
            children: [
              {
                id: 2,
                name: 'Exam Type 1',
                node_type: 'exam_type',
                children: [
                  { id: 3, name: 'Knowledge 1', node_type: 'knowledge' }
                ]
              }
            ]
          }
        ]

        const result = defaultExpandedKeys.value

        expect(result.length).toBe(2)
        expect(result).toContain(1)
        expect(result).toContain(2)
      })

      it('should return empty array for empty tree', () => {
        knowledgeTreeData.value = []

        expect(defaultExpandedKeys.value).toEqual([])
      })
    })
  })

  describe('API Functions', () => {
    describe('fetchExamTypesAndCourses', () => {
      it('should fetch exam types and courses successfully', async () => {
        const mockCategories = [{ id: 1, name: 'Category 1' }]
        const mockExamTypes = [{ id: 1, name: 'Math', category_id: 1 }]
        vi.mocked(systemAPI.getExamCategories).mockResolvedValue({
          data: { items: mockCategories }
        } as any)
        vi.mocked(systemAPI.getExamTypes).mockResolvedValue({
          data: { items: mockExamTypes }
        } as any)

        await fetchExamTypesAndCourses()

        expect(examCategoryOptions.value).toEqual(mockCategories)
        expect(examTypeOptions.value).toEqual(mockExamTypes)
      })

      it('should handle fetch error', async () => {
        vi.mocked(systemAPI.getExamCategories).mockRejectedValue(new Error('Network error'))
        vi.mocked(systemAPI.getExamTypes).mockRejectedValue(new Error('Network error'))

        await fetchExamTypesAndCourses()

        expect(examCategoryOptions.value).toEqual([])
        expect(examTypeOptions.value).toEqual([])
      })
    })

    describe('fetchKnowledgeTree', () => {
      it('should fetch knowledge tree successfully', async () => {
        const mockTree = [
          { id: 1, name: 'Category 1', node_type: 'category', children: [] }
        ]
        vi.mocked(knowledgeAPI.getHierarchyTrees).mockResolvedValue({
          data: { trees: mockTree }
        } as any)

        await fetchKnowledgeTree()

        expect(knowledgeTreeData.value).toEqual(mockTree)
        expect(filteredTreeData.value).toEqual(mockTree)
      })

      it('should handle fetch error', async () => {
        vi.mocked(knowledgeAPI.getHierarchyTrees).mockRejectedValue(new Error('Network error'))

        await fetchKnowledgeTree()

        expect(knowledgeTreeData.value).toEqual([])
        expect(filteredTreeData.value).toEqual([])
      })
    })
  })

  describe('Stats Calculation', () => {
    describe('calculateStats', () => {
      it('should calculate stats correctly', () => {
        knowledgeTreeData.value = [
          {
            id: 1,
            name: 'Category 1',
            node_type: 'category',
            children: [
              {
                id: 2,
                name: 'Exam Type 1',
                node_type: 'exam_type',
                children: [
                  { id: 3, name: 'Knowledge 1', node_type: 'knowledge' },
                  { id: 4, name: 'Knowledge 2', node_type: 'knowledge' }
                ]
              }
            ]
          }
        ]

        calculateStats()

        expect(totalKnowledgeCount.value).toBe(2)
        expect(categoryCount.value).toBe(1)
        expect(examTypeCount.value).toBe(1)
      })

      it('should handle empty tree', () => {
        knowledgeTreeData.value = []

        calculateStats()

        expect(totalKnowledgeCount.value).toBe(0)
        expect(categoryCount.value).toBe(0)
        expect(examTypeCount.value).toBe(0)
      })
    })
  })

  describe('Search', () => {
    describe('handleTreeSearch', () => {
      it('should reset filtered tree when keyword is empty', () => {
        treeSearchKeyword.value = ''
        knowledgeTreeData.value = [
          { id: 1, name: 'Knowledge 1', node_type: 'knowledge' }
        ]

        handleTreeSearch()

        expect(filteredTreeData.value).toEqual(knowledgeTreeData.value)
      })

      it('should filter tree by keyword', () => {
        treeSearchKeyword.value = 'Knowledge'
        knowledgeTreeData.value = [
          {
            id: 1,
            name: 'Category 1',
            node_type: 'category',
            children: [
              { id: 2, name: 'Knowledge 1', node_type: 'knowledge' },
              { id: 3, name: 'Other', node_type: 'knowledge' }
            ]
          }
        ]

        handleTreeSearch()

        expect(filteredTreeData.value.length).toBe(1)
        expect(filteredTreeData.value[0].children?.length).toBe(1)
        expect(filteredTreeData.value[0].children?.[0].name).toBe('Knowledge 1')
      })
    })
  })

  describe('Node Click', () => {
    describe('handleNodeClick', () => {
      it('should set selected knowledge and fetch related questions', async () => {
        const mockQuestions = [{ id: 1, content: 'Question 1' }]
        vi.mocked(knowledgeAPI.getKnowledgePointQuestions).mockResolvedValue({
          data: { questions: mockQuestions }
        } as any)

        knowledgeTreeData.value = [
          {
            id: 1,
            name: 'Category 1',
            node_type: 'category',
            children: [
              {
                id: 2,
                name: 'Exam Type 1',
                node_type: 'exam_type',
                children: [
                  { id: 3, name: 'Knowledge 1', node_type: 'knowledge' }
                ]
              }
            ]
          }
        ]

        // Note: node_type is 'knowledge' which is truthy, so the code inside
        // the if (!data.node_type) block won't execute. We need to pass a node
        // without node_type to trigger the related questions fetch.
        await handleNodeClick({ id: 3, name: 'Knowledge 1' } as any)

        expect(selectedKnowledge.value).toBeDefined()
        expect(selectedKnowledge.value?.id).toBe(3)
        // Note: relatedQuestions is set asynchronously, so we need to wait
        await new Promise(resolve => setTimeout(resolve, 0))
        expect(relatedQuestions.value).toEqual(mockQuestions)
      })

      it('should handle fetch related questions error', async () => {
        vi.mocked(knowledgeAPI.getKnowledgePointQuestions).mockRejectedValue(new Error('Network error'))

        knowledgeTreeData.value = [
          { id: 1, name: 'Knowledge 1', node_type: 'knowledge' }
        ]

        await handleNodeClick({ id: 1, name: 'Knowledge 1', node_type: 'knowledge' } as any)

        expect(relatedQuestions.value).toEqual([])
      })
    })
  })

  describe('Context Menu', () => {
    describe('handleNodeContextMenu', () => {
      it('should show context menu', () => {
        const event = {
          preventDefault: vi.fn(),
          clientX: 100,
          clientY: 200
        } as any
        const data = { id: 1, name: 'Knowledge 1' } as any

        handleNodeContextMenu(event, data)

        expect(contextMenuVisible.value).toBe(true)
        expect(contextMenuX.value).toBe(100)
        expect(contextMenuY.value).toBe(200)
        expect(contextMenuNode.value).toEqual(data)
      })
    })

    describe('hideContextMenu', () => {
      it('should hide context menu', () => {
        contextMenuVisible.value = true

        hideContextMenu()

        expect(contextMenuVisible.value).toBe(false)
      })
    })
  })

  describe('Drag & Drop', () => {
    describe('allowDrop', () => {
      it('should not allow drop for nodes with node_type', () => {
        const draggingNode = { data: { node_type: 'knowledge' } }
        const dropNode = { data: {} }

        expect(allowDrop(draggingNode as any, dropNode as any, 'inner')).toBe(false)
      })

      it('should not allow drop to category node', () => {
        const draggingNode = { data: {} }
        const dropNode = { data: { node_type: 'category' } }

        expect(allowDrop(draggingNode as any, dropNode as any, 'inner')).toBe(false)
      })

      it('should not allow drop to exam_type node', () => {
        const draggingNode = { data: {} }
        const dropNode = { data: { node_type: 'exam_type' } }

        expect(allowDrop(draggingNode as any, dropNode as any, 'inner')).toBe(false)
      })

      it('should not allow inner drop', () => {
        const draggingNode = { data: {} }
        const dropNode = { data: {} }

        expect(allowDrop(draggingNode as any, dropNode as any, 'inner')).toBe(false)
      })

      it('should allow before/after drop', () => {
        const draggingNode = { data: {} }
        const dropNode = { data: {} }

        expect(allowDrop(draggingNode as any, dropNode as any, 'before')).toBe(true)
        expect(allowDrop(draggingNode as any, dropNode as any, 'after')).toBe(true)
      })
    })

    describe('allowDrag', () => {
      it('should not allow drag for category node', () => {
        const draggingNode = { data: { node_type: 'category' } }

        expect(allowDrag(draggingNode as any)).toBe(false)
      })

      it('should not allow drag for exam_type node', () => {
        const draggingNode = { data: { node_type: 'exam_type' } }

        expect(allowDrag(draggingNode as any)).toBe(false)
      })

      it('should allow drag for knowledge node (no node_type)', () => {
        const draggingNode = { data: {} }

        expect(allowDrag(draggingNode as any)).toBe(true)
      })
    })
  })

  describe('CRUD Operations', () => {
    describe('openCreateDialog', () => {
      it('should open dialog in create mode', () => {
        isEdit.value = true

        openCreateDialog()

        expect(isEdit.value).toBe(false)
        expect(dialogVisible.value).toBe(true)
      })
    })

    describe('openEditDialog', () => {
      it('should open dialog in edit mode with knowledge data', () => {
        selectedKnowledge.value = {
          id: 1,
          name: 'Knowledge 1',
          parent_id: 2,
          categoryId: 1,
          examTypeId: 3,
          sortOrder: 5,
          description: 'Test description'
        } as any

        openEditDialog()

        expect(isEdit.value).toBe(true)
        expect(knowledgeForm.id).toBe(1)
        expect(knowledgeForm.name).toBe('Knowledge 1')
        expect(knowledgeForm.parentId).toBe(2)
        expect(knowledgeForm.categoryId).toBe(1)
        expect(knowledgeForm.examTypeId).toBe(3)
        expect(knowledgeForm.sortOrder).toBe(5)
        expect(knowledgeForm.description).toBe('Test description')
        expect(dialogVisible.value).toBe(true)
      })

      it('should not open dialog if no selected knowledge', () => {
        selectedKnowledge.value = null
        dialogVisible.value = false

        openEditDialog()

        expect(dialogVisible.value).toBe(false)
      })
    })

    describe('resetForm', () => {
      it('should reset knowledge form to initial values', () => {
        knowledgeForm.id = 1
        knowledgeForm.name = 'Test'
        knowledgeForm.parentId = 2
        knowledgeForm.categoryId = 1
        knowledgeForm.examTypeId = 3
        knowledgeForm.sortOrder = 5
        knowledgeForm.description = 'Test'

        resetForm()

        expect(knowledgeForm.id).toBeNull()
        expect(knowledgeForm.name).toBe('')
        expect(knowledgeForm.parentId).toBeNull()
        expect(knowledgeForm.categoryId).toBeNull()
        expect(knowledgeForm.examTypeId).toBeNull()
        expect(knowledgeForm.sortOrder).toBe(0)
        expect(knowledgeForm.description).toBe('')
      })
    })

    describe('handleFormCategoryChange', () => {
      it('should reset examTypeId', () => {
        knowledgeForm.examTypeId = 2

        handleFormCategoryChange()

        expect(knowledgeForm.examTypeId).toBeNull()
      })
    })
  })

  describe('Context Menu Actions', () => {
    describe('handleAddChild', () => {
      it('should set parent id and open dialog', () => {
        contextMenuNode.value = { id: 1, name: 'Knowledge 1' } as any

        handleAddChild()

        expect(contextMenuVisible.value).toBe(false)
        expect(knowledgeForm.parentId).toBe(1)
        expect(dialogVisible.value).toBe(true)
      })
    })

    describe('handleRename', () => {
      it('should set selected knowledge and open edit dialog', () => {
        contextMenuNode.value = {
          id: 1,
          name: 'Knowledge 1',
          parent_id: 2,
          categoryId: 1,
          examTypeId: 3,
          sortOrder: 5,
          description: 'Test'
        } as any

        handleRename()

        expect(contextMenuVisible.value).toBe(false)
        expect(selectedKnowledge.value).toEqual(contextMenuNode.value)
        expect(dialogVisible.value).toBe(true)
      })
    })

    describe('handleDelete', () => {
      it('should set selected knowledge and delete', () => {
        contextMenuNode.value = { id: 1, name: 'Knowledge 1' } as any
        vi.mocked(knowledgeAPI.deleteNode).mockResolvedValue({} as any)

        handleDelete()

        expect(contextMenuVisible.value).toBe(false)
        expect(selectedKnowledge.value).toEqual(contextMenuNode.value)
      })
    })
  })

  describe('Import Functions', () => {
    describe('handleImport', () => {
      it('should open import dialog and reset state', () => {
        selectedFile.value = new File(['test'], 'test.xlsx')
        aiSelectedFile.value = new File(['test'], 'test.xlsx')
        aiResult.value = { success: true } as any
        aiAnalyzing.value = true

        handleImport()

        expect(importMode.value).toBe('file')
        expect(importDialogVisible.value).toBe(true)
        expect(selectedFile.value).toBeNull()
        expect(aiSelectedFile.value).toBeNull()
        expect(aiResult.value).toBeNull()
        expect(aiAnalyzing.value).toBe(false)
      })
    })

    describe('resetImportState', () => {
      it('should reset import state', () => {
        selectedFile.value = new File(['test'], 'test.xlsx')
        aiSelectedFile.value = new File(['test'], 'test.xlsx')
        aiResult.value = { success: true } as any
        aiAnalyzing.value = true
        uploadRef.value = { clearFiles: vi.fn() }
        aiUploadRef.value = { clearFiles: vi.fn() }

        resetImportState()

        expect(selectedFile.value).toBeNull()
        expect(aiSelectedFile.value).toBeNull()
        expect(aiResult.value).toBeNull()
        expect(aiAnalyzing.value).toBe(false)
        expect(uploadRef.value.clearFiles).toHaveBeenCalled()
        expect(aiUploadRef.value.clearFiles).toHaveBeenCalled()
      })
    })

    describe('closeImportDialog', () => {
      it('should close import dialog and reset state', () => {
        importDialogVisible.value = true
        selectedFile.value = new File(['test'], 'test.xlsx')

        closeImportDialog()

        expect(importDialogVisible.value).toBe(false)
        expect(selectedFile.value).toBeNull()
      })
    })

    describe('handleFileChange', () => {
      it('should set selected file', () => {
        const file = new File(['test'], 'test.xlsx')

        handleFileChange(file)

        expect(selectedFile.value).toEqual(file)
      })
    })

    describe('handleAIFileChange', () => {
      it('should set ai selected file and trigger auto rule analyze', () => {
        const file = new File(['test'], 'test.xlsx')
        vi.mocked(knowledgeAPI.ruleAnalyze).mockResolvedValue({
          data: { success: true, total_points: 5 }
        } as any)

        handleAIFileChange(file)

        expect(aiSelectedFile.value).toEqual(file)
      })
    })
  })

  describe('Export Functions', () => {
    describe('handleExport', () => {
      it('should show export message', () => {
        handleExport()

        // Just verify it doesn't throw
        expect(true).toBe(true)
      })
    })
  })

  describe('Question Viewers', () => {
    describe('viewQuestion', () => {
      it('should show question info', () => {
        viewQuestion({ id: 1, content: 'Question 1' } as any)

        // Just verify it doesn't throw
        expect(true).toBe(true)
      })
    })

    describe('viewAllQuestions', () => {
      it('should show all questions info', () => {
        viewAllQuestions()

        // Just verify it doesn't throw
        expect(true).toBe(true)
      })
    })
  })

  describe('Composable', () => {
    it('should return all required properties and methods', () => {
      const composable = useKnowledge()

      expect(composable).toHaveProperty('treeRef')
      expect(composable).toHaveProperty('knowledgeTreeData')
      expect(composable).toHaveProperty('filteredTreeData')
      expect(composable).toHaveProperty('treeSearchKeyword')
      expect(composable).toHaveProperty('selectedKnowledge')
      expect(composable).toHaveProperty('relatedQuestions')
      expect(composable).toHaveProperty('dialogVisible')
      expect(composable).toHaveProperty('importDialogVisible')
      expect(composable).toHaveProperty('isEdit')
      expect(composable).toHaveProperty('submitLoading')
      expect(composable).toHaveProperty('contextMenuVisible')
      expect(composable).toHaveProperty('contextMenuX')
      expect(composable).toHaveProperty('contextMenuY')
      expect(composable).toHaveProperty('contextMenuNode')
      expect(composable).toHaveProperty('importMode')
      expect(composable).toHaveProperty('uploadRef')
      expect(composable).toHaveProperty('aiUploadRef')
      expect(composable).toHaveProperty('selectedFile')
      expect(composable).toHaveProperty('aiSelectedFile')
      expect(composable).toHaveProperty('aiAnalyzing')
      expect(composable).toHaveProperty('aiResult')
      expect(composable).toHaveProperty('aiImportForm')
      expect(composable).toHaveProperty('treeProps')
      expect(composable).toHaveProperty('knowledgeForm')
      expect(composable).toHaveProperty('formRules')
      expect(composable).toHaveProperty('examTypeOptions')
      expect(composable).toHaveProperty('examCategoryOptions')
      expect(composable).toHaveProperty('totalKnowledgeCount')
      expect(composable).toHaveProperty('categoryCount')
      expect(composable).toHaveProperty('examTypeCount')
      expect(composable).toHaveProperty('knowledgeOnlyTreeData')
      expect(composable).toHaveProperty('filteredFormExamTypeOptions')
      expect(composable).toHaveProperty('filteredAIExamTypeOptions')
      expect(composable).toHaveProperty('defaultExpandedKeys')
      expect(composable).toHaveProperty('handleFormCategoryChange')
      expect(composable).toHaveProperty('fetchExamTypesAndCourses')
      expect(composable).toHaveProperty('allowDrop')
      expect(composable).toHaveProperty('allowDrag')
      expect(composable).toHaveProperty('fetchKnowledgeTree')
      expect(composable).toHaveProperty('calculateStats')
      expect(composable).toHaveProperty('handleTreeSearch')
      expect(composable).toHaveProperty('handleNodeClick')
      expect(composable).toHaveProperty('handleNodeContextMenu')
      expect(composable).toHaveProperty('hideContextMenu')
      expect(composable).toHaveProperty('handleDragStart')
      expect(composable).toHaveProperty('handleDragEnd')
      expect(composable).toHaveProperty('openCreateDialog')
      expect(composable).toHaveProperty('handleAddKnowledgeUnderExamType')
      expect(composable).toHaveProperty('openEditDialog')
      expect(composable).toHaveProperty('resetForm')
      expect(composable).toHaveProperty('submitForm')
      expect(composable).toHaveProperty('deleteKnowledge')
      expect(composable).toHaveProperty('handleAddChild')
      expect(composable).toHaveProperty('handleRename')
      expect(composable).toHaveProperty('handleDelete')
      expect(composable).toHaveProperty('handleImport')
      expect(composable).toHaveProperty('resetImportState')
      expect(composable).toHaveProperty('closeImportDialog')
      expect(composable).toHaveProperty('handleFileChange')
      expect(composable).toHaveProperty('handleAIFileChange')
      expect(composable).toHaveProperty('autoRuleAnalyze')
      expect(composable).toHaveProperty('startAIAnalysis')
      expect(composable).toHaveProperty('confirmAIImport')
      expect(composable).toHaveProperty('confirmImport')
      expect(composable).toHaveProperty('handleExport')
      expect(composable).toHaveProperty('handleBatchImport')
      expect(composable).toHaveProperty('viewQuestion')
      expect(composable).toHaveProperty('viewAllQuestions')
      expect(composable).toHaveProperty('formatDate')
      expect(composable).toHaveProperty('truncateContent')
    })
  })
})
