"""
动态衰减率计算模块
基于用户实际加载的数据，计算PQI/PCI/RQI的衰减系数
支持按县分别计算
"""
import pandas as pd
import numpy as np
import warnings
import re
warnings.filterwarnings('ignore')


def _parse_km_value(value: str) -> float:
    """
    解析路段起终点的公里值
    支持格式：K10+000, 10+000, 10, 10.0, K10.000等
    返回公里数（如K10+500返回10.5）
    """
    if not value:
        return None
    
    value = str(value).strip().upper()
    
    value = re.sub(r'[^0-9.+K]', '', value)
    
    if 'K' in value:
        value = value.replace('K', '')
    
    if '+' in value:
        parts = value.split('+')
        if len(parts) == 2:
            try:
                km = float(parts[0])
                m = float(parts[1]) / 1000
                return km + m
            except ValueError:
                pass
    
    try:
        return float(value)
    except ValueError:
        return None


def _segments_overlap(seg_start: float, seg_end: float, plan_start: float, plan_end: float) -> bool:
    """
    判断两个路段范围是否重叠
    seg_start, seg_end: 数据中路段的起终点（公里值）
    plan_start, plan_end: 手动规划的路段起终点（公里值）
    """
    if seg_start is None or seg_end is None or plan_start is None or plan_end is None:
        return False
    
    seg_min = min(seg_start, seg_end)
    seg_max = max(seg_start, seg_end)
    plan_min = min(plan_start, plan_end)
    plan_max = max(plan_start, plan_end)
    
    return plan_min < seg_max and plan_max > seg_min


def _calculate_overlap_ratio(seg_start: float, seg_end: float, plan_start: float, plan_end: float) -> float:
    """
    计算手动规划路段与数据路段的重叠比例
    返回重叠长度占数据路段总长度的比例（0.0-1.0）
    """
    if seg_start is None or seg_end is None or plan_start is None or plan_end is None:
        return 0.0
    
    seg_min = min(seg_start, seg_end)
    seg_max = max(seg_start, seg_end)
    plan_min = min(plan_start, plan_end)
    plan_max = max(plan_start, plan_end)
    
    overlap_start = max(seg_min, plan_min)
    overlap_end = min(seg_max, plan_max)
    
    if overlap_end <= overlap_start:
        return 0.0
    
    seg_length = seg_max - seg_min
    if seg_length <= 0:
        return 0.0
    
    overlap_length = overlap_end - overlap_start
    return overlap_length / seg_length


def _fuzzy_match_segment(segment_value: str, plan_value: str) -> bool:
    """
    模糊匹配路段起终点（用于单端匹配，如只填起点或只填终点）
    """
    if not plan_value:
        return False
    
    segment_value = str(segment_value).strip()
    plan_value = str(plan_value).strip()
    
    if not segment_value:
        return False
    
    if segment_value == plan_value:
        return True
    
    if plan_value in segment_value or segment_value in plan_value:
        return True
    
    segment_numbers = re.findall(r'[\d.]+', segment_value)
    plan_numbers = re.findall(r'[\d.]+', plan_value)
    
    if segment_numbers and plan_numbers:
        for seg_num in segment_numbers:
            for plan_num in plan_numbers:
                try:
                    seg_float = float(seg_num)
                    plan_float = float(plan_num)
                    if abs(seg_float - plan_float) < 0.1:
                        return True
                except ValueError:
                    continue
    
    segment_clean = re.sub(r'[\s,.，。、-]+', '', segment_value)
    plan_clean = re.sub(r'[\s,.，。、-]+', '', plan_value)
    
    if segment_clean == plan_clean:
        return True
    
    if plan_clean in segment_clean or segment_clean in plan_clean:
        return True
    
    return False


# 养护类型和单价
MAINTENANCE_TYPES = {
    '路面改造': {'单价': {'沥青路面': 319, '水泥路面': 299}, 'threshold': 70},
    '预防性养护': {'单价': {'沥青路面': 160, '水泥路面': 140}, 'threshold': 80},
}
# 日常养护阈值
DAILY_THRESHOLD = 85

# 养护后PQI回调值（可手动调整）
# 格式：{养护类型: {路面类型: (PQI回调值, PCI回调值, RQI回调值)}}
MAINTENANCE_CALLBACK = {
    '路面改造': {
        '沥青路面': {'PQI': 92, 'PCI': 92, 'RQI': 93},
        '水泥路面': {'PQI': 88, 'PCI': 88, 'RQI': 90},
    },
    '预防性养护': {
        '沥青路面': {'PQI': 89, 'PCI': 89, 'RQI': 91},
        '水泥路面': {'PQI': 86, 'PCI': 86, 'RQI': 88},
    },
}


def set_maintenance_callback(callback_config: dict = None):
    """
    设置养护后PQI回调值
    参数: callback_config 字典，格式如：
    {
        '路面改造': {'沥青路面': {'PQI': 92, 'PCI': 92, 'RQI': 93}, '水泥路面': {...}},
        '预防性养护': {'沥青路面': {...}, '水泥路面': {...}}
    }
    如果为None，则重置为默认值
    """
    global MAINTENANCE_CALLBACK
    if callback_config is None:
        # 重置为默认值
        MAINTENANCE_CALLBACK = {
            '路面改造': {
                '沥青路面': {'PQI': 92, 'PCI': 92, 'RQI': 93},
                '水泥路面': {'PQI': 88, 'PCI': 88, 'RQI': 90},
            },
            '预防性养护': {
                '沥青路面': {'PQI': 89, 'PCI': 89, 'RQI': 91},
                '水泥路面': {'PQI': 86, 'PCI': 86, 'RQI': 88},
            },
        }
    else:
        MAINTENANCE_CALLBACK = callback_config


def get_maintenance_callback() -> dict:
    """获取当前养护回调值配置"""
    return MAINTENANCE_CALLBACK


# ══════════════════════════════════════════════
# 养护触发模型参数（可配置）
# ══════════════════════════════════════════════

