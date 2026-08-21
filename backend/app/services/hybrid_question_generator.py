"""混合出题引擎 - 规则规划 + AI执行

架构：规则引擎做"策略师"，AI做"写手"
1. 规则层：分析知识点类型 → 匹配出题策略 → 生成结构化出题计划
2. 快速通道：规则引擎秒级出基础题（兜底）
3. 深度通道：AI按策略生成灵活高质量题目
4. 合并：AI题优先，规则题补缺

与知识点导入的思路一致：规则做骨架，AI做血肉。
"""

from dataclasses import dataclass, field
import logging
import random
import re
from typing import Dict, List, Tuple

from app.models.knowledge import KnowledgePoint

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 第一层：知识点类型识别（规则）
# ──────────────────────────────────────────────

# 知识点类型枚举
KP_DEFINITION = "definition"  # 定义类：X是指Y、X的含义
KP_NORMATIVE = "normative"  # 规范类：应当X、必须Y
KP_PROHIBITIVE = "prohibitive"  # 禁止类：不得X、禁止Y
KP_PROCEDURAL = "procedural"  # 程序类：经过X程序、由Y批准
KP_SCOPE = "scope"  # 范围类：适用于X、包括Y
KP_PENALTY = "penalty"  # 处罚类：处罚、罚款、撤销
KP_GENERAL = "general"  # 通用类

# 类型识别规则：关键词 → 类型
TYPE_PATTERNS = [
    (KP_PROHIBITIVE, [r"不得", r"禁止", r"严禁", r"不允许", r"不可以", r"不得有", r"禁止性"]),
    (KP_PENALTY, [r"处罚", r"罚款", r"撤销", r"吊销", r"取消", r"追究", r"责令", r"没收", r"构成犯罪"]),
    (KP_NORMATIVE, [r"应当", r"必须", r"需要", r"应当按照", r"按照规定", r"依法应当", r"应当依法", r"须", r"应"]),
    (
        KP_PROCEDURAL,
        [r"程序", r"流程", r"步骤", r"审批", r"批准", r"申请", r"登记", r"备案", r"受理", r"报送", r"办理"],
    ),
    (KP_DEFINITION, [r"是指", r"定义为", r"含义", r"概念", r"定义", r"简称", r"称为", r"所称"]),
    (KP_SCOPE, [r"适用", r"包括", r"分为", r"范围", r"种类", r"类别", r"情形", r"以下.*属于"]),
]


def classify_knowledge_point(kp_name: str, kp_desc: str) -> str:
    """根据知识点名称和描述，判断其类型

    优先匹配禁止类和处罚类（最严格），
    然后是规范类、程序类，最后是定义类和范围类。
    """
    text = f"{kp_name} {kp_desc or ''}"

    for kp_type, patterns in TYPE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return kp_type

    return KP_GENERAL


# ──────────────────────────────────────────────
# 第二层：出题策略定义
# ──────────────────────────────────────────────

