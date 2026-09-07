"""Tree utility functions for knowledge points.

Provides recursive tree building, node counting, leaf counting, and depth calculation.
"""

from typing import List

from app.models.knowledge import KnowledgePoint


def _count_tree_nodes(nodes: List[dict]) -> int:
    """递归统计树中节点总数"""
    count = 0
    for node in nodes:
        count += 1
        children = node.get("children") or node.get("子节点", [])
        if children and isinstance(children, list):
            count += _count_tree_nodes(children)
    return count


def _build_tree(nodes: List[KnowledgePoint], parent_id: int | None = None) -> List[dict]:
    """递归构建树形结构"""
    tree = []
    for node in nodes:
        if node.parent_id == parent_id:
            # 递归获取子节点
            children_nodes = [n for n in nodes if n.parent_id == node.id]
            children = _build_tree(nodes, node.id)

            # 只有根节点（parent_id is None）才在名称后面显示最末级知识点统计
            display_name = node.name
            is_root = parent_id is None
            leaf_count = 0
            if is_root and children:
                # 统计该根节点下的所有叶子节点数量
                leaf_count = _count_leaf_nodes(children)
                display_name = f"{node.name}（共{leaf_count}个知识点）"

            tree.append(
                {
                    "id": node.id,
                    "name": display_name,
                    "original_name": node.name,  # 保留原始名称
                    "parent_id": node.parent_id,
                    "category": node.category,
                    "exam_type": node.exam_type,
                    "description": node.description,
                    "order": node.order,
                    "status": node.status,
                    "created_by": node.created_by,
                    "created_at": node.created_at,
                    "updated_at": node.updated_at,
                    "leaf_count": leaf_count if is_root else 0,  # 仅根节点记录叶子节点数
                    "children": children,
                }
            )
    return tree


def _count_leaf_nodes(nodes: List[dict]) -> int:
    """统计节点列表中的叶子节点数量（没有 children 或 children 为空的节点）"""
    count = 0
    for node in nodes:
        if not node.get("children") or len(node["children"]) == 0:
            count += 1
        else:
            count += _count_leaf_nodes(node["children"])
    return count


def _get_tree_depth(nodes: List[dict], node_id: int | None, current_depth: int = 1) -> int:
    """计算树的深度"""
    children = [n for n in nodes if n.get("parent_id") == node_id]
    if not children:
        return current_depth
    return max(_get_tree_depth(nodes, child["id"], current_depth + 1) for child in children)


def _build_kp_tree(root_points: list, child_points: list) -> list:
    """从根知识点和子知识点列表构建树（复用 _build_tree 逻辑但用对象而非全量查询）"""
    all_points = root_points + child_points
    return _build_tree(all_points, None)
