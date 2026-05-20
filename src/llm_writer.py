"""
大模型调用模块
支持OpenAI兼容接口（OpenAI、DeepSeek、智谱、讯飞等）
"""
import json
import os
from typing import Optional

# 尝试导入openai模块
try:
    import openai
    # 检查openai版本 - 1.0+版本使用from openai import OpenAI
    if hasattr(openai, 'OpenAI'):
        from openai import OpenAI
        OPENAI_AVAILABLE = True
    else:
        # 旧版本openai
        OPENAI_AVAILABLE = False
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class LLMClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._client = None
    
    def _get_client(self):
        if not self._client:
            if not OPENAI_AVAILABLE:
                raise ImportError("请安装 openai 包：pip install openai>=1.0")
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client
    
    def chat(self, prompt: str, system: str = None, max_tokens: int = 2000) -> str:
        """调用大模型生成文本"""
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    
    def test_connection(self) -> tuple[bool, str]:
        """测试连接是否正常"""
        try:
            result = self.chat("你好，请回复'连接正常'", max_tokens=20)
            return True, result
        except Exception as e:
            return False, str(e)


# ─────────────────────────────────────────────
# 报告文字生成提示词模板
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位专业的公路养护技术分析师，擅长撰写公路路况分析和养护需求预测报告。
请根据提供的数据和图表分析结果，用专业、严谨、流畅的中文撰写报告内容。
要求：
1. 语言专业规范，符合公路行业技术文件风格
2. 数据引用准确，分析结论有据可查
3. 逻辑清晰，层次分明
4. 适当使用专业术语（PQI、PCI、RQI、路面技术状况指数等）"""


def generate_overview_text(stats: dict, county: str, years: list, llm: LLMClient) -> str:
    """生成概述章节文字"""
    prompt = f"""请为以下数据撰写公路路况分析报告的"概述"章节（约200-300字）：

县份：{county}
数据年份：{', '.join(str(y) for y in years)}
检测路段总数：{stats.get('total_segments', 'N/A')}
总里程：{stats.get('total_length_km', 0):.1f} km
PQI均值：{stats.get('PQI_mean', 'N/A')}
PCI均值：{stats.get('PCI_mean', 'N/A')}
RQI均值：{stats.get('RQI_mean', 'N/A')}

要求：说明本报告的数据来源、覆盖范围、分析目的。"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=600)


def generate_trend_analysis_text(trend_data: dict, county: str, llm: LLMClient) -> str:
    """生成趋势分析章节文字"""
    trend_str = json.dumps(trend_data, ensure_ascii=False, indent=2)
    prompt = f"""请根据以下{county}历年路面状况指数数据，撰写"路面技术状况年度趋势分析"章节（约300-400字）：

数据：
{trend_str}

要求：
1. 分析PQI、PCI、RQI的历年变化趋势（上升/下降/平稳）
2. 指出变化显著的年份及可能原因
3. 总体评价路面技术状况水平"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=800)


def generate_grade_analysis_text(grade_data: dict, county: str, year: int, llm: LLMClient) -> str:
    """生成等级分布分析文字"""
    grade_str = json.dumps(grade_data, ensure_ascii=False)
    prompt = f"""请根据以下{county} {year}年PQI等级分布数据，撰写"路面技术状况等级分布分析"（约250-350字）：

各等级里程（km）：{grade_str}

要求：
1. 分析优良路段占比情况
2. 指出需要重点关注的等级区间
3. 与行业标准对比评价"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=700)


def generate_maintenance_text(maint_summary, county: str, year: int, total_cost: float, llm: LLMClient) -> str:
    """生成养护需求分析文字"""
    try:
        summary_str = maint_summary.to_string()
    except:
        summary_str = str(maint_summary)
    
    prompt = f"""请根据以下{county} {year}年养护需求分析数据，撰写"养护需求分析与资金估算"章节（约350-450字）：

养护需求汇总：
{summary_str}

合计估算养护费用：{total_cost:.1f} 万元

要求：
1. 说明各类型养护的里程和费用情况
2. 重点阐述路面改造和预防养护需求
3. 提出合理的养护建议和优先级
4. 说明资金需求测算依据"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=900)


def generate_forecast_text(county: str, latest_year: int, trend_data: dict, llm: LLMClient) -> str:
    """生成养护需求预测文字（基于趋势推断）"""
    prompt = f"""请根据{county}历年路面状况指数数据，结合指数衰减模型，撰写"养护需求预测"章节（约400-500字）：

历年PQI/PCI/RQI数据：
{json.dumps(trend_data, ensure_ascii=False, indent=2)}

基准年：{latest_year}年
预测周期：{latest_year+1}-{latest_year+5}年

要求：
1. 基于当前趋势描述未来5年路面状况变化预测
2. 说明采用的预测原则（数据驱动、分路施策、动态滚动）
3. 预测各年度大概的养护资金需求变化趋势
4. 给出养护建议和管理措施"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=1000)


def generate_conclusion_text(county: str, stats: dict, llm: LLMClient) -> str:
    """生成结论与建议文字"""
    prompt = f"""请为{county}公路路况分析报告撰写"结论与建议"章节（约200-250字）：

主要数据：
- 检测总里程：{stats.get('total_length_km', 0):.1f} km
- PQI均值：{stats.get('PQI_mean', 'N/A')}
- PCI均值：{stats.get('PCI_mean', 'N/A')}
- RQI均值：{stats.get('RQI_mean', 'N/A')}

要求：提炼主要结论，提出针对性建议，语言简洁有力。"""
    return llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=500)


def generate_full_report_texts(data_dict: dict, charts: dict, stats_dict: dict,
                                llm: LLMClient, county: str, progress_callback=None) -> dict:
    """
    生成完整报告所需的所有文字段落
    
    Returns:
        {section_name: text_content} 字典
    """
    texts = {}
    df = data_dict.get(county, data_dict.get('全部'))
    if df is None or df.empty:
        return texts
    
    stats = stats_dict.get(county, {})
    years = sorted(df['年份'].unique().tolist()) if '年份' in df.columns else []
    latest_year = max(years) if years else None
    county_charts = charts.get(county, {})
    
    def _progress(msg):
        if progress_callback:
            progress_callback(msg)
    
    _progress("正在生成概述...")
    texts['overview'] = generate_overview_text(stats, county, years, llm)
    
    trend_data = county_charts.get('trend', {}).get('data', {})
    if trend_data:
        _progress("正在生成趋势分析...")
        texts['trend'] = generate_trend_analysis_text(trend_data, county, llm)
    
    grade_data = county_charts.get('grade_dist', {}).get('data', {})
    if grade_data and latest_year:
        _progress("正在生成等级分布分析...")
        texts['grade'] = generate_grade_analysis_text(grade_data, county, latest_year, llm)
    
    maint = county_charts.get('maintenance', {})
    if maint and 'summary' in maint and latest_year:
        _progress("正在生成养护需求分析...")
        texts['maintenance'] = generate_maintenance_text(
            maint['summary'], county, latest_year, maint.get('total_cost_wan', 0), llm)
    
    if trend_data and latest_year:
        _progress("正在生成养护需求预测...")
        texts['forecast'] = generate_forecast_text(county, latest_year, trend_data, llm)
    
    _progress("正在生成结论与建议...")
    texts['conclusion'] = generate_conclusion_text(county, stats, llm)
    
    return texts