# 默认养护触发模型参数
DEFAULT_TRIGGER_MODEL = {
    '启用': True,
    '年度配置': {  # 新增：按年份设置是否启用养护触发
        2026: True,
        2027: True,
        2028: True,
        2029: True,
        2030: True,
    },
    '路面改造': {
        '沥青路面': {
            '一级公路': {'PCI': 80, 'PCI启用': True, 'PQI': 80, 'PQI启用': True, 'RQI': 80, 'RQI启用': True},
            '二级及以下': {'PCI': 75, 'PCI启用': True, 'PQI': 75, 'PQI启用': True, 'RQI': 75, 'RQI启用': True},
        },
        '水泥路面': {
            '一级公路': {'PCI': 80, 'PCI启用': True, 'PQI': 80, 'PQI启用': True, 'RQI': 80, 'RQI启用': False},
            '二级及以下': {'PCI': 75, 'PCI启用': True, 'PQI': 75, 'PQI启用': True, 'RQI': 75, 'RQI启用': False},
        },
    },
    '预防性养护': {
        '沥青路面': {
            '一级公路': {'PCI低': 80, 'PCI高': 90, 'PCI启用': True, 'RQI低': 80, 'RQI高': 90, 'RQI启用': True, 'PQI': 80, 'PQI启用': True},
            '二级及以下': {'PCI低': 78, 'PCI高': 85, 'PCI启用': True, 'RQI低': 78, 'RQI高': 85, 'RQI启用': True, 'PQI': 75, 'PQI启用': True},
        },
        '水泥路面': {
            '一级公路': {'PCI低': 80, 'PCI高': 90, 'PCI启用': True, 'RQI低': 60, 'RQI高': 85, 'RQI启用': False, 'PQI': 80, 'PQI启用': True},
            '二级及以下': {'PCI低': 78, 'PCI高': 85, 'PCI启用': True, 'RQI低': 60, 'RQI高': 85, 'RQI启用': False, 'PQI': 75, 'PQI启用': True},
        },
    },
}

# 当前使用的触发模型参数（可由用户修改）
TRIGGER_MODEL = None

def _init_trigger_model():
    """初始化触发模型（深拷贝默认值）"""
    global TRIGGER_MODEL
    import copy
    TRIGGER_MODEL = copy.deepcopy(DEFAULT_TRIGGER_MODEL)

_init_trigger_model()

def get_trigger_model() -> dict:
    """获取当前养护触发模型参数"""
    global TRIGGER_MODEL
    if TRIGGER_MODEL is None:
        _init_trigger_model()
    return TRIGGER_MODEL

def set_trigger_model(config: dict = None):
    """设置养护触发模型参数，None则恢复默认"""
    global TRIGGER_MODEL
    if config is None:
        _init_trigger_model()
    else:
        TRIGGER_MODEL = config


def calculate_decay_rates(df: pd.DataFrame, county: str = None) -> dict:
    """
    根据加载的数据动态计算衰减率
    方法：
    1. 同一路段需有多于一年的数据，且路段ID必须完全匹配（路线编码+起点+终点）
    2. 对同一路段相邻两年，若指标上升>2分 → 判定为养护干预，剔除
    3. 对保留的纯衰减序列，用 ln(PQI_t/PQI_0) = -k*t 线性化拟合
    4. 按县（可选）×路面类型×技术等级分组，取中位数
    
    参数:
        df: 数据DataFrame
        county: 县名，如果为None则计算全部数据的衰减率
    """
    if df is None or df.empty:
        return None
    
    # 按县筛选
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
        if df.empty:
            return None
    else:
        df = df.copy()
    
    # 需要的数据列
    required_cols = ['路线编码', '路段起点', '路段终点', '年份', 'PQI', '路面类型', '技术等级']
    for col in required_cols:
        if col not in df.columns:
            return None
    
    # 确保有PCI和RQI
    has_pci = 'PCI' in df.columns
    has_rqi = 'RQI' in df.columns
    
    # 准备数据
    df['年份'] = pd.to_numeric(df['年份'], errors='coerce')
    df['PQI'] = pd.to_numeric(df['PQI'], errors='coerce')
    if has_pci:
        df['PCI'] = pd.to_numeric(df['PCI'], errors='coerce')
    if has_rqi:
        df['RQI'] = pd.to_numeric(df['RQI'], errors='coerce')
    
    # 按路段分组（路线+起点+终点）
    df['路段ID'] = df['路线编码'].astype(str) + '_' + df['路段起点'].astype(str) + '_' + df['路段终点'].astype(str)
    df = df.sort_values(['路段ID', '年份'])
    
    # 存储各组的衰减系数
    results = {}  # (路面类型, 技术等级): {PQI: [k1, k2, ...], PCI: [...], RQI: [...]}
    
    for (ptype, tgrade), group in df.groupby(['路面类型', '技术等级']):
        key = (str(ptype), str(tgrade))
        if key not in results:
            results[key] = {'PQI': [], 'PCI': [], 'RQI': []}
        
        # 遍历每个路段，计算衰减序列
        for seg_id, seg_data in group.groupby('路段ID'):
            seg_data = seg_data.sort_values('年份')
            if len(seg_data) < 2:
                continue
            
            years = seg_data['年份'].values
            pqi_vals = seg_data['PQI'].values
            pci_vals = seg_data['PCI'].values if has_pci else None
            rqi_vals = seg_data['RQI'].values if has_rqi else None
            
            # 剔除养护干预点（指标上升>2分）
            valid_idx = [0]
            for i in range(1, len(pqi_vals)):
                if pqi_vals[i] - pqi_vals[i-1] <= 2:
                    valid_idx.append(i)
            
            if len(valid_idx) < 2:
                continue
            
            valid_years = years[valid_idx]
            valid_pqi = pqi_vals[valid_idx]
            
            # 线性化拟合: ln(PQI_t/PQI_0) = -k * t
            if len(valid_years) >= 2:
                try:
                    t_vals = valid_years - valid_years[0]
                    ratios = valid_pqi / valid_pqi[0]
                    ratios = np.maximum(ratios, 0.01)  # 防止log(0)
                    ln_ratios = np.log(ratios)
                    
                    # 线性拟合
                    if np.std(t_vals) > 0:
                        k = -np.polyfit(t_vals, ln_ratios, 1)[0]
                        if 0 < k < 0.5:  # 合理的衰减系数范围
                            results[key]['PQI'].append(k)
                except:
                    pass
            
            # PCI同理
            if pci_vals is not None and len(valid_idx) >= 2:
                valid_pci = pci_vals[valid_idx]
                try:
                    t_vals = valid_years - valid_years[0]
                    ratios = valid_pci / valid_pci[0]
                    ratios = np.maximum(ratios, 0.01)
                    ln_ratios = np.log(ratios)
                    if np.std(t_vals) > 0:
                        k = -np.polyfit(t_vals, ln_ratios, 1)[0]
                        if 0 < k < 0.5:
                            results[key]['PCI'].append(k)
                except:
                    pass
            
            # RQI同理
            if rqi_vals is not None and len(valid_idx) >= 2:
                valid_rqi = rqi_vals[valid_idx]
                try:
                    t_vals = valid_years - valid_years[0]
                    ratios = valid_rqi / valid_rqi[0]
                    ratios = np.maximum(ratios, 0.01)
                    ln_ratios = np.log(ratios)
                    if np.std(t_vals) > 0:
                        k = -np.polyfit(t_vals, ln_ratios, 1)[0]
                        if 0 < k < 0.5:
                            results[key]['RQI'].append(k)
                except:
                    pass
    
    # 取中位数
    final_results = {}
    for key, vals in results.items():
        final_results[key] = {
            'PQI': round(np.median(vals['PQI']), 4) if vals['PQI'] else None,
            'PCI': round(np.median(vals['PCI']), 4) if vals.get('PCI') and vals['PCI'] else None,
            'RQI': round(np.median(vals['RQI']), 4) if vals.get('RQI') and vals['RQI'] else None,
            '样本数': len(vals['PQI']) if vals['PQI'] else 0,
        }
    
    return final_results


