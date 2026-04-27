TOPICS = ["Agent", "RAG", "AI产品经理", "AI运营", "多模态", "AI搜索", "AI办公", "商业化"]


MARKET_SOURCES = [
    {
        "name": "机器之心",
        "type": "行业媒体",
        "language": "中文",
        "url": "https://www.jiqizhixin.com/",
        "topics": ["Agent", "RAG", "多模态", "AI搜索"],
    },
    {
        "name": "量子位",
        "type": "行业媒体",
        "language": "中文",
        "url": "https://www.qbitai.com/",
        "topics": ["Agent", "多模态", "AI办公", "AI搜索"],
    },
    {
        "name": "晚点 LatePost",
        "type": "商业媒体",
        "language": "中文",
        "url": "https://www.latepost.com/",
        "topics": ["商业化", "AI产品经理", "AI办公"],
    },
    {
        "name": "Founder Park",
        "type": "创业/产品媒体",
        "language": "中文",
        "url": "https://www.founderpark.com/",
        "topics": ["AI产品经理", "商业化", "Agent"],
    },
    {
        "name": "宝玉",
        "type": "KOL",
        "language": "中文",
        "url": "https://baoyu.io/",
        "topics": ["Agent", "RAG", "AI办公", "AI产品经理"],
    },
    {
        "name": "orange.ai",
        "type": "KOL/社区",
        "language": "中文",
        "url": "https://orange.ai/",
        "topics": ["AI产品经理", "AI运营", "商业化"],
    },
    {
        "name": "硅星人",
        "type": "科技媒体",
        "language": "中文",
        "url": "https://www.guixingren.com/",
        "topics": ["商业化", "AI办公", "多模态"],
    },
    {
        "name": "Latent Space",
        "type": "英文播客/社区",
        "language": "英文",
        "url": "https://www.latent.space/",
        "topics": ["Agent", "RAG", "多模态"],
    },
    {
        "name": "Ben Thompson",
        "type": "英文分析师",
        "language": "英文",
        "url": "https://stratechery.com/",
        "topics": ["商业化", "AI产品经理", "AI办公"],
    },
    {
        "name": "a16z AI",
        "type": "英文机构观点",
        "language": "英文",
        "url": "https://a16z.com/ai/",
        "topics": ["Agent", "RAG", "商业化"],
    },
    {
        "name": "阑夕",
        "type": "KOL",
        "language": "中文",
        "url": "",
        "topics": ["商业化", "AI产品经理", "AI运营"],
    },
    {
        "name": "卡兹克",
        "type": "KOL",
        "language": "中文",
        "url": "",
        "topics": ["AI产品经理", "AI运营", "Agent"],
    },
    {
        "name": "小红书",
        "type": "内容社区/公司信号",
        "language": "中文",
        "url": "https://www.xiaohongshu.com/",
        "topics": ["AI运营", "AI产品经理", "AI搜索", "商业化"],
    },
    {
        "name": "哔哩哔哩",
        "type": "内容社区/公司信号",
        "language": "中文",
        "url": "https://www.bilibili.com/",
        "topics": ["AI运营", "多模态", "AI搜索", "商业化"],
    },
    {
        "name": "快手",
        "type": "内容平台/公司信号",
        "language": "中文",
        "url": "https://www.kuaishou.com/",
        "topics": ["多模态", "AI运营", "商业化", "AI产品经理"],
    },
    {
        "name": "美团",
        "type": "本地生活/公司信号",
        "language": "中文",
        "url": "https://www.meituan.com/",
        "topics": ["AI搜索", "AI产品经理", "AI办公", "商业化"],
    },
    {
        "name": "阿里巴巴",
        "type": "互联网/云厂商信号",
        "language": "中文",
        "url": "https://www.alibaba.com/",
        "topics": ["Agent", "RAG", "AI办公", "商业化"],
    },
    {
        "name": "京东",
        "type": "电商/公司信号",
        "language": "中文",
        "url": "https://www.jd.com/",
        "topics": ["AI搜索", "AI办公", "商业化", "AI产品经理"],
    },
    {
        "name": "Meta",
        "type": "海外科技公司",
        "language": "英文",
        "url": "https://ai.meta.com/",
        "topics": ["Agent", "多模态", "AI产品经理", "商业化"],
    },
    {
        "name": "Google",
        "type": "海外科技公司",
        "language": "英文",
        "url": "https://ai.google/",
        "topics": ["Agent", "RAG", "AI搜索", "多模态"],
    },
    {
        "name": "Anthropic",
        "type": "海外 AI 公司",
        "language": "英文",
        "url": "https://www.anthropic.com/news",
        "topics": ["Agent", "AI办公", "AI产品经理", "商业化"],
    },
    {
        "name": "Microsoft",
        "type": "海外科技公司",
        "language": "英文",
        "url": "https://www.microsoft.com/en-us/ai",
        "topics": ["Agent", "RAG", "AI办公", "商业化"],
    },
]


def get_market_sources():
    return MARKET_SOURCES


def get_topic_source_map():
    topic_map = {topic: [] for topic in TOPICS}
    for source in MARKET_SOURCES:
        for topic in source["topics"]:
            topic_map.setdefault(topic, []).append(source)
    return topic_map


def get_sources_for_topics(topics):
    topic_map = get_topic_source_map()
    seen = set()
    sources = []
    for topic in topics:
        for source in topic_map.get(topic, []):
            key = source["name"]
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)
    return sources
