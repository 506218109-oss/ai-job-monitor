#!/usr/bin/env python3
"""
Seed demo data with realistic AI non-dev job listings.
This fills the database with sample data so the dashboard can be explored
even before real scraping is set up.
"""

import sys
import os
import json
from datetime import date, datetime, timedelta
from random import randint, choice, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import SessionLocal
from app.models import Job, Company, Skill, JobSkill
from app.services.analysis_service import generate_snapshot
from app.analyzers.skill_extractor import extract_and_link_skills
from app.services.scraping_service import update_company_stats

DEMO_JOBS = [
    # (title, company, city, salary_min, salary_max, salary_months, job_type, exp, edu)
    ("大模型产品经理", "字节跳动", "北京", 35, 60, 15, "产品经理", "3-5年", "本科"),
    ("AI产品经理（大语言模型方向）", "字节跳动", "上海", 30, 55, 15, "产品经理", "3-5年", "本科"),
    ("高级AI产品经理", "阿里巴巴", "杭州", 35, 65, 16, "产品经理", "5-10年", "本科"),
    ("AI产品运营专家", "阿里巴巴", "北京", 25, 45, 15, "AI运营", "3-5年", "本科"),
    ("AIGC产品经理", "腾讯", "深圳", 30, 58, 16, "产品经理", "3-5年", "本科"),
    ("大模型产品运营", "腾讯", "北京", 25, 48, 14, "AI运营", "1-3年", "本科"),
    ("AI商业化产品经理", "百度", "北京", 28, 55, 15, "商业化/增长", "3-5年", "本科"),
    ("文心一言产品经理", "百度", "北京", 30, 60, 16, "产品经理", "5-10年", "本科"),
    ("AI策略产品经理", "美团", "北京", 25, 50, 15, "产品经理", "1-3年", "本科"),
    ("AI产品运营（智能助手方向）", "小米", "北京", 20, 40, 14, "AI运营", "1-3年", "本科"),
    ("提示词工程师", "字节跳动", "北京", 28, 55, 15, "提示词工程", "1-3年", "本科"),
    ("Prompt Engineer", "Minimax", "北京", 30, 60, 15, "提示词工程", "1-3年", "本科"),
    ("AI训练师（数据标注）", "百度", "北京", 15, 28, 14, "训练/标注", "不限", "大专"),
    ("数据标注项目经理", "数据堂", "北京", 18, 30, 13, "训练/标注", "1-3年", "本科"),
    ("AI产品经理（多模态）", "快手", "北京", 28, 55, 15, "产品经理", "3-5年", "本科"),
    ("AI增长产品经理", "小红书", "上海", 25, 50, 15, "商业化/增长", "3-5年", "本科"),
    ("大模型产品经理", "华为", "深圳", 30, 60, 15, "产品经理", "5-10年", "硕士"),
    ("AI产品经理（企业服务）", "钉钉", "杭州", 25, 50, 15, "产品经理", "3-5年", "本科"),
    ("AI运营经理", "网易", "杭州", 22, 42, 15, "AI运营", "3-5年", "本科"),
    ("AI策略运营", "拼多多", "上海", 25, 48, 14, "AI运营", "3-5年", "本科"),
    ("大模型产品经理（Agent方向）", "智谱AI", "北京", 30, 65, 15, "产品经理", "3-5年", "硕士"),
    ("AI产品运营", "Kimi", "北京", 25, 50, 15, "AI运营", "1-3年", "本科"),
    ("数据产品经理（AI方向）", "京东", "北京", 28, 52, 15, "产品经理", "3-5年", "本科"),
    ("AIGC商业化运营", "字节跳动", "深圳", 28, 55, 15, "商业化/增长", "3-5年", "本科"),
    ("AI产品经理（对话机器人）", "商汤科技", "上海", 25, 50, 15, "产品经理", "3-5年", "硕士"),
    ("大模型数据标注主管", "数据堂", "北京", 20, 35, 13, "训练/标注", "3-5年", "本科"),
    ("AI产品经理实习生", "字节跳动", "北京", 6, 10, 12, "产品经理", "应届", "本科"),
    ("大模型产品运营实习生", "百度", "北京", 5, 9, 12, "AI运营", "应届", "本科"),
    ("AI产品经理（国际化）", "TikTok", "北京", 35, 65, 15, "产品经理", "5-10年", "本科"),
    ("AI商务拓展经理", "阿里云", "杭州", 25, 48, 15, "商业化/增长", "3-5年", "本科"),
]

