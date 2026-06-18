"""
广告法合规审查 Agent — 评测数据管线

包含:
  1. 30 题 Agent 评测 (端到端审查能力)
  2. 15 题 RAG 评测 (检索质量)
  3. 评测脚本 (自动跑分)
"""
import json
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 评测数据结构
# ============================================================

@dataclass
class AgentEvalCase:
    """Agent 评测题。"""
    id: str
    category: str               # 评测类别
    input_text: str             # 待审查的广告文案
    industry: str = ""          # 所属行业
    expected_issues: list[str] = field(default_factory=list)  # 期望发现的问题列表
    expected_risk_level: str = "medium"  # low / medium / high / critical
    expected_suggestions: list[str] = field(default_factory=list)  # 期望的修改建议
    reference_laws: list[str] = field(default_factory=list)  # 应引用的法条
    reference_cases: list[str] = field(default_factory=list)  # 应引用的案例
    difficulty: str = "medium"  # easy / medium / hard


@dataclass
class RAGEvalCase:
    """RAG 评测题。"""
    id: str
    query: str                  # 检索查询
    expected_doc_keys: list[str] = field(default_factory=list)  # 期望命中的文档 key
    expected_sources: list[str] = field(default_factory=list)  # 期望命中的子库
    min_recall: float = 0.6     # 最低召回率
    min_precision: float = 0.5  # 最低精确率


# ============================================================
# 30 题 Agent 评测数据
# ============================================================