def get_calibration_table(df: pd.DataFrame, county: str = None) -> list:
    """
    返回标定结果表格数据，供UI显示
    """
    calc_results = calculate_decay_rates(df, county)
    
    if not calc_results:
        return []
    
    # 准备表格行
    table_data = []
    grade_order = ['一级公路', '二级公路', '三级公路', '四级公路']
    ptype_order = ['沥青路面', '水泥路面']
    
    for ptype in ptype_order:
        for grade in grade_order:
            key = (ptype, grade)
            if key in calc_results:
                vals = calc_results[key]
                pqi_k = vals['PQI'] if vals['PQI'] else '-'
                pci_k = vals['PCI'] if vals['PCI'] else '-'
                rqi_k = vals['RQI'] if vals['RQI'] else '-'
                samples = vals['样本数']
                
                table_data.append((ptype, grade, str(pqi_k), str(pci_k), str(rqi_k), str(samples)))
    
    return table_data


def _judge_maintenance(ptype, grade_key, pqi_pred, pci_pred, rqi_pred, trigger_cfg=None):
    """
    根据触发模型参数判断养护类型
    返回：'路面改造' / '预防性养护' / None（日常养护）
    
    参数:
        ptype: 路面类型（'沥青路面'/'水泥路面'）
        grade_key: 技术等级分组（'一级公路'/'二级及以下'）
        pqi_pred/pci_pred/rqi_pred: 预测指标值
        trigger_cfg: 触发模型配置字典，None则使用当前配置
    """
    if trigger_cfg is None:
        trigger_cfg = get_trigger_model()
    
    reform_cfg = trigger_cfg.get('路面改造', {}).get(ptype, {}).get(grade_key, {})
    prev_cfg = trigger_cfg.get('预防性养护', {}).get(ptype, {}).get(grade_key, {})
    
    # 路面改造条件（满足任一即触发）
    pci_threshold = reform_cfg.get('PCI', 80)
    pci_enabled = reform_cfg.get('PCI启用', True)
    pqi_threshold = reform_cfg.get('PQI', 80)
    pqi_enabled = reform_cfg.get('PQI启用', True)
    rqi_threshold = reform_cfg.get('RQI', 80)
    rqi_enabled = reform_cfg.get('RQI启用', ptype == '沥青路面')
    
    if (pci_enabled and pci_pred < pci_threshold) or (pqi_enabled and pqi_pred < pqi_threshold):
        return '路面改造'
    if rqi_enabled and rqi_pred < rqi_threshold:
        return '路面改造'
    
    # 预防养护条件（不满足路面改造时，需同时满足启用的条件）
    pci_lo = prev_cfg.get('PCI低', 80)
    pci_hi = prev_cfg.get('PCI高', 90)
    pci_enabled = prev_cfg.get('PCI启用', True)
    rqi_lo = prev_cfg.get('RQI低', 80)
    rqi_hi = prev_cfg.get('RQI高', 90)
    rqi_enabled = prev_cfg.get('RQI启用', ptype == '沥青路面')
    pqi_min = prev_cfg.get('PQI', 80)
    pqi_enabled = prev_cfg.get('PQI启用', True)
    
    # 检查启用的条件是否都满足
    pci_ok = not pci_enabled or (pci_lo <= pci_pred <= pci_hi)
    rqi_ok = not rqi_enabled or (rqi_lo <= rqi_pred <= rqi_hi)
    pqi_ok = not pqi_enabled or (pqi_pred >= pqi_min)
    
    if pci_ok and rqi_ok and pqi_ok:
        # 至少有一个条件启用才判定为预防性养护
        if pci_enabled or rqi_enabled or pqi_enabled:
            return '预防性养护'
    
    return None  # 日常养护


