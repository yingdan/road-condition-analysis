"""
效益评估模块
按《公路养护决策技术规范》第9章实现效益评估

功能：
1. 路况提升效益计算
2. 社会效益估算
3. 费用效益分析（CEA/CBA）
4. 综合效益评估报告
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# 1. 路况提升效益
# ══════════════════════════════════════════════════════════════════════════════

def road_condition_benefit(df_before: pd.DataFrame,
                           df_after: pd.DataFrame,
                           unit_value: float = 10000) -> Dict:
    """
    计算路况提升效益

    效益 = Σ(PQI提升值 × 里程 × 单位效益值)

    参数:
        df_before: 实施前路况数据
        df_after: 实施后路况数据
        unit_value: 单位效益值（元/公里·分），默认10000

    返回:
        路况提升效益字典
    """
    if df_before is None or df_after is None:
        return {}

    # 简化处理：假设df_before和df_after是同一批路段
    # 实际应用中需要按路线和桩号匹配

    if 'PQI' not in df_before.columns or 'PQI' not in df_after.columns:
        return {'error': '缺少PQI数据'}

    # 假设数据已按相同顺序排列
    pqi_before = df_before['PQI'].values
    pqi_after = df_after['PQI'].values

    if len(pqi_before) != len(pqi_after):
        return {'error': '数据长度不一致'}

    # 获取里程数据
    if '路段长度km' in df_before.columns:
        lengths = df_before['路段长度km'].values
    else:
        lengths = np.ones(len(pqi_before))

    # 计算提升值
    pqi_improvement = pqi_after - pqi_before

    # 只计算正效益（路况改善）
    positive_improvement = np.maximum(pqi_improvement, 0)

    # 计算总效益
    total_benefit = np.sum(positive_improvement * lengths) * unit_value / 10000  # 万元

    # 按路段分解
    segment_benefits = []
    for i in range(len(pqi_before)):
        benefit = positive_improvement[i] * lengths[i] * unit_value / 10000
        if benefit > 0:
            segment_benefits.append({
                '路段': df_before.iloc[i].get('路线编码', f'路段{i+1}'),
                'PQI变化': round(pqi_improvement[i], 1),
                '里程(km)': round(lengths[i], 3),
                '效益(万元)': round(benefit, 2),
            })

    return {
        '总效益(万元)': round(total_benefit, 2),
        '平均PQI提升': round(np.mean(positive_improvement), 2),
        '最大PQI提升': round(np.max(positive_improvement), 2),
        '改善路段数': np.sum(positive_improvement > 0),
        '各路段效益': pd.DataFrame(segment_benefits) if segment_benefits else pd.DataFrame(),
    }


def calculate_good_rate_benefit(df_before: pd.DataFrame,
                                 df_after: pd.DataFrame,
                                 threshold: float = 80) -> Dict:
    """
    计算优良路率提升带来的效益

    参数:
        df_before: 实施前路况数据
        df_after: 实施后路况数据
        threshold: PQI优良阈值

    返回:
        优良路率效益字典
    """
    if df_before is None or df_after is None:
        return {}

    def calc_good_rate(df):
        if 'PQI' not in df.columns:
            return 0, 0
        if '路段长度km' not in df.columns:
            return len(df[df['PQI'] >= threshold]), len(df)

        total_length = df['路段长度km'].sum()
        good_length = df[df['PQI'] >= threshold]['路段长度km'].sum()
        return good_length, total_length

    good_before, total_before = calc_good_rate(df_before)
    good_after, total_after = calc_good_rate(df_after)

    rate_before = good_before / total_before * 100 if total_before > 0 else 0
    rate_after = good_after / total_after * 100 if total_after > 0 else 0

    # 优良路率每提升1%，带来的社会效益（简化估算）
    # 实际应根据当地经济发展水平确定
    unit_rate_value = 100  # 万元/百分点

    benefit = (rate_after - rate_before) * unit_rate_value

    return {
        '实施前优良路率(%)': round(rate_before, 2),
        '实施后优良路率(%)': round(rate_after, 2),
        '优良路率提升(百分点)': round(rate_after - rate_before, 2),
        '优良路率效益(万元)': round(benefit, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. 社会效益估算
# ══════════════════════════════════════════════════════════════════════════════

def social_benefit(project: Dict,
                   traffic_volume: float = None,
                   road_length: float = None) -> Dict:
    """
    估算社会效益

    包括：
    - 事故减少效益
    - 出行时间节约效益
    - 车辆运营成本节约效益

    参数:
        project: 项目信息字典，包含PQI改善等
        traffic_volume: 日均交通量（辆/天），None则使用默认值
        road_length: 路段长度(km)

    返回:
        社会效益字典
    """
    if traffic_volume is None:
        traffic_volume = 5000  # 默认日均交通量
    if road_length is None:
        road_length = project.get('length', 1.0)

    # 简化估算参数
    # 实际应用中应根据当地统计数据确定

    # 1. 事故减少效益
    # 假设PQI每提升1分，事故率降低0.5%
    pqi_improvement = project.get('pqi_improvement', 0)
    accident_reduction_rate = pqi_improvement * 0.005  # 事故率降低比例
    base_accident_rate = 0.01  # 基准事故率（次/车·公里）
    accident_cost = 50000  # 每次事故平均损失（元）

    accident_benefit = (
        traffic_volume * 365 * road_length *
        base_accident_rate * accident_reduction_rate *
        accident_cost / 10000
    )

    # 2. 出行时间节约效益
    # 假设PQI每提升1分，行车速度提升0.5km/h
    speed_improvement = pqi_improvement * 0.5  # km/h
    average_trip_length = 50  # 平均出行距离(km)
    time_value = 20  # 时间价值（元/车·小时）
    occupancy = 1.5  # 平均载客数

    travel_time_benefit = (
        traffic_volume * 365 *
        (average_trip_length / (60 + speed_improvement) - average_trip_length / 60) *
        time_value * occupancy / 10000
    )

    # 3. 车辆运营成本节约效益
    # 假设PQI每提升1分，车辆运营成本降低0.3%
    vehicle_cost_reduction_rate = pqi_improvement * 0.003
    base_vehicle_cost = 0.5  # 基准车辆运营成本（元/车·公里）

    vehicle_cost_benefit = (
        traffic_volume * 365 * road_length *
        base_vehicle_cost * vehicle_cost_reduction_rate / 10000
    )

    return {
        '事故减少效益(万元)': round(accident_benefit, 2),
        '出行时间节约效益(万元)': round(travel_time_benefit, 2),
        '车辆运营成本节约效益(万元)': round(vehicle_cost_benefit, 2),
        '总社会效益(万元)': round(accident_benefit + travel_time_benefit + vehicle_cost_benefit, 2),
        '年均社会效益(万元/年)': round((accident_benefit + travel_time_benefit + vehicle_cost_benefit) / 5, 2),
    }


def estimate_user_benefits(df: pd.DataFrame,
                           pqi_before: str = 'PQI_before',
                           pqi_after: str = 'PQI_after') -> pd.DataFrame:
    """
    估算用户效益（逐路段）

    参数:
        df: 包含路况数据的DataFrame
        pqi_before: 实施前PQI列名
        pqi_after: 实施后PQI列名

    返回:
        用户效益DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if pqi_before not in df.columns or pqi_after not in df.columns:
        return pd.DataFrame({'error': '缺少PQI数据列'})

    results = []

    for _, row in df.iterrows():
        pqi_b = row[pqi_before]
        pqi_a = row[pqi_after]
        length = row.get('路段长度km', 1.0)

        pqi_improvement = pqi_a - pqi_b

        if pqi_improvement <= 0:
            continue

        benefits = social_benefit(
            {'pqi_improvement': pqi_improvement, 'length': length}
        )

        results.append({
            '路线编码': row.get('路线编码', ''),
            '路段起点': row.get('路段起点', ''),
            '路段终点': row.get('路段终点', ''),
            'PQI提升': round(pqi_improvement, 1),
            '事故减少效益(万元)': benefits['事故减少效益(万元)'],
            '时间节约效益(万元)': benefits['出行时间节约效益(万元)'],
            '成本节约效益(万元)': benefits['车辆运营成本节约效益(万元)'],
            '总效益(万元)': benefits['总社会效益(万元)'],
        })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 3. 费用效益分析
