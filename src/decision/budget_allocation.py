"""
资金优化分配模块
按《公路养护决策技术规范》附录G实现资金优化分配方法

功能：
1. 优先序法
2. 增量分析法
3. 多目标优化（简化版线性规划）
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# 1. 优先序法
# ══════════════════════════════════════════════════════════════════════════════

def priority_allocation(demand_list: List[Dict],
                        budget: float,
                        priority_key: str = '优先级评分') -> Tuple[List[Dict], Dict]:
    """
    优先序法资金分配

    按项目优先级从高到低分配资金，直到预算用完

    参数:
        demand_list: 养护需求列表，每个元素包含：
            - route_code: 路线编码
            - length: 长度(km)
            - cost: 费用(万元)
            - priority_score: 优先级评分
            - maintenance_type: 养护类型
        budget: 可用预算（万元）
        priority_key: 优先级字段名

    返回:
        (已分配项目列表, 分配结果摘要)
    """
    if not demand_list:
        return [], {'总需求': 0, '已分配': 0, '满足率': 0}

    # 按优先级降序排序
    sorted_demand = sorted(
        demand_list,
        key=lambda x: x.get(priority_key, 0),
        reverse=True
    )

    allocated = []
    remaining = budget
    total_cost = 0

    for item in sorted_demand:
        item_cost = item.get('cost', 0)
        if item_cost <= remaining:
            allocated.append(item)
            remaining -= item_cost
            total_cost += item_cost

    summary = {
        '总需求项目数': len(demand_list),
        '已分配项目数': len(allocated),
        '总需求(万元)': sum(d.get('cost', 0) for d in demand_list),
        '已分配(万元)': round(total_cost, 2),
        '剩余预算(万元)': round(remaining, 2),
        '满足率(%)': round(len(allocated) / len(demand_list) * 100, 1) if demand_list else 0,
    }

    return allocated, summary


def priority_allocation_by_type(demand_df: pd.DataFrame,
                                 budget: float,
                                 priority_ratio: Dict[str, float] = None) -> Dict:
    """
    按养护类型分配资金的优先序法

    参数:
        demand_df: 养护需求DataFrame，需包含列：
            - 养护类型
            - 估算费用(万元)
            - 优先级评分
        budget: 总预算（万元）
        priority_ratio: 各养护类型预算占比 {'路面改造': 0.6, '预防性养护': 0.3, '日常养护': 0.1}

    返回:
        分配结果字典
    """
    if demand_df is None or demand_df.empty:
        return {}

    if priority_ratio is None:
        priority_ratio = {
            '路面改造': 0.6,
            '预防性养护': 0.3,
            '日常养护': 0.1,
        }

    results = {}
    remaining_budget = budget

    for maint_type in ['路面改造', '预防性养护', '日常养护']:
        type_df = demand_df[demand_df['养护类型'] == maint_type].copy()

        if type_df.empty:
            results[maint_type] = {
                '分配预算(万元)': 0,
                '需求金额(万元)': 0,
                '满足程度': '无需求',
            }
            continue

        # 该类型分配的预算
        type_budget = budget * priority_ratio.get(maint_type, 0)
        type_cost = type_df['估算费用(万元)'].sum()

        # 按优先级排序后分配
        type_df = type_df.sort_values('优先级评分', ascending=False)
        allocated_cost = 0
        allocated_items = []

        for _, row in type_df.iterrows():
            item_cost = row['估算费用(万元)']
            if allocated_cost + item_cost <= type_budget:
                allocated_cost += item_cost
                allocated_items.append(row.to_dict())

        results[maint_type] = {
            '分配预算(万元)': round(allocated_cost, 2),
            '需求金额(万元)': round(type_cost, 2),
            '满足程度(%)': round(allocated_cost / type_cost * 100, 1) if type_cost > 0 else 0,
            '已分配项目数': len(allocated_items),
        }

        remaining_budget -= allocated_cost

    # 总计
    total_allocated = sum(r['分配预算(万元)'] for r in results.values())
    total_demand = demand_df['估算费用(万元)'].sum()
    results['总计'] = {
        '分配预算(万元)': round(total_allocated, 2),
        '需求金额(万元)': round(total_demand, 2),
        '满足程度(%)': round(total_allocated / total_demand * 100, 1) if total_demand > 0 else 0,
        '剩余预算(万元)': round(remaining_budget, 2),
    }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 2. 增量分析法
# ══════════════════════════════════════════════════════════════════════════════

def incremental_analysis(demand_list: List[Dict],
                         budget: float,
                         benefit_key: str = 'effect') -> Dict:
    """
    增量分析法资金分配

    通过分析增加投资带来的边际效益来优化分配

    参数:
        demand_list: 养护需求列表，每个元素包含：
            - cost: 费用(万元)
            - effect: 效益（如PQI提升×里程）
        budget: 总预算（万元）
        benefit_key: 效益字段名

    返回:
        优化分配结果
    """
    if not demand_list:
        return {}

    # 计算各项目的效益费用比
    for item in demand_list:
        cost = item.get('cost', 0)
        effect = item.get(benefit_key, 0)
        item['效益费用比'] = effect / cost if cost > 0 else 0

    # 按效益费用比降序排序
    sorted_demand = sorted(
        demand_list,
        key=lambda x: x.get('效益费用比', 0),
        reverse=True
    )

    # 贪婪选择
    allocated = []
    remaining = budget
    total_effect = 0

    for item in sorted_demand:
        cost = item.get('cost', 0)
        if cost <= remaining:
            allocated.append(item)
            remaining -= cost
            total_effect += item.get(benefit_key, 0)

    # 计算边际效益
    if allocated:
        avg_effectiveness = total_effect / sum(a.get('cost', 0) for a in allocated)
    else:
        avg_effectiveness = 0

    return {
        '已分配项目': allocated,
        '已分配金额(万元)': round(budget - remaining, 2),
        '剩余预算(万元)': round(remaining, 2),
        '总效益': round(total_effect, 2),
        '平均效益费用比': round(avg_effectiveness, 4),
    }


def calculate_marginal_benefit(project: Dict,
                                baseline: pd.DataFrame,
                                target: float) -> float:
    """
    计算项目的边际效益

    边际效益 = 项目实施后路况改善带来的社会效益价值

    参数:
        project: 项目信息
        baseline: 基准路况DataFrame
        target: 目标指标值

    返回:
        边际效益值
    """
    # 简化计算：边际效益 = PQI提升值 × 里程 × 单位效益系数
    pqi_improvement = project.get('pqi_improvement', 0)
    length = project.get('length', 1)
    unit_benefit = 10000  # 元/公里·分

    return pqi_improvement * length * unit_benefit / 10000  # 万元


# ══════════════════════════════════════════════════════════════════════════════
# 3. 多目标优化（简化版线性规划）
# ══════════════════════════════════════════════════════════════════════════════

def multi_objective_optimization(demand_list: List[Dict],
                                  budget: float,
                                  targets: Dict = None) -> Dict:
    """
    多目标优化资金分配（简化版）

    目标：
    1. 最大化优良路率
    2. 最小化总费用
    3. 满足最低优先级项目需求

    使用贪心算法模拟优化过程

    参数:
        demand_list: 养护需求列表
        budget: 总预算（万元）
        targets: 养护目标字典

    返回:
        优化分配结果
    """
    if not demand_list:
        return {}

    if targets is None:
        targets = {
            '路面改造': 0.4,  # 路面改造至少占40%
            '预防性养护': 0.4,  # 预防性养护至少占40%
        }

    # 计算总需求
    total_demand = sum(d.get('cost', 0) for d in demand_list)

    # 按类型分组
    by_type = {}
    for item in demand_list:
        maint_type = item.get('养护类型', '日常养护')
        if maint_type not in by_type:
            by_type[maint_type] = []
        by_type[maint_type].append(item)

    # 按目标约束分配
    allocated = []
    remaining = budget

    # 第一轮：满足各类型最低比例要求
    for maint_type, min_ratio in targets.items():
        min_budget = budget * min_ratio
        type_items = by_type.get(maint_type, [])

        if not type_items:
            continue

        # 按优先级排序
        type_items = sorted(
            type_items,
            key=lambda x: x.get('优先级评分', 0),
            reverse=True
        )

        # 分配满足最低比例的资金
        allocated_cost = 0
        type_allocated = []

        for item in type_items:
            cost = item.get('cost', 0)
            if allocated_cost + cost <= min_budget and remaining >= cost:
                type_allocated.append(item)
                allocated_cost += cost
                remaining -= cost

        allocated.extend(type_allocated)

    # 第二轮：将剩余资金分配给效益最高的项目
    unallocated = [d for d in demand_list if d not in allocated]
    unallocated = sorted(
        unallocated,
        key=lambda x: x.get('效益费用比', x.get('优先级评分', 0)),
        reverse=True
    )

    for item in unallocated:
        cost = item.get('cost', 0)
        if cost <= remaining:
            allocated.append(item)
            remaining -= cost

    # 生成结果
    total_cost = sum(a.get('cost', 0) for a in allocated)
    type_summary = {}
    for item in allocated:
        maint_type = item.get('养护类型', '其他')
        type_summary[maint_type] = type_summary.get(maint_type, 0) + item.get('cost', 0)

    return {
        '已分配项目': allocated,
        '已分配金额(万元)': round(total_cost, 2),
        '剩余预算(万元)': round(remaining, 2),
        '预算使用率(%)': round(total_cost / budget * 100, 1) if budget > 0 else 0,
        '按类型分配(万元)': {k: round(v, 2) for k, v in type_summary.items()},
    }


def optimize_allocation_knapsack(demand_list: List[Dict],
                                  budget: float,
                                  objective: str = 'effect') -> Dict:
    """
    0-1背包模型优化分配

    将资金分配问题建模为背包问题：
    - 背包容量 = 预算
    - 物品 = 养护项目
    - 物品重量 = 项目费用
    - 物品价值 = 效益或优先级

    参数:
        demand_list: 养护需求列表
        budget: 总预算（万元）
        objective: 优化目标 ('effect'/'priority')

    返回:
        最优分配方案
    """
    if not demand_list:
        return {}

    # 简化的贪心算法
    # 按价值/重量比排序
    for item in demand_list:
        weight = item.get('cost', 0)
        if objective == 'effect':
            value = item.get('effect', item.get('优先级评分', 0) * item.get('cost', 1))
        else:
            value = item.get('优先级评分', 0) * item.get('cost', 1)

        item['价值'] = value
        item['价值重量比'] = value / weight if weight > 0 else 0

    # 按价值重量比降序排序
    sorted_items = sorted(
        demand_list,
        key=lambda x: x.get('价值重量比', 0),
        reverse=True
    )

    # 贪心选择
    allocated = []
    remaining = budget

    for item in sorted_items:
        cost = item.get('cost', 0)
        if cost <= remaining:
            allocated.append(item)
            remaining -= cost

    return {
        'allocated': allocated,
        'total_cost': round(sum(a.get('cost', 0) for a in allocated), 2),
        'remaining': round(remaining, 2),
        'total_value': round(sum(a.get('价值', 0) for a in allocated), 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. 预算敏感性分析
# ══════════════════════════════════════════════════════════════════════════════

def sensitivity_analysis(demand_df: pd.DataFrame,
                         budget_range: List[float],
                         unit_prices: Dict = None) -> pd.DataFrame:
    """
    预算敏感性分析

    分析不同预算水平下的项目满足程度

    参数:
        demand_df: 养护需求DataFrame
        budget_range: 预算范围列表（万元）
        unit_prices: 单价字典

    返回:
        敏感性分析结果DataFrame
    """
    if demand_df is None or demand_df.empty:
        return pd.DataFrame()

    results = []
    total_demand = demand_df['估算费用(万元)'].sum()

    for budget in budget_range:
        # 使用优先序法分配
        allocated, summary = priority_allocation(
            demand_df.to_dict('records'),
            budget,
            priority_key='优先级评分'
        )

        # 计算满足程度
        allocated_cost = budget - summary['剩余预算(万元)']
        satisfaction = allocated_cost / total_demand * 100 if total_demand > 0 else 0

        results.append({
            '预算(万元)': budget,
            '需求(万元)': round(total_demand, 2),
            '满足(万元)': round(allocated_cost, 2),
            '满足率(%)': round(satisfaction, 1),
            '剩余(万元)': round(summary['剩余预算(万元)'], 2),
        })

    return pd.DataFrame(results)


def find_budget_breakeven(demand_df: pd.DataFrame,
                           target_satisfaction: float = 0.8) -> float:
    """
    寻找达到目标满足率所需的最低预算（盈亏平衡点）

    参数:
        demand_df: 养护需求DataFrame
        target_satisfaction: 目标满足率（0-1）

    返回:
        最低预算（万元）
    """
    if demand_df is None or demand_df.empty:
        return 0

    total_demand = demand_df['估算费用(万元)'].sum()
    target_budget = total_demand * target_satisfaction

    return round(target_budget, 2)


# ══════════════════════════════════════════════════════════════════════════════
# 5. 综合分配方案生成
# ══════════════════════════════════════════════════════════════════════════════

def generate_allocation_plan(demand_df: pd.DataFrame,
                               budget: float,
                               method: str = 'priority') -> Dict:
    """
    生成综合资金分配方案

    参数:
        demand_df: 养护需求DataFrame
        budget: 总预算（万元）
        method: 分配方法 ('priority'/'incremental'/'optimization')

    返回:
        分配方案字典
    """
    if demand_df is None or demand_df.empty:
        return {'error': '无养护需求数据'}

    if method == 'priority':
        allocated, summary = priority_allocation(
            demand_df.to_dict('records'),
            budget,
            priority_key='优先级评分'
        )
        return {
            'method': '优先序法',
            'allocated_projects': pd.DataFrame(allocated) if allocated else pd.DataFrame(),
            'summary': summary,
        }

    elif method == 'incremental':
        return incremental_analysis(
            demand_df.to_dict('records'),
            budget
        )

    elif method == 'optimization':
        return multi_objective_optimization(
            demand_df.to_dict('records'),
            budget
        )

    else:
        return {'error': f'未知分配方法: {method}'}


def export_allocation_report(allocation_result: Dict,
                              demand_df: pd.DataFrame,
                              output_path: str = None) -> pd.DataFrame:
    """
    导出资金分配报告

    参数:
        allocation_result: 分配结果
        demand_df: 原始需求DataFrame
        output_path: 输出文件路径

    返回:
        报告DataFrame
    """
    if not allocation_result or allocation_result.get('error'):
        return pd.DataFrame()

    report_data = []

    # 添加已分配项目
    if 'allocated_projects' in allocation_result:
        allocated_df = allocation_result['allocated_projects']
        if not allocated_df.empty:
            for _, row in allocated_df.iterrows():
                report_data.append({
                    '项目类型': '已分配',
                    '路线编码': row.get('路线编码', ''),
                    '养护类型': row.get('养护类型', ''),
                    '费用(万元)': row.get('cost', row.get('估算费用(万元)', 0)),
                    '优先级': row.get('优先级评分', 0),
                })

    # 添加汇总信息
    if 'summary' in allocation_result:
        summary = allocation_result['summary']
        report_data.append({
            '项目类型': '汇总',
            '路线编码': f"总需求: {summary.get('总需求项目数', 0)}个",
            '养护类型': f"已分配: {summary.get('已分配项目数', 0)}个",
            '费用(万元)': summary.get('已分配(万元)', 0),
            '优先级': f"满足率: {summary.get('满足率(%)', 0)}%",
        })

    report_df = pd.DataFrame(report_data)

    if output_path and not report_df.empty:
        report_df.to_excel(output_path, index=False)

    return report_df