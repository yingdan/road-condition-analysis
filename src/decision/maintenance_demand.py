"""
养护需求分析模块
按《公路养护决策技术规范》第7章实现养护需求分析

功能：
1. 养护目标设定
2. 养护触发阈值配置
3. 养护需求分析
4. 需求优先级排序
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from .performance_models import exponential_decay_model


# ══════════════════════════════════════════════════════════════════════════════
# 1. 养护目标定义
# ══════════════════════════════════════════════════════════════════════════════

MAINTENANCE_TARGETS = {
    '普通国道': {
        'PQI': 80,      # PQI≥80为优良
        '优良率': 90,    # 优良路率目标（%）
        '优等率': 60,    # 优等路率目标（%）
    },
    '普通省道': {
        'PQI': 80,
        '优良率': 85,
        '优等率': 50,
    },
    '县道': {
        'PQI': 75,
        '优良率': 80,
        '优等率': 40,
    },
}


def get_road_type(route_code: str) -> str:
    """
    根据路线编码判断道路类型

    参数:
        route_code: 路线编码（如G205、S120）

    返回:
        道路类型：'普通国道'/'普通省道'/'县道'/'其他'
    """
    if pd.isna(route_code):
        return '其他'
    code = str(route_code).strip()
    if code.startswith('G') or code.startswith('国道'):
        return '普通国道'
    elif code.startswith('S') or code.startswith('省道'):
        return '普通省道'
    elif code.startswith('X') or code.startswith('县道'):
        return '县道'
    else:
        return '其他'


def get_target(road_type: str) -> Dict:
    """获取指定道路类型的养护目标"""
    return MAINTENANCE_TARGETS.get(road_type, MAINTENANCE_TARGETS['县道'])


# ══════════════════════════════════════════════════════════════════════════════
# 2. 养护触发阈值（扩展自decay_calculator.py）
# ══════════════════════════════════════════════════════════════════════════════

# 触发阈值配置（可由用户修改）
TRIGGER_THRESHOLDS = {
    '路面改造': {
        '沥青路面': {
            '一级公路': {'PCI': 80, 'PQI': 80, 'RQI': 80},
            '二级及以下': {'PCI': 75, 'PQI': 75, 'RQI': 75},
        },
        '水泥路面': {
            '一级公路': {'PCI': 80, 'PQI': 80},
            '二级及以下': {'PCI': 75, 'PQI': 75},
        },
    },
    '预防性养护': {
        '沥青路面': {
            '一级公路': {'PCI低': 80, 'PCI高': 90, 'RQI低': 80, 'RQI高': 90, 'PQI': 80},
            '二级及以下': {'PCI低': 78, 'PCI高': 85, 'RQI低': 78, 'RQI高': 85, 'PQI': 75},
        },
        '水泥路面': {
            '一级公路': {'PCI低': 80, 'PCI高': 90, 'PQI': 80},
            '二级及以下': {'PCI低': 78, 'PCI高': 85, 'PQI': 75},
        },
    },
}


def get_grade_key(tech_grade: str) -> str:
    """获取技术等级分组键"""
    if tech_grade in ['一级公路', '高速公路']:
        return '一级公路'
    else:
        return '二级及以下'


def judge_maintenance(pqi: float, pci: float, rqi: float,
                      pavement_type: str, tech_grade: str,
                      thresholds: Dict = None) -> Tuple[str, str]:
    """
    判断养护类型

    返回:
        (养护类型, 触发条件描述)
        养护类型：'路面改造'/'预防性养护'/'日常养护'
    """
    if thresholds is None:
        thresholds = TRIGGER_THRESHOLDS

    grade_key = get_grade_key(tech_grade)

    # 检查路面改造条件
    reform_cfg = thresholds.get('路面改造', {}).get(pavement_type, {}).get(grade_key, {})
    if reform_cfg:
        pci_threshold = reform_cfg.get('PCI', 80)
        pqi_threshold = reform_cfg.get('PQI', 80)
        rqi_threshold = reform_cfg.get('RQI', 80)

        if pci < pci_threshold:
            return ('路面改造', f'PCI({pci:.1f}) < {pci_threshold}')
        if pqi < pqi_threshold:
            return ('路面改造', f'PQI({pqi:.1f}) < {pqi_threshold}')
        if not pd.isna(rqi) and rqi < rqi_threshold:
            return ('路面改造', f'RQI({rqi:.1f}) < {rqi_threshold}')

    # 检查预防性养护条件
    prev_cfg = thresholds.get('预防性养护', {}).get(pavement_type, {}).get(grade_key, {})
    if prev_cfg:
        pci_lo = prev_cfg.get('PCI低', 80)
        pci_hi = prev_cfg.get('PCI高', 90)
        pqi_min = prev_cfg.get('PQI', 80)

        # PCI在范围内且PQI满足条件
        if pci_lo <= pci <= pci_hi and pqi >= pqi_min:
            return ('预防性养护', f'PCI({pci:.1f})在{pci_lo}-{pci_hi}范围，PQI({pqi:.1f})≥{pqi_min}')

    return ('日常养护', '路况良好，仅需日常养护')


# ══════════════════════════════════════════════════════════════════════════════
# 3. 养护需求分析
# ══════════════════════════════════════════════════════════════════════════════

def analyze_demand(df: pd.DataFrame,
                   target_year: int = 2026,
                   targets: Dict = None,
                   decay_rates: Dict = None,
                   thresholds: Dict = None) -> pd.DataFrame:
    """
    分析路网养护需求

    参数:
        df: 包含当前路况数据的DataFrame
        target_year: 目标年份（默认2026）
        targets: 养护目标字典，None则使用默认值
        decay_rates: 衰减率字典 {(路面类型,技术等级): {'PQI': k}}
        thresholds: 触发阈值字典

    返回:
        养护需求分析结果DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if targets is None:
        targets = MAINTENANCE_TARGETS

    if decay_rates is None:
        decay_rates = {}

    df = df.copy()

    # 确保数值列
    for col in ['PQI', 'PCI', 'RQI', '路段长度km']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(80)

    if '路面宽度' not in df.columns:
        df['路面宽度'] = 7.0
    df['路面宽度'] = pd.to_numeric(df['路面宽度'], errors='coerce').fillna(7.0)

    # 添加道路类型
    df['道路类型'] = df['路线编码'].apply(get_road_type)

    results = []

    for _, row in df.iterrows():
        route = row.get('路线编码', '')
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        road_type = row.get('道路类型', '其他')
        seg_start = row.get('路段起点', '')
        seg_end = row.get('路段终点', '')

        # 计算目标年份的预测PQI
        years_ahead = target_year - 2025
        if years_ahead > 0:
            key = (ptype, tgrade)
            k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
            pqi_pred = exponential_decay_model(pqi0, k, years_ahead)
        else:
            pqi_pred = pqi0

        # 获取道路类型对应的目标
        target = get_target(road_type)
        target_pqi = target['PQI']
        target_good_rate = target['优良率']

        # 判断养护需求
        maint_type, reason = judge_maintenance(
            pqi_pred, pci0, rqi0, ptype, tgrade, thresholds
        )

        # 计算优先级分数（路况差→高优先级）
        priority_score = max(0, (90 - pqi_pred) / 90 * 100)

        results.append({
            '路线编码': route,
            '路段起点': seg_start,
            '路段终点': seg_end,
            '路段长度(km)': round(seg_length, 3),
            '道路类型': road_type,
            '路面类型': ptype,
            '技术等级': tgrade,
            '当前PQI': round(pqi0, 1),
            f'{target_year}年预测PQI': round(pqi_pred, 1),
            '目标PQI': target_pqi,
            'PQI差距': round(pqi_pred - target_pqi, 1),
            '养护类型': maint_type,
            '触发原因': reason,
            '优先级评分': round(priority_score, 1),
        })

    return pd.DataFrame(results)