DESCRIPTIONS = {
    "产品经理": "【岗位职责】\n1. 负责大模型/AI产品的规划与设计，完成PRD撰写\n2. 深入理解用户需求，进行竞品分析和用户研究\n3. 与算法、工程团队协作推进产品落地\n4. 建立产品指标体系，通过数据分析驱动产品迭代\n5. 跟踪大模型行业趋势，挖掘AI应用场景\n\n【任职要求】\n1. {exp}以上产品经验，有AI相关产品经验优先\n2. {edu}及以上学历，计算机、统计学等相关专业优先\n3. 了解大模型原理（GPT、Transformer等），有Prompt Engineering经验加分\n4. 熟练掌握Axure/Figma等原型工具，具备SQL数据分析能力\n5. 优秀的跨部门沟通推动能力，有较强的产品思维",
    "AI运营": "【岗位职责】\n1. 负责AI产品的运营策略制定与执行\n2. 制定内容运营、用户运营方案，提升产品活跃度\n3. 分析用户反馈和数据，驱动产品优化\n4. 策划AI产品推广活动，提升市场认知\n5. 建立AI产品运营指标体系\n\n【任职要求】\n1. {exp}运营经验，有AI产品运营经验优先\n2. {edu}及以上学历\n3. 了解大模型/AIGC相关技术，对AI行业有热情\n4. 具备数据分析能力，熟练使用SQL和BI工具\n5. 优秀的项目管理和跨部门协调能力",
    "商业化/增长": "【岗位职责】\n1. 负责AI产品的商业化策略设计与落地\n2. 制定定价方案、销售策略和增长计划\n3. 分析市场需求和竞争对手，寻找商业机会\n4. 与产品、销售团队协作推进商业化进程\n5. 对营收和增长指标负责\n\n【任职要求】\n1. {exp}商业化/增长相关经验\n2. {edu}及以上学历\n3. 了解AI行业商业模式和变现路径\n4. 具备较强的数据分析和商业思维\n5. 优秀的商务谈判和沟通能力",
    "提示词工程": "【岗位职责】\n1. 设计和优化大模型的提示词模板和策略\n2. 针对不同应用场景开发高效的Prompt方案\n3. 进行A/B测试评估Prompt效果\n4. 建立Prompt工程的最佳实践和方法论\n5. 与产品、算法团队协作优化模型输出质量\n\n【任职要求】\n1. {exp}相关经验\n2. {edu}及以上学历\n3. 深入了解LLM原理，有丰富的Prompt Engineering实践经验\n4. 具备编程能力（Python优先），能进行Prompt自动化测试\n5. 较强的逻辑思维和问题拆解能力",
    "训练/标注": "【岗位职责】\n1. 负责AI模型训练数据的标注和管理\n2. 制定标注标准和流程规范\n3. 管理标注团队，确保标注质量和效率\n4. 分析标注数据质量，持续优化标注流程\n5. 与算法团队协作优化数据需求\n\n【任职要求】\n1. {exp}相关工作经验\n2. {edu}及以上学历\n3. 了解AI数据标注流程和质量标准\n4. 具备团队管理和项目管理能力\n5. 细心、耐心，对数据质量有追求",
}


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Job).count()
        if existing > 0:
            print(f"Database already has {existing} jobs. Run with FORCE=1 to re-seed.")
            if not os.environ.get("FORCE"):
                return

        today = date.today()
        jobs_added = 0

        for title, company, city, sal_min, sal_max, sal_months, job_type, exp, edu in DEMO_JOBS:
            days_ago = randint(0, 14)
            posting_date = today - timedelta(days=days_ago)
            seen_date = datetime.utcnow() - timedelta(days=days_ago)

            desc_template = DESCRIPTIONS.get(job_type, DESCRIPTIONS["产品经理"])
            desc = desc_template.format(exp=exp, edu=edu)

            job = Job(
                platform="boss",
                platform_job_id=f"demo_{jobs_added}_{randint(1000, 9999)}",
                title=title,
                company_name=company,
                company_size=choice(["1000-9999人", "10000人以上", "500-999人"]),
                company_industry="互联网/人工智能",
                location_city=city,
                salary_min=sal_min,
                salary_max=sal_max,
                salary_months=sal_months,
                job_type=job_type,
                experience_required=exp,
                education_required=edu,
                description_text=desc,
                benefits=json.dumps(choice([
                    ["五险一金", "股票期权", "免费三餐", "弹性工作"],
                    ["五险一金", "年终奖金", "带薪年假", "技术氛围好"],
                    ["五险一金", "免费健身房", "扁平化管理", "大牛云集"],
                ]), ensure_ascii=False),
                posting_date=posting_date,
                first_seen_at=seen_date,
                last_seen_at=seen_date,
                is_active=True,
            )
            db.add(job)
            jobs_added += 1

        db.commit()
        print(f"Seeded {jobs_added} demo jobs.")

        update_company_stats(db)
        db.commit()

        count = extract_and_link_skills(db)
        print(f"Extracted {count} skill associations.")

        generate_snapshot()
        print("Generated daily snapshot.")

        print("\nDemo data ready! Run: make run")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