def predict_5year_pqi(df: pd.DataFrame, county: str = None) -> pd.DataFrame:
    """
    预测各线路未来5年的PQI/PCI/RQI值（2026-2030）
    1. 逐路段进行预测，只对需要养护的路段进行值回调
    2. 然后按路线计算加权平均值
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 按县筛选
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    # 获取衰减率
    decay_rates = calculate_decay_rates(df, county)
    
    # 获取最新年份数据（2025）
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    # 确保有路段长度
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    # 存储每条路线的路段数据
    route_segment_data = {}
    
    # 获取触发模型配置
    trigger_cfg = get_trigger_model()
    trigger_enabled = trigger_cfg.get('启用', True)
    
    # 获取年度配置（按年份设置是否启用养护触发）
    yearly_config = trigger_cfg.get('年度配置', {})
    
    # 逐路段计算预测
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        
        key = (ptype, tgrade)
        
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
        rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
        
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        is_secondary_or_below = tgrade in ['二级公路', '三级公路', '四级公路']
        grade_key = '二级及以下' if is_secondary_or_below else '一级公路'
        
        # 存储该路段每年的PQI/PCI/RQI值
        segment_yearly = {
            '路线编码': route,
            '路面类型': ptype,
            '技术等级': tgrade,
            '路段长度km': seg_length,
            '2025年PQI': pqi0,
            '2025年PCI': pci0,
            '2025年RQI': rqi0,
        }
        
        # 逐年递推预测该路段
        cur_pqi = pqi0
        cur_pci = pci0
        cur_rqi = rqi0
        
        for year in range(2026, 2031):
            # 检查本年度是否启用养护触发（全局启用 + 年度启用）
            year_enabled = trigger_enabled and yearly_config.get(year, True)
            
            pqi_pred = cur_pqi * np.exp(-pqi_k)
            pci_pred = cur_pci * np.exp(-pci_k)
            rqi_pred = cur_rqi * np.exp(-rqi_k)
            
            # 判断养护类型（仅在本年度启用触发模型时）
            maint_type = None
            if year_enabled:
                maint_type = _judge_maintenance(ptype, grade_key, pqi_pred, pci_pred, rqi_pred, trigger_cfg)
            
            if maint_type:
                # 触发养护，用回调值作为下一年基准，本年显示回调值
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                display_pqi = callback.get('PQI', 90)
                display_pci = callback.get('PCI', 90)
                display_rqi = callback.get('RQI', 90)
                cur_pqi = display_pqi
                cur_pci = display_pci
                cur_rqi = display_rqi
            else:
                # 未触发养护，显示衰减后的值，作为下一年基准
                display_pqi = pqi_pred
                display_pci = pci_pred
                display_rqi = rqi_pred
                cur_pqi = pqi_pred
                cur_pci = pci_pred
                cur_rqi = rqi_pred
            
            segment_yearly[f'{year}年PQI'] = display_pqi
            segment_yearly[f'{year}年PCI'] = display_pci
            segment_yearly[f'{year}年RQI'] = display_rqi
        
        if route not in route_segment_data:
            route_segment_data[route] = []
        route_segment_data[route].append(segment_yearly)
    
    # 按路线计算加权平均值
    results = []
    for route, segments in route_segment_data.items():
        total_length = sum(s['路段长度km'] for s in segments)
        if total_length <= 0:
            continue
        
        # 获取该路线的主要路面类型和技术等级（众数）
        ptypes = [s['路面类型'] for s in segments]
        tgrades = [s['技术等级'] for s in segments]
        ptype = max(set(ptypes), key=ptypes.count)
        tgrade = max(set(tgrades), key=tgrades.count)
        
        row_data = {
            '路线编码': route,
            '路面类型': ptype,
            '技术等级': tgrade,
        }
        
        # 计算每年的加权平均值
        for year in range(2025, 2031):
            weighted_pqi = sum(s[f'{year}年PQI'] * s['路段长度km'] for s in segments) / total_length
            weighted_pci = sum(s[f'{year}年PCI'] * s['路段长度km'] for s in segments) / total_length
            weighted_rqi = sum(s[f'{year}年RQI'] * s['路段长度km'] for s in segments) / total_length
            
            row_data[f'{year}年PQI'] = round(weighted_pqi, 1)
            row_data[f'{year}年PCI'] = round(weighted_pci, 1)
            row_data[f'{year}年RQI'] = round(weighted_rqi, 1)
        
        results.append(row_data)
    
    return pd.DataFrame(results)


def predict_5year_pqi_with_manual_plan(df: pd.DataFrame, county: str = None, manual_plans: list = None) -> pd.DataFrame:
    """
    预测各线路未来5年的PQI/PCI/RQI值（2026-2030），支持手动养护规划
    手动养护规划格式：[{'route': '路线编码', 'start': '路段起点', 'end': '路段终点', 'year': 2026, 'maint_type': '路面改造/预防性养护'}, ...]
    如果start和end为空，则对整个路线进行养护规划
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    decay_rates = calculate_decay_rates(df, county)
    
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    if manual_plans is None:
        manual_plans = []
    
    route_segment_data = {}
    
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        seg_start = str(row.get('路段起点', '')).strip()
        seg_end = str(row.get('路段终点', '')).strip()
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        key = (ptype, tgrade)
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
        rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
        
        segment_yearly = {
            '路线编码': route,
            '路面类型': ptype,
            '技术等级': tgrade,
            '路段长度km': seg_length,
            '2025年PQI': pqi0,
            '2025年PCI': pci0,
            '2025年RQI': rqi0,
        }
        
        cur_pqi = pqi0
        cur_pci = pci0
        cur_rqi = rqi0
        
        for year in range(2026, 2031):
            pqi_pred = cur_pqi * np.exp(-pqi_k)
            pci_pred = cur_pci * np.exp(-pci_k)
            rqi_pred = cur_rqi * np.exp(-rqi_k)
            
            maint_type = None
            overlap_ratio = 1.0
            for plan in manual_plans:
                if str(plan.get('route', '')).strip() == str(route).strip() and plan.get('year') == year:
                    plan_start = plan.get('start', '').strip()
                    plan_end = plan.get('end', '').strip()
                    
                    if not plan_start and not plan_end:
                        maint_type = plan.get('maint_type')
                        overlap_ratio = 1.0
                        break
                    elif plan_start and plan_end:
                        seg_start_km = _parse_km_value(seg_start)
                        seg_end_km = _parse_km_value(seg_end)
                        plan_start_km = _parse_km_value(plan_start)
                        plan_end_km = _parse_km_value(plan_end)
                        
                        if seg_start_km is not None and seg_end_km is not None and plan_start_km is not None and plan_end_km is not None:
                            if _segments_overlap(seg_start_km, seg_end_km, plan_start_km, plan_end_km):
                                maint_type = plan.get('maint_type')
                                overlap_ratio = _calculate_overlap_ratio(seg_start_km, seg_end_km, plan_start_km, plan_end_km)
                                break
                        else:
                            if _fuzzy_match_segment(str(seg_start), plan_start) or _fuzzy_match_segment(str(seg_end), plan_end):
                                maint_type = plan.get('maint_type')
                                overlap_ratio = 1.0
                                break
                    elif plan_start:
                        if _fuzzy_match_segment(str(seg_start), plan_start):
                            maint_type = plan.get('maint_type')
                            overlap_ratio = 1.0
                            break
                    elif plan_end:
                        if _fuzzy_match_segment(str(seg_end), plan_end):
                            maint_type = plan.get('maint_type')
                            overlap_ratio = 1.0
                            break
            
            if maint_type:
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                callback_pqi = callback.get('PQI', 90)
                callback_pci = callback.get('PCI', 90)
                callback_rqi = callback.get('RQI', 90)
                
                display_pqi = pqi_pred * (1 - overlap_ratio) + callback_pqi * overlap_ratio
                display_pci = pci_pred * (1 - overlap_ratio) + callback_pci * overlap_ratio
                display_rqi = rqi_pred * (1 - overlap_ratio) + callback_rqi * overlap_ratio
                
                cur_pqi = display_pqi
                cur_pci = display_pci
                cur_rqi = display_rqi
            else:
                display_pqi = pqi_pred
                display_pci = pci_pred
                display_rqi = rqi_pred
                cur_pqi = pqi_pred
                cur_pci = pci_pred
                cur_rqi = rqi_pred
            
            segment_yearly[f'{year}年PQI'] = display_pqi
            segment_yearly[f'{year}年PCI'] = display_pci
            segment_yearly[f'{year}年RQI'] = display_rqi
        
        if route not in route_segment_data:
            route_segment_data[route] = []
        route_segment_data[route].append(segment_yearly)
    
    results = []
    for route, segments in route_segment_data.items():
        total_length = sum(s['路段长度km'] for s in segments)
        if total_length <= 0:
            continue
        
        ptypes = [s['路面类型'] for s in segments]
        tgrades = [s['技术等级'] for s in segments]
        ptype = max(set(ptypes), key=ptypes.count)
        tgrade = max(set(tgrades), key=tgrades.count)
        
        row_data = {
            '路线编码': route,
            '路面类型': ptype,
            '技术等级': tgrade,
        }
        
        for year in range(2025, 2031):
            weighted_pqi = sum(s[f'{year}年PQI'] * s['路段长度km'] for s in segments) / total_length
            weighted_pci = sum(s[f'{year}年PCI'] * s['路段长度km'] for s in segments) / total_length
            weighted_rqi = sum(s[f'{year}年RQI'] * s['路段长度km'] for s in segments) / total_length
            
            row_data[f'{year}年PQI'] = round(weighted_pqi, 1)
            row_data[f'{year}年PCI'] = round(weighted_pci, 1)
            row_data[f'{year}年RQI'] = round(weighted_rqi, 1)
        
        results.append(row_data)
    
    return pd.DataFrame(results)