# 每种知识点类型对应的出题策略
# format: 题型占比 → prompt策略片段
STRATEGY_MAP = {
    KP_DEFINITION: {
        "name": "定义类",
        "question_mix": {
            "single_choice": 0.4,  # 40% 单选
            "true_false": 0.3,  # 30% 判断
            "fill_blank": 0.3,  # 30% 填空（用单选实现）
        },
        "ai_strategy": """【定义类知识点出题策略】
- 30%：改写定义，用"以下对X的理解/定义，正确的是"提问（不照搬原文表述）
- 30%：给出具体情形，判断是否符合某定义（情景化）
- 20%：填空式，挖掉关键词让选择（如"X是指____"）
- 20%：判断题，把定义中的关键条件稍微改写，判断正误""",
        "rule_templates": [
            # (模板, 适合的题型)
            ("以下关于{name}的理解，正确的是？", "single_choice"),
            ("关于{name}，下列说法错误的是？", "single_choice"),
            ("{desc_head}____{desc_tail}", "fill_blank"),
            ("{name}是指{modified_desc}。", "true_false"),
        ],
    },
    KP_NORMATIVE: {
        "name": "规范类",
        "question_mix": {
            "single_choice": 0.4,
            "true_false": 0.3,
            "multiple_choice": 0.3,
        },
        "ai_strategy": """【规范类知识点出题策略】
- 40%：情景题——给出具体场景，问"应当如何处理"（不照搬法条原文）
- 30%：否定题——"以下做法不符合X规定的是"（反向考查，灵活度高）
- 30%：判断题——改写规范中的关键条件，判断是否正确""",
        "rule_templates": [
            ("根据相关规定，{situation}，应当如何处理？", "single_choice"),
            ("以下关于{name}的做法，不符合规定的是？", "single_choice"),
            ("{situation}时，{action}。", "true_false"),
            ("根据{name}的规定，以下哪些是必须遵守的？", "multiple_choice"),
        ],
    },
    KP_PROHIBITIVE: {
        "name": "禁止类",
        "question_mix": {
            "single_choice": 0.35,
            "true_false": 0.35,
            "multiple_choice": 0.3,
        },
        "ai_strategy": """【禁止类知识点出题策略】
- 35%：选择正确的禁止行为（改写场景，不照搬原文）
- 35%：判断某种行为是否违规（情景化判断）
- 30%：多选，选出所有违规行为或合规要求""",
        "rule_templates": [
            ("根据{name}的规定，以下哪种行为是被禁止的？", "single_choice"),
            ("{situation}，这一行为是否违规？", "true_false"),
            ("根据{name}，以下哪些行为属于违规？", "multiple_choice"),
        ],
    },
    KP_PROCEDURAL: {
        "name": "程序类",
        "question_mix": {
            "single_choice": 0.35,
            "true_false": 0.3,
            "multiple_choice": 0.35,
        },
        "ai_strategy": """【程序类知识点出题策略】
- 35%：流程顺序题——某事项应经过哪些步骤/由谁审批
- 35%：多选，选出正确的程序要求或需要提交的材料
- 30%：判断题，判断某程序性要求是否正确""",
        "rule_templates": [
            ("办理{name}，应当经过什么程序？", "single_choice"),
            ("关于{name}的程序要求，以下正确的是？", "single_choice"),
            ("{procedure_step}是{name}的必经程序。", "true_false"),
            ("根据{name}的规定，申请时需要提交以下哪些材料？", "multiple_choice"),
        ],
    },
    KP_PENALTY: {
        "name": "处罚类",
        "question_mix": {
            "single_choice": 0.4,
            "true_false": 0.3,
            "multiple_choice": 0.3,
        },
        "ai_strategy": """【处罚类知识点出题策略】
- 40%：给出违规行为，问应受什么处罚（不照搬法条，改写表述）
- 30%：判断某处罚是否适当（情景化判断）
- 30%：多选，哪些行为会受到同种处罚""",
        "rule_templates": [
            ("违反{name}的规定，将面临以下哪种处罚？", "single_choice"),
            ("{violation}，将被处以{penalty}。", "true_false"),
            ("以下哪些行为将受到{name}规定的处罚？", "multiple_choice"),
        ],
    },
    KP_SCOPE: {
        "name": "范围类",
        "question_mix": {
            "single_choice": 0.35,
            "multiple_choice": 0.4,
            "true_false": 0.25,
        },
        "ai_strategy": """【范围类知识点出题策略】
- 40%：多选题，选出属于/不属于某范围的项目（灵活组合选项）
- 35%：单选题，判断某事项是否属于某范围（改写表述）
- 25%：判断题，判断范围描述是否正确""",
        "rule_templates": [
            ("以下哪项属于{name}的范围？", "single_choice"),
            ("根据{name}，以下哪些属于其适用范围？", "multiple_choice"),
            ("{item}属于{name}的范围。", "true_false"),
        ],
    },
    KP_GENERAL: {
        "name": "通用类",
        "question_mix": {
            "single_choice": 0.5,
            "true_false": 0.3,
            "multiple_choice": 0.2,
        },
        "ai_strategy": """【通用类知识点出题策略】
- 50%：单选题，围绕知识点核心内容出题（改写表述，不照搬原文）
- 30%：判断题，判断对知识点的理解是否正确
- 20%：多选题，考查知识点的多个方面""",
        "rule_templates": [
            ("关于{name}，以下说法正确的是？", "single_choice"),
            ("{statement}。", "true_false"),
            ("关于{name}，以下哪些说法是正确的？", "multiple_choice"),
        ],
    },
}


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────


