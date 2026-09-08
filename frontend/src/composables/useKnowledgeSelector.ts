// ============
// Knowledge Selector Module for useAutoPaper
// ============
// Handles knowledge tree operations, selection, and weight calculation.

import { ElMessage } from 'element-plus'
import { knowledgeAPI } from '@/api'
import { type KnowledgePoint } from './useAutoPaperTypes'
import {
  knowledgeTree,
  selectedKnowledgePoints,
  skipKnowledgePoints,
  knowledgeTreeRef,
  paperForm
} from './useAutoPaperCore'

// ============ Internal Helpers ============

// 统计节点的子节点数量（递归）
const countDescendants = (node: any): number => {
  if (!node.children || node.children.length === 0) return 1
  let count = 1
  for (const child of node.children) {
    count += countDescendants(child)
  }
  return count
}

// 根据子节点数量和题目数量计算智能权重
// 公式：权重 = (子节点数量占比) × (1 - 题目数量占比 × 0.3)
const calculateIntelligentWeight = (
  kpList: any[],
  totalDescendants: number,
  totalQuestions: number,
  countsData: any
) => {
  if (kpList.length === 0) return

  // 计算各维度占比
  const weights = kpList.map((kp) => {
    const descendantRatio = totalDescendants > 0 ? kp._descendantCount / totalDescendants : 0
    const questionInfo = countsData[kp.id] || { question_count: 0 }
    const questionCount = questionInfo.question_count || 0
    const questionRatio = totalQuestions > 0 ? questionCount / totalQuestions : 0

    // 综合权重：子节点占比 × (1 - 题目占比 × 0.3)
    // 题目多的降权(最多降30%)，题目少的保持较高权重
    const adjustedRatio = descendantRatio * (1 - questionRatio * 0.3)

    return {
      id: kp.id,
      weight: adjustedRatio,
      questionCount,
      descendantCount: kp._descendantCount
    }
  })

  // 归一化，确保总和为100
  const totalWeight = weights.reduce((sum, w) => sum + w.weight, 0)

  weights.forEach((w, index) => {
    const normalizedWeight = totalWeight > 0 ? Math.round((w.weight / totalWeight) * 100) : Math.floor(100 / kpList.length)
    kpList[index].weight = normalizedWeight
  })

  // 确保总和为100，调整最大值
  const currentTotal = kpList.reduce((sum, kp) => sum + kp.weight, 0)
  if (currentTotal !== 100 && kpList.length > 0) {
    const diff = 100 - currentTotal
    // 找到最大权重的知识点进行补偿
    let maxIndex = 0
    let maxWeight = kpList[0].weight
    kpList.forEach((kp, index) => {
      if (kp.weight > maxWeight) {
        maxWeight = kp.weight
        maxIndex = index
      }
    })
    kpList[maxIndex].weight += diff
  }

  console.log('智能权重计算结果:', kpList.map((kp) => ({
    id: kp.id,
    label: kp.label,
    weight: kp.weight,
    descendantCount: kp._descendantCount,
    questionCount: kp._questionCount
  })))
}

// ============ Knowledge Point Selection ============

// 自动选择所有知识点（用于模拟测试卷）- 只选择挂在exam_type下的第一层知识点
export const selectAllKnowledgePoints = async () => {
  if (!knowledgeTree.value || knowledgeTree.value.length === 0) return

  // 找到 exam_type 节点，取其直接子节点（挂在exam_type下的第一层知识点）
  let examTypeNode: any = null
  for (const cat of knowledgeTree.value) {
    if (cat.children) {
      for (const child of cat.children) {
        if (child.node_type === 'exam_type') {
          examTypeNode = child
          break
        }
      }
    }
    if (examTypeNode) break
  }

  if (!examTypeNode || !examTypeNode.children) return

  // 只取 exam_type 的直接子节点（第一层知识点）
  const firstLevelKps = examTypeNode.children.filter(
    (node: any) => node.node_type !== 'category' && node.node_type !== 'exam_type'
  )

  // 构建知识点列表，同时统计子节点数量
  const kpList = firstLevelKps.map((kp: any) => {
    const descendantCount = countDescendants(kp)
    return {
      id: kp.id,
      label: kp.name,
      weight: 0,
      _descendantCount: descendantCount
    }
  })

  // 获取各知识点的题目数量
  try {
    const kpIds = kpList.map((kp: any) => kp.id)
    const res = await knowledgeAPI.getQuestionCounts(kpIds)
    const countsData = res.data || {}

    // 计算总子节点数和总题目数
    const totalDescendants = kpList.reduce((sum: number, kp: any) => sum + kp._descendantCount, 0)
    const totalQuestions = Object.values(countsData).reduce((sum: number, info: any) => sum + (info.question_count || 0), 0)

    // 计算智能权重
    calculateIntelligentWeight(kpList, totalDescendants, totalQuestions, countsData)
  } catch (error) {
    console.error('获取知识点题目数量失败，使用平均权重:', error)
    // 失败时使用平均权重
    const baseWeight = Math.floor(100 / kpList.length)
    const remainder = 100 - baseWeight * kpList.length
    kpList.forEach((kp: any, index: number) => {
      kp.weight = baseWeight + (index < remainder ? 1 : 0)
    })
  }

  selectedKnowledgePoints.value = kpList

  // 同时设置树的勾选状态
  const allKeys = kpList.map((kp: any) => kp.id)
  knowledgeTreeRef.value?.setCheckedKeys(allKeys)
}