def calculate_good_road_rate_with_manual_plan(df: pd.DataFrame, county: str = None, manual_plans: list = None) -> pd.DataFrame:
    """
    计算每年普通国道、普通省道的PQI优良路率，支持手动养护规划
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    decay_rates = calculate_decay_rates(df, county)
    
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    if manual_plans is None:
        manual_plans = []
    
    predictions = []
    
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        seg_start = str(row.get('路段起点', '')).strip()
        seg_end = str(row.get('路段终点', '')).strip()
        pqi0 = row.get('PQI', 80)
        
        route_code = str(route)
        if route_code.startswith('G') or route_code.startswith('国道'):
            road_type = '普通国道'
        elif route_code.startswith('S') or route_code.startswith('省道'):
            road_type = '普通省道'
        else:
            road_type = '其他道路'
        
        key = (ptype, tgrade)
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        
        predictions.append({
            '路线编码': route,
            '道路类型': road_type,
            '年份': 2025,
            'PQI预测': pqi0,
            '路段长度': seg_length
        })
        
        cur_pqi = pqi0
        
        for year in range(2026, 2031):
            pqi_pred = cur_pqi * np.exp(-pqi_k)
            
            maint_type = None
            for plan in manual_plans:
                if str(plan.get('route', '')).strip() == str(route).strip() and plan.get('year') == year:
                    plan_start = plan.get('start', '').strip()
                    plan_end = plan.get('end', '').strip()
                    
                    if not plan_start and not plan_end:
                        maint_type = plan.get('maint_type')
                        break
                    elif plan_start and plan_end:
                        seg_start_km = _parse_km_value(seg_start)
                        seg_end_km = _parse_km_value(seg_end)
                        plan_start_km = _parse_km_value(plan_start)
                        plan_end_km = _parse_km_value(plan_end)
                        
                        if seg_start_km is not None and seg_end_km is not None and plan_start_km is not None and plan_end_km is not None:
                            if _segments_overlap(seg_start_km, seg_end_km, plan_start_km, plan_end_km):
                                maint_type = plan.get('maint_type')
                                break
                        else:
                            if _fuzzy_match_segment(str(seg_start), plan_start) or _fuzzy_match_segment(str(seg_end), plan_end):
                                maint_type = plan.get('maint_type')
                                break
                    elif plan_start:
                        if _fuzzy_match_segment(str(seg_start), plan_start):
                            maint_type = plan.get('maint_type')
                            break
                    elif plan_end:
                        if _fuzzy_match_segment(str(seg_end), plan_end):
                            maint_type = plan.get('maint_type')
                            break
            
            if maint_type:
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                display_pqi = callback.get('PQI', 90)
                cur_pqi = display_pqi
            else:
                display_pqi = pqi_pred
                cur_pqi = pqi_pred
            
            predictions.append({
                '路线编码': route,
                '道路类型': road_type,
                '年份': year,
                'PQI预测': display_pqi,
                '路段长度': seg_length
            })
    
    if not predictions:
        return pd.DataFrame()
    
    pred_df = pd.DataFrame(predictions)
    
    results = []
    for year in range(2025, 2031):
        year_data = pred_df[pred_df['年份'] == year]
        for road_type in ['普通国道', '普通省道']:
            type_data = year_data[year_data['道路类型'] == road_type]
            if type_data.empty:
                continue
            
            total_length = type_data['路段长度'].sum()
            good_length = type_data[type_data['PQI预测'] >= 80]['路段长度'].sum()
            good_rate = (good_length / total_length * 100) if total_length > 0 else 0
            
            results.append({
                '年份': year,
                '道路类型': road_type,
                'PQI≥80的路段里程(km)': round(good_length, 2),
                '总里程(km)': round(total_length, 2),
                '优良路率(%)': f'{round(good_rate, 2)}%'
            })
    
    return pd.DataFrame(results)


def calculate_maintenance_plan(df: pd.DataFrame, county: str = None) -> dict:
    """
    计算养护计划：各线路5年的路面改造和预防性养护里程及资金
    逻辑（参考养护需求预测.docx中的养护触发模型）：
    1. 基准年2026，预测2026-2030（5年）
    2. 先逐路段计算预测PQI/PCI/RQI，判断养护类型
    3. 再按路线小计各年份的里程和资金
    
    养护触发模型：
    - 路面改造条件（满足任一）：
      水泥路面一级公路：PCI < 80 或 PQI < 80
      水泥路面二级及以下：PCI < 75 或 PQI < 75
      沥青路面一级公路：PCI < 80 或 RQI < 80 或 PQI < 80
      沥青路面二级及以下：PCI < 75 或 RQI < 75 或 PQI < 75
    - 预防养护条件（不满足路面改造时）：
      水泥路面一级公路：PCI 80-90 且 RQI 60-85 且 PQI ≥ 80
      水泥路面二级及以下：PCI 78-85 且 RQI 60-85 且 PQI ≥ 75
      沥青路面一级公路：PCI 80-90 且 RQI 80-90 且 PQI ≥ 80
      沥青路面二级及以下：PCI 78-85 且 RQI 78-85 且 PQI ≥ 75
    - 日常养护：不满足上述条件
    - 养护后PQI回调值：路面改造→沥青92/水泥88，预防→沥青89/水泥86
    """
    if df is None or df.empty:
        return {}
    
    # 按县筛选
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return {}
    
    # 获取衰减率
    decay_rates = calculate_decay_rates(df, county)
    
    # 获取最新年份数据（2025）
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    # 确保有路段长度
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    # 存储路段级别的养护计划
    route_plans = {}
    
    for route, group in latest_df.groupby('路线编码'):
        route_plans[route] = {
            '里程': {year: {'路面改造': 0, '预防性养护': 0} for year in range(2026, 2031)},
            '资金': {year: {'路面改造': 0, '预防性养护': 0} for year in range(2026, 2031)},
        }
        
        for idx, row in group.iterrows():
            ptype = row.get('路面类型', '沥青路面')
            tgrade = row.get('技术等级', '三级公路')
            seg_length = row.get('路段长度km', 1.0)
            
            key = (ptype, tgrade)
            
            pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
            pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
            rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
            
            pqi0 = row.get('PQI', 80)
            pci0 = row.get('PCI', 80)
            rqi0 = row.get('RQI', 80)
            
            # 路段当前状态（基准年2025）
            current_pqi = pqi0
            current_pci = pci0
            current_rqi = rqi0
            
            # 获取路段宽度（米），默认为7米
            seg_width = row.get('路面宽度', 7)
            if pd.isna(seg_width) or seg_width <= 0:
                seg_width = 7
            
            # 基准年2025，逐年递推预测2026-2030（5年）
            # 每年 = 上一年值 × exp(-k×1)，触发养护后重置基准值再继续衰减
            is_secondary_or_below = tgrade in ['二级公路', '三级公路', '四级公路']
            grade_key = '二级及以下' if is_secondary_or_below else '一级公路'
            
            # 获取触发模型配置
            trigger_cfg = get_trigger_model()
            trigger_enabled = trigger_cfg.get('启用', True)
            yearly_config = trigger_cfg.get('年度配置', {})
            
            for year in range(2026, 2031):
                # 本年预测值 = 上一年基准值衰减1年
                pqi_pred = current_pqi * np.exp(-pqi_k)
                pci_pred = current_pci * np.exp(-pci_k)
                rqi_pred = current_rqi * np.exp(-rqi_k)
                
                # 判断养护类型（仅在全局启用且本年度启用触发模型时）
                maint_type = None
                year_enabled = trigger_enabled and yearly_config.get(year, True)
                if year_enabled:
                    maint_type = _judge_maintenance(ptype, grade_key, pqi_pred, pci_pred, rqi_pred, trigger_cfg)
                
                # 如果触发养护，计入里程资金，并用回调值作为下一年的衰减基准
                if maint_type:
                    price = MAINTENANCE_TYPES[maint_type]['单价'].get(ptype, 300)
                    route_plans[route]['里程'][year][maint_type] += seg_length
                    # 资金计算公式：路段长度(km) × 1000 × 路段宽度(m) × 单价(元/m²)
                    route_plans[route]['资金'][year][maint_type] += seg_length * 1000 * seg_width * price
                    
                    # 养护后PQI回调（使用可配置的回调值），作为下一年的衰减基准
                    callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                    current_pqi = callback.get('PQI', 90)
                    current_pci = callback.get('PCI', 90)
                    current_rqi = callback.get('RQI', 90)
                else:
                    # 未触发养护或本年度未启用触发模型，以本年预测值作为下一年的衰减基准
                    current_pqi = pqi_pred
                    current_pci = pci_pred
                    current_rqi = rqi_pred
    
    return route_plans


def get_segment_maintenance_plan(df: pd.DataFrame, county: str = None) -> pd.DataFrame:
    """
    获取详细的路段养护计划：每年各线路各路段的桩号和养护类型
    返回DataFrame，包含：路线编码、路段起点、路段终点、路段长度、年份、养护类型
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    decay_rates = calculate_decay_rates(df, county)
    
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    results = []
    
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        seg_start = row.get('路段起点', '')
        seg_end = row.get('路段终点', '')
        
        key = (ptype, tgrade)
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
        rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
        
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        current_pqi = pqi0
        current_pci = pci0
        current_rqi = rqi0
        
        is_secondary_or_below = tgrade in ['二级公路', '三级公路', '四级公路']
        grade_key = '二级及以下' if is_secondary_or_below else '一级公路'
        
        trigger_cfg = get_trigger_model()
        trigger_enabled = trigger_cfg.get('启用', True)
        yearly_config = trigger_cfg.get('年度配置', {})
        
        for year in range(2026, 2031):
            pqi_pred = current_pqi * np.exp(-pqi_k)
            pci_pred = current_pci * np.exp(-pci_k)
            rqi_pred = current_rqi * np.exp(-rqi_k)
            
            maint_type = None
            year_enabled = trigger_enabled and yearly_config.get(year, True)
            if year_enabled:
                maint_type = _judge_maintenance(ptype, grade_key, pqi_pred, pci_pred, rqi_pred, trigger_cfg)
            
            if maint_type:
                results.append({
                    '路线编码': route,
                    '路段起点': seg_start,
                    '路段终点': seg_end,
                    '路段长度(km)': round(seg_length, 3),
                    '路面类型': ptype,
                    '技术等级': tgrade,
                    '年份': year,
                    '养护类型': maint_type,
                })
                
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                current_pqi = callback.get('PQI', 90)
                current_pci = callback.get('PCI', 90)
                current_rqi = callback.get('RQI', 90)
            else:
                current_pqi = pqi_pred
                current_pci = pci_pred
                current_rqi = rqi_pred
    
    result_df = pd.DataFrame(results)
    result_df = result_df.drop_duplicates(subset=['路线编码', '路段起点', '路段终点', '年份', '养护类型'], keep='first')
    return result_df