def build_agent_eval_dataset() -> list[AgentEvalCase]:
    """构建 30 题 Agent 评测集。"""
    cases = [
        # ----- 极限用语 (10 题) -----
        AgentEvalCase(
            id="agent_01",
            category="极限用语",
            input_text="我们的产品是全网销量第一，行业领导品牌，品质绝对有保障！",
            industry="电商",
            expected_issues=["极限用语: 全网销量第一", "极限用语: 行业领导品牌", "绝对化用语: 绝对"],
            expected_risk_level="high",
            expected_suggestions=["删除'全网销量第一'", "删除'行业领导品牌'", "将'绝对'改为'非常'"],
            reference_laws=["第九条第(三)项", "第五十七条"],
            reference_cases=["案例 1"],
        ),
        AgentEvalCase(
            id="agent_02",
            category="极限用语",
            input_text="国家级品质标准，全球第一安全，让您买得放心！",
            industry="汽车",
            expected_issues=["极限用语: 国家级", "极限用语: 全球第一"],
            expected_risk_level="high",
            expected_suggestions=["删除'国家级'", "删除'全球第一'"],
            reference_laws=["第九条第(三)项"],
            reference_cases=["案例 8"],
        ),
        AgentEvalCase(
            id="agent_03",
            category="极限用语",
            input_text="史上最低价！全网最便宜！错过不再，仅限今天！",
            industry="电商",
            expected_issues=["极限用语: 史上最低价", "极限用语: 全网最便宜", "虚假紧迫感: 错过不再", "虚假紧迫感: 仅限今天"],
            expected_risk_level="high",
            expected_suggestions=["改为'限时优惠'", "删除'最便宜'表述", "标注具体活动日期"],
            reference_laws=["第九条第(三)项"],
        ),
        AgentEvalCase(
            id="agent_04",
            category="极限用语",
            input_text="顶级私人教练，王牌课程，健身行业的天花板！",
            industry="健身",
            expected_issues=["极限用语: 顶级", "极限用语: 王牌", "极限用语: 天花板"],
            expected_risk_level="high",
            expected_suggestions=["改为'高端私人教练'", "改为'精选课程'"],
            reference_laws=["第九条第(三)项"],
            reference_cases=["案例 10"],
        ),
        AgentEvalCase(
            id="agent_05",
            category="极限用语",
            input_text="考研首选机构，业内唯一全名师授课，100%通过率！",
            industry="教育培训",
            expected_issues=["极限用语: 首选", "极限用语: 唯一", "极限用语: 100%", "虚假宣传: 100%通过率"],
            expected_risk_level="critical",
            expected_suggestions=["删除'首选'", "删除'唯一'", "删除'100%通过率'"],
            reference_laws=["第九条第(三)项", "第二十四条"],
            reference_cases=["案例 4", "案例 18"],
        ),
        AgentEvalCase(
            id="agent_06",
            category="极限用语",
            input_text="绝版地段，顶级豪宅，至尊享受，最后10套！",
            industry="房地产",
            expected_issues=["极限用语: 绝版", "极限用语: 顶级", "极限用语: 至尊", "虚假紧迫感: 最后10套"],
            expected_risk_level="high",
            expected_suggestions=["删除'绝版地段'", "改为'高端豪宅'", "删除'至尊享受'"],
            reference_laws=["第九条第(三)项", "第二十六条"],
            reference_cases=["案例 5"],
        ),
        AgentEvalCase(
            id="agent_07",
            category="极限用语",
            input_text="全网独家首发，全球限量，独一无二的收藏价值！",
            industry="电商",
            expected_issues=["极限用语: 全网独家", "极限用语: 全球限量", "极限用语: 独一无二"],
            expected_risk_level="high",
            reference_laws=["第九条第(三)项"],
            reference_cases=["案例 14"],
        ),
        AgentEvalCase(
            id="agent_08",
            category="极限用语",
            input_text="行业唯一通过国际认证的品牌，无与伦比的品质！",
            industry="家电",
            expected_issues=["极限用语: 行业唯一", "极限用语: 无与伦比", "虚假宣传: 虚假认证"],
            expected_risk_level="high",
            reference_laws=["第九条第(三)项", "第十一条", "第二十八条"],
            reference_cases=["案例 9"],
        ),
        AgentEvalCase(
            id="agent_09",
            category="极限用语",
            input_text="我们的装修服务是全市唯一零投诉，行业第一品牌！",
            industry="装修",
            expected_issues=["极限用语: 唯一零投诉", "极限用语: 行业第一"],
            expected_risk_level="high",
            reference_laws=["第九条第(三)项"],
            reference_cases=["案例 15"],
        ),
        AgentEvalCase(
            id="agent_10",
            category="极限用语",
            input_text="国酒品质，顶级酿造工艺，千年传承的经典口感！",
            industry="酒类",
            expected_issues=["极限用语: 国酒", "极限用语: 顶级"],
            expected_risk_level="high",
            reference_laws=["第九条第(三)项", "第二十三条"],
            reference_cases=["案例 13"],
        ),

        # ----- 虚假宣传 (10 题) -----
        AgentEvalCase(
            id="agent_11",
            category="虚假宣传",
            input_text="7天瘦10斤，永不反弹，无效退款！",
            industry="保健品",
            expected_issues=["虚假宣传: 虚假功效承诺", "极限用语: 永不反弹", "虚假承诺: 无效退款"],
            expected_risk_level="critical",
            expected_suggestions=["删除减肥效果承诺", "删除'永不反弹'"],
            reference_laws=["第四条", "第二十八条"],
            reference_cases=["案例 16"],
        ),
        AgentEvalCase(
            id="agent_12",
            category="虚假宣传",
            input_text="这款面霜能根治痘痘，永久美白，100%有效！",
            industry="化妆品",
            expected_issues=["虚假宣传: 化妆品宣称治疗效果", "极限用语: 永久", "极限用语: 100%"],
            expected_risk_level="critical",
            reference_laws=["第四条", "第十七条", "第二十八条"],
            reference_cases=["案例 17"],
        ),
        AgentEvalCase(
            id="agent_13",
            category="虚假宣传",
            input_text="年化收益12%，保本保息，稳赚不赔的投资首选！",
            industry="金融",
            expected_issues=["违规承诺: 保本保息", "违规承诺: 稳赚不赔", "虚假宣传: 承诺收益", "极限用语: 首选"],
            expected_risk_level="critical",
            reference_laws=["第二十五条"],
            reference_cases=["案例 19"],
        ),
        AgentEvalCase(
            id="agent_14",
            category="虚假宣传",
            input_text="这款酵素能排毒养颜，治疗便秘，增强免疫力！",
            industry="食品",
            expected_issues=["虚假宣传: 食品宣称治疗功能", "违规: 普通食品暗示保健功能"],
            expected_risk_level="high",
            reference_laws=["第十七条", "第十八条"],
            reference_cases=["案例 20", "案例 24"],
        ),
        AgentEvalCase(
            id="agent_15",
            category="虚假宣传",
            input_text="累计销量10万+，好评率99.9%，1亿用户都在用！",
            industry="互联网",
            expected_issues=["虚假宣传: 虚假销量数据", "虚假宣传: 虚假用户数"],
            expected_risk_level="high",
            reference_laws=["第四条", "第二十八条"],
            reference_cases=["案例 21", "案例 28"],
        ),
        AgentEvalCase(
            id="agent_16",
            category="虚假宣传",
            input_text="经临床验证，治愈率99%，无任何副作用，患者好评如潮！",
            industry="医疗",
            expected_issues=["虚假宣传: 虚假治愈率", "虚假宣传: 无副作用", "违规: 使用患者形象"],
            expected_risk_level="critical",
            reference_laws=["第十六条", "第二十八条"],
            reference_cases=["案例 22"],
        ),
        AgentEvalCase(
            id="agent_17",
            category="虚假宣传",
            input_text="名师押题，命中率90%，签约保过，不过全额退款！",
            industry="教育培训",
            expected_issues=["虚假宣传: 虚假押题命中率", "违规承诺: 保过", "违规: 暗示与考试机构有关联"],
            expected_risk_level="critical",
            reference_laws=["第二十四条", "第二十八条"],
            reference_cases=["案例 18"],
        ),
        AgentEvalCase(
            id="agent_18",
            category="虚假宣传",
            input_text="纯天然植物配方，零化学成分，安全无毒，FDA认证！",
            industry="日化",
            expected_issues=["虚假宣传: 虚假成分宣称", "虚假宣传: 虚假认证"],
            expected_risk_level="high",
            reference_laws=["第四条", "第十一条", "第二十八条"],
            reference_cases=["案例 27"],
        ),
        AgentEvalCase(
            id="agent_19",
            category="虚假宣传",
            input_text="买到就是赚到，每年稳涨20%，5年回本的投资好房！",
            industry="房地产",
            expected_issues=["违规承诺: 升值回报", "违规承诺: 投资回报率"],
            expected_risk_level="high",
            reference_laws=["第二十六条"],
            reference_cases=["案例 23"],
        ),
        AgentEvalCase(
            id="agent_20",
            category="虚假宣传",
            input_text="续航1000公里，百公里油耗仅2L，远超同级对手！",
            industry="新能源汽车",
            expected_issues=["虚假宣传: 虚假续航", "虚假宣传: 虚假油耗", "对比贬低: 远超同级"],
            expected_risk_level="high",
            reference_laws=["第四条", "第十三条", "第二十八条"],
            reference_cases=["案例 44"],
        ),

        # ----- 行业特殊规则 (5 题) -----
        AgentEvalCase(
            id="agent_21",
            category="行业特殊规则",
            input_text="这款白酒喝了活血化瘀，消除紧张焦虑，让您身心放松！",
            industry="酒类",
            expected_issues=["违规: 酒类暗示保健功能", "违规: 暗示消除焦虑"],
            expected_risk_level="high",
            reference_laws=["第二十三条"],
            reference_cases=["案例 35"],
        ),
        AgentEvalCase(
            id="agent_22",
            category="行业特殊规则",
            input_text="别让孩子输在起跑线！现在不学就晚了，别人家孩子都在学！",
            industry="教育培训",
            expected_issues=["违规: 制造教育焦虑", "违规: 焦虑营销"],
            expected_risk_level="medium",
            reference_laws=["第九条第(七)项"],
            reference_cases=["案例 33"],
        ),
        AgentEvalCase(
            id="agent_23",
            category="行业特殊规则",
            input_text="这款处方药疗效显著，请在各大药店购买，全国有售！",
            industry="医药",
            expected_issues=["违法: 处方药在大众媒体做广告"],
            expected_risk_level="critical",
            reference_laws=["第十五条"],
            reference_cases=["案例 36"],
        ),
        AgentEvalCase(
            id="agent_24",
            category="行业特殊规则",
            input_text="风水宝地，旺财旺丁，龙脉所在，置业首选！",
            industry="房地产",
            expected_issues=["违规: 封建迷信内容", "极限用语: 首选"],
            expected_risk_level="high",
            reference_laws=["第九条第(七)项", "第二十六条"],
            reference_cases=["案例 39"],
        ),
        AgentEvalCase(
            id="agent_25",
            category="行业特殊规则",
            input_text="这款保健品能治疗糖尿病，替代药物，药到病除！",
            industry="保健品",
            expected_issues=["虚假宣传: 保健品宣称治疗功能", "违规: 替代药物"],
            expected_risk_level="critical",
            reference_laws=["第十七条", "第十八条"],
            reference_cases=["案例 24"],
        ),

        # ----- 新业态 (3 题) -----
        AgentEvalCase(
            id="agent_26",
            category="新业态违规",
            input_text="家人们！全网最低价！史上最强秒杀！秒杀一切竞品！错过再等一年！",
            industry="直播电商",
            expected_issues=["极限用语: 全网最低", "极限用语: 史上最强", "对比贬低: 秒杀一切", "虚假紧迫感: 错过再等一年"],
            expected_risk_level="high",
            reference_laws=["第九条第(三)项"],
            reference_cases=["案例 37"],
        ),
        AgentEvalCase(
            id="agent_27",
            category="新业态违规",
            input_text="这款AI产品完全替代人工，100%准确率，零失误！",
            industry="科技/AI",
            expected_issues=["虚假宣传: 夸大AI能力", "极限用语: 100%", "极限用语: 零失误"],
            expected_risk_level="high",
            reference_laws=["第四条", "第二十八条"],
            reference_cases=["案例 41"],
        ),
        AgentEvalCase(
            id="agent_28",
            category="新业态违规",
            input_text="【好物推荐】这款护肤品真的绝了！姐妹们冲！亲测有效！",
            industry="社交媒体",
            expected_issues=["违规: 未标注广告", "违规: 使用个人推荐"],
            expected_risk_level="medium",
            reference_laws=["第十四条"],
            reference_cases=["案例 43"],
        ),

        # ----- 合规文案 (2 题，应判定为合规) -----
        AgentEvalCase(
            id="agent_29",
            category="合规文案",
            input_text="本品选用优质原料，口感醇厚，适合日常饮用。请适量饮用。",
            industry="食品",
            expected_issues=[],
            expected_risk_level="low",
            expected_suggestions=[],
            reference_laws=[],
        ),
        AgentEvalCase(
            id="agent_30",
            category="合规文案",
            input_text="含有烟酰胺成分，有助于提亮肤色。请按说明使用。",
            industry="化妆品",
            expected_issues=[],
            expected_risk_level="low",
            expected_suggestions=[],
            reference_laws=[],
        ),
    ]
    return cases