@dataclass
class KnowledgePointInfo:
    """知识点信息（从数据库模型提取）"""

    id: int
    name: str
    description: str
    excerpt: str = ""  # 原文片段（content_excerpt）
    parent_name: str = ""
    kp_type: str = KP_GENERAL
    text: str = ""  # 完整文本（name + desc + excerpt）

    def __post_init__(self):
        self.text = f"【{self.name}】"
        if self.description:
            self.text += f"：{self.description}"
        if self.excerpt:
            self.text += f"\n\n原文参考：\n{self.excerpt}"


@dataclass
class QuestionPlan:
    """出题计划"""

    kp_type: str  # 知识点类型
    type_name: str  # 类型中文名
    knowledge_points: List[KnowledgePointInfo]  # 该类型的知识点列表
    total_count: int  # 该类型分配的题目数
    question_mix: Dict[str, float]  # 题型占比
    difficulty_distribution: Dict[int, float] = field(
        default_factory=lambda: {1: 0.2, 2: 0.3, 3: 0.3, 4: 0.1, 5: 0.1}
    )  # 难度分布
    ai_strategy: str = ""  # AI出题策略
    rule_templates: List[Tuple[str, str]] = field(default_factory=list)  # 规则模板列表


# ──────────────────────────────────────────────
# 第三层：出题计划生成（规则）
# ──────────────────────────────────────────────


def build_question_plans(
    knowledge_points: List[KnowledgePointInfo],
    total_count: int,
    question_types: List[str] = None,
    difficulty_distribution: Dict[int, float] = None,
) -> List[QuestionPlan]:
    """根据知识点类型分布，制定出题计划

    Args:
        knowledge_points: 知识点列表
        total_count: 总题目数
        question_types: 前端指定的题型列表，为空则自动分配
        difficulty_distribution: 难度分布比例，如 {1: 0.2, 2: 0.3, 3: 0.3, 4: 0.1, 5: 0.1}

    Returns:
        出题计划列表
    """
    # 默认难度分布
    if difficulty_distribution is None:
        difficulty_distribution = {1: 0.2, 2: 0.3, 3: 0.3, 4: 0.1, 5: 0.1}

    # 1. 对每个知识点分类
    for kp in knowledge_points:
        kp.kp_type = classify_knowledge_point(kp.name, kp.description)

    # 2. 按类型分组
    type_groups: Dict[str, List[KnowledgePointInfo]] = {}
    for kp in knowledge_points:
        type_groups.setdefault(kp.kp_type, []).append(kp)

    # 3. 按比例分配题目数
    total_kps = len(knowledge_points)
    plans = []

    for kp_type, kps in type_groups.items():
        strategy = STRATEGY_MAP.get(kp_type, STRATEGY_MAP[KP_GENERAL])
        ratio = len(kps) / total_kps
        type_count = max(1, round(total_count * ratio))

        # 如果前端指定了题型，调整 question_mix
        question_mix = strategy["question_mix"]
        if question_types:
            # 只保留前端指定的题型，重新计算占比
            filtered_mix = {k: v for k, v in question_mix.items() if k in question_types}
            if filtered_mix:
                total_ratio = sum(filtered_mix.values())
                question_mix = {k: v / total_ratio for k, v in filtered_mix.items()}
            else:
                # 如果没有任何交集，平均分配
                question_mix = {qt: 1.0 / len(question_types) for qt in question_types}

        plan = QuestionPlan(
            kp_type=kp_type,
            type_name=strategy["name"],
            knowledge_points=kps,
            total_count=type_count,
            question_mix=question_mix,
            difficulty_distribution=difficulty_distribution,
            ai_strategy=strategy["ai_strategy"],
            rule_templates=strategy["rule_templates"],
        )
        plans.append(plan)

    # 4. 修正总数（四舍五入可能导致偏差）
    actual_total = sum(p.total_count for p in plans)
    if actual_total != total_count and plans:
        diff = total_count - actual_total
        plans[0].total_count += diff  # 差额加到第一个计划

    logger.info(
        f"出题计划: {len(plans)} 个类型组, "
        + ", ".join(f"{p.type_name}({len(p.knowledge_points)}个知识点,{p.total_count}题)" for p in plans)
    )

    return plans