def get_yearly_summary(df: pd.DataFrame, county: str = None) -> pd.DataFrame:
    """
    汇总表：每年路面改造里程、预防养护里程、改造资金、预防资金，总计
    年份范围：2026-2030（基准年2026，预测5年）
    """
    plan = calculate_maintenance_plan(df, county)
    
    yearly_data = {year: {'改造里程': 0, '预防里程': 0, '改造资金': 0, '预防资金': 0} for year in range(2026, 2031)}
    
    for route, data in plan.items():
        for year in range(2026, 2031):
            yearly_data[year]['改造里程'] += data['里程'][year].get('路面改造', 0)
            yearly_data[year]['预防里程'] += data['里程'][year].get('预防性养护', 0)
            yearly_data[year]['改造资金'] += data['资金'][year].get('路面改造', 0)
            yearly_data[year]['预防资金'] += data['资金'][year].get('预防性养护', 0)
    
    # 计算小计和总计
    results = []
    total = {'改造里程': 0, '预防里程': 0, '改造资金': 0, '预防资金': 0}
    for year in range(2026, 2031):
        d = yearly_data[year]
        total['改造里程'] += d['改造里程']
        total['预防里程'] += d['预防里程']
        total['改造资金'] += d['改造资金']
        total['预防资金'] += d['预防资金']
        
        year_fund_total = d['改造资金'] + d['预防资金']
        results.append({
            '年份': year,
            '路面改造里程(km)': round(d['改造里程'], 2),
            '预防养护里程(km)': round(d['预防里程'], 2),
            '路面改造资金(万元)': round(d['改造资金'] / 10000, 2),
            '预防养护资金(万元)': round(d['预防资金'] / 10000, 2),
            '资金总计(万元)': round(year_fund_total / 10000, 2),
        })
    
    # 添加总计行
    total_fund = total['改造资金'] + total['预防资金']
    results.append({
        '年份': '总计',
        '路面改造里程(km)': round(total['改造里程'], 2),
        '预防养护里程(km)': round(total['预防里程'], 2),
        '路面改造资金(万元)': round(total['改造资金'] / 10000, 2),
        '预防养护资金(万元)': round(total['预防资金'] / 10000, 2),
        '资金总计(万元)': round(total_fund / 10000, 2),
    })
    
    return pd.DataFrame(results)