export const handleKnowledgeChange = () => {
  // 只获取完全选中的节点键，避免半选父节点被包含
  const checkedKeys = knowledgeTreeRef.value?.getCheckedKeys() || []

  if (checkedKeys.length === 0) {
    selectedKnowledgePoints.value = []
    return
  }

  // 构建所有节点的映射
  const allNodesMap = new Map<number, any>()

  // 递归收集所有节点
  const collectNodes = (nodes: any[]) => {
    for (const node of nodes) {
      allNodesMap.set(node.id, node)
      if (node.children && node.children.length > 0) {
        collectNodes(node.children)
      }
    }
  }
  collectNodes(knowledgeTree.value)

  // 使用完全选中的键获取节点
  const checkedNodes = checkedKeys.map((key: any) => allNodesMap.get(key)).filter(Boolean)

  // 找出每个选中节点对应的顶级父节点（挂在exam_type下的第一层知识点）
  const rootKnowledgePoints = new Map<number, { id: number; label: string; weight: number }>()

  for (const node of checkedNodes) {
    // 找出这个节点的最顶层父节点（挂在exam_type下的第一层知识点）
    let currentNode: any = node

    // 向上追溯直到找到挂在exam_type下的第一层知识点
    while (currentNode) {
      const parentNode = currentNode.parent_id ? allNodesMap.get(currentNode.parent_id) : null

      if (!parentNode) {
        break
      }

      // 如果父节点是exam_type，当前节点就是挂在exam_type下的第一层知识点
      if (parentNode.node_type === 'exam_type') {
        break
      }

      // 如果父节点是category，继续向上找
      if (parentNode.node_type === 'category') {
        currentNode = parentNode
        continue
      }

      currentNode = parentNode
    }

    // 如果找到的节点不是category也不是exam_type，就是我们要找的顶级知识点
    if (currentNode && currentNode.node_type !== 'category' && currentNode.node_type !== 'exam_type') {
      if (!rootKnowledgePoints.has(currentNode.id)) {
        rootKnowledgePoints.set(currentNode.id, {
          id: currentNode.id,
          label: currentNode.name,
          weight: 0
        })
      }
    }
  }

  // 转换为数组并计算权重
  const rootNodes = Array.from(rootKnowledgePoints.values())
  const count = rootNodes.length

  if (count > 0) {
    const baseWeight = Math.floor(100 / count)
    const remainder = 100 - baseWeight * count

    rootNodes.forEach((kp, index) => {
      kp.weight = baseWeight + (index < remainder ? 1 : 0)
    })
  }

  selectedKnowledgePoints.value = rootNodes as unknown as KnowledgePoint[]
}

export const autoBalanceWeight = () => {
  const count = selectedKnowledgePoints.value.length
  if (count === 0) return

  const baseWeight = Math.floor(100 / count)
  const remainder = 100 - baseWeight * count

  selectedKnowledgePoints.value.forEach((kp, index) => {
    kp.weight = baseWeight + (index < remainder ? 1 : 0)
  })
}

export const handleSkipKnowledgeChange = (checked: boolean) => {
  if (checked) {
    // 清空知识点选择
    selectedKnowledgePoints.value = []
    knowledgeTreeRef.value?.setCheckedKeys([])
  }
}

export const getKnowledgePointName = (kpId: number) => {
  const allNodes: any[] = []
  const collect = (nodes: any[]) => {
    for (const node of nodes) {
      allNodes.push(node)
      if (node.children) collect(node.children)
    }
  }
  collect(knowledgeTree.value)
  const node = allNodes.find(n => n.id === kpId)
  return node?.name || `知识点${kpId}`
}