# ──────────────────────────────────────────────
# 第四层：规则出题（快速通道，秒级）
# ──────────────────────────────────────────────

# 同义替换词库（用于不照搬原文）
SYNONYM_MAP = {
    "应当": ["应该", "须", "必须", "需要", "有义务"],
    "不得": ["不可以", "禁止", "不能", "严禁", "绝不允许"],
    "必须": ["应当", "务必", "一定", "须"],
    "可以": ["允许", "有权", "能够", "可"],
    "属于": ["归入", "划为", "纳入", "是"],
    "违反": ["违背", "触犯", "不遵守", "未遵守"],
    "处罚": ["惩罚", "制裁", "处理", "追究"],
    "撤销": ["取消", "废止", "吊销", "注销"],
    "申请": ["提出申请", "报送", "提出", "提交"],
    "批准": ["审批", "核准", "同意", "许可"],
}

# 判断题真假改写
TRUE_FALSE_MODIFIERS = {
    "assert_true": ["是正确的", "符合规定", "是合法的", "符合要求"],
    "assert_false": ["是错误的", "不符合规定", "是不合法的", "不符合要求"],
}


def _synonym_replace(text: str) -> str:
    """对文本进行同义替换，避免照搬原文"""
    result = text
    for original, synonyms in SYNONYM_MAP.items():
        if original in result:
            replacement = random.choice(synonyms)
            result = result.replace(original, replacement, 1)
            break  # 只替换一个词，保持自然
    return result


def _generate_distractors(correct_text: str, all_kps: List[KnowledgePointInfo], count: int = 3) -> List[str]:
    """从其他知识点生成干扰选项

    策略：从同级/同类知识点中提取信息，生成半真半假的干扰项
    """
    distractors = []

    # 收集其他知识点的描述片段
    other_descs = []
    for kp in all_kps:
        if kp.description and kp.text != correct_text:
            other_descs.append(kp.description)

    if not other_descs:
        # 没有其他知识点，生成通用干扰项
        distractors = ["以上都不是", "无需特殊要求", "由当事人自行决定"]
        return distractors[:count]

    # 从其他描述中随机选取，可能进行同义替换
    random.shuffle(other_descs)
    for desc in other_descs[: count * 2]:  # 多取一些，后面筛选
        if len(desc) > 5:  # 太短的描述不适合做选项
            modified = _synonym_replace(desc[:80])  # 截断过长的描述
            if modified not in distractors and modified != correct_text[:80]:
                distractors.append(modified)
        if len(distractors) >= count:
            break

    # 仍然不够则生成通用干扰项
    while len(distractors) < count:
        distractors.append("以上均不正确")

    return distractors[:count]


def rule_generate_single_choice(
    kp: KnowledgePointInfo,
    all_kps: List[KnowledgePointInfo],
) -> dict | None:
    """规则生成单选题"""
    if not kp.description or len(kp.description) < 4:
        return None

    # 随机选择一种模板
    templates = [
        f"以下关于{kp.name}的说法，正确的是？",
        f"关于{kp.name}，下列说法错误的是？",
        f"根据相关规定，以下哪项对{kp.name}的表述是正确的？",
    ]
    question_content = random.choice(templates)

    # 正确答案（同义替换）
    correct = _synonym_replace(kp.description[:80])

    # 干扰项
    distractors = _generate_distractors(kp.text, all_kps, 3)

    # 随机排列选项
    all_options = [correct, *distractors]
    random.shuffle(all_options)
    correct_index = all_options.index(correct)
    correct_label = chr(65 + correct_index)  # A, B, C, D

    options = [{"option_label": chr(65 + i), "option_content": opt} for i, opt in enumerate(all_options)]

    return {
        "question_type": "single_choice",
        "content": question_content,
        "answer": correct_label,
        "explanation": f"根据{kp.parent_name or '相关规定'}，{kp.name}：{kp.description}",
        "difficulty": 3,
        "options": options,
    }