def calculate_maintenance_plan_with_manual(df: pd.DataFrame, county: str = None, manual_plans: list = None) -> dict:
    """
    计算养护计划（支持手动养护规划）
    手动养护规划格式：[{'route': '路线编码', 'start': '路段起点', 'end': '路段终点', 'year': 2026, 'maint_type': '路面改造/预防性养护'}, ...]
    如果start和end为空，则对整个路线进行养护规划
    """
    if df is None or df.empty:
        return {}
    
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return {}
    
    if manual_plans is None:
        manual_plans = []
    
    decay_rates = calculate_decay_rates(df, county)
    
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    if '路段宽度' not in latest_df.columns:
        latest_df['路段宽度'] = 7.0
    latest_df['路段宽度'] = pd.to_numeric(latest_df['路段宽度'], errors='coerce').fillna(7.0)
    
    route_plans = {}
    
    for route in latest_df['路线编码'].unique():
        route_plans[route] = {
            '里程': {y: {} for y in range(2026, 2031)},
            '资金': {y: {} for y in range(2026, 2031)}
        }
    
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        seg_width = row.get('路段宽度', 7)
        seg_start = str(row.get('路段起点', '')).strip()
        seg_end = str(row.get('路段终点', '')).strip()
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        key = (ptype, tgrade)
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
        rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
        
        current_pqi = pqi0
        current_pci = pci0
        current_rqi = rqi0
        
        for year in range(2026, 2031):
            pqi_pred = current_pqi * np.exp(-pqi_k)
            pci_pred = current_pci * np.exp(-pci_k)
            rqi_pred = current_rqi * np.exp(-rqi_k)
            
            maint_type = None
            for plan in manual_plans:
                if str(plan.get('route', '')).strip() == str(route).strip() and plan.get('year') == year:
                    plan_start = plan.get('start', '').strip()
                    plan_end = plan.get('end', '').strip()
                    
                    if not plan_start and not plan_end:
                        maint_type = plan.get('maint_type')
                        break
                    elif plan_start and plan_end:
                        seg_start_km = _parse_km_value(seg_start)
                        seg_end_km = _parse_km_value(seg_end)
                        plan_start_km = _parse_km_value(plan_start)
                        plan_end_km = _parse_km_value(plan_end)
                        
                        if seg_start_km is not None and seg_end_km is not None and plan_start_km is not None and plan_end_km is not None:
                            if _segments_overlap(seg_start_km, seg_end_km, plan_start_km, plan_end_km):
                                maint_type = plan.get('maint_type')
                                break
                        else:
                            if _fuzzy_match_segment(str(seg_start), plan_start) or _fuzzy_match_segment(str(seg_end), plan_end):
                                maint_type = plan.get('maint_type')
                                break
                    elif plan_start:
                        if _fuzzy_match_segment(str(seg_start), plan_start):
                            maint_type = plan.get('maint_type')
                            break
                    elif plan_end:
                        if _fuzzy_match_segment(str(seg_end), plan_end):
                            maint_type = plan.get('maint_type')
                            break
            
            if maint_type:
                price = MAINTENANCE_TYPES[maint_type]['单价'].get(ptype, 300)
                route_plans[route]['里程'][year][maint_type] = route_plans[route]['里程'][year].get(maint_type, 0) + seg_length
                route_plans[route]['资金'][year][maint_type] = route_plans[route]['资金'][year].get(maint_type, 0) + seg_length * 1000 * seg_width * price
                
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                current_pqi = callback.get('PQI', 90)
                current_pci = callback.get('PCI', 90)
                current_rqi = callback.get('RQI', 90)
            else:
                current_pqi = pqi_pred
                current_pci = pci_pred
                current_rqi = rqi_pred
    
    return route_plans


def get_yearly_summary_with_manual(df: pd.DataFrame, county: str = None, manual_plans: list = None) -> pd.DataFrame:
    """
    汇总表：每年路面改造里程、预防养护里程、改造资金、预防资金，总计（支持手动养护规划）
    """
    plan = calculate_maintenance_plan_with_manual(df, county, manual_plans)
    
    yearly_data = {year: {'改造里程': 0, '预防里程': 0, '改造资金': 0, '预防资金': 0} for year in range(2026, 2031)}
    
    for route, data in plan.items():
        for year in range(2026, 2031):
            yearly_data[year]['改造里程'] += data['里程'][year].get('路面改造', 0)
            yearly_data[year]['预防里程'] += data['里程'][year].get('预防性养护', 0)
            yearly_data[year]['改造资金'] += data['资金'][year].get('路面改造', 0)
            yearly_data[year]['预防资金'] += data['资金'][year].get('预防性养护', 0)
    
    results = []
    total = {'改造里程': 0, '预防里程': 0, '改造资金': 0, '预防资金': 0}
    for year in range(2026, 2031):
        d = yearly_data[year]
        total['改造里程'] += d['改造里程']
        total['预防里程'] += d['预防里程']
        total['改造资金'] += d['改造资金']
        total['预防资金'] += d['预防资金']
        
        year_fund_total = d['改造资金'] + d['预防资金']
        results.append({
            '年份': year,
            '路面改造里程(km)': round(d['改造里程'], 2),
            '预防养护里程(km)': round(d['预防里程'], 2),
            '路面改造资金(万元)': round(d['改造资金'] / 10000, 2),
            '预防养护资金(万元)': round(d['预防资金'] / 10000, 2),
            '资金总计(万元)': round(year_fund_total / 10000, 2),
        })
    
    total_fund = total['改造资金'] + total['预防资金']
    results.append({
        '年份': '总计',
        '路面改造里程(km)': round(total['改造里程'], 2),
        '预防养护里程(km)': round(total['预防里程'], 2),
        '路面改造资金(万元)': round(total['改造资金'] / 10000, 2),
        '预防养护资金(万元)': round(total['预防资金'] / 10000, 2),
        '资金总计(万元)': round(total_fund / 10000, 2),
    })
    
    return pd.DataFrame(results)