# ============================================================
# 15 题 RAG 评测数据
# ============================================================

def build_rag_eval_dataset() -> list[RAGEvalCase]:
    """构建 15 题 RAG 评测集。"""
    cases = [
        RAGEvalCase(
            id="rag_01",
            query="广告中使用'最'字系列用语是否违法？",
            expected_doc_keys=["law:第九条"],
            expected_sources=["ad_law"],
            min_recall=0.8,
        ),
        RAGEvalCase(
            id="rag_02",
            query="虚假广告的定义和处罚标准是什么？",
            expected_doc_keys=["law:第四条", "law:第二十八条", "law:第五十五条"],
            expected_sources=["ad_law"],
            min_recall=0.7,
        ),
        RAGEvalCase(
            id="rag_03",
            query="食品广告有哪些特殊限制？",
            expected_doc_keys=["law:第十七条", "law:第十八条", "industry:food"],
            expected_sources=["ad_law", "ad_industry"],
            min_recall=0.6,
        ),
        RAGEvalCase(
            id="rag_04",
            query="化妆品广告使用'永久美白'会怎么处罚？",
            expected_doc_keys=["case:17"],
            expected_sources=["ad_case"],
            min_recall=0.8,
        ),
        RAGEvalCase(
            id="rag_05",
            query="教育培训行业广告有哪些禁区？",
            expected_doc_keys=["industry:education"],
            expected_sources=["ad_industry"],
            min_recall=0.7,
        ),
        RAGEvalCase(
            id="rag_06",
            query="金融理财产品广告不得有哪些内容？",
            expected_doc_keys=["law:第二十五条", "industry:finance"],
            expected_sources=["ad_law", "ad_industry"],
            min_recall=0.6,
        ),
        RAGEvalCase(
            id="rag_07",
            query="烟草广告有什么规定？",
            expected_doc_keys=["law:第二十二条"],
            expected_sources=["ad_law"],
            min_recall=0.8,
        ),
        RAGEvalCase(
            id="rag_08",
            query="使用国家机关工作人员形象做广告会受到什么处罚？",
            expected_doc_keys=["case:38"],
            expected_sources=["ad_case"],
            min_recall=0.7,
        ),
        RAGEvalCase(
            id="rag_09",
            query="房地产广告不得包含哪些内容？",
            expected_doc_keys=["law:第二十六条", "industry:real_estate"],
            expected_sources=["ad_law", "ad_industry"],
            min_recall=0.6,
        ),
        RAGEvalCase(
            id="rag_10",
            query="直播带货使用极限用语的处罚案例有哪些？",
            expected_doc_keys=["case:37"],
            expected_sources=["ad_case"],
            min_recall=0.7,
        ),
        RAGEvalCase(
            id="rag_11",
            query="酒类广告的特殊规定是什么？",
            expected_doc_keys=["law:第二十三条", "industry:alcohol"],
            expected_sources=["ad_law", "ad_industry"],
            min_recall=0.6,
        ),
        RAGEvalCase(
            id="rag_12",
            query="'全网销量第一'这类用语违反广告法哪一条？",
            expected_doc_keys=["law:第九条"],
            expected_sources=["ad_law"],
            min_recall=0.8,
        ),
        RAGEvalCase(
            id="rag_13",
            query="互联网广告管理办法对广告可识别性有什么要求？",
            expected_doc_keys=["law:internet:第八条"],
            expected_sources=["ad_law"],
            min_recall=0.7,
        ),
        RAGEvalCase(
            id="rag_14",
            query="使用焦虑营销话术有什么法律后果？",
            expected_doc_keys=["case:33", "industry:education"],
            expected_sources=["ad_case", "ad_industry"],
            min_recall=0.5,
        ),
        RAGEvalCase(
            id="rag_15",
            query="保本保息的理财广告违反了什么法规？",
            expected_doc_keys=["law:第二十五条", "case:19", "industry:finance"],
            expected_sources=["ad_law", "ad_case", "ad_industry"],
            min_recall=0.5,
        ),
    ]
    return cases