def rule_generate_true_false(
    kp: KnowledgePointInfo,
    all_kps: List[KnowledgePointInfo],
) -> dict | None:
    """规则生成判断题"""
    if not kp.description or len(kp.description) < 4:
        return None

    # 50% 正确陈述，50% 错误陈述
    is_correct = random.choice([True, False])

    if is_correct:
        # 正确陈述：同义替换
        statement = _synonym_replace(kp.description[:100])
    else:
        # 错误陈述：从其他知识点偷换概念
        other_descs = [kp2.description for kp2 in all_kps if kp2.description and kp2.id != kp.id]
        if other_descs:
            wrong_desc = random.choice(other_descs)[:80]
            statement = f"{kp.name}{_synonym_replace(wrong_desc)}"
        else:
            # 没有其他选项，简单改写
            statement = _synonym_replace(kp.description[:60])
            # 加一点错误
            statement = statement.replace("应当", "不需要").replace("必须", "无需")
            if statement == _synonym_replace(kp.description[:60]):
                return None  # 无法生成有效错误陈述

    assertion = random.choice(TRUE_FALSE_MODIFIERS["assert_true" if is_correct else "assert_false"])
    question_content = f"{statement}{assertion}。"

    return {
        "question_type": "true_false",
        "content": question_content,
        "answer": "true" if is_correct else "false",
        "explanation": f"根据{kp.parent_name or '相关规定'}，{kp.name}：{kp.description}",
        "difficulty": 2 if is_correct else 3,
        "options": None,
    }


def rule_generate_multiple_choice(
    kp: KnowledgePointInfo,
    all_kps: List[KnowledgePointInfo],
) -> dict | None:
    """规则生成多选题"""
    if not kp.description or len(kp.description) < 4:
        return None

    # 从知识点描述中拆出多个要点（简单策略：按逗号、顿号、分号拆分）
    parts = re.split(r"[，、；]", kp.description)
    parts = [p.strip() for p in parts if len(p.strip()) > 3]

    if len(parts) < 2:
        # 知识点描述不可拆分，用其他知识点补充
        for other_kp in all_kps:
            if other_kp.id != kp.id and other_kp.description:
                other_parts = re.split(r"[，、；]", other_kp.description)
                parts.extend([p.strip() for p in other_parts if len(p.strip()) > 3])
        if len(parts) < 2:
            return None  # 仍然不够，跳过

    # 选2-3个正确选项
    correct_count = min(random.choice([2, 3]), len(parts))
    correct_options = random.sample(parts, correct_count)

    # 生成干扰项
    distractors = _generate_distractors(kp.text, all_kps, 2)

    all_options_text = correct_options + distractors[:2]
    random.shuffle(all_options_text)

    correct_labels = []
    options = []
    for i, opt in enumerate(all_options_text):
        label = chr(65 + i)
        options.append({"option_label": label, "option_content": opt})
        if opt in correct_options:
            correct_labels.append(label)

    question_content = f"关于{kp.name}，以下说法正确的是？"

    return {
        "question_type": "multiple_choice",
        "content": question_content,
        "answer": ",".join(correct_labels),
        "explanation": f"根据{kp.parent_name or '相关规定'}，{kp.name}：{kp.description}",
        "difficulty": 3,
        "options": options,
    }


def rule_generate_essay(
    kp: KnowledgePointInfo,
    all_kps: List[KnowledgePointInfo],
) -> dict | None:
    """规则生成问答题"""
    if not kp.description or len(kp.description) < 10:
        return None

    # 问答题模板：围绕知识点的定义、规范、程序等提问
    templates = [
        f"请简述{kp.name}的定义及其主要特点。",
        f"根据相关规定，{kp.name}应当满足哪些要求？",
        f"请说明{kp.name}的基本流程和关键环节。",
        f"试述{kp.name}在实践中的应用及注意事项。",
    ]
    question_content = random.choice(templates)

    # 参考答案：使用知识点描述作为参考答案
    reference_answer = f"【参考答案】\n{kp.name}：{kp.description}"
    if kp.parent_name:
        reference_answer += f"\n\n【相关背景】{kp.parent_name}"

    return {
        "question_type": "essay",
        "content": question_content,
        "answer": reference_answer,
        "explanation": f"本题考察对{kp.name}的理解和应用。建议结合{kp.parent_name or '相关规定'}进行回答。",
        "difficulty": 3,
        "options": None,
    }


# 规则出题函数映射
RULE_GENERATORS = {
    "single_choice": rule_generate_single_choice,
    "true_false": rule_generate_true_false,
    "multiple_choice": rule_generate_multiple_choice,
    "essay": rule_generate_essay,
}