def calculate_good_road_rate(df: pd.DataFrame, county: str = None) -> pd.DataFrame:
    """
    计算每年普通国道、普通省道的PQI优良路率
    优良路定义：PQI ≥ 80（优：≥90，良：80-89.99）
    
    计算逻辑：逐路段计算PQI，然后按道路类型汇总
    返回DataFrame包含：年份、道路类型、总里程、优良里程、优良路率
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 按县筛选
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    # 获取衰减率
    decay_rates = calculate_decay_rates(df, county)
    
    # 获取最新年份数据（2025）
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    # 确保有路段长度
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    # 获取触发模型配置
    trigger_cfg = get_trigger_model()
    trigger_enabled = trigger_cfg.get('启用', True)
    yearly_config = trigger_cfg.get('年度配置', {})
    
    # 逐路段预测2025-2030年的PQI
    predictions = []
    
    for idx, row in latest_df.iterrows():
        route = row['路线编码']
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        # 判断道路类型
        route_code = str(route)
        if route_code.startswith('G') or route_code.startswith('国道'):
            road_type = '普通国道'
        elif route_code.startswith('S') or route_code.startswith('省道'):
            road_type = '普通省道'
        else:
            road_type = '其他道路'
        
        key = (ptype, tgrade)
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        
        is_secondary_or_below = tgrade in ['二级公路', '三级公路', '四级公路']
        grade_key = '二级及以下' if is_secondary_or_below else '一级公路'
        
        # 记录2025年的实际数据
        predictions.append({
            '路线编码': route,
            '道路类型': road_type,
            '年份': 2025,
            'PQI预测': pqi0,
            '路段长度': seg_length
        })
        
        # 逐年递推预测
        cur_pqi = pqi0
        
        for year in range(2026, 2031):
            # 检查本年度是否启用养护触发（全局启用 + 年度启用）
            year_enabled = trigger_enabled and yearly_config.get(year, True)
            
            pqi_pred = cur_pqi * np.exp(-pqi_k)
            
            # 判断养护类型（仅在本年度启用触发模型时）
            maint_type = None
            if year_enabled:
                maint_type = _judge_maintenance(ptype, grade_key, pqi_pred, pci0, rqi0, trigger_cfg)
            
            if maint_type:
                # 触发养护，用回调值作为下一年基准，本年显示回调值
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                display_pqi = callback.get('PQI', 90)
                cur_pqi = display_pqi
            else:
                # 未触发养护，显示衰减后的值，作为下一年基准
                display_pqi = pqi_pred
                cur_pqi = pqi_pred
            
            # 记录预测结果
            predictions.append({
                '路线编码': route,
                '道路类型': road_type,
                '年份': year,
                'PQI预测': display_pqi,
                '路段长度': seg_length
            })
    
    if not predictions:
        return pd.DataFrame()
    
    # 创建预测DataFrame
    pred_df = pd.DataFrame(predictions)
    
    # 计算每年每种道路类型的优良路率
    results = []
    for year in range(2025, 2031):
        year_data = pred_df[pred_df['年份'] == year]
        for road_type in ['普通国道', '普通省道']:
            type_data = year_data[year_data['道路类型'] == road_type]
            if type_data.empty:
                continue
            
            total_length = type_data['路段长度'].sum()
            # 优良路：PQI≥80（优：≥90，良：80-89.99）
            good_length = type_data[type_data['PQI预测'] >= 80]['路段长度'].sum()
            good_rate = (good_length / total_length * 100) if total_length > 0 else 0
            
            results.append({
                '年份': year,
                '道路类型': road_type,
                'PQI≥80的路段里程(km)': round(good_length, 2),
                '总里程(km)': round(total_length, 2),
                '优良路率(%)': f'{round(good_rate, 2)}%'
            })
    
    return pd.DataFrame(results)


def calculate_segment_maintenance_plan(df: pd.DataFrame, county: str = None) -> pd.DataFrame:
    """
    计算路段级养护计划：各条路每年需要路面改造或者预防性养护的路段
    
    返回DataFrame包含：路线编码、路段起点、路段终点、路面类型、技术等级、年份、养护类型、路段长度
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 按县筛选
    if county and '县份' in df.columns:
        df = df[df['县份'] == county].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    # 获取衰减率
    decay_rates = calculate_decay_rates(df, county)
    
    # 获取最新年份数据（2025）
    latest_year = df['年份'].max()
    latest_df = df[df['年份'] == latest_year].copy()
    
    # 确保有路段长度
    if '路段长度km' not in latest_df.columns:
        latest_df['路段长度km'] = 1.0
    latest_df['路段长度km'] = pd.to_numeric(latest_df['路段长度km'], errors='coerce').fillna(1.0).round(3)
    
    # 存储路段级别的养护计划
    segment_plans = []
    
    # 遍历每个路段
    for idx, row in latest_df.iterrows():
        route = row.get('路线编码')
        start = row.get('路段起点')
        end = row.get('路段终点')
        ptype = row.get('路面类型', '沥青路面')
        tgrade = row.get('技术等级', '三级公路')
        seg_length = row.get('路段长度km', 1.0)
        
        key = (ptype, tgrade)
        
        pqi_k = decay_rates.get(key, {}).get('PQI', 0.015) or 0.015
        pci_k = decay_rates.get(key, {}).get('PCI', 0.02) or 0.02
        rqi_k = decay_rates.get(key, {}).get('RQI', 0.01) or 0.01
        
        pqi0 = row.get('PQI', 80)
        pci0 = row.get('PCI', 80)
        rqi0 = row.get('RQI', 80)
        
        # 路段当前状态（基准年2025）
        current_pqi = pqi0
        current_pci = pci0
        current_rqi = rqi0
        
        # 基准年2025，逐年递推预测2026-2030（5年）
        is_secondary_or_below = tgrade in ['二级公路', '三级公路', '四级公路']
        grade_key = '二级及以下' if is_secondary_or_below else '一级公路'
        
        # 获取触发模型配置
        trigger_cfg = get_trigger_model()
        trigger_enabled = trigger_cfg.get('启用', True)
        yearly_config = trigger_cfg.get('年度配置', {})
        
        for year in range(2026, 2031):
            # 本年预测值 = 上一年基准值衰减1年
            pqi_pred = current_pqi * np.exp(-pqi_k)
            pci_pred = current_pci * np.exp(-pci_k)
            rqi_pred = current_rqi * np.exp(-rqi_k)
            
            # 判断养护类型（仅在全局启用且本年度启用触发模型时）
            maint_type = None
            year_enabled = trigger_enabled and yearly_config.get(year, True)
            if year_enabled:
                maint_type = _judge_maintenance(ptype, grade_key, pqi_pred, pci_pred, rqi_pred, trigger_cfg)
            
            # 如果触发养护，记录路段养护计划
            if maint_type:
                segment_plans.append({
                    '路线编码': route,
                    '路段起点': start,
                    '路段终点': end,
                    '路面类型': ptype,
                    '技术等级': tgrade,
                    '年份': year,
                    '养护类型': maint_type,
                    '路段长度(km)': round(seg_length, 3)
                })
                
                # 养护后PQI回调（使用可配置的回调值），作为下一年的衰减基准
                callback = MAINTENANCE_CALLBACK.get(maint_type, {}).get(ptype, {})
                current_pqi = callback.get('PQI', 90)
                current_pci = callback.get('PCI', 90)
                current_rqi = callback.get('RQI', 90)
            else:
                # 未触发养护或本年度未启用触发模型，以本年预测值作为下一年的衰减基准
                current_pqi = pqi_pred
                current_pci = pci_pred
                current_rqi = rqi_pred
    
    return pd.DataFrame(segment_plans)