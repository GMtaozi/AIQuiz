/**
 * Shared knowledge-tree node type used by the generation composables.
 * Mirrors the runtime shape of knowledge points returned by the backend.
 */
export interface QuestionNode {
  id: number
  name: string
  parent_id?: number
  categoryId?: number
  examTypeId?: number
  sortOrder?: number
  description?: string
  node_type?: string
  children?: QuestionNode[]
  chapter_id?: number
}