def rule_generate_questions(plan: QuestionPlan) -> List[dict]:
    """规则引擎出题（快速通道）

    按知识点权重（description长度）占比分配题目。
    知识点内容越多，分配的题目越多。
    质量不如AI，但秒级完成，作为兜底。
    """
    questions = []
    kps = plan.knowledge_points[:]

    # 计算每个知识点的权重（基于description长度）
    kp_weights = []
    total_weight = 0
    for kp in kps:
        weight = max(1, len(kp.description or ""))  # description越长权重越大
        kp_weights.append(weight)
        total_weight += weight

    # 按题型占比分配题目数
    type_counts = {}
    for qtype, ratio in plan.question_mix.items():
        type_counts[qtype] = max(1, round(plan.total_count * ratio))

    # 修正总数
    actual = sum(type_counts.values())
    if actual != plan.total_count and type_counts:
        first_key = next(iter(type_counts))
        type_counts[first_key] += plan.total_count - actual

    # 按知识点权重分配题目
    kp_index = 0
    for qtype, count in type_counts.items():
        generator = RULE_GENERATORS.get(qtype)
        if not generator:
            continue

        generated = 0
        attempts = 0
        while generated < count and attempts < count * 3:
            # 按权重选取知识点
            if total_weight > 0:
                kp_idx = 0
                rand_val = random.randint(1, total_weight)
                cum_weight = 0
                for i, w in enumerate(kp_weights):
                    cum_weight += w
                    if cum_weight >= rand_val:
                        kp_idx = i
                        break
                kp = kps[kp_idx]
            else:
                kp = kps[kp_index % len(kps)]
            kp_index = (kp_index + 1) % len(kps)
            attempts += 1

            q = generator(kp, plan.knowledge_points)
            if q:
                questions.append(q)
                generated += 1

    logger.info(f"规则出题 [{plan.type_name}]: 生成 {len(questions)}/{plan.total_count} 题")
    return questions


# ──────────────────────────────────────────────
# 第五层：AI策略出题 Prompt 构建
# ──────────────────────────────────────────────


def build_strategic_prompt(
    plan: QuestionPlan,
    subject_name: str,
    chapter_names: List[str],
    difficulty: int,
    template_prompt: str | None = None,
) -> str:
    """构建带策略的AI出题prompt

    关键：把知识点类型、出题策略、题型分配都放进prompt，
    让AI按策略精准出题，而不是通用地出题。
    """
    difficulty_label = {1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难"}.get(difficulty, "中等")

    # 构建知识点内容（含 excerpt 原文参考，适当放宽截断阈值）
    kp_texts = [kp.text for kp in plan.knowledge_points]
    knowledge_content = "\n".join(kp_texts)
    if len(knowledge_content) > 6000:
        knowledge_content = knowledge_content[:6000] + "\n...(更多知识点已省略)"

    # 题型分配说明
    mix_parts = []
    type_name_map = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "essay": "问答题",
    }
    for qtype, ratio in plan.question_mix.items():
        count = max(1, round(plan.total_count * ratio))
        mix_parts.append(f"- {type_name_map.get(qtype, qtype)}：{count}道")
    mix_description = "\n".join(mix_parts)

    # 如果用户选择了自定义模板，优先使用模板 prompt
    if template_prompt:
        safe_template = template_prompt.strip()
        if safe_template:
            return f'''{safe_template}

科目："{subject_name}"
章节：{"、".join(chapter_names) if chapter_names else "全章节"}
难度：{difficulty_label}（1-5级）

【知识点参考内容】
---
{knowledge_content}
---

【题型分配要求】
{mix_description}

请严格按照上述模板指令和题型分配来生成题目。返回JSON数组格式，每道题目包含：
- question_type: 题型（single_choice/multiple_choice/true_false/essay）
- content: 题目内容
- answer: 正确答案（单选为"A"，多选为"A,B"，判断为"true"/"false"）
- explanation: 详细解析
- difficulty: 难度等级（{difficulty}）
- options: 数组，仅选择题有此字段，每个选项包含option_label和option_content

请直接返回JSON数组，不要包含任何其他文字。'''

    prompt = f'''你是一个专业的试题生成助手。请根据以下知识点和出题策略生成{plan.total_count}道题目。

科目："{subject_name}"
章节：{"、".join(chapter_names) if chapter_names else "全章节"}
难度：{difficulty_label}（1-5级）

【知识点类型】{plan.type_name}

【知识点参考内容】
---
{knowledge_content}
---

{plan.ai_strategy}

【题型分配】
{mix_description}

【出题要求】
1. 严格按照上述出题策略和题型分配来生成题目
2. 题目必须围绕知识点展开，但不要照搬原文表述——要改写、情景化、转换视角
3. 每道题目必须包含：题目内容、正确答案、详细解析
4. 选择题必须提供4个选项（A/B/C/D），多选题正确答案2-3个
5. 判断题答案为"true"或"false"
6. 干扰选项要合理，使用其他知识点的内容做半真半假的干扰
7. 解析应引用具体知识点内容，帮助考生理解
8. 返回JSON数组格式，每道题目包含以下字段：
   - question_type: 题型（single_choice/multiple_choice/true_false/essay）
   - content: 题目内容
   - answer: 正确答案（单选为"A"，多选为"A,B"，判断为"true"/"false"）
   - explanation: 详细解析
   - difficulty: 难度等级（{difficulty}）
   - options: 数组，仅选择题有此字段，每个选项包含option_label和option_content

请直接返回JSON数组，不要包含任何其他文字。'''

    return prompt