# ══════════════════════════════════════════════════════════════════════════════

def cost_effectiveness_analysis(project_list: List[Dict]) -> pd.DataFrame:
    """
    费用效果分析（CEA）

    计算各项目的单位费用效果
    CEA = 效果 / 费用

    参数:
        project_list: 项目列表，每个项目包含：
            - name: 项目名称
            - cost: 费用（万元）
            - effect: 效果（如PQI提升×里程）

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
            '费用(万元)': round(cost, 2),
            '效果': round(effect, 2),
            'CEA': round(cea, 4),
            '排序': 0,
        })

    # 按CEA排序
    results = sorted(results, key=lambda x: x['CEA'], reverse=True)
    for i, r in enumerate(results):
        r['排序'] = i + 1

    # 添加汇总行
    overall_cea = total_effect / total_cost if total_cost > 0 else 0
    results.append({
        '项目名称': '合计',
        '费用(万元)': round(total_cost, 2),
        '效果': round(total_effect, 2),
        'CEA': round(overall_cea, 4),
        '排序': '-',
    })

    return pd.DataFrame(results)


def cost_benefit_ratio(project_cost: float,
                       project_benefits: Dict,
                       discount_rate: float = 0.05) -> Dict:
    """
    计算费用效益比（B/C）

    B/C = 效益现值 / 费用现值

    参数:
        project_cost: 项目费用（万元）
        project_benefits: 项目逐年效益字典 {年份: 效益(万元)}
        discount_rate: 折现率

    返回:
        B/C分析结果
    """
    if not project_benefits:
        return {'error': '无效益数据'}

    # 计算效益现值
    pv_benefits = 0
    for year, benefit in project_benefits.items():
        discount_factor = 1 / (1 + discount_rate) ** year
        pv_benefits += benefit * discount_factor

    # 计算费用现值（项目费用作为初始投资）
    pv_cost = project_cost

    # B/C比
    bcr = pv_benefits / pv_cost if pv_cost > 0 else 0

    # 净效益
    net_benefit = pv_benefits - pv_cost

    return {
        '费用现值(万元)': round(pv_cost, 2),
        '效益现值(万元)': round(pv_benefits, 2),
        '净效益(万元)': round(net_benefit, 2),
        'B/C比': round(bcr, 2),
        '评价': '可行' if bcr >= 1 else '不可行',
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. 综合效益评估
# ══════════════════════════════════════════════════════════════════════════════

def comprehensive_benefit_evaluation(projects: List[Dict],
                                      df_before: pd.DataFrame = None,
                                      df_after: pd.DataFrame = None) -> Dict:
    """
    综合效益评估

    综合考虑：
    - 路况提升效益
    - 社会效益
    - 费用效益

    参数:
        projects: 项目列表
        df_before: 实施前路况数据
        df_after: 实施后路况数据

    返回:
        综合评估结果
    """
    if not projects:
        return {}

    # 计算各项效益
    total_road_condition_benefit = 0
    total_social_benefit = 0
    total_cost = 0

    for proj in projects:
        cost = proj.get('cost', proj.get('估算费用(万元)', 0))
        total_cost += cost

        # 路况提升效益
        pqi_improvement = proj.get('pqi_improvement', 0)
        length = proj.get('length', proj.get('路段长度(km)', 1.0))
        road_benefit = pqi_improvement * length * 10000 / 10000  # 万元
        total_road_condition_benefit += road_benefit

        # 社会效益
        social = social_benefit(proj)
        total_social_benefit += social.get('总社会效益(万元)', 0)

    # 汇总
    total_benefit = total_road_condition_benefit + total_social_benefit

    return {
        '总投资(万元)': round(total_cost, 2),
        '路况提升效益(万元)': round(total_road_condition_benefit, 2),
        '社会效益(万元)': round(total_social_benefit, 2),
        '总效益(万元)': round(total_benefit, 2),
        '费用效益比': round(total_benefit / total_cost, 2) if total_cost > 0 else 0,
        '效益成本比': round(total_benefit / total_cost, 2) if total_cost > 0 else 0,
        '评价': '优秀' if total_benefit / total_cost > 1.5 else ('良好' if total_benefit / total_cost > 1 else '一般'),
    }


def generate_benefit_report(project_pool,
                             df_before: pd.DataFrame = None,
                             df_after: pd.DataFrame = None) -> pd.DataFrame:
    """
    生成效益评估报告

    参数:
        project_pool: 项目库
        df_before: 实施前路况数据
        df_after: 实施后路况数据

    返回:
        效益报告DataFrame
    """
    if project_pool is None or not project_pool.projects:
        return pd.DataFrame()

    results = []

    for p in project_pool.projects:
        # 计算该项目的效益
        pqi_before = p.current_condition.get('PQI', 80)
        pqi_after = 90  # 假设养护后PQI达到90

        pqi_improvement = pqi_after - pqi_before

        # 路况效益
        road_benefit = pqi_improvement * p.length * 10000 / 10000

        # 社会效益
        social = social_benefit({'pqi_improvement': pqi_improvement, 'length': p.length})

        # 综合评价
        total_benefit = road_benefit + social.get('总社会效益(万元)', 0)

        results.append({
            '项目编号': p.project_id,
            '路线编码': p.route_code,
            '养护类型': p.maintenance_type,
            '计划年度': p.maintenance_year,
            '投资(万元)': p.estimated_cost,
            '路况效益(万元)': round(road_benefit, 2),
            '社会效益(万元)': social.get('总社会效益(万元)', 0),
            '总效益(万元)': round(total_benefit, 2),
            'B/C比': round(total_benefit / p.estimated_cost, 2) if p.estimated_cost else 0,
        })

    report_df = pd.DataFrame(results)

    # 添加汇总行
    if not report_df.empty:
        summary = {
            '项目编号': '合计',
            '路线编码': '',
            '养护类型': '',
            '计划年度': '',
            '投资(万元)': report_df['投资(万元)'].sum(),
            '路况效益(万元)': report_df['路况效益(万元)'].sum(),
            '社会效益(万元)': report_df['社会效益(万元)'].sum(),
            '总效益(万元)': report_df['总效益(万元)'].sum(),
            'B/C比': round(report_df['总效益(万元)'].sum() / report_df['投资(万元)'].sum(), 2)
                    if report_df['投资(万元)'].sum() > 0 else 0,
        }
        report_df = pd.concat([report_df, pd.DataFrame([summary])], ignore_index=True)

    return report_df


# ══════════════════════════════════════════════════════════════════════════════
# 5. 效益对比分析
# ══════════════════════════════════════════════════════════════════════════════

def compare_benefits_by_type(project_pool: 'ProjectPool') -> pd.DataFrame:
    """
    按养护类型对比效益

    参数:
        project_pool: 项目库

    返回:
        按类型对比DataFrame
    """
    if project_pool is None or not project_pool.projects:
        return pd.DataFrame()

    type_stats = {}

    for p in project_pool.projects:
        mtype = p.maintenance_type
        if mtype not in type_stats:
            type_stats[mtype] = {
                'count': 0,
                'cost': 0,
                'length': 0,
                'benefit': 0,
            }

        pqi_improvement = 90 - p.current_condition.get('PQI', 80)
        road_benefit = pqi_improvement * p.length * 10000 / 10000
        social = social_benefit({'pqi_improvement': pqi_improvement, 'length': p.length})

        type_stats[mtype]['count'] += 1
        type_stats[mtype]['cost'] += p.estimated_cost or 0
        type_stats[mtype]['length'] += p.length or 0
        type_stats[mtype]['benefit'] += road_benefit + social.get('总社会效益(万元)', 0)

    results = []
    for mtype, stats in type_stats.items():
        results.append({
            '养护类型': mtype,
            '项目数': stats['count'],
            '投资(万元)': round(stats['cost'], 2),
            '里程(km)': round(stats['length'], 2),
            '效益(万元)': round(stats['benefit'], 2),
            'B/C比': round(stats['benefit'] / stats['cost'], 2) if stats['cost'] > 0 else 0,
            '单位投资效益': round(stats['benefit'] / stats['length'], 2) if stats['length'] > 0 else 0,
        })

    return pd.DataFrame(results)


def compare_benefits_by_year(project_pool: 'ProjectPool',
                              years: List[int] = None) -> pd.DataFrame:
    """
    按年份对比效益

    参数:
        project_pool: 项目库
        years: 年份列表，None则使用所有年份

    返回:
        按年份对比DataFrame
    """
    if project_pool is None or not project_pool.projects:
        return pd.DataFrame()

    if years is None:
        years = sorted(set(p.maintenance_year for p in project_pool.projects if p.maintenance_year))

    results = []

    for year in years:
        year_projects = [p for p in project_pool.projects if p.maintenance_year == year]

        total_cost = sum(p.estimated_cost or 0 for p in year_projects)
        total_length = sum(p.length or 0 for p in year_projects)

        total_benefit = 0
        for p in year_projects:
            pqi_improvement = 90 - p.current_condition.get('PQI', 80)
            road_benefit = pqi_improvement * p.length * 10000 / 10000
            social = social_benefit({'pqi_improvement': pqi_improvement, 'length': p.length})
            total_benefit += road_benefit + social.get('总社会效益(万元)', 0)

        results.append({
            '年份': year,
            '项目数': len(year_projects),
            '投资(万元)': round(total_cost, 2),
            '里程(km)': round(total_length, 2),
            '效益(万元)': round(total_benefit, 2),
            'B/C比': round(total_benefit / total_cost, 2) if total_cost > 0 else 0,
        })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 6. 效益评估汇总表
# ══════════════════════════════════════════════════════════════════════════════

def generate_summary_table(project_pool: 'ProjectPool') -> pd.DataFrame:
    """
    生成效益评估汇总表

    参数:
        project_pool: 项目库

    返回:
        汇总表DataFrame
    """
    if project_pool is None or not project_pool.projects:
        return pd.DataFrame()

    # 按养护类型汇总
    by_type = compare_benefits_by_type(project_pool)

    # 按年份汇总
    by_year = compare_benefits_by_year(project_pool)

    # 总计
    total_cost = sum(p.estimated_cost or 0 for p in project_pool.projects)
    total_length = sum(p.length or 0 for p in project_pool.projects)
    total_benefit = 0

    for p in project_pool.projects:
        pqi_improvement = 90 - p.current_condition.get('PQI', 80)
        road_benefit = pqi_improvement * p.length * 10000 / 10000
        social = social_benefit({'pqi_improvement': pqi_improvement, 'length': p.length})
        total_benefit += road_benefit + social.get('总社会效益(万元)', 0)

    summary = pd.DataFrame([{
        '汇总项': '总计',
        '项目数': len(project_pool.projects),
        '投资(万元)': round(total_cost, 2),
        '里程(km)': round(total_length, 2),
        '效益(万元)': round(total_benefit, 2),
        'B/C比': round(total_benefit / total_cost, 2) if total_cost > 0 else 0,
    }])

    return summary