# ============================================================
# 评测脚本
# ============================================================

@dataclass
class EvalScore:
    """单题评测得分。"""
    id: str
    category: str
    score: float           # 0-1
    details: dict = field(default_factory=dict)
    passed: bool = False


@dataclass
class EvalReport:
    """评测报告。"""
    eval_type: str          # "agent" / "rag"
    total_cases: int
    passed: int
    failed: int
    avg_score: float
    scores: list[EvalScore] = field(default_factory=list)
    category_scores: dict = field(default_factory=dict)
    timestamp: str = ""


class AgentEvaluator:
    """Agent 端到端评测器。"""

    def __init__(self, agent_fn, threshold: float = 0.6):
        """
        Args:
            agent_fn: callable(input_text) -> dict
                返回值应包含:
                  - issues: list[str]   发现的问题
                  - risk_level: str     风险等级
                  - suggestions: list[str]  修改建议
                  - references: list[str]   引用的法条/案例
            threshold: 及格线
        """
        self.agent_fn = agent_fn
        self.threshold = threshold

    def evaluate_single(self, case: AgentEvalCase) -> EvalScore:
        """评测单个 case。"""
        try:
            result = self.agent_fn(case.input_text)
        except Exception as e:
            return EvalScore(
                id=case.id,
                category=case.category,
                score=0.0,
                details={"error": str(e)},
                passed=False,
            )

        scores = {}

        # 1. 问题发现率 (Recall of issues)
        if case.expected_issues:
            found = sum(
                1 for issue in case.expected_issues
                if any(issue.split(":")[0] in r for r in result.get("issues", []))
            )
            scores["issue_recall"] = found / len(case.expected_issues)
        else:
            # 合规文案: 期望无问题，正确判断为合规给满分
            scores["issue_recall"] = 1.0 if not result.get("issues") else 0.0

        # 2. 风险等级准确度
        risk_map = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        expected_risk = risk_map.get(case.expected_risk_level, 1)
        actual_risk = risk_map.get(result.get("risk_level", "medium"), 1)
        risk_diff = abs(expected_risk - actual_risk)
        scores["risk_accuracy"] = max(0, 1.0 - risk_diff * 0.33)

        # 3. 法条引用准确度
        if case.reference_laws:
            ref_text = " ".join(result.get("references", []))
            cited = sum(1 for law in case.reference_laws if law in ref_text)
            scores["law_citation"] = cited / len(case.reference_laws)
        else:
            scores["law_citation"] = 1.0

        # 4. 修改建议质量 (关键词匹配)
        if case.expected_suggestions:
            sugg_text = " ".join(result.get("suggestions", []))
            sugg_hits = sum(
                1 for s in case.expected_suggestions
                if any(kw in sugg_text for kw in s.split(":")[-1].split("、"))
            )
            scores["suggestion_quality"] = sugg_hits / len(case.expected_suggestions)
        else:
            scores["suggestion_quality"] = 1.0

        # 加权总分
        weights = {
            "issue_recall": 0.35,
            "risk_accuracy": 0.25,
            "law_citation": 0.25,
            "suggestion_quality": 0.15,
        }
        total = sum(scores[k] * weights[k] for k in scores)

        return EvalScore(
            id=case.id,
            category=case.category,
            score=round(total, 3),
            details=scores,
            passed=total >= self.threshold,
        )

    def evaluate_all(self, cases: list[AgentEvalCase] = None) -> EvalReport:
        """跑完全部评测。"""
        if cases is None:
            cases = build_agent_eval_dataset()

        scores = [self.evaluate_single(c) for c in cases]

        passed = sum(1 for s in scores if s.passed)
        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0

        # 分类统计
        cat_scores = {}
        for s in scores:
            if s.category not in cat_scores:
                cat_scores[s.category] = []
            cat_scores[s.category].append(s.score)
        category_avgs = {
            cat: round(sum(ss) / len(ss), 3)
            for cat, ss in cat_scores.items()
        }

        return EvalReport(
            eval_type="agent",
            total_cases=len(cases),
            passed=passed,
            failed=len(cases) - passed,
            avg_score=round(avg_score, 3),
            scores=scores,
            category_scores=category_avgs,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )


class RAGEvaluator:
    """RAG 检索质量评测器。"""

    def __init__(self, retrieve_fn, threshold: float = 0.5):
        """
        Args:
            retrieve_fn: callable(query) -> list[dict]
                返回值每个元素应包含 key, source
            threshold: 及格线
        """
        self.retrieve_fn = retrieve_fn
        self.threshold = threshold

    def evaluate_single(self, case: RAGEvalCase) -> EvalScore:
        """评测单个 case。"""
        try:
            results = self.retrieve_fn(case.query)
        except Exception as e:
            return EvalScore(
                id=case.id,
                category="RAG",
                score=0.0,
                details={"error": str(e)},
                passed=False,
            )

        result_keys = [r.get("key", "") for r in results]
        result_sources = [r.get("source", "") for r in results]

        scores = {}

        # 1. Key 召回率 (Recall@K)
        if case.expected_doc_keys:
            key_hits = sum(1 for k in case.expected_doc_keys if k in result_keys)
            scores["key_recall"] = key_hits / len(case.expected_doc_keys)
        else:
            scores["key_recall"] = 1.0

        # 2. Source 召回率
        if case.expected_sources:
            source_hits = sum(1 for s in case.expected_sources if s in result_sources)
            scores["source_recall"] = source_hits / len(case.expected_sources)
        else:
            scores["source_recall"] = 1.0

        # 3. 精确率 (命中的结果中有多少是相关的)
        if case.expected_doc_keys and results:
            relevant_in_results = sum(1 for k in result_keys if k in case.expected_doc_keys)
            scores["precision"] = relevant_in_results / len(results)
        else:
            scores["precision"] = 1.0

        # 加权总分
        weights = {
            "key_recall": 0.45,
            "source_recall": 0.30,
            "precision": 0.25,
        }
        total = sum(scores[k] * weights[k] for k in scores)

        return EvalScore(
            id=case.id,
            category="RAG",
            score=round(total, 3),
            details={
                "key_recall": scores["key_recall"],
                "source_recall": scores["source_recall"],
                "precision": scores["precision"],
                "retrieved_keys": result_keys[:10],
            },
            passed=total >= self.threshold,
        )

    def evaluate_all(self, cases: list[RAGEvalCase] = None) -> EvalReport:
        """跑完全部 RAG 评测。"""
        if cases is None:
            cases = build_rag_eval_dataset()

        scores = [self.evaluate_single(c) for c in cases]

        passed = sum(1 for s in scores if s.passed)
        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0

        return EvalReport(
            eval_type="rag",
            total_cases=len(cases),
            passed=passed,
            failed=len(cases) - passed,
            avg_score=round(avg_score, 3),
            scores=scores,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )


# ============================================================
# 报告输出
# ============================================================

def format_eval_report(report: EvalReport) -> str:
    """格式化评测报告为可读文本。"""
    lines = [
        f"{'='*60}",
        f"  {report.eval_type.upper()} 评测报告",
        f"  时间: {report.timestamp}",
        f"{'='*60}",
        f"",
        f"  总题数: {report.total_cases}",
        f"  通过: {report.passed}",
        f"  失败: {report.failed}",
        f"  平均分: {report.avg_score:.3f}",
        f"  通过率: {report.passed/report.total_cases*100:.1f}%",
        f"",
    ]

    if report.category_scores:
        lines.append("  分类得分:")
        for cat, score in report.category_scores.items():
            lines.append(f"    {cat}: {score:.3f}")
        lines.append("")

    lines.append("  详细得分:")
    for s in report.scores:
        status = "PASS" if s.passed else "FAIL"
        lines.append(f"    [{status}] {s.id} ({s.category}): {s.score:.3f}")
        if s.details:
            for k, v in s.details.items():
                if isinstance(v, float):
                    lines.append(f"           {k}: {v:.3f}")
                elif isinstance(v, list) and len(v) <= 5:
                    lines.append(f"           {k}: {v}")

    return "\n".join(lines)


def save_eval_report(report: EvalReport, output_path: Path):
    """保存评测报告为 JSON。"""
    data = {
        "eval_type": report.eval_type,
        "timestamp": report.timestamp,
        "total_cases": report.total_cases,
        "passed": report.passed,
        "failed": report.failed,
        "avg_score": report.avg_score,
        "category_scores": report.category_scores,
        "scores": [
            {
                "id": s.id,
                "category": s.category,
                "score": s.score,
                "passed": s.passed,
                "details": s.details,
            }
            for s in report.scores
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
