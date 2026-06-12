"""
养护费用模型模块
按《公路养护决策技术规范》第7.3.5节实现费用模型

功能：
1. 单价标准定义
2. 费用计算
3. 全寿命周期费用分析（LCC）
4. 费用效益分析（CBA/CEA）
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# 1. 单价标准（元/m²）
# ══════════════════════════════════════════════════════════════════════════════

UNIT_PRICES = {
    '沥青路面': {
        '路面改造': 319,
        '大修': 380,
        '中修': 180,
        '预防性养护': 160,
        '日常养护': 30,
    },
    '水泥路面': {
        '路面改造': 299,
        '大修': 350,
        '中修': 160,
        '预防性养护': 140,
        '日常养护': 25,
    },
}

# 养护类型映射（规范术语与程序术语对应）
MAINTENANCE_TYPE_MAPPING = {
    '路面改造': '路面改造',
    '大修': '路面改造',
    '中修': '预防性养护',
    '预防性养护': '预防性养护',
    '日常养护': '日常养护',
}


def get_unit_price(pavement_type: str, maintenance_type: str) -> float:
    """
    获取单价

    参数:
        pavement_type: 路面类型（'沥青路面'/'水泥路面'）
        maintenance_type: 养护类型

    返回:
        单价（元/m²）
    """
    prices = UNIT_PRICES.get(pavement_type, UNIT_PRICES['沥青路面'])
    return prices.get(maintenance_type, 300)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 费用计算
# ══════════════════════════════════════════════════════════════════════════════

def calculate_cost(length_km: float, width_m: float, unit_price: float) -> float:
    """
    计算养护费用

    公式：资金 = 长度(km) × 1000 × 宽度(m) × 单价(元/m²)

    参数:
        length_km: 路段长度（公里）
        width_m: 路面宽度（米）
        unit_price: 单价（元/m²）

    返回:
        养护费用（元）
    """
    return length_km * 1000 * width_m * unit_price


def calculate_cost_from_df(row: pd.Series, maintenance_type: str) -> float:
    """
    从DataFrame行数据计算养护费用

    参数:
        row: 包含路段长度、路面宽度等数据的Series
        maintenance_type: 养护类型

    返回:
        养护费用（元）
    """
    length = row.get('路段长度km', row.get('路段长度(km)', 1.0))
    width = row.get('路面宽度', 7)
    pavement_type = row.get('路面类型', '沥青路面')

    unit_price = get_unit_price(pavement_type, maintenance_type)
    return calculate_cost(length, width, unit_price)


def calculate_maintenance_summary(df: pd.DataFrame, maintenance_type: str) -> Dict:
    """
    计算养护汇总费用

    参数:
        df: 包含路段数据的DataFrame
        maintenance_type: 养护类型

    返回:
        费用汇总字典
    """
    if df is None or df.empty:
        return {}

    total_length = df.get('路段长度km', df.get('路段长度(km)', pd.Series([1.0]*len(df)))).sum()
    total_cost = df.apply(lambda row: calculate_cost_from_df(row, maintenance_type), axis=1).sum()

    # 按路面类型统计
    pavement_stats = {}
    for ptype in df['路面类型'].unique():
        type_df = df[df['路面类型'] == ptype]
        type_length = type_df.get('路段长度km', type_df.get('路段长度(km)', pd.Series([1.0]*len(type_df)))).sum()
        type_cost = type_df.apply(lambda row: calculate_cost_from_df(row, maintenance_type), axis=1).sum()
        pavement_stats[ptype] = {
            '里程(km)': round(type_length, 2),
            '费用(万元)': round(type_cost / 10000, 2),
        }

    return {
        '总里程(km)': round(total_length, 2),
        '总费用(万元)': round(total_cost / 10000, 2),
        '费用(元)': total_cost,
        '按路面类型': pavement_stats,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. 全寿命周期费用分析（LCC）
# ══════════════════════════════════════════════════════════════════════════════

def life_cycle_cost_analysis(df: pd.DataFrame,
                               analysis_period: int = 20,
                               discount_rate: float = 0.05,
                               targets: Dict = None) -> Dict:
    """
    全寿命周期费用分析（LCC）

    分析内容包括：
    - 初始建设费用
    - 养护费用（各年）
    - 残值
    - 净现值（NPV）

    参数:
        df: 包含路段数据的DataFrame
        analysis_period: 分析期（年），默认20年
        discount_rate: 折现率，默认5%
        targets: 养护目标字典

    返回:
        LCC分析结果字典
    """
    if df is None or df.empty:
        return {}

    # 确保数值列
    if '路段长度km' not in df.columns:
        df = df.copy()
        df['路段长度km'] = 1.0
    df['路段长度km'] = pd.to_numeric(df['路段长度km'], errors='coerce').fillna(1.0)

    if '路面宽度' not in df.columns:
        df['路面宽度'] = 7.0
    df['路面宽度'] = pd.to_numeric(df['路面宽度'], errors='coerce').fillna(7.0)

    total_length = df['路段长度km'].sum()
    avg_width = df['路面宽度'].mean()

    # 初始建设费用（简化估算）
    # 假设当前路况对应的初始费用为当前路况水平的等效价值
    current_pqi_avg = df['PQI'].mean() if 'PQI' in df.columns else 80
    initial_cost = total_length * 1000 * avg_width * 400 * (current_pqi_avg / 100)  # 简化估算

    # 折现系数
    discount_factors = [1 / (1 + discount_rate) ** t for t in range(1, analysis_period + 1)]

    # 逐年养护费用估算（简化模型）
    yearly_costs = []
    cumulative_cost = 0

    for year in range(1, analysis_period + 1):
        # 简化的年度养护费用模型
        # 假设每年需要的养护费用与路况衰减相关
        if year <= 5:
            # 前5年主要是预防性养护
            yearly_cost = total_length * 1000 * avg_width * 50  # 日常养护
        elif year <= 10:
            # 5-10年开始需要中修
            yearly_cost = total_length * 1000 * avg_width * 120
        elif year <= 15:
            # 10-15年需要大修
            yearly_cost = total_length * 1000 * avg_width * 200
        else:
            # 15年后路面状况较差，需要路面改造
            yearly_cost = total_length * 1000 * avg_width * 300

        discounted_cost = yearly_cost * discount_factors[year - 1]
        cumulative_cost += discounted_cost
        yearly_costs.append({
            '年份': year,
            '当年费用(元)': yearly_cost,
            '折现费用(元)': discounted_cost,
            '累计折现费用(元)': cumulative_cost,
        })

    # 残值（分析期末路面残余价值）
    residual_value = total_length * 1000 * avg_width * 100 * 0.2  # 简化估算

    # 净现值
    npv = initial_cost + cumulative_cost - residual_value * discount_factors[-1]

    return {
        '初始建设费用(元)': initial_cost,
        '初始建设费用(万元)': round(initial_cost / 10000, 2),
        '养护费用(万元)': round(cumulative_cost / 10000, 2),
        '残值(万元)': round(residual_value / 10000, 2),
        '净现值(万元)': round(npv / 10000, 2),
        '年均费用(万元/年)': round(npv / analysis_period, 2),
        '分析期(年)': analysis_period,
        '折现率(%)': discount_rate * 100,
        '逐年费用明细': pd.DataFrame(yearly_costs),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. 费用效益分析
# ══════════════════════════════════════════════════════════════════════════════

def cost_benefit_analysis(project_cost: float,
                          benefit_yearly: List[float],
                          discount_rate: float = 0.05) -> Dict:
    """
    费用效益分析（CBA）

    计算：
    - 费用现值（PVC）
    - 效益现值（PVB）
    - 效益费用比（B/C）
    - 净现值（NPV）
    - 内部收益率（IRR）

    参数:
        project_cost: 项目费用（元）
        benefit_yearly: 逐年效益列表（长度与分析期相同）
        discount_rate: 折现率

    返回:
        CBA分析结果字典
    """
    if not benefit_yearly:
        return {'error': '无效益数据'}

    analysis_period = len(benefit_yearly)

    # 费用现值
    pvc = project_cost

    # 效益现值
    discount_factors = [1 / (1 + discount_rate) ** t for t in range(1, analysis_period + 1)]
    pvb = sum(b * d for b, d in zip(benefit_yearly, discount_factors))

    # 效益费用比
    bcr = pvb / pvc if pvc > 0 else 0

    # 净现值
    npv = pvb - pvc

    # 简化内部收益率（使用二分法近似计算）
    irr = calculate_irr(project_cost, benefit_yearly)

    return {
        '费用现值(万元)': round(pvc / 10000, 2),
        '效益现值(万元)': round(pvb / 10000, 2),
        '效益费用比(B/C)': round(bcr, 2),
        '净现值(万元)': round(npv / 10000, 2),
        '内部收益率(%)': round(irr * 100, 2),
    }


def calculate_irr(project_cost: float, benefit_yearly: List[float], max_iter: int = 100) -> float:
    """
    计算内部收益率（IRR）

    使用二分法迭代求解

    参数:
        project_cost: 项目费用
        benefit_yearly: 逐年效益列表
        max_iter: 最大迭代次数

    返回:
        IRR值
    """
    # 确定IRR的大致范围
    rate_low = -0.5
    rate_high = 2.0

    for _ in range(max_iter):
        rate_mid = (rate_low + rate_high) / 2
        npv = -project_cost
        for i, benefit in enumerate(benefit_yearly):
            npv += benefit / (1 + rate_mid) ** (i + 1)

        if abs(npv) < 1:  # 收敛条件
            return rate_mid

        if npv > 0:
            rate_low = rate_mid
        else:
            rate_high = rate_mid

    return (rate_low + rate_high) / 2


def cost_effectiveness_analysis(project_list: List[Dict]) -> pd.DataFrame:
    """
    费用效果分析（CEA）

    计算各项目的单位费用效果

    参数:
        project_list: 项目列表，每个项目包含：
            - name: 项目名称
            - cost: 费用（万元）
            - effect: 效果（PQI提升值×里程等）

    返回:
        CEA分析结果DataFrame
    """
    if not project_list:
        return pd.DataFrame()

    results = []
    total_cost = 0
    total_effect = 0

    for proj in project_list:
        cost = proj.get('cost', 0)
        effect = proj.get('effect', 0)
        total_cost += cost
        total_effect += effect

        cea = effect / cost if cost > 0 else 0

        results.append({
            '项目名称': proj.get('name', ''),
            '费用(万元)': cost,
            '效果': effect,
            '费用效果比(CEA)': round(cea, 4),
        })

    # 添加汇总行
    overall_cea = total_effect / total_cost if total_cost > 0 else 0
    results.append({
        '项目名称': '合计',
        '费用(万元)': total_cost,
        '效果': total_effect,
        '费用效果比(CEA)': round(overall_cea, 4),
    })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 5. 年度预算分析
# ══════════════════════════════════════════════════════════════════════════════

def analyze_budget_requirement(df: pd.DataFrame,
                                 year: int,
                                 decay_rates: Dict = None) -> Dict:
    """
    分析指定年份的预算需求

    参数:
        df: 包含路段数据的DataFrame
        year: 目标年份
        decay_rates: 衰减率字典

    返回:
        预算需求分析结果
    """
    if df is None or df.empty:
        return {}

    from .maintenance_demand import analyze_demand, MAINTENANCE_TARGETS

    # 分析养护需求
    demand = analyze_demand(df, year, MAINTENANCE_TARGETS, decay_rates)

    if demand.empty:
        return {}

    # 按养护类型统计
    results = {
        '年份': year,
        '总需求里程(km)': demand['路段长度(km)'].sum(),
    }

    for maint_type in ['路面改造', '预防性养护', '日常养护']:
        type_demand = demand[demand['养护类型'] == maint_type]
        if not type_demand.empty:
            type_length = type_demand['路段长度(km)'].sum()
            type_cost = type_demand.apply(
                lambda row: calculate_cost_from_df(row, maint_type), axis=1
            ).sum()
            results[f'{maint_type}里程(km)'] = round(type_length, 2)
            results[f'{maint_type}费用(万元)'] = round(type_cost / 10000, 2)

    return results


def generate_budget_comparison(df: pd.DataFrame,
                                  years: List[int],
                                  budgets: Dict[int, float],
                                  decay_rates: Dict = None) -> pd.DataFrame:
    """
    生成多年预算需求与预算对比表

    参数:
        df: 包含路段数据的DataFrame
        years: 年份列表
        budgets: 预算字典 {年份: 预算(万元)}
        decay_rates: 衰减率字典

    返回:
        对比结果DataFrame
    """
    from .maintenance_demand import predict_multiyear_demand, MAINTENANCE_TARGETS

    results = []

    for year in years:
        # 需求分析
        demand_analysis = analyze_budget_requirement(df, year, decay_rates)

        if demand_analysis:
            budget = budgets.get(year, 0)
            total_cost = sum(
                demand_analysis.get(f'{t}费用(万元)', 0)
                for t in ['路面改造', '预防性养护', '日常养护']
            )

            results.append({
                '年份': year,
                '预算(万元)': budget,
                '需求(万元)': round(total_cost, 2),
                '差额(万元)': round(budget - total_cost, 2),
                '满足程度(%)': round(budget / total_cost * 100, 1) if total_cost > 0 else 0,
            })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 6. 资金需求汇总表
# ══════════════════════════════════════════════════════════════════════════════

def generate_funding_summary(demand_df: pd.DataFrame,
                               unit_prices: Dict = None) -> pd.DataFrame:
    """
    生成资金需求汇总表

    参数:
        demand_df: 养护需求分析结果
        unit_prices: 单价字典

    返回:
        汇总表DataFrame
    """
    if demand_df is None or demand_df.empty:
        return pd.DataFrame()

    if unit_prices is None:
        unit_prices = UNIT_PRICES

    # 计算各项目费用
    def calc_cost(row):
        maint_type = row['养护类型']
        ptype = row['路面类型']
        length = row['路段长度(km)']
        width = row.get('路面宽度', 7)
        price = unit_prices.get(ptype, {}).get(maint_type, 300)
        return length * 1000 * width * price / 10000

    demand_df = demand_df.copy()
    demand_df['估算费用(万元)'] = demand_df.apply(calc_cost, axis=1)

    # 按养护类型汇总
    results = []
    for maint_type in ['路面改造', '预防性养护', '日常养护']:
        type_df = demand_df[demand_df['养护类型'] == maint_type]
        if not type_df.empty:
            results.append({
                '养护类型': maint_type,
                '路段数': len(type_df),
                '总里程(km)': round(type_df['路段长度(km)'].sum(), 2),
                '总费用(万元)': round(type_df['估算费用(万元)'].sum(), 2),
            })

    # 添加总计行
    total_cost = demand_df['估算费用(万元)'].sum()
    results.append({
        '养护类型': '合计',
        '路段数': len(demand_df),
        '总里程(km)': round(demand_df['路段长度(km)'].sum(), 2),
        '总费用(万元)': round(total_cost, 2),
    })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 经济指标计算函数（需路龄、交通量数据）
# ══════════════════════════════════════════════════════════════════════════════

def calc_weighted_pqi(df: pd.DataFrame) -> float:
    """按里程加权计算PQI"""
    if df is None or df.empty or 'PQI' not in df.columns:
        return 0
    if '路段长度km' not in df.columns:
        return float(df['PQI'].mean())
    t = df['路段长度km'].sum()
    return float((df['PQI'] * df['路段长度km']).sum() / t) if t > 0 else 0


def calc_good_road_rate(df: pd.DataFrame, threshold: float = 80) -> float:
    """计算优良路率(%)"""
    if df is None or df.empty:
        return 0
    if '路段长度km' not in df.columns:
        return len(df[df['PQI'] >= threshold]) / len(df) * 100 if len(df) > 0 else 0
    t = df['路段长度km'].sum()
    g = df[df['PQI'] >= threshold]['路段长度km'].sum() if 'PQI' in df.columns else 0
    return g / t * 100 if t > 0 else 0


def calc_bcr_ratio(df: pd.DataFrame, maintenance_cost: float,
                   analysis_years: int = 5, discount_rate: float = 0.05) -> float:
    """效益费用比 B/C：交通量×PQI提升产生的用户效益 / 投资成本"""
    if df is None or df.empty or maintenance_cost <= 0:
        return 0
    current_pqi = calc_weighted_pqi(df)
    pqi_improvement = max(0, 92 - current_pqi)
    if pqi_improvement <= 0:
        return 1.0
    aadt = float(df['交通量'].mean()) if '交通量' in df.columns else 5000
    total_km = float(df['路段长度km'].sum()) if '路段长度km' in df.columns else 1
    # 单位效益 = 每车每公里因PQI提升1分节约的运营成本(元)
    # 参考值: 燃油+轮胎+维修 ≈ 0.015元/车/公里/PQI分
    unit_value = 0.015
    annual_benefit = aadt * 365 * total_km * pqi_improvement * unit_value / 10000
    pv_benefit = sum(annual_benefit / (1 + discount_rate) ** t for t in range(1, analysis_years + 1))
    return pv_benefit / maintenance_cost


def calc_unit_pqi_cost(df: pd.DataFrame, maintenance_cost: float) -> float:
    """单位投资PQI提升(分/万元)"""
    if df is None or df.empty or maintenance_cost <= 0:
        return 0
    current_pqi = calc_weighted_pqi(df)
    improvement = max(0, 92 - current_pqi)
    total_km = float(df['路段长度km'].sum()) if '路段长度km' in df.columns else 1
    return improvement * total_km / maintenance_cost


def calc_km_cost(maintenance_cost: float, df: pd.DataFrame) -> float:
    """每公里养护成本(万元/km)"""
    total_km = float(df['路段长度km'].sum()) if df is not None and '路段长度km' in df.columns else 1
    return maintenance_cost / total_km if total_km > 0 else 0


def calc_lcc(df: pd.DataFrame, analysis_years: int = 20,
             discount_rate: float = 0.05, traffic_growth: float = 0.02) -> dict:
    """全寿命周期费用 LCC — 考虑路龄和交通量增长"""
    if df is None or df.empty:
        return {'NPV(万元)': 0, '年均费用(万元)': 0, '总里程(km)': 0}
    total_km = float(df['路段长度km'].sum()) if '路段长度km' in df.columns else 1
    width = float(df['路面宽度'].mean()) if '路面宽度' in df.columns else 7
    road_age = float(df['路龄'].mean()) if '路龄' in df.columns else 5
    initial_value = total_km * 1000 * width * 400 / 10000
    base_cost = total_km * width * 1000 * 30 / 10000
    npv = 0
    for t in range(1, analysis_years + 1):
        age_factor = 1 + (road_age + t) * 0.03
        tf = (1 + traffic_growth) ** t
        npv += base_cost * age_factor * tf / (1 + discount_rate) ** t
    return {'NPV(万元)': round(npv, 2), '年均费用(万元)': round(npv/analysis_years, 2),
            '总里程(km)': round(total_km,1), '初始资产(万元)': round(initial_value,2)}


def calc_economic_indicators(df: pd.DataFrame, maintenance_cost: float = None) -> dict:
    """一键计算所有经济技术指标"""
    if df is None or df.empty:
        return {}
    if maintenance_cost is None:
        total_km = float(df['路段长度km'].sum()) if '路段长度km' in df.columns else 1
        maintenance_cost = total_km * 300
    w_pqi = calc_weighted_pqi(df)
    good_rate = calc_good_road_rate(df)
    bcr = calc_bcr_ratio(df, maintenance_cost)
    unit_cost = calc_unit_pqi_cost(df, maintenance_cost)
    km_cost = calc_km_cost(maintenance_cost, df)
    lcc = calc_lcc(df)
    aadt = int(df['交通量'].mean()) if '交通量' in df.columns else 5000
    road_age = float(df['路龄'].mean()) if '路龄' in df.columns else 5
    return {
        '加权PQI': round(w_pqi, 1),
        '优良路率(%)': round(good_rate, 1),
        '交通量(AADT)': aadt,
        '平均路龄(年)': round(road_age, 1),
        '养护投资(万元)': round(maintenance_cost, 2),
        'B/C比': round(bcr, 2),
        '单位PQI提升(分/万元)': round(unit_cost, 2),
        '每公里成本(万元/km)': round(km_cost, 2),
        'LCC-NPV(万元)': lcc['NPV(万元)'],
        'LCC年均(万元)': lcc['年均费用(万元)'],
    }


def calc_comprehensive_score(technical_score: float, economic_score: float,
                               tech_weight: float = 0.6, econ_weight: float = 0.4) -> dict:
    """技术+经济综合评分"""
    total = technical_score * tech_weight + economic_score * econ_weight
    grade = '优秀' if total >= 90 else ('良好' if total >= 75 else ('合格' if total >= 60 else '需调整'))
    return {
        '技术得分': round(technical_score, 1),
        '经济得分': round(economic_score, 1),
        '综合得分': round(total, 1),
        '等级': grade,
        '建议': '达标可执行' if total >= 75 else ('优化资金后可行' if total >= 60 else '需调整目标或增加投入')
    }