# ──────────────────────────────────────────────
# 第六层：从数据库构建知识点信息
# ──────────────────────────────────────────────


def build_kp_info_list(db, knowledge_point_ids: List[int]) -> List[KnowledgePointInfo]:
    """从数据库查询知识点，构建知识点信息列表

    优化策略：先批量查询所有选中节点的子树，避免N+1递归查询。
    使用一次性查询获取整个子树，然后在内存中构建树结构。
    """
    if not knowledge_point_ids:
        return []

    # 查询选中的知识点
    selected_kps = (
        db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(knowledge_point_ids), KnowledgePoint.status == 1).all()
    )

    if not selected_kps:
        return []

    # 收集所有选中节点的ID，以及它们的category和exam_type用于批量查询子树
    selected_ids = {kp.id for kp in selected_kps}

    # 一次性查询所有可能相关的知识点（同category/exam_type下的）
    # 这样避免了递归N+1查询，一次性把所有需要的节点都取出来
    categories = {kp.category for kp in selected_kps if kp.category}
    exam_types = {kp.exam_type for kp in selected_kps if kp.exam_type}

    # 批量查询：获取同类别下的所有知识点，然后在内存中筛选子树
    query = db.query(KnowledgePoint).filter(KnowledgePoint.status == 1)
    if categories:
        query = query.filter(KnowledgePoint.category.in_(categories))
    elif exam_types:
        query = query.filter(KnowledgePoint.exam_type.in_(exam_types))

    all_kps = query.order_by(KnowledgePoint.order).all()
    logger.info(f"批量查询知识点: 选中{len(selected_ids)}个, 同类别共{len(all_kps)}个")

    # 在内存中构建 parent_id → children 映射
    children_map: Dict[int, List[KnowledgePoint]] = {}
    kp_by_id: Dict[int, KnowledgePoint] = {}
    for kp in all_kps:
        kp_by_id[kp.id] = kp
        children_map.setdefault(kp.parent_id, []).append(kp)

    # 从选中的节点出发，在内存中递归收集子树
    info_list = []
    visited_ids = set()

    def _collect_in_memory(kp_id: int, parent_name: str = ""):
        if kp_id in visited_ids:
            return
        visited_ids.add(kp_id)

        kp = kp_by_id.get(kp_id)
        if not kp:
            return

        info = KnowledgePointInfo(
            id=kp.id,
            name=kp.name,
            description=kp.description or "",
            excerpt=kp.content_excerpt or "",
            parent_name=parent_name,
        )
        info_list.append(info)

        # 递归收集子节点（从内存映射中获取，不再查数据库）
        for child in children_map.get(kp_id, []):
            _collect_in_memory(child.id, parent_name=kp.name)

    for kp in selected_kps:
        _collect_in_memory(kp.id)

    logger.info(f"知识点收集完成: {len(info_list)} 个知识点")
    return info_list