def summarize_demand(demand_df: pd.DataFrame) -> Dict:
    """
    汇总养护需求统计

    参数:
        demand_df: 养护需求分析结果

    返回:
        需求统计字典
    """
    if demand_df is None or demand_df.empty:
        return {}

    # 按养护类型统计
    maint_type_stats = demand_df.groupby('养护类型').agg({
        '路段长度(km)': 'sum',
    }).to_dict()

    # 按道路类型统计
    road_type_stats = demand_df.groupby('道路类型').agg({
        '路段长度(km)': 'sum',
    }).to_dict()

    # 按路面类型统计
    pavement_type_stats = demand_df.groupby('路面类型').agg({
        '路段长度(km)': 'sum',
    }).to_dict()

    return {
        '总路段数': len(demand_df),
        '总里程(km)': round(demand_df['路段长度(km)'].sum(), 2),
        '路面改造里程(km)': round(maint_type_stats['路段长度(km)'].get('路面改造', 0), 2),
        '预防性养护里程(km)': round(maint_type_stats['路段长度(km)'].get('预防性养护', 0), 2),
        '日常养护里程(km)': round(maint_type_stats['路段长度(km)'].get('日常养护', 0), 2),
        '道路类型分布': road_type_stats['路段长度(km)'],
        '路面类型分布': pavement_type_stats['路段长度(km)'],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. 需求优先级排序
# ══════════════════════════════════════════════════════════════════════════════

def prioritize_demand(demand_df: pd.DataFrame,
                      criteria: List[str] = None,
                      weights: Dict = None) -> pd.DataFrame:
    """
    养护需求优先级排序

    参数:
        demand_df: 养护需求分析结果
        criteria: 排序标准列表 ['urgency', 'cost_effectiveness', 'safety']
                  - urgency: 紧迫性（基于PQI差距）
                  - cost_effectiveness: 费用效益（基于优先级评分）
                  - safety: 安全性（预留）
        weights: 各标准权重字典

    返回:
        按优先级排序的DataFrame
    """
    if demand_df is None or demand_df.empty:
        return pd.DataFrame()

    if criteria is None:
        criteria = ['urgency']

    if weights is None:
        weights = {'urgency': 0.7, 'cost_effectiveness': 0.3}

    df = demand_df.copy()

    # 计算综合优先级评分
    if 'urgency' in criteria:
        # 紧迫性：PQI差距越大优先级越高
        df['urgency_score'] = df['PQI差距'].apply(lambda x: max(0, -x) if x < 0 else 0)

    if 'cost_effectiveness' in criteria:
        # 费用效益：优先级评分（已在analyze_demand中计算）
        if '优先级评分' not in df.columns:
            df['优先级评分'] = df['当前PQI'].apply(lambda x: max(0, (90 - x) / 90 * 100))

    # 综合评分
    if len(criteria) == 1:
        df['综合优先级'] = df.get(f'{criteria[0]}_score', df.get('优先级评分', 0))
    else:
        df['综合优先级'] = 0
        for criterion in criteria:
            weight = weights.get(criterion, 0.5)
            score_col = f'{criterion}_score' if criterion != 'cost_effectiveness' else '优先级评分'
            df['综合优先级'] += df.get(score_col, 0) * weight

    # 按综合优先级降序排序
    df = df.sort_values('综合优先级', ascending=False)

    # 添加优先级排名
    df['优先级排名'] = range(1, len(df) + 1)

    return df


def filter_demand_by_year(demand_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """按年份筛选养护需求（仅返回该年份需要养护的路段）"""
    return demand_df[demand_df[f'{year}年预测PQI'].notna()]


def filter_demand_by_type(demand_df: pd.DataFrame, maint_type: str) -> pd.DataFrame:
    """按养护类型筛选"""
    return demand_df[demand_df['养护类型'] == maint_type]


def filter_demand_by_budget(demand_df: pd.DataFrame, budget: float,
                           unit_prices: Dict = None) -> pd.DataFrame:
    """
    按预算筛选可执行的养护需求

    参数:
        demand_df: 养护需求分析结果
        budget: 预算金额（万元）
        unit_prices: 单价字典 {养护类型: {路面类型: 元/m²}}

    返回:
        在预算范围内的需求DataFrame
    """
    if unit_prices is None:
        unit_prices = {
            '路面改造': {'沥青路面': 319, '水泥路面': 299},
            '预防性养护': {'沥青路面': 160, '水泥路面': 140},
            '日常养护': {'沥青路面': 30, '水泥路面': 25},
        }

    df = demand_df.copy()

    # 计算每个项目的估算费用
    def calc_cost(row):
        maint_type = row['养护类型']
        ptype = row['路面类型']
        length = row['路段长度(km)']
        width = row.get('路面宽度', 7)
        unit_price = unit_prices.get(maint_type, {}).get(ptype, 300)
        return length * 1000 * width * unit_price / 10000  # 万元

    df['估算费用(万元)'] = df.apply(calc_cost, axis=1)

    # 按优先级排序后累加
    df = df.sort_values('优先级排名' if '优先级排名' in df.columns else '综合优先级',
                       ascending=False)

    # 筛选预算内项目
    selected = []
    remaining = budget
    for _, row in df.iterrows():
        if row['估算费用(万元)'] <= remaining:
            selected.append(row['路线编码'])
            remaining -= row['估算费用(万元)']

    return df[df['路线编码'].isin(selected)]


# ══════════════════════════════════════════════════════════════════════════════
# 5. 多年养护需求预测
# ══════════════════════════════════════════════════════════════════════════════

def predict_multiyear_demand(df: pd.DataFrame,
                              years: List[int] = None,
                              targets: Dict = None,
                              decay_rates: Dict = None) -> pd.DataFrame:
    """
    预测多年养护需求

    参数:
        df: 包含当前路况数据的DataFrame
        years: 预测年份列表，默认为[2026,2027,2028,2029,2030]
        targets: 养护目标字典
        decay_rates: 衰减率字典

    返回:
        多年养护需求汇总DataFrame
    """
    if years is None:
        years = [2026, 2027, 2028, 2029, 2030]

    if df is None or df.empty:
        return pd.DataFrame()

    # 对每一年进行分析
    yearly_results = []
    for year in years:
        demand = analyze_demand(df, year, targets, decay_rates)
        if not demand.empty:
            yearly_results.append({
                '年份': year,
                '总里程(km)': demand['路段长度(km)'].sum(),
                '路面改造里程(km)': demand[demand['养护类型'] == '路面改造']['路段长度(km)'].sum(),
                '预防性养护里程(km)': demand[demand['养护类型'] == '预防性养护']['路段长度(km)'].sum(),
                '日常养护里程(km)': demand[demand['养护类型'] == '日常养护']['路段长度(km)'].sum(),
            })

    return pd.DataFrame(yearly_results)


# ══════════════════════════════════════════════════════════════════════════════
# 6. 优良路率分析
# ══════════════════════════════════════════════════════════════════════════════

def calculate_good_road_rate(df: pd.DataFrame,
                             road_type: str = None,
                             pqi_threshold: float = 80) -> Dict:
    """
    计算优良路率

    参数:
        df: 包含PQI数据的DataFrame
        road_type: 道路类型过滤，None表示全部
        pqi_threshold: PQI优良阈值，默认80

    返回:
        优良路率统计字典
    """
    if df is None or df.empty:
        return {}

    temp_df = df.copy()
    temp_df['PQI'] = pd.to_numeric(temp_df['PQI'], errors='coerce')

    if '路段长度km' not in temp_df.columns:
        temp_df['路段长度km'] = 1.0
    temp_df['路段长度km'] = pd.to_numeric(temp_df['路段长度km'], errors='coerce').fillna(1.0)

    if '路线编码' in temp_df.columns:
        temp_df['道路类型'] = temp_df['路线编码'].apply(get_road_type)

    if road_type:
        temp_df = temp_df[temp_df['道路类型'] == road_type]

    total_length = temp_df['路段长度km'].sum()
    good_length = temp_df[temp_df['PQI'] >= pqi_threshold]['路段长度km'].sum()
    excellent_length = temp_df[temp_df['PQI'] >= 90]['路段长度km'].sum()

    return {
        '总里程(km)': round(total_length, 2),
        '优良里程(km)': round(good_length, 2),
        '优等里程(km)': round(excellent_length, 2),
        '优良路率(%)': round(good_length / total_length * 100, 2) if total_length > 0 else 0,
        '优等路率(%)': round(excellent_length / total_length * 100, 2) if total_length > 0 else 0,
    }


def compare_with_target(df: pd.DataFrame, targets: Dict = None) -> pd.DataFrame:
    """
    比较当前优良路率与目标值

    参数:
        df: 包含路况数据的DataFrame
        targets: 养护目标字典

    返回:
        对比结果DataFrame
    """
    if targets is None:
        targets = MAINTENANCE_TARGETS

    results = []
    for road_type, target in targets.items():
        rate_info = calculate_good_road_rate(df, road_type)
        if rate_info:
            results.append({
                '道路类型': road_type,
                '总里程(km)': rate_info['总里程(km)'],
                '优良里程(km)': rate_info['优良里程(km)'],
                '当前优良路率(%)': rate_info['优良路率(%)'],
                '目标优良路率(%)': target['优良率'],
                '差距(%)': round(rate_info['优良路率(%)'] - target['优良率'], 2),
            })

    return pd.DataFrame(results)