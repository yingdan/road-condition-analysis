"""
性能预测模型模块
按《公路养护决策技术规范》附录D/E实现多种性能预测模型

模型类型：
1. 指数衰减模型（已有）
2. 线性回归模型
3. S形曲线模型
4. 马尔科夫模型
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict


# ══════════════════════════════════════════════════════════════════════════════
# 1. 指数衰减模型（已有，扩展）
# ══════════════════════════════════════════════════════════════════════════════

def exponential_decay_model(PQI_0: float, k: float, t: float) -> float:
    """
    指数衰减模型：PQI_t = PQI_0 * exp(-k*t)

    参数:
        PQI_0: 初始PQI值
        k: 衰减系数
        t: 路龄（年）

    返回:
        预测PQI值
    """
    if k < 0:
        k = 0
    if k > 0.5:
        k = 0.5  # 防止过度衰减
    return PQI_0 * np.exp(-k * t)


def exponential_decay_inverse(PQI_target: float, k: float, PQI_0: float = 100) -> float:
    """
    指数衰减模型反算：根据目标PQI反算需要的路龄

    参数:
        PQI_target: 目标PQI值
        k: 衰减系数
        PQI_0: 初始PQI值（默认100）

    返回:
        达到目标PQI需要的年数
    """
    if k <= 0:
        return float('inf')
    return np.log(PQI_target / PQI_0) / (-k)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 线性回归模型
# ══════════════════════════════════════════════════════════════════════════════

def linear_decay_model(PQI_0: float, alpha: float, t: float, PQI_min: float = 0) -> float:
    """
    线性衰减模型：PI = PI_0 - alpha*t

    参数:
        PQI_0: 初始PQI值
        alpha: 衰减速率（每年下降值）
        t: 路龄（年）
        PQI_min: 最小值下限

    返回:
        预测PQI值
    """
    result = PQI_0 - alpha * t
    return max(result, PQI_min)


# ══════════════════════════════════════════════════════════════════════════════
# 3. S形曲线模型（改进的S形回归模型）
# ══════════════════════════════════════════════════════════════════════════════

def s_curve_model(PQI_0: float, PQI_min: float, a: float, b: float, t: float) -> float:
    """
    S形曲线模型：PI = PI_min + (PI_0 - PI_min) / (1 + exp(a - b*t))

    适用于：路面技术状况指数衰减到一定程度后，由于采取养护措施使路面状况
    改善，衰变速率减小的情况

    参数:
        PQI_0: 初始PQI值
        PQI_min: 最低PQI水平
        a: 位置参数
        b: 形状参数（控制曲线陡峭程度）
        t: 路龄（年）

    返回:
        预测PQI值
    """
    return PQI_min + (PQI_0 - PQI_min) / (1 + np.exp(a - b * t))


def s_curve_inverse(PQI_target: float, PQI_0: float, PQI_min: float, a: float, b: float) -> float:
    """
    S形曲线模型反算：根据目标PQI反算需要的路龄
    """
    if PQI_target <= PQI_min or PQI_target >= PQI_0:
        return float('inf')
    ratio = (PQI_0 - PQI_target) / (PQI_target - PQI_min)
    return (a - np.log(ratio)) / b


# ══════════════════════════════════════════════════════════════════════════════
# 4. 双参数曲线模型
# ══════════════════════════════════════════════════════════════════════════════

def dual_parameter_model(PQI_0: float, PQI_min: float, k: float, m: float, t: float) -> float:
    """
    双参数曲线模型：综合考虑环境、交通和材料等因素

    PI = PI_min + (PI_0 - PI_min) * exp(-k * t^m)

    参数:
        PQI_0: 初始PQI值
        PQI_min: 最低PQI水平
        k: 衰减系数
        m: 形状参数
        t: 路龄（年）

    返回:
        预测PQI值
    """
    return PQI_min + (PQI_0 - PQI_min) * np.exp(-k * (t ** m))


# ══════════════════════════════════════════════════════════════════════════════
# 5. 马尔科夫模型（简化版）
# ══════════════════════════════════════════════════════════════════════════════

class MarkovModel:
    """
    马尔科夫状态转移概率模型

    假定当前路段的路面技术状况指标处于状态i，
    则其状态变化只能维持在i状态或者变为更差的i+1状态

    状态划分（按PQI值）：
        优：90-100
        良：80-89.99
        中：70-79.99
        次：60-69.99
        差：0-59.99
    """

    # 默认状态转移矩阵（每年）
    DEFAULT_TRANSITION_MATRIX = {
        # 从优转移到(优,良,中,次,差)的概率
        '优': [0.85, 0.12, 0.02, 0.01, 0.00],
        # 从良转移到...
        '良': [0.00, 0.80, 0.15, 0.04, 0.01],
        # 从中转移到...
        '中': [0.00, 0.00, 0.75, 0.18, 0.07],
        # 从次转移到...
        '次': [0.00, 0.00, 0.00, 0.65, 0.35],
        # 从差转移到...
        '差': [0.00, 0.00, 0.00, 0.00, 1.00],
    }

    def __init__(self, transition_matrix: Dict = None):
        """
        初始化马尔科夫模型

        参数:
            transition_matrix: 状态转移矩阵，None则使用默认值
        """
        self.states = ['优', '良', '中', '次', '差']
        self.transition_matrix = transition_matrix or self.DEFAULT_TRANSITION_MATRIX

    def get_state(self, pqi: float) -> str:
        """根据PQI值确定状态"""
        if pd.isna(pqi):
            return '良'  # 默认状态
        if pqi >= 90:
            return '优'
        elif pqi >= 80:
            return '良'
        elif pqi >= 70:
            return '中'
        elif pqi >= 60:
            return '次'
        else:
            return '差'

    def get_pqi_range(self, state: str) -> Tuple[float, float]:
        """获取状态对应的PQI范围"""
        ranges = {
            '优': (90, 100),
            '良': (80, 90),
            '中': (70, 80),
            '次': (60, 70),
            '差': (0, 60),
        }
        return ranges.get(state, (80, 90))

    def predict(self, current_pqi: float, years: int = 1) -> Dict[str, float]:
        """
        预测n年后的状态分布

        参数:
            current_pqi: 当前PQI值
            years: 预测年数

        返回:
            各状态的概率分布字典
        """
        current_state = self.get_state(current_pqi)

        # 初始化状态概率分布
        state_probs = {s: 0.0 for s in self.states}
        state_probs[current_state] = 1.0

        # 逐年转移
        for _ in range(years):
            new_probs = {s: 0.0 for s in self.states}
            for from_state, probs in state_probs.items():
                if probs > 0:
                    trans = self.transition_matrix.get(from_state, [0]*5)
                    for i, to_state in enumerate(self.states):
                        new_probs[to_state] += probs * trans[i]
            state_probs = new_probs

        return state_probs

    def expected_pqi(self, current_pqi: float, years: int = 1) -> float:
        """
        预测n年后的期望PQI值

        参数:
            current_pqi: 当前PQI值
            years: 预测年数

        返回:
            期望PQI值
        """
        state_probs = self.predict(current_pqi, years)
        expected = 0.0
        for state, prob in state_probs.items():
            pqi_range = self.get_pqi_range(state)
            expected += prob * (pqi_range[0] + pqi_range[1]) / 2
        return expected


# ══════════════════════════════════════════════════════════════════════════════
# 6. 模型标定
# ══════════════════════════════════════════════════════════════════════════════

def calibrate_exponential_model(df: pd.DataFrame) -> Dict[Tuple, Dict]:
    """
    基于历史数据标定指数衰减模型参数

    方法：
    1. 同一路段需有多于一年的数据
    2. 剔除养护干预点（指标上升>2分）
    3. 用 ln(PQI_t/PQI_0) = -k*t 线性化拟合

    参数:
        df: 包含多年PQI数据的DataFrame

    返回:
        按(路面类型,技术等级)分组的衰减系数字典
    """
    if df is None or df.empty:
        return None

    # 确保有必要的列
    required_cols = ['路线编码', '路段起点', '路段终点', '年份', 'PQI', '路面类型', '技术等级']
    for col in required_cols:
        if col not in df.columns:
            return None

    # 数值化
    df = df.copy()
    df['年份'] = pd.to_numeric(df['年份'], errors='coerce')
    df['PQI'] = pd.to_numeric(df['PQI'], errors='coerce')

    # 按路段分组
    df['路段ID'] = df['路线编码'].astype(str) + '_' + df['路段起点'].astype(str) + '_' + df['路段终点'].astype(str)
    df = df.sort_values(['路段ID', '年份'])

    # 存储各组衰减系数
    results = {}

    for (ptype, tgrade), group in df.groupby(['路面类型', '技术等级']):
        key = (str(ptype), str(tgrade))
        if key not in results:
            results[key] = {'PQI': [], 'PCI': [], 'RQI': []}

        for seg_id, seg_data in group.groupby('路段ID'):
            seg_data = seg_data.sort_values('年份')
            if len(seg_data) < 2:
                continue

            years = seg_data['年份'].values
            pqi_vals = seg_data['PQI'].values

            # 剔除养护干预点（指标上升>2分）
            valid_idx = [0]
            for i in range(1, len(pqi_vals)):
                if pqi_vals[i] - pqi_vals[i-1] <= 2:
                    valid_idx.append(i)

            if len(valid_idx) < 2:
                continue

            valid_years = years[valid_idx]
            valid_pqi = pqi_vals[valid_idx]

            # 线性化拟合
            if len(valid_years) >= 2:
                try:
                    t_vals = valid_years - valid_years[0]
                    ratios = valid_pqi / valid_pqi[0]
                    ratios = np.maximum(ratios, 0.01)
                    ln_ratios = np.log(ratios)

                    if np.std(t_vals) > 0:
                        k = -np.polyfit(t_vals, ln_ratios, 1)[0]
                        if 0 < k < 0.5:
                            results[key]['PQI'].append(k)
                except:
                    pass

    # 取中位数
    final_results = {}
    for key, vals in results.items():
        final_results[key] = {
            'PQI': round(np.median(vals['PQI']), 4) if vals['PQI'] else None,
            '样本数': len(vals['PQI']) if vals['PQI'] else 0,
        }

    return final_results


def calibrate_linear_model(df: pd.DataFrame) -> Dict[Tuple, Dict]:
    """
    基于历史数据标定线性衰减模型参数

    参数:
        df: 包含多年PQI数据的DataFrame

    返回:
        按(路面类型,技术等级)分组的衰减速率字典
    """
    if df is None or df.empty:
        return None

    required_cols = ['路线编码', '路段起点', '路段终点', '年份', 'PQI', '路面类型', '技术等级']
    for col in required_cols:
        if col not in df.columns:
            return None

    df = df.copy()
    df['年份'] = pd.to_numeric(df['年份'], errors='coerce')
    df['PQI'] = pd.to_numeric(df['PQI'], errors='coerce')

    df['路段ID'] = df['路线编码'].astype(str) + '_' + df['路段起点'].astype(str) + '_' + df['路段终点'].astype(str)
    df = df.sort_values(['路段ID', '年份'])

    results = {}

    for (ptype, tgrade), group in df.groupby(['路面类型', '技术等级']):
        key = (str(ptype), str(tgrade))
        if key not in results:
            results[key] = []

        for seg_id, seg_data in group.groupby('路段ID'):
            seg_data = seg_data.sort_values('年份')
            if len(seg_data) < 2:
                continue

            years = seg_data['年份'].values
            pqi_vals = seg_data['PQI'].values

            # 剔除养护干预点
            valid_idx = [0]
            for i in range(1, len(pqi_vals)):
                if pqi_vals[i] - pqi_vals[i-1] <= 2:
                    valid_idx.append(i)

            if len(valid_idx) < 2:
                continue

            valid_years = years[valid_idx]
            valid_pqi = pqi_vals[valid_idx]

            try:
                t_vals = valid_years - valid_years[0]
                # 线性拟合: PQI = PQI_0 - alpha * t
                if np.std(t_vals) > 0:
                    coeffs = np.polyfit(t_vals, valid_pqi, 1)
                    alpha = -coeffs[0]  # 衰减速率
                    if 0 < alpha < 5:  # 合理范围：每年下降不超过5分
                        results[key].append(alpha)
            except:
                pass

    # 取中位数
    final_results = {}
    for key, vals in results.items():
        final_results[key] = {
            'alpha': round(np.median(vals), 2) if vals else None,
            '样本数': len(vals) if vals else 0,
        }

    return final_results


def calibrate_model(df: pd.DataFrame, model_type: str = 'exponential') -> Dict:
    """
    通用模型标定函数

    参数:
        df: 包含多年数据的DataFrame
        model_type: 模型类型 ('exponential', 'linear')

    返回:
        标定结果字典
    """
    if model_type == 'exponential':
        return calibrate_exponential_model(df)
    elif model_type == 'linear':
        return calibrate_linear_model(df)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. 预测函数统一接口
# ══════════════════════════════════════════════════════════════════════════════

class PerformancePredictor:
    """
    性能预测统一接口
    支持多种预测模型
    """

    def __init__(self, model_type: str = 'exponential'):
        """
        初始化预测器

        参数:
            model_type: 预测模型类型 ('exponential', 'linear', 's_curve', 'markov')
        """
        self.model_type = model_type
        self.calibrated_params = {}

    def calibrate(self, df: pd.DataFrame):
        """标定模型参数"""
        if self.model_type == 'exponential':
            self.calibrated_params = calibrate_exponential_model(df)
        elif self.model_type == 'linear':
            self.calibrated_params = calibrate_linear_model(df)
        elif self.model_type == 's_curve':
            # S曲线需要更多参数，简化处理
            self.calibrated_params = {
                'a': 2.0,
                'b': 0.3,
                'PQI_min': 40,
            }
        elif self.model_type == 'markov':
            self.markov_model = MarkovModel()

    def predict(self, PQI_0: float, pavement_type: str, tech_grade: str, t: float) -> float:
        """
        预测t年后的PQI值

        参数:
            PQI_0: 初始PQI值
            pavement_type: 路面类型
            tech_grade: 技术等级
            t: 预测年数

        返回:
            预测PQI值
        """
        key = (pavement_type, tech_grade)

        if self.model_type == 'exponential':
            k = self.calibrated_params.get(key, {}).get('PQI', 0.015) or 0.015
            return exponential_decay_model(PQI_0, k, t)

        elif self.model_type == 'linear':
            alpha = self.calibrated_params.get(key, {}).get('alpha', 1.5) or 1.5
            return linear_decay_model(PQI_0, alpha, t)

        elif self.model_type == 's_curve':
            params = self.calibrated_params
            return s_curve_model(
                PQI_0,
                params.get('PQI_min', 40),
                params.get('a', 2.0),
                params.get('b', 0.3),
                t
            )

        elif self.model_type == 'markov':
            return self.markov_model.expected_pqi(PQI_0, t)

        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def predict_batch(self, df: pd.DataFrame, years: list) -> pd.DataFrame:
        """
        批量预测多年数据

        参数:
            df: 包含初始PQI数据的DataFrame
            years: 预测年份列表

        返回:
            预测结果DataFrame
        """
        results = []

        for _, row in df.iterrows():
            ptype = row.get('路面类型', '沥青路面')
            tgrade = row.get('技术等级', '三级公路')
            pqi0 = row.get('PQI', 80)

            row_data = {
                '路线编码': row.get('路线编码'),
                '路面类型': ptype,
                '技术等级': tgrade,
            }

            for year in years:
                pqi_pred = self.predict(pqi0, ptype, tgrade, year - df['年份'].max())
                row_data[f'{year}年PQI'] = round(pqi_pred, 1)

            results.append(row_data)

        return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 8. 模型评估指标
# ══════════════════════════════════════════════════════════════════════════════

def calculate_model_metrics(df_predicted: pd.Series, df_actual: pd.Series) -> Dict:
    """
    计算模型评估指标

    参数:
        df_predicted: 预测值序列
        df_actual: 实际值序列

    返回:
        评估指标字典
    """
    # 去除NaN
    mask = ~(df_predicted.isna() | df_actual.isna())
    pred = df_predicted[mask]
    actual = df_actual[mask]

    if len(pred) == 0:
        return {'error': '无有效数据进行评估'}

    # 平均绝对误差 MAE
    mae = np.mean(np.abs(pred - actual))

    # 均方根误差 RMSE
    rmse = np.sqrt(np.mean((pred - actual) ** 2))

    # 平均绝对百分比误差 MAPE
    mape = np.mean(np.abs((actual - pred) / actual)) * 100

    # R²决定系数
    ss_res = np.sum((actual - pred) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return {
        'MAE': round(mae, 2),
        'RMSE': round(rmse, 2),
        'MAPE': round(mape, 2),
        'R²': round(r_squared, 4),
    }