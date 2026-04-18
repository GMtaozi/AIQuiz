"""AI Templates Router - CRUD for AI prompt templates and question generation"""
import re
import logging
import threading
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel
from app.database import get_db
from app.schemas.question import AiTemplateCreate, AiTemplateUpdate, AiTemplateResponse
from app.models.question import AIPromptTemplate, GenerationTask, Question
from app.models.knowledge import KnowledgePoint
from app.services.ai_question import generate_questions, _call_ai_with_retry, _try_parse_questions_json, _verify_questions
from app.services.hybrid_question_generator import (
    build_kp_info_list, build_question_plans, rule_generate_questions,
    build_strategic_prompt, STRATEGY_MAP,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/templates", response_model=List[AiTemplateResponse])
def list_templates(
    template_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all AI prompt templates"""
    query = db.query(AIPromptTemplate)

    if template_type:
        query = query.filter(AIPromptTemplate.template_type == template_type)
    if status:
        query = query.filter(AIPromptTemplate.status == status)
    else:
        query = query.filter(AIPromptTemplate.status == "active")

    return query.order_by(AIPromptTemplate.id).all()


@router.post("/templates", response_model=AiTemplateResponse, status_code=201)
def create_template(template_data: AiTemplateCreate, db: Session = Depends(get_db)):
    """Create a new AI prompt template"""
    template = AIPromptTemplate(
        name=template_data.name,
        template_type=template_data.template_type,
        prompt_template=template_data.prompt_template,
        variables=template_data.variables,
        model=template_data.model or "abab6.5s-chat",
        config=template_data.config,
        status=template_data.status or "active",
        created_by=template_data.created_by,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates/{template_id}", response_model=AiTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    """Get a template by ID"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=AiTemplateResponse)
def update_template(template_id: int, template_data: AiTemplateUpdate, db: Session = Depends(get_db)):
    """Update a template"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a template (soft delete)"""
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.status = "inactive"
    db.commit()
    return None


def _build_knowledge_context(db: Session, knowledge_point_ids: List[int]) -> str:
    """根据知识点ID列表构建知识点上下文内容
    
    支持选中科目根节点后自动展开全部子知识点，
    提供足够丰富的知识内容供 AI 出题。
    
    优化：批量查询知识点，避免N+1递归查询。
    """
    if not knowledge_point_ids:
        return ""

    # 查询选中的知识点
    selected_kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.id.in_(knowledge_point_ids),
        KnowledgePoint.status == 1
    ).all()

    if not selected_kps:
        return ""

    # 批量查询同类别下的所有知识点，避免N+1递归
    categories = {kp.category for kp in selected_kps if kp.category}
    exam_types = {kp.exam_type for kp in selected_kps if kp.exam_type}
    
    query = db.query(KnowledgePoint).filter(KnowledgePoint.status == 1)
    if categories:
        query = query.filter(KnowledgePoint.category.in_(categories))
    elif exam_types:
        query = query.filter(KnowledgePoint.exam_type.in_(exam_types))
    all_kps = query.order_by(KnowledgePoint.order).all()
    
    # 在内存中构建 parent_id → children 映射
    children_map = {}
    kp_by_id = {}
    for kp in all_kps:
        kp_by_id[kp.id] = kp
        children_map.setdefault(kp.parent_id, []).append(kp)

    # 在内存中递归收集子树内容
    def _collect_subtree(kp: KnowledgePoint, depth: int = 0) -> str:
        indent = "  " * depth
        parts = []
        name_part = f"{indent}【{kp.name}】"
        if kp.description:
            name_part += f"：{kp.description}"
        parts.append(name_part)
        
        # 从内存映射获取子节点，不再查数据库
        for child in children_map.get(kp.id, []):
            parts.append(_collect_subtree(child, depth + 1))
        
        return "\n".join(parts)

    sections = []
    for kp in selected_kps:
        sections.append(_collect_subtree(kp, depth=0))

    result = "\n\n".join(sections)
    
    # 不在这里截断，让调用方（分组逻辑）决定如何分配
    return result


def _build_knowledge_groups(db: Session, knowledge_point_ids: List[int], max_chars_per_group: int = 4000) -> List[str]:
    """将知识点拆分为多个分组，每组不超过 max_chars_per_group 字符

    用于大知识点集合的出题：每组知识点单独出一批题，轮转覆盖全部知识点。
    比如选了整个科目的 200 个知识点，拆成 5 组，每组 ~4000 字符，
    每组出一批题，确保所有知识点都被覆盖到。
    """
    full_context = _build_knowledge_context(db, knowledge_point_ids)
    if not full_context:
        return []

    # 如果总长度不超限，直接返回单个分组
    if len(full_context) <= max_chars_per_group:
        return [full_context]

    # 按"章"或顶层知识点分块（以空行+【】开头的行作为分隔点）
    sections = re.split(r'\n\n(?=【)', full_context)

    groups = []
    current_group = ""
    
    for section in sections:
        # 如果单个 section 就超过限制，需要进一步拆分
        if len(section) > max_chars_per_group:
            # 先把当前分组收尾
            if current_group:
                groups.append(current_group)
                current_group = ""
            # 按条目拆分大 section
            sub_sections = re.split(r'\n(?=  【)', section)
            for sub in sub_sections:
                if len(current_group) + len(sub) + 2 <= max_chars_per_group:
                    current_group += ("\n" if current_group else "") + sub
                else:
                    if current_group:
                        groups.append(current_group)
                    # 如果单个条目就超限，截断
                    current_group = sub[:max_chars_per_group]
        elif len(current_group) + len(section) + 2 <= max_chars_per_group:
            current_group += ("\n\n" if current_group else "") + section
        else:
            groups.append(current_group)
            current_group = section
    
    if current_group:
        groups.append(current_group)

    return groups if groups else [full_context[:max_chars_per_group]]


class GenerateQuestionsRequest(BaseModel):
    subject_id: int
    subject_name: str
    chapter_ids: List[int] = []
    chapter_names: List[str] = []
    question_type: str = "single_choice"
    difficulty: int = 3
    count: int = 5
    template_id: Optional[int] = None
    knowledge_point_ids: List[int] = []
    knowledge_content: str = ""  # 前端可直接传知识点内容文本


class GenerateQuestionsResponse(BaseModel):
    questions: List[dict]
    count: int
    generated_by: str = "MiniMax"


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate_questions_endpoint(
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
):
    """Generate questions using AI (MiniMax) with retry and circuit breaker
    
    支持大知识点集合：自动将知识点拆分为多组，轮转覆盖全部知识点出题。
    每组知识点单独出一批题，确保 200+ 知识点也能被完整覆盖。
    """
    if request.template_id:
        template = db.query(AIPromptTemplate).filter(
            AIPromptTemplate.id == request.template_id
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

    # 构建知识点分组：每个分组不超过 4000 字符，适配 MiniMax-M2.7
    if request.knowledge_point_ids:
        knowledge_groups = _build_knowledge_groups(
            db, request.knowledge_point_ids, max_chars_per_group=4000
        )
    elif request.knowledge_content:
        # 前端直接传内容，作为单个分组
        knowledge_groups = [request.knowledge_content[:4000]]
    else:
        knowledge_groups = [""]

    total_questions = []
    group_count = len(knowledge_groups)

    logger.info(f"出题请求: 题型={request.question_type}, 总题数={request.count}, 知识点分组={group_count}")

    if group_count <= 1:
        # 知识点少，一次性出题
        questions = await generate_questions(
            subject_id=request.subject_id,
            subject_name=request.subject_name,
            chapter_ids=request.chapter_ids,
            chapter_names=request.chapter_names,
            question_type=request.question_type,
            difficulty=request.difficulty,
            count=request.count,
            knowledge_content=knowledge_groups[0] if knowledge_groups else "",
        )
        total_questions = questions
    else:
        # 知识点多，分组轮转出题
        # 按组分配题目数量：总题数平均分配到各组
        base_per_group = request.count // group_count
        remainder = request.count % group_count
        
        for i, group_content in enumerate(knowledge_groups):
            group_count_i = base_per_group + (1 if i < remainder else 0)
            if group_count_i <= 0:
                continue

            logger.info(f"知识点分组 {i+1}/{group_count}: {len(group_content)} 字符, 出 {group_count_i} 题")

            questions = await generate_questions(
                subject_id=request.subject_id,
                subject_name=request.subject_name,
                chapter_ids=request.chapter_ids,
                chapter_names=request.chapter_names,
                question_type=request.question_type,
                difficulty=request.difficulty,
                count=group_count_i,
                knowledge_content=group_content,
            )
            total_questions.extend(questions)
            logger.info(f"分组 {i+1}/{group_count} 完成: 本组生成 {len(questions)} 题, 累计 {len(total_questions)}/{request.count} 题")

    logger.info(f"出题完成: 最终生成 {len(total_questions)}/{request.count} 题")
    return GenerateQuestionsResponse(questions=total_questions, count=len(total_questions))


# ──────────────────────────────────────────────
# 混合出题接口（规则规划 + AI执行）
# ──────────────────────────────────────────────

class HybridGenerateRequest(BaseModel):
    """混合出题请求"""
    subject_id: int
    subject_name: str
    chapter_ids: List[int] = []
    chapter_names: List[str] = []
    question_types: List[str] = ["single_choice"]  # 支持多题型
    difficulty: int = 3
    count: int = 10
    knowledge_point_ids: List[int] = []
    mode: str = "hybrid"  # hybrid=规则+AI, rule_only=仅规则


class HybridGenerateResponse(BaseModel):
    """混合出题响应"""
    questions: List[dict]
    count: int
    generated_by: str = "Hybrid"
    plan_summary: dict = {}  # 出题计划摘要
    rule_questions: int = 0  # 规则生成的题数
    ai_questions: int = 0    # AI生成的题数


@router.post("/hybrid-generate", response_model=HybridGenerateResponse)
async def hybrid_generate_endpoint(
    request: HybridGenerateRequest,
    db: Session = Depends(get_db),
):
    """混合出题：规则引擎做策略规划，AI按策略灵活执行
    
    流程：
    1. 规则层：分析知识点类型 → 制定出题策略和计划
    2. 快速通道：规则引擎秒级出基础题（兜底保障）
    3. 深度通道：AI按策略生成高质量灵活题目
    4. 合并：AI题优先替换规则题，规则题补缺
    
    mode 参数：
    - hybrid: 规则+AI混合（默认）
    - rule_only: 仅规则出题（秒级，不调用AI）
    """
    # mode 参数只允许 hybrid 和 rule_only
    if request.mode not in ("hybrid", "rule_only"):
        request.mode = "hybrid"

    # 1. 构建知识点信息列表
    kp_info_list = build_kp_info_list(db, request.knowledge_point_ids)
    if not kp_info_list:
        raise HTTPException(status_code=400, detail="未找到有效的知识点")
    
    logger.info(f"混合出题请求: mode={request.mode}, 题型={request.question_types}, "
                f"总题数={request.count}, 知识点={len(kp_info_list)}")
    
    # 2. 生成出题计划（规则层）
    plans = build_question_plans(kp_info_list, request.count, request.question_types)
    
    plan_summary = {
        "total_kps": len(kp_info_list),
        "type_distribution": {p.type_name: len(p.knowledge_points) for p in plans},
        "question_allocation": {p.type_name: p.total_count for p in plans},
    }
    
    # 3. 快速通道：规则出题（秒级）
    rule_questions = []
    if request.mode in ("hybrid", "rule_only"):
        for plan in plans:
            rqs = rule_generate_questions(plan)
            rule_questions.extend(rqs)
        logger.info(f"规则出题完成: {len(rule_questions)} 题")
    
    # 4. 深度通道：AI按策略出题
    ai_questions = []
    if request.mode == "hybrid":
        import asyncio
        AI_BATCH_SIZE = 15  # 每批生成题目数，增大批次减少API调用次数
        # 总超时控制：根据题目数量动态计算，最多不超过120秒
        max_total_time = min(30 + request.count * 2, 120)
        ai_start_time = asyncio.get_event_loop().time()
        ai_timed_out = False
        
        # 优化：合并多个小plan为更大的batch，减少API调用次数
        # 将所有plan的题目需求汇总，按题型分组批量生成
        # 这样7种类型不需要7次串行调用，而是2-3次并行调用
        
        async def _ai_batch_call(batch_prompt: str, batch_label: str) -> list:
            """单个AI批处理调用，返回解析后的题目列表"""
            try:
                result_text = await _call_ai_with_retry(batch_prompt, max_tokens=8192)
            except Exception as e:
                logger.error(f"AI出题 [{batch_label}]: API调用异常: {e}")
                return []
            
            if result_text is None:
                logger.warning(f"AI出题 [{batch_label}]: API返回None（可能超时/限流/熔断）")
                return []
            
            questions_data = _try_parse_questions_json(result_text)
            if not questions_data:
                logger.warning(f"AI出题 [{batch_label}]: JSON解析失败, "
                              f"text_len={len(result_text)}, text_preview={result_text[:200]}")
                return []
            
            processed = []
            for q in questions_data:
                processed_q = {
                    "content": q.get("content", ""),
                    "answer": q.get("answer", ""),
                    "explanation": q.get("explanation", ""),
                    "question_type": q.get("question_type", "single_choice"),
                    "difficulty": q.get("difficulty", request.difficulty),
                    "subject_id": request.subject_id,
                    "options": q.get("options", []),
                }
                processed.append(processed_q)
            logger.info(f"AI出题 [{batch_label}]: 生成 {len(processed)} 题")
            return processed
        
        # 合并小plan：将题目数<=3的plan合并到一起，减少API调用
        # 大plan单独调用，小plan合并为一次调用
        big_plans = [p for p in plans if p.total_count > 3]
        small_plans = [p for p in plans if p.total_count <= 3]
        
        # 构建所有需要调用的prompt列表
        batch_tasks = []  # [(prompt, label, count)]
        
        for plan in big_plans:
            # 大plan按AI_BATCH_SIZE分批
            for batch_start in range(0, plan.total_count, AI_BATCH_SIZE):
                batch_count = min(AI_BATCH_SIZE, plan.total_count - batch_start)
                batch_num = batch_start // AI_BATCH_SIZE + 1
                
                prompt = build_strategic_prompt(
                    plan=plan,
                    subject_name=request.subject_name,
                    chapter_names=request.chapter_names,
                    difficulty=request.difficulty,
                )
                # 修改prompt中的题目数
                batch_prompt = prompt.replace(
                    f"生成{plan.total_count}道题目",
                    f"生成{batch_count}道题目"
                )
                batch_tasks.append((batch_prompt, f"{plan.type_name}-b{batch_num}", batch_count))
        
        # 小plan合并：将所有小plan的策略和知识点合并到一个prompt
        if small_plans:
            # 合并小plan的知识点和策略
            merged_kps = []
            merged_strategies = []
            merged_mix = {}
            for sp in small_plans:
                merged_kps.extend(sp.knowledge_points)
                merged_strategies.append(f"【{sp.type_name}】({sp.total_count}题): {sp.ai_strategy[:200]}")
                for qt, ratio in sp.question_mix.items():
                    merged_mix[qt] = merged_mix.get(qt, 0) + sp.total_count * ratio
            
            total_small = sum(sp.total_count for sp in small_plans)
            kp_texts = [kp.text for kp in merged_kps]
            knowledge_content = "\n".join(kp_texts)
            if len(knowledge_content) > 4000:
                knowledge_content = knowledge_content[:4000] + "\n...(更多知识点已省略)"
            
            difficulty_label = {1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难"}.get(request.difficulty, "中等")
            type_name_map = {"single_choice": "单选题", "multiple_choice": "多选题", "true_false": "判断题", "essay": "问答题"}
            mix_parts = [f"- {type_name_map.get(qt, qt)}：{max(1, round(total_small * r))}道" for qt, r in merged_mix.items()]
            
            merged_prompt = f'''你是一个专业的试题生成助手。请根据以下知识点和出题策略生成{total_small}道题目。

科目："{request.subject_name}"
章节：{"、".join(request.chapter_names) if request.chapter_names else "全章节"}
难度：{difficulty_label}（1-5级）

【多类型知识点混合出题】
需要同时覆盖以下{len(small_plans)}种知识点类型：
{chr(10).join(merged_strategies)}

【知识点参考内容】
---
{knowledge_content}
---

【题型分配】
{chr(10).join(mix_parts)}

【出题要求】
1. 按照上述出题策略和题型分配来生成题目
2. 题目不要照搬原文表述——要改写、情景化、转换视角
3. 每道题目必须包含：题目内容、正确答案、详细解析
4. 选择题必须提供4个选项（A/B/C/D），多选题正确答案2-3个
5. 判断题答案为"true"或"false"
6. 干扰选项要合理
7. 返回JSON数组格式，每道题目包含以下字段：
   - question_type: 题型（single_choice/multiple_choice/true_false/essay）
   - content: 题目内容
   - answer: 正确答案（单选为"A"，多选为"A,B"，判断为"true"/"false"）
   - explanation: 详细解析
   - difficulty: 难度等级（{request.difficulty}）
   - options: 数组，仅选择题有此字段，每个选项包含option_label和option_content

请直接返回JSON数组，不要包含任何其他文字。'''
            
            batch_tasks.append((merged_prompt, f"合并({len(small_plans)}类型)", total_small))
        
        logger.info(f"AI出题: 共{len(batch_tasks)}个批处理任务, 预计{sum(t[2] for t in batch_tasks)}题")
        
        # 并行执行AI调用（最多3个并发）
        semaphore = asyncio.Semaphore(3)
        
        async def _limited_call(prompt, label, count):
            async with semaphore:
                if asyncio.get_event_loop().time() - ai_start_time > max_total_time:
                    logger.warning(f"AI出题 [{label}]: 总超时，跳过")
                    return []
                return await _ai_batch_call(prompt, label)
        
        # 启动所有并行任务
        tasks = [_limited_call(p, l, c) for p, l, c in batch_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"AI出题并行任务异常: {result}")
                continue
            if isinstance(result, list):
                ai_questions.extend(result)
        
        elapsed = asyncio.get_event_loop().time() - ai_start_time
        if elapsed > max_total_time:
            logger.warning(f"AI出题因超时提前结束，已生成 {len(ai_questions)} 题（目标 {request.count} 题），"
                          f"不足部分将用规则题补齐")
        logger.info(f"AI出题完成: {len(ai_questions)} 题, 耗时 {elapsed:.1f}s")

    # 5. 查询题库中已存在的题目内容，进行去重
    existing_contents = set()
    if request.subject_id:
        existing_questions = db.query(Question.content).filter(
            Question.subject_id == request.subject_id,
            Question.audit_status != "rejected"  # 不包括已驳回的题目
        ).all()
        existing_contents = {q.content for q in existing_questions}
        if existing_contents:
            logger.info(f"题库中已存在 {len(existing_contents)} 道题目，将进行去重")

    # 6. 合并结果并与题库去重
    # 策略：hybrid模式下，AI题优先，规则题补缺，同时剔除题库中已存在的题目
    final_questions = []

    if request.mode == "rule_only":
        final_questions = rule_questions
    else:  # hybrid
        # AI题优先，先去除AI题目之间的重复
        seen_contents = set()
        unique_ai_questions = []
        for q in ai_questions:
            content = q.get("content", "")
            if content and content not in seen_contents:
                seen_contents.add(content)
                unique_ai_questions.append(q)
        ai_questions = unique_ai_questions
        logger.info(f"AI题目去重：原始 {len(unique_ai_questions) if 'unique_ai_questions' in dir() else len(ai_questions)} 道，去重后 {len(ai_questions)} 道")

        final_questions = ai_questions[:]
        # 不足部分用规则题补齐
        if len(final_questions) < request.count:
            shortage = request.count - len(final_questions)
            # 去重：避免AI和规则出了同样的题
            used_contents = {q.get("content", "") for q in final_questions}
            for rq in rule_questions:
                if shortage <= 0:
                    break
                if rq.get("content", "") not in used_contents:
                    final_questions.append(rq)
                    used_contents.add(rq.get("content", ""))
                    shortage -= 1

    # 与题库已有的题目进行去重
    original_count = len(final_questions)
    final_questions = [q for q in final_questions if q.get("content", "") not in existing_contents]
    removed_count = original_count - len(final_questions)

    if removed_count > 0:
        logger.info(f"去重完成：剔除 {removed_count} 道已存在于题库的题目，剩余 {len(final_questions)} 道")

    # 如果去重后数量不足，用规则题继续补齐
    if request.mode == "hybrid" and len(final_questions) < request.count:
        shortage = request.count - len(final_questions)
        used_contents = {q.get("content", "") for q in final_questions}
        for rq in rule_questions:
            if shortage <= 0:
                break
            if rq.get("content", "") not in used_contents and rq.get("content", "") not in existing_contents:
                final_questions.append(rq)
                used_contents.add(rq.get("content", ""))
                shortage -= 1

    # 截断到请求的题数
    final_questions = final_questions[:request.count]

    # 计算截断后实际各类型题数
    actual_rule_count = len([q for q in final_questions if q in rule_questions])
    actual_ai_count = len([q for q in final_questions if q in ai_questions])

    logger.info(f"混合出题完成: 最终 {len(final_questions)} 题 "
                f"(规则={actual_rule_count}, "
                f"AI={actual_ai_count})")

    return HybridGenerateResponse(
        questions=final_questions,
        count=len(final_questions),
        generated_by=f"Hybrid({request.mode})",
        plan_summary=plan_summary,
        rule_questions=actual_rule_count,
        ai_questions=actual_ai_count,
    )


# ──────────────────────────────────────────────
# 异步出题接口（前端轮询，解决"一直计算中"问题）
# ──────────────────────────────────────────────

class AsyncGenerateRequest(BaseModel):
    """异步出题请求（参数同 HybridGenerateRequest）"""
    subject_id: int
    subject_name: str
    chapter_ids: List[int] = []
    chapter_names: List[str] = []
    question_types: List[str] = ["single_choice"]
    difficulty: int = 3
    count: int = 10
    knowledge_point_ids: List[int] = []
    mode: str = "hybrid"
    user_id: Optional[int] = None


class AsyncTaskResponse(BaseModel):
    """异步任务创建响应"""
    task_id: int
    status: str = "pending"
    message: str = "出题任务已创建"


class TaskProgressResponse(BaseModel):
    """任务进度查询响应"""
    task_id: int
    status: str  # pending / running / completed / failed
    progress: int  # 0-100
    mode: str = ""
    rule_questions: int = 0
    ai_questions: int = 0
    total_questions: int = 0
    error_message: str = ""
    questions: List[dict] = []  # completed 时返回题目


def _execute_generation_task(task_id: int, req_dict: dict):
    """在后台线程中执行出题任务（独立 Session）"""
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if not task:
            return
        
        # 更新状态为 running
        task.status = "running"
        task.progress = 5
        db.commit()
        
        request = HybridGenerateRequest(**req_dict)
        
        # 复用现有的混合出题逻辑，但在独立线程中执行
        # 1. 构建知识点信息列表
        task.progress = 10
        db.commit()
        
        kp_info_list = build_kp_info_list(db, request.knowledge_point_ids)
        if not kp_info_list:
            task.status = "failed"
            task.error_message = "未找到有效的知识点"
            task.progress = 0
            db.commit()
            return
        
        # 2. 生成出题计划
        task.progress = 15
        db.commit()
        
        plans = build_question_plans(kp_info_list, request.count, request.question_types)
        
        plan_summary = {
            "total_kps": len(kp_info_list),
            "type_distribution": {p.type_name: len(p.knowledge_points) for p in plans},
            "question_allocation": {p.type_name: p.total_count for p in plans},
        }
        
        # 3. 快速通道：规则出题
        rule_questions = []
        if request.mode in ("hybrid", "rule_only"):
            for plan in plans:
                rqs = rule_generate_questions(plan)
                rule_questions.extend(rqs)
            task.progress = 40 if request.mode == "rule_only" else 30
            db.commit()
        
        # 4. 深度通道：AI出题
        ai_questions = []
        if request.mode == "hybrid":
            import asyncio
            AI_BATCH_SIZE = 15
            max_total_time = min(30 + request.count * 2, 120)
            
            async def _run_ai_generation():
                nonlocal ai_questions
                
                async def _ai_batch_call(batch_prompt: str, batch_label: str) -> list:
                    try:
                        result_text = await _call_ai_with_retry(batch_prompt, max_tokens=8192)
                    except Exception as e:
                        logger.error(f"AI出题 [{batch_label}]: API调用异常: {e}")
                        return []
                    if result_text is None:
                        return []
                    questions_data = _try_parse_questions_json(result_text)
                    if not questions_data:
                        return []
                    processed = []
                    for q in questions_data:
                        processed.append({
                            "content": q.get("content", ""),
                            "answer": q.get("answer", ""),
                            "explanation": q.get("explanation", ""),
                            "question_type": q.get("question_type", "single_choice"),
                            "difficulty": q.get("difficulty", request.difficulty),
                            "subject_id": request.subject_id,
                            "options": q.get("options", []),
                        })
                    return processed
                
                big_plans = [p for p in plans if p.total_count > 3]
                small_plans = [p for p in plans if p.total_count <= 3]
                
                batch_tasks = []
                for plan in big_plans:
                    for batch_start in range(0, plan.total_count, AI_BATCH_SIZE):
                        batch_count = min(AI_BATCH_SIZE, plan.total_count - batch_start)
                        batch_num = batch_start // AI_BATCH_SIZE + 1
                        prompt = build_strategic_prompt(
                            plan=plan, subject_name=request.subject_name,
                            chapter_names=request.chapter_names, difficulty=request.difficulty,
                        )
                        batch_prompt = prompt.replace(
                            f"生成{plan.total_count}道题目", f"生成{batch_count}道题目"
                        )
                        batch_tasks.append((batch_prompt, f"{plan.type_name}-b{batch_num}", batch_count))
                
                # 小plan合并
                if small_plans:
                    merged_kps = []
                    merged_strategies = []
                    merged_mix = {}
                    for sp in small_plans:
                        merged_kps.extend(sp.knowledge_points)
                        merged_strategies.append(f"【{sp.type_name}】({sp.total_count}题): {sp.ai_strategy[:200]}")
                        for qt, ratio in sp.question_mix.items():
                            merged_mix[qt] = merged_mix.get(qt, 0) + sp.total_count * ratio
                    
                    total_small = sum(sp.total_count for sp in small_plans)
                    kp_texts = [kp.text for kp in merged_kps]
                    knowledge_content = "\n".join(kp_texts)
                    if len(knowledge_content) > 4000:
                        knowledge_content = knowledge_content[:4000] + "\n...(更多知识点已省略)"
                    
                    difficulty_label = {1: "简单", 2: "较简单", 3: "中等", 4: "较难", 5: "困难"}.get(request.difficulty, "中等")
                    type_name_map = {"single_choice": "单选题", "multiple_choice": "多选题", "true_false": "判断题", "essay": "问答题"}
                    mix_parts = [f"- {type_name_map.get(qt, qt)}：{max(1, round(total_small * r))}道" for qt, r in merged_mix.items()]
                    
                    merged_prompt = f'''你是一个专业的试题生成助手。请根据以下知识点和出题策略生成{total_small}道题目。

科目："{request.subject_name}"
章节：{"、".join(request.chapter_names) if request.chapter_names else "全章节"}
难度：{difficulty_label}（1-5级）

【多类型知识点混合出题】
需要同时覆盖以下{len(small_plans)}种知识点类型：
{chr(10).join(merged_strategies)}

【知识点参考内容】
---
{knowledge_content}
---

【题型分配】
{chr(10).join(mix_parts)}

【出题要求】
1. 按照上述出题策略和题型分配来生成题目
2. 题目不要照搬原文表述——要改写、情景化、转换视角
3. 每道题目必须包含：题目内容、正确答案、详细解析
4. 选择题必须提供4个选项（A/B/C/D），多选题正确答案2-3个
5. 判断题答案为"true"或"false"
6. 干扰选项要合理
7. 返回JSON数组格式，每道题目包含以下字段：
   - question_type: 题型（single_choice/multiple_choice/true_false/essay）
   - content: 题目内容
   - answer: 正确答案
   - explanation: 详细解析
   - difficulty: 难度等级（{request.difficulty}）
   - options: 数组，仅选择题有此字段

请直接返回JSON数组，不要包含任何其他文字。'''
                    batch_tasks.append((merged_prompt, f"合并({len(small_plans)}类型)", total_small))
                
                # 更新进度
                task.progress = 40
                db.commit()
                
                # 并行执行
                semaphore = asyncio.Semaphore(3)
                ai_start_time = asyncio.get_event_loop().time()
                
                async def _limited_call(prompt, label, count):
                    async with semaphore:
                        if asyncio.get_event_loop().time() - ai_start_time > max_total_time:
                            return []
                        return await _ai_batch_call(prompt, label)
                
                tasks = [_limited_call(p, l, c) for p, l, c in batch_tasks]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"AI出题并行任务异常: {result}")
                        continue
                    if isinstance(result, list):
                        ai_questions.extend(result)

            # 在新事件循环中运行异步代码，使用 asyncio.run() 更安全
            asyncio.run(_run_ai_generation())

            # AI 题目校验：剔除答非所问的题目
            if ai_questions:
                # 构建完整知识点内容用于校验
                all_kp_texts = []
                for plan in plans:
                    for kp in plan.knowledge_points:
                        if kp.text:
                            all_kp_texts.append(kp.text)
                verify_knowledge = "\n".join(all_kp_texts)
                if len(verify_knowledge) > 4000:
                    verify_knowledge = verify_knowledge[:4000] + "\n...(更多知识点已省略)"

                async def _run_verification():
                    logger.info(f"[异步任务{task_id}] AI出题完成，开始校验 {len(ai_questions)} 道题目...")
                    # 逐个题型校验
                    questions_by_type: Dict[str, List[dict]] = {}
                    for q in ai_questions:
                        qt = q.get("question_type", "single_choice")
                        if qt not in questions_by_type:
                            questions_by_type[qt] = []
                        questions_by_type[qt].append(q)

                    verified_ai_questions = []
                    for qt, q_list in questions_by_type.items():
                        verified = await _verify_questions(q_list, verify_knowledge, qt)
                        verified_ai_questions.extend(verified)
                    return verified_ai_questions

                verified_ai_questions = asyncio.run(_run_verification())
                original_count = len(ai_questions)
                ai_questions = verified_ai_questions
                removed = original_count - len(ai_questions)
                if removed > 0:
                    logger.info(f"[异步任务{task_id}] 校验剔除 {removed} 道无效题目，剩余 {len(ai_questions)} 道")

        # 5. 合并结果
        task.progress = 80
        db.commit()

        # 6. 查询题库中已存在的题目内容，进行去重
        existing_contents = set()
        if request.subject_id:
            existing_questions = db.query(Question.content).filter(
                Question.subject_id == request.subject_id,
                Question.audit_status != "rejected"
            ).all()
            existing_contents = {q.content for q in existing_questions}
            if existing_contents:
                logger.info(f"[异步任务{task_id}] 题库中已存在 {len(existing_contents)} 道题目，将进行去重")

        final_questions = []
        if request.mode == "rule_only":
            final_questions = rule_questions
        else:
            # 先去除AI题目之间的重复
            seen_contents = set()
            unique_ai_questions = []
            for q in ai_questions:
                content = q.get("content", "")
                if content and content not in seen_contents:
                    seen_contents.add(content)
                    unique_ai_questions.append(q)
            ai_questions = unique_ai_questions

            final_questions = ai_questions[:]
            if len(final_questions) < request.count:
                shortage = request.count - len(final_questions)
                used_contents = {q.get("content", "") for q in final_questions}
                for rq in rule_questions:
                    if shortage <= 0:
                        break
                    if rq.get("content", "") not in used_contents:
                        final_questions.append(rq)
                        used_contents.add(rq.get("content", ""))
                        shortage -= 1

        # 与题库已有的题目进行去重
        original_count = len(final_questions)
        final_questions = [q for q in final_questions if q.get("content", "") not in existing_contents]
        removed_count = original_count - len(final_questions)
        if removed_count > 0:
            logger.info(f"[异步任务{task_id}] 去重完成：剔除 {removed_count} 道已存在于题库的题目，剩余 {len(final_questions)} 道")

        # 如果去重后数量不足，用规则题继续补齐
        if request.mode == "hybrid" and len(final_questions) < request.count:
            shortage = request.count - len(final_questions)
            used_contents = {q.get("content", "") for q in final_questions}
            for rq in rule_questions:
                if shortage <= 0:
                    break
                if rq.get("content", "") not in used_contents and rq.get("content", "") not in existing_contents:
                    final_questions.append(rq)
                    used_contents.add(rq.get("content", ""))
                    shortage -= 1

        final_questions = final_questions[:request.count]

        # 计算截断后实际各类型题数
        actual_rule_count = len([q for q in final_questions if q in rule_questions])
        actual_ai_count = len([q for q in final_questions if q in ai_questions])

        # 7. 保存结果
        task.status = "completed"
        task.progress = 100
        task.rule_questions = actual_rule_count
        task.ai_questions = actual_ai_count
        task.result = {
            "questions": final_questions,
            "count": len(final_questions),
            "generated_by": f"Hybrid({request.mode})",
            "plan_summary": plan_summary,
            "rule_questions": actual_rule_count,
            "ai_questions": actual_ai_count,
        }
        db.commit()
        
        logger.info(f"异步出题任务 {task_id} 完成: {len(final_questions)} 题")
    
    except Exception as e:
        logger.error(f"异步出题任务 {task_id} 失败: {e}", exc_info=True)
        try:
            task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.progress = 0
                db.commit()
        except:
            pass
    finally:
        db.close()


@router.post("/hybrid-generate-async", response_model=AsyncTaskResponse)
async def hybrid_generate_async(
    request: AsyncGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """异步出题：立即返回任务ID，后台执行，前端轮询进度
    
    解决"前端一直计算中"的问题：
    - 规则出题：1-2秒完成，前端轮询1-2次即可拿到结果
    - AI出题：30-120秒完成，前端持续轮询获取进度
    - 即使后端卡住，前端也不会白屏等待
    """
    # 1. 创建任务记录
    task = GenerationTask(
        user_id=request.user_id,
        status="pending",
        progress=0,
        mode=request.mode,
        params=request.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 2. 在后台线程中执行（不用 BackgroundTasks 因为需要独立 Session）
    req_dict = request.model_dump()
    thread = threading.Thread(
        target=_execute_generation_task,
        args=(task.id, req_dict),
        daemon=True,
    )
    thread.start()
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="pending",
        message=f"出题任务已创建（模式: {request.mode}）",
    )


@router.get("/task/{task_id}/progress", response_model=TaskProgressResponse)
async def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
):
    """查询出题任务进度"""
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    questions = []
    if task.status == "completed" and task.result:
        questions = task.result.get("questions", [])
    
    return TaskProgressResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        mode=task.mode,
        rule_questions=task.rule_questions,
        ai_questions=task.ai_questions,
        total_questions=len(questions),
        error_message=task.error_message or "",
        questions=questions,
    )


@router.get("/tasks", response_model=List[dict])
async def list_tasks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """列出最近的出题任务"""
    tasks = db.query(GenerationTask).order_by(
        GenerationTask.id.desc()
    ).offset(offset).limit(limit).all()
    
    return [{
        "id": t.id,
        "status": t.status,
        "progress": t.progress,
        "mode": t.mode,
        "rule_questions": t.rule_questions,
        "ai_questions": t.ai_questions,
        "error_message": t.error_message,
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
    } for t in tasks]