"""
数据分析与图表生成模块
v3优化：
- 整合养护需求预测Excel的单价体系和逻辑
- 新增5年资金预测图、路线级养护汇总图
- 多县对比图动态化，支持任意数量县份
- 精细化衰减率：按路面类型×技术等级分类，基于2021-2025实测数据（1452有效样本）指数函数拟合
  剔除养护干预改善路段后，用 ln(PQI_t/PQI_0) = -k*t 线性化拟合，取中位数（样本≥5时）
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
from matplotlib.ticker import MaxNLocator
import os
import warnings
warnings.filterwarnings('ignore')

# 中文字体设置
rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# ── 颜色方案 ──
GRADE_COLORS = {
    '优': '#2ecc71', '良': '#3498db', '中': '#f39c12',
    '次': '#e67e22', '差': '#e74c3c', '未知': '#95a5a6'
}
GRADE_ORDER = ['优', '良', '中', '次', '差']
METRIC_COLORS = {'PQI': '#2980b9', 'PCI': '#27ae60', 'RQI': '#8e44ad'}

# 养护类型颜色
MAINT_COLORS = {
    '路面改造': '#e74c3c',
    '预防养护': '#f1c40f',
    '日常养护': '#2ecc71',
}
MAINT_ORDER = ['路面改造', '预防养护', '日常养护']

# ── 养护单价（元/m²，来自养护需求预测.xlsx Sheet2逻辑）──
# 路面改造：沥青≈319元/m²，水泥≈299元/m²，取均值
# 预防养护：≈160元/m²；日常养护：≈0元（不计费用）
UNIT_PRICE_PER_M2 = {
    '路面改造': {'沥青路面': 319, '水泥路面': 299, 'default': 310},
    '预防养护': {'沥青路面': 160, '水泥路面': 140, 'default': 150},
    '日常养护': {'沥青路面': 0,   '水泥路面': 0,   'default': 0},
}
# ── 精细化衰减率表（指数衰减系数 k，年衰减率 = 1-exp(-k) ≈ k）──
# 来源：基于2021-2025四县实测数据，指数函数拟合，剔除养护干预路段（样本≥5用实测中位数，否则用Sheet4预设）
# 公式：PQI_t = PQI_0 * exp(-k_PQI * t)，t 为年数
DECAY_RATES = {
    # (路面类型, 技术等级): {PQI: k, PCI: k, RQI: k}
    ('沥青路面', '一级公路'): {'PQI': 0.0144, 'PCI': 0.0413, 'RQI': 0.0044},
    ('沥青路面', '二级公路'): {'PQI': 0.0148, 'PCI': 0.0240, 'RQI': 0.0017},
    ('沥青路面', '三级公路'): {'PQI': 0.0137, 'PCI': 0.0210, 'RQI': 0.0030},
    ('沥青路面', '四级公路'): {'PQI': 0.0450, 'PCI': 0.0450, 'RQI': 0.0350},  # Sheet4预设（样本不足）
    ('水泥路面', '一级公路'): {'PQI': 0.0162, 'PCI': 0.0273, 'RQI': 0.0166},
    ('水泥路面', '二级公路'): {'PQI': 0.0075, 'PCI': 0.0135, 'RQI': 0.0068},
    ('水泥路面', '三级公路'): {'PQI': 0.0104, 'PCI': 0.0076, 'RQI': 0.0169},
    ('水泥路面', '四级公路'): {'PQI': 0.0300, 'PCI': 0.0258, 'RQI': 0.0112},
}
# 默认衰减率（路面类型/等级无法匹配时使用）
DECAY_DEFAULT = {'PQI': 0.025, 'PCI': 0.030, 'RQI': 0.020}


def get_decay_rate(pavement_type: str, tech_grade: str, metric: str) -> float:
    """根据路面类型和技术等级获取对应指标的衰减系数 k"""
    ptype = '沥青路面' if '沥青' in str(pavement_type) else '水泥路面'

    grade_str = str(tech_grade)
    if '一级' in grade_str:
        grade = '一级公路'
    elif '二级' in grade_str:
        grade = '二级公路'
    elif '三级' in grade_str:
        grade = '三级公路'
    elif '四级' in grade_str:
        grade = '四级公路'
    else:
        grade = '三级公路'  # 默认三级

    return DECAY_RATES.get((ptype, grade), DECAY_DEFAULT).get(metric, DECAY_DEFAULT[metric])


# 路面宽度默认值（m），用于估算面积
DEFAULT_WIDTH = 7.0


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


# ═══════════════════════════════════════════════════════
# 1. 年度趋势折线图（PQI / PCI / RQI）
# ═══════════════════════════════════════════════════════
def plot_trend(df: pd.DataFrame, county: str, output_dir: str) -> dict:
    """生成年度趋势折线图，返回图表路径和统计数据"""
    ensure_dir(output_dir)

    metrics = [c for c in ['PQI', 'PCI', 'RQI'] if c in df.columns]
    if not metrics or '年份' not in df.columns:
        return {}

    trend_data = df.groupby('年份')[metrics].mean().round(2)
    years = trend_data.index.tolist()
    if len(years) < 1:
        return {}

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for metric in metrics:
        vals = trend_data[metric].tolist()
        line, = ax.plot(years, vals, 'o-', label=metric,
                        color=METRIC_COLORS.get(metric, '#333'),
                        linewidth=2.5, markersize=7)
        for x, y in zip(years, vals):
            ax.annotate(f'{y:.1f}', (x, y),
                        textcoords='offset points', xytext=(0, 10),
                        ha='center', fontsize=9,
                        color=METRIC_COLORS.get(metric, '#333'))

    # 参考线
    ax.axhline(y=75, color='#e74c3c', linestyle='--', linewidth=1, alpha=0.5, label='75分线（中等）')
    ax.axhline(y=85, color='#27ae60', linestyle='--', linewidth=1, alpha=0.5, label='85分线（良好）')

    ax.set_xlabel('年份', fontsize=11)
    ax.set_ylabel('指数均值', fontsize=11)
    ax.set_title(f'{county}  路面状况指数年度趋势（{min(years)}—{max(years)}年）',
                 fontsize=13, fontweight='bold')
    ax.set_ylim(55, 100)
    ax.set_xticks(years)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    path = os.path.join(output_dir, f'{county}_趋势图.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path, 'data': trend_data.to_dict()}


# ═══════════════════════════════════════════════════════
# 2. PQI等级分布柱状图（最新年份）
# ═══════════════════════════════════════════════════════
def plot_grade_distribution(df: pd.DataFrame, county: str,
                            output_dir: str, year: int = None) -> dict:
    """生成PQI等级分布柱状图（按里程）"""
    ensure_dir(output_dir)

    if year is None:
        year = int(df['年份'].max()) if '年份' in df.columns else None
    sub = df[df['年份'] == year].copy() if year else df.copy()

    if '路段长度km' not in sub.columns or 'PQI分级' not in sub.columns:
        return {}

    grade_len = sub.groupby('PQI分级')['路段长度km'].sum()
    total = grade_len.sum()
    if total == 0:
        return {}

    grades = [g for g in GRADE_ORDER if g in grade_len.index]
    values = [grade_len.get(g, 0) for g in grades]
    colors = [GRADE_COLORS[g] for g in grades]
    pcts   = [v / total * 100 for v in values]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(grades, values, color=colors, edgecolor='white',
                  linewidth=0.8, width=0.6)

    for bar, pct, val in zip(bars, pcts, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + total * 0.01,
                f'{val:.1f}km\n({pct:.1f}%)',
                ha='center', va='bottom', fontsize=9)

    avg_pqi = sub['PQI'].mean() if 'PQI' in sub.columns else None
    title_suffix = f'  均值PQI={avg_pqi:.1f}' if avg_pqi else ''
    ax.set_xlabel('PQI等级', fontsize=11)
    ax.set_ylabel('路段里程 (km)', fontsize=11)
    ax.set_title(f'{county}  {year}年  PQI等级里程分布{title_suffix}',
                 fontsize=13, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(values) * 1.25)

    path = os.path.join(output_dir, f'{county}_{year}_PQI等级分布.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {
        'path': path,
        'data': {g: round(v, 2) for g, v in zip(grades, values)},
        'total_km': round(total, 2),
        'avg_pqi': round(avg_pqi, 2) if avg_pqi else None
    }


# ═══════════════════════════════════════════════════════
# 3. 历年等级比例堆叠柱状图
# ═══════════════════════════════════════════════════════
def plot_grade_yearly_stacked(df: pd.DataFrame, county: str,
                              output_dir: str) -> dict:
    """生成多年PQI等级比例堆叠柱状图"""
    ensure_dir(output_dir)

    if 'PQI分级' not in df.columns or '年份' not in df.columns or '路段长度km' not in df.columns:
        return {}

    years = sorted(df['年份'].unique())
    if len(years) < 2:
        return {}

    grade_year = {}
    for year in years:
        sub = df[df['年份'] == year]
        gl = sub.groupby('PQI分级')['路段长度km'].sum()
        total = gl.sum()
        grade_year[year] = {
            g: gl.get(g, 0) / total * 100 if total > 0 else 0
            for g in GRADE_ORDER
        }

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(years))
    bottoms = np.zeros(len(years))

    for grade in GRADE_ORDER:
        vals = np.array([grade_year[y].get(grade, 0) for y in years])
        bars = ax.bar(x, vals, bottom=bottoms, label=grade,
                      color=GRADE_COLORS[grade],
                      edgecolor='white', linewidth=0.5, width=0.65)
        for i, (bar, val) in enumerate(zip(bars, vals)):
            if val > 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bottoms[i] + val / 2,
                        f'{val:.0f}%',
                        ha='center', va='center',
                        fontsize=8, color='white', fontweight='bold')
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years])
    ax.set_ylabel('里程比例 (%)', fontsize=11)
    ax.set_ylim(0, 105)
    ax.set_title(f'{county}  历年PQI等级比例变化', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9, ncol=5,
              bbox_to_anchor=(1, 1.12))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    path = os.path.join(output_dir, f'{county}_历年PQI等级堆叠图.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path}


# ═══════════════════════════════════════════════════════
# 4. 路面类型饼图
# ═══════════════════════════════════════════════════════
def plot_pavement_type(df: pd.DataFrame, county: str,
                       output_dir: str, year: int = None) -> dict:
    """路面类型里程饼图（含甜甜圈样式）"""
    ensure_dir(output_dir)

    if year is None:
        year = int(df['年份'].max()) if '年份' in df.columns else None
    sub = df[df['年份'] == year].copy() if year else df.copy()

    if '路面类型' not in sub.columns or '路段长度km' not in sub.columns:
        return {}

    type_len = sub.groupby('路面类型')['路段长度km'].sum().sort_values(ascending=False)
    if type_len.empty:
        return {}

    fig, ax = plt.subplots(figsize=(7, 5.5))
    colors_pie = ['#2980b9', '#27ae60', '#e67e22', '#8e44ad', '#95a5a6']
    wedges, texts, autotexts = ax.pie(
        type_len.values,
        labels=type_len.index,
        autopct='%1.1f%%',
        colors=colors_pie[:len(type_len)],
        startangle=90,
        pctdistance=0.75,
        wedgeprops=dict(edgecolor='white', linewidth=2, width=0.55)
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight('bold')

    total_km = type_len.sum()
    ax.text(0, 0, f'{total_km:.1f}\nkm',
            ha='center', va='center', fontsize=12, fontweight='bold',
            color=THEME_DARK)

    ax.set_title(f'{county}  {year}年  路面类型里程分布',
                 fontsize=12, fontweight='bold')

    path = os.path.join(output_dir, f'{county}_{year}_路面类型分布.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path, 'data': type_len.to_dict()}

THEME_DARK = '#2C3E50'


# ═══════════════════════════════════════════════════════
# 5. 技术等级分布水平柱状图
# ═══════════════════════════════════════════════════════
def plot_tech_grade(df: pd.DataFrame, county: str,
                    output_dir: str, year: int = None) -> dict:
    """技术等级里程分布水平柱状图"""
    ensure_dir(output_dir)

    if year is None:
        year = int(df['年份'].max()) if '年份' in df.columns else None
    sub = df[df['年份'] == year].copy() if year else df.copy()

    if '技术等级' not in sub.columns or '路段长度km' not in sub.columns:
        return {}

    # 按技术等级顺序排序：一级、二级、三级、四级
    grade_order = ['一级公路', '二级公路', '三级公路', '四级公路']
    tg = sub.groupby('技术等级')['路段长度km'].sum()
    if tg.empty:
        return {}
    # 按照指定顺序重新排序
    tg = tg.reindex([g for g in grade_order if g in tg.index])
    tg = tg.dropna()

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(tg) * 0.7 + 1.5)))
    colors_bar = ['#2980b9', '#27ae60', '#f39c12', '#e74c3c', '#8e44ad', '#1abc9c']
    bars = ax.barh(tg.index.tolist(), tg.values,
                   color=colors_bar[:len(tg)],
                   edgecolor='white', linewidth=0.8, height=0.6)
    total = tg.sum()
    for bar, val in zip(bars, tg.values):
        pct = val / total * 100 if total > 0 else 0
        ax.text(bar.get_width() + total * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f'{val:.1f} km  ({pct:.1f}%)',
                va='center', fontsize=9)

    ax.set_xlabel('里程 (km)', fontsize=11)
    ax.set_title(f'{county}  {year}年  技术等级里程分布  （总计 {total:.1f} km）',
                 fontsize=12, fontweight='bold')
    ax.set_xlim(0, tg.max() * 1.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    path = os.path.join(output_dir, f'{county}_{year}_技术等级分布.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path, 'data': tg.to_dict()}


# ═══════════════════════════════════════════════════════
# 6. 多县对比雷达图（动态，支持任意数量县份）
# ═══════════════════════════════════════════════════════
def plot_county_radar(data_dict: dict, output_dir: str,
                      year: int = None) -> dict:
    """
    多县PQI/PCI/RQI对比雷达图。
    data_dict 中除 '全部' 键外的所有县份都参与对比，
    颜色调色板自动扩展，支持任意数量县份。
    """
    ensure_dir(output_dir)

    counties = [k for k in data_dict.keys() if k != '全部']
    if not counties:
        return {}

    metrics = ['PQI', 'PCI', 'RQI']
    county_vals = {}
    for county in counties:
        df = data_dict[county].copy()
        if year and '年份' in df.columns:
            df = df[df['年份'] == year]
        vals = []
        for m in metrics:
            if m in df.columns and not df[m].isna().all():
                vals.append(round(df[m].mean(), 1))
            else:
                vals.append(0)
        county_vals[county] = vals

    num_vars = len(metrics)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    # 动态颜色调色板（支持任意多县）
    palette = [
        '#2980b9', '#27ae60', '#e67e22', '#8e44ad',
        '#c0392b', '#16a085', '#d35400', '#2c3e50',
        '#f39c12', '#1abc9c'
    ]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    for i, (county, vals) in enumerate(county_vals.items()):
        plot_vals = vals + vals[:1]
        color = palette[i % len(palette)]
        ax.plot(angles, plot_vals, 'o-', linewidth=2,
                label=county, color=color)
        ax.fill(angles, plot_vals, alpha=0.08, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=12)
    ax.set_ylim(55, 100)
    ax.set_yticks([60, 70, 75, 80, 85, 90, 95])
    ax.yaxis.set_tick_params(labelsize=7)

    n = len(counties)
    county_label = f'{n}县' if n != 4 else '四县'
    title = (f'{county_label}路面状况指数对比雷达图（{year}年）'
             if year else f'{county_label}路面状况指数对比雷达图')
    ax.set_title(title, fontsize=12, fontweight='bold', pad=20)

    # 图例位置随县数自适应
    legend_anchor = (1.35, 1.1) if n <= 4 else (1.4, 1.15)
    ax.legend(loc='upper right', bbox_to_anchor=legend_anchor, fontsize=10)
    ax.grid(True, alpha=0.3)

    suffix = f'_{year}' if year else ''
    path = os.path.join(output_dir, f'多县对比雷达图{suffix}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path, 'data': county_vals}


# ═══════════════════════════════════════════════════════
# 7. 多县PQI均值横向对比柱状图（新增）
# ═══════════════════════════════════════════════════════
def plot_county_bar_compare(data_dict: dict, output_dir: str,
                             year: int = None) -> dict:
    """
    多县PQI/PCI/RQI均值横向对比柱状图，支持任意数量县份。
    """
    ensure_dir(output_dir)

    counties = [k for k in data_dict.keys() if k != '全部']
    if len(counties) < 2:
        return {}

    metrics = ['PQI', 'PCI', 'RQI']
    records = []
    for county in counties:
        df = data_dict[county].copy()
        if year and '年份' in df.columns:
            df = df[df['年份'] == year]
        row = {'县份': county}
        for m in metrics:
            row[m] = round(df[m].mean(), 2) if m in df.columns and not df[m].isna().all() else 0
        records.append(row)

    cdf = pd.DataFrame(records).set_index('县份')

    fig, ax = plt.subplots(figsize=(max(8, len(counties) * 1.8), 5.5))
    x = np.arange(len(counties))
    width = 0.25
    offsets = np.linspace(-(len(metrics)-1)/2*width,
                          (len(metrics)-1)/2*width, len(metrics))

    for j, metric in enumerate(metrics):
        vals = [cdf.loc[c, metric] for c in counties]
        bars = ax.bar(x + offsets[j], vals, width,
                      label=metric,
                      color=METRIC_COLORS[metric],
                      edgecolor='white', linewidth=0.6)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.3,
                        f'{val:.1f}', ha='center', fontsize=8,
                        color=METRIC_COLORS[metric])

    ax.set_xticks(x)
    ax.set_xticklabels(counties, fontsize=10)
    ax.set_ylabel('指数均值', fontsize=11)
    ax.set_ylim(55, 100)
    title_year = f'（{year}年）' if year else ''
    ax.set_title(f'各县路面状况指数横向对比{title_year}',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=75, color='#e74c3c', linestyle='--',
               linewidth=1, alpha=0.4)
    ax.axhline(y=85, color='#27ae60', linestyle='--',
               linewidth=1, alpha=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    suffix = f'_{year}' if year else ''
    path = os.path.join(output_dir, f'多县横向对比柱状图{suffix}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path, 'data': cdf.to_dict()}


# ═══════════════════════════════════════════════════════
# 8. 养护需求分析（依据Excel中的单价和养护判定逻辑）
# ═══════════════════════════════════════════════════════
def analyze_maintenance_need(df: pd.DataFrame, year: int = None) -> dict:
    """
    根据PQI/PCI/RQI等级判断养护类型，用路面类型差异化单价估算费用。
    判定逻辑参照养护需求预测.xlsx中的推荐措施列。
    """
    if year:
        sub = df[df['年份'] == year].copy()
    else:
        sub = df.copy()

    if sub.empty or 'PQI' not in sub.columns:
        return {}

    def classify(row):
        pqi = row.get('PQI', 100) or 100
        pci = row.get('PCI', 100) or 100
        rqi = row.get('RQI', 100) or 100
        if pqi < 60 or pci < 60:
            return '路面改造'
        if pqi < 72 or pci < 70:
            return '中修'
        if pqi < 82 or pci < 80 or rqi < 85:
            return '预防养护'
        return '日常养护'

    sub['养护建议'] = sub.apply(classify, axis=1)

    # 估算费用：面积 = 里程 × 路面宽度
    def calc_cost(row):
        mtype = row.get('养护建议', '日常养护')
        ptype = str(row.get('路面类型', ''))
        km = row.get('路段长度km', 0) or 0
        width = row.get('路面宽度', DEFAULT_WIDTH) or DEFAULT_WIDTH

        price_map = UNIT_PRICE_PER_M2.get(mtype, {})
        if '沥青' in ptype:
            price = price_map.get('沥青路面', price_map.get('default', 0))
        elif '水泥' in ptype:
            price = price_map.get('水泥路面', price_map.get('default', 0))
        else:
            price = price_map.get('default', 0)

        area_m2 = km * 1000 * width
        return round(area_m2 * price / 10000, 2)   # 转万元

    sub['估算费用(万元)'] = sub.apply(calc_cost, axis=1)

    maint_summary = sub.groupby('养护建议').agg(
        路段数=('路线编码', 'count'),
        里程_km=('路段长度km', 'sum'),
        费用_万元=('估算费用(万元)', 'sum')
    ).round(2)

    # 按路线汇总
    route_summary = None
    if '路线编码' in sub.columns:
        route_summary = sub.groupby(['路线编码', '养护建议']).agg(
            里程_km=('路段长度km', 'sum'),
            费用_万元=('估算费用(万元)', 'sum')
        ).round(2).reset_index()

    return {
        'detail': sub[['路线编码', '方向', '路段起点', '路段终点',
                        '路段长度km', 'PQI', 'PCI', 'RQI',
                        '养护建议', '估算费用(万元)']].copy(),
        'summary': maint_summary,
        'route_summary': route_summary,
        'total_cost_wan': round(maint_summary['费用_万元'].sum(), 2)
    }


def plot_maintenance_bar(maint_result: dict, county: str,
                         output_dir: str, year: int = None) -> dict:
    """
    养护需求双图：左=各养护类型里程柱状，右=各养护类型费用柱状。
    """
    ensure_dir(output_dir)

    if not maint_result or 'summary' not in maint_result:
        return {}

    summary = maint_result['summary']
    present = [o for o in MAINT_ORDER if o in summary.index]
    if not present:
        return {}

    values = [summary.loc[o, '里程_km'] for o in present]
    costs  = [summary.loc[o, '费用_万元'] for o in present]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    # ── 里程 ──
    bars1 = ax1.bar(present, values,
                    color=[MAINT_COLORS[p] for p in present],
                    edgecolor='white', width=0.6)
    for bar, val in zip(bars1, values):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(values) * 0.02,
                 f'{val:.1f} km', ha='center', va='bottom', fontsize=9)
    ax1.set_ylabel('里程 (km)', fontsize=11)
    year_str = str(year) if year else ''
    ax1.set_title(f'{county}  {year_str}年  养护需求里程', fontsize=12, fontweight='bold')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_ylim(0, max(values) * 1.25 if values else 10)

    # ── 费用 ──
    bars2 = ax2.bar(present, costs,
                    color=[MAINT_COLORS[p] for p in present],
                    edgecolor='white', width=0.6)
    for bar, val in zip(bars2, costs):
        label = f'{val:.0f}万' if val < 10000 else f'{val/10000:.2f}亿'
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(costs) * 0.02,
                 label, ha='center', va='bottom', fontsize=9)
    ax2.set_ylabel('估算费用 (万元)', fontsize=11)
    total_cost = sum(costs)
    cost_label = f'{total_cost:.0f}万元' if total_cost < 10000 else f'{total_cost/10000:.2f}亿元'
    ax2.set_title(f'{county}  {year_str}年  养护需求费用  (合计 {cost_label})',
                  fontsize=12, fontweight='bold')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_ylim(0, max(costs) * 1.25 if costs else 10)

    path = os.path.join(output_dir, f'{county}_{year}_养护需求.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path}


# ═══════════════════════════════════════════════════════
# 9. 路线级养护需求汇总图（新增，参照Excel Sheet3逻辑）
# ═══════════════════════════════════════════════════════
def plot_route_maintenance(maint_result: dict, county: str,
                           output_dir: str, year: int = None) -> dict:
    """
    按路线编码展示养护需求堆叠柱状图（里程 + 费用双图），
    对应Excel Sheet3中各路线分项工程量汇总逻辑。
    """
    ensure_dir(output_dir)

    if not maint_result or 'route_summary' not in maint_result:
        return {}
    rs = maint_result['route_summary']
    if rs is None or rs.empty:
        return {}

    routes = sorted(rs['路线编码'].unique())
    if len(routes) > 20:
        # 取里程最大的前20条路线
        top_routes = rs.groupby('路线编码')['里程_km'].sum().nlargest(20).index
        rs = rs[rs['路线编码'].isin(top_routes)]
        routes = sorted(rs['路线编码'].unique())

    pivot_km   = rs.pivot_table(index='路线编码', columns='养护建议',
                                values='里程_km',  aggfunc='sum', fill_value=0)
    pivot_cost = rs.pivot_table(index='路线编码', columns='养护建议',
                                values='费用_万元', aggfunc='sum', fill_value=0)

    # 统一列顺序
    for pivot in (pivot_km, pivot_cost):
        for g in MAINT_ORDER:
            if g not in pivot.columns:
                pivot[g] = 0
    pivot_km   = pivot_km[[g for g in MAINT_ORDER if g in pivot_km.columns]]
    pivot_cost = pivot_cost[[g for g in MAINT_ORDER if g in pivot_cost.columns]]

    fig, (ax1, ax2) = plt.subplots(2, 1,
                                    figsize=(max(12, len(routes) * 0.9 + 3), 11))
    x = np.arange(len(routes))

    for ax, pivot, ylabel, title_suffix in [
        (ax1, pivot_km,   '里程 (km)',   '养护需求里程'),
        (ax2, pivot_cost, '费用 (万元)', '养护需求费用'),
    ]:
        bottoms = np.zeros(len(routes))
        for grade in [g for g in MAINT_ORDER if g in pivot.columns]:
            vals = [pivot.loc[r, grade] if r in pivot.index else 0
                    for r in routes]
            vals = np.array(vals, dtype=float)
            bars = ax.bar(x, vals, bottom=bottoms, label=grade,
                          color=MAINT_COLORS[grade],
                          edgecolor='white', linewidth=0.4, width=0.7)
            for i, (bar, val) in enumerate(zip(bars, vals)):
                if val > 0.5:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bottoms[i] + val / 2,
                            f'{val:.0f}', ha='center', va='center',
                            fontsize=7, color='white', fontweight='bold')
            bottoms += vals

        ax.set_xticks(x)
        ax.set_xticklabels(routes, rotation=35, ha='right', fontsize=8)
        ax.set_ylabel(ylabel, fontsize=10)
        year_str = str(year) if year else ''
        ax.set_title(f'{county}  {year_str}年  各路线{title_suffix}',
                     fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8, ncol=4)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

    path = os.path.join(output_dir, f'{county}_{year}_路线养护汇总.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return {'path': path}


# ═══════════════════════════════════════════════════════
# 10. 5年养护需求预测图（新增，参照Excel Sheet4/Sheet5逻辑）
# ═══════════════════════════════════════════════════════
def plot_5year_forecast(df: pd.DataFrame, county: str,
                        output_dir: str, base_year: int = None) -> dict:
    """
    基于当前路况数据，预测未来5年各类养护里程和资金需求。
    逻辑参照养护需求预测.xlsx Sheet4/Sheet5：
    - 按每个路段的路面类型 × 技术等级查表获取衰减系数 k
    - 指数衰减：PQI_t = PQI_0 * exp(-k_PQI * t)，PCI/RQI同理
    - 如预测年份判断需要路面改造/中修，则改造后第2年恢复至85（模拟养护效果）
    """
    ensure_dir(output_dir)

    if 'PQI' not in df.columns:
        return {}

    if base_year is None:
        base_year = int(df['年份'].max()) if '年份' in df.columns else 2025

    base = df[df['年份'] == base_year].copy() if '年份' in df.columns else df.copy()
    if base.empty:
        return {}

    forecast_years = list(range(base_year + 1, base_year + 6))

    def classify_need(pqi, pci, rqi):
        if pqi < 60 or pci < 60:
            return '路面改造'
        if pqi < 82 or pci < 80 or rqi < 85:
            return '预防养护'
        return '日常养护'

    def calc_cost_row(row, mtype):
        ptype = str(row.get('路面类型', ''))
        km    = row.get('路段长度km', 0) or 0
        width = row.get('路面宽度', DEFAULT_WIDTH) or DEFAULT_WIDTH
        price_map = UNIT_PRICE_PER_M2.get(mtype, {})
        if '沥青' in ptype:
            price = price_map.get('沥青路面', price_map.get('default', 0))
        elif '水泥' in ptype:
            price = price_map.get('水泥路面', price_map.get('default', 0))
        else:
            price = price_map.get('default', 0)
        return round(km * 1000 * width * price / 10000, 2)

    # 逐路段逐年预测（携带"上次改造时间"状态）
    # 初始化：每行路段有自己的当前PQI/PCI/RQI
    seg = base.copy()
    seg['_pqi'] = seg['PQI'].fillna(85)
    seg['_pci'] = seg['PCI'].fillna(85)
    seg['_rqi'] = seg['RQI'].fillna(85)
    seg['_years_since_repair'] = 0   # 距上次改造年数

    year_data = {}
    for offset, fy in enumerate(forecast_years, start=1):
        # 衰减：对每行按路面类型+技术等级取衰减系数
        ptype_arr  = seg.get('路面类型',  pd.Series(['沥青路面'] * len(seg))).fillna('沥青路面')
        tgrade_arr = seg.get('技术等级',  pd.Series(['三级公路'] * len(seg))).fillna('三级公路')

        k_pqi = np.array([get_decay_rate(p, g, 'PQI') for p, g in zip(ptype_arr, tgrade_arr)])
        k_pci = np.array([get_decay_rate(p, g, 'PCI') for p, g in zip(ptype_arr, tgrade_arr)])
        k_rqi = np.array([get_decay_rate(p, g, 'RQI') for p, g in zip(ptype_arr, tgrade_arr)])

        seg['_pqi'] = np.clip(seg['_pqi'].values * np.exp(-k_pqi), 0, 100)
        seg['_pci'] = np.clip(seg['_pci'].values * np.exp(-k_pci), 0, 100)
        seg['_rqi'] = np.clip(seg['_rqi'].values * np.exp(-k_rqi), 0, 100)

        seg['_养护建议'] = [
            classify_need(r['_pqi'], r['_pci'], r['_rqi'])
            for _, r in seg.iterrows()
        ]
        seg['_费用'] = [calc_cost_row(r, r['_养护建议']) for _, r in seg.iterrows()]

        # 对需要路面改造/中修的路段，模拟养护后下一年指标恢复到85
        repair_mask = seg['_养护建议'].isin(['路面改造', '中修'])
        seg.loc[repair_mask, '_pqi'] = 85.0
        seg.loc[repair_mask, '_pci'] = 85.0
        seg.loc[repair_mask, '_rqi'] = 85.0

        summ = seg.groupby('_养护建议').agg(
            里程_km=('路段长度km', 'sum'),
            费用_万元=('_费用', 'sum')
        ).round(2)

        year_data[fy] = {
            'km':   {g: summ.loc[g, '里程_km']   if g in summ.index else 0 for g in MAINT_ORDER},
            'cost': {g: summ.loc[g, '费用_万元'] if g in summ.index else 0 for g in MAINT_ORDER},
        }

    # ── 绘图 ──
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    x = np.arange(len(forecast_years))

    for ax, key, ylabel, title_suffix in [
        (axes[0], 'km',   '里程 (km)',   '养护里程预测'),
        (axes[1], 'cost', '费用 (万元)', '养护资金预测'),
    ]:
        bottoms = np.zeros(len(forecast_years))
        for grade in MAINT_ORDER:
            vals = np.array([year_data[fy][key].get(grade, 0) for fy in forecast_years])
            bars = ax.bar(x, vals, bottom=bottoms, label=grade,
                          color=MAINT_COLORS[grade],
                          edgecolor='white', linewidth=0.4, width=0.6)
            total_max = max((sum(year_data[fy][key].values()) for fy in forecast_years), default=1)
            for i, (bar, val) in enumerate(zip(bars, vals)):
                if val > total_max * 0.04:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bottoms[i] + val / 2,
                            f'{val:.0f}', ha='center', va='center',
                            fontsize=7.5, color='white', fontweight='bold')
            bottoms += vals

        # 总量标注在顶部
        for i, fy in enumerate(forecast_years):
            total = sum(year_data[fy][key].values())
            label = f'{total:.0f}万' if key == 'cost' and total < 10000 else (
                f'{total/10000:.1f}亿' if key == 'cost' else f'{total:.0f}km')
            ax.text(i, bottoms[i] + bottoms[i] * 0.01 + 1,
                    label, ha='center', fontsize=8, color=THEME_DARK, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in forecast_years])
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(f'{county}  {base_year+1}—{base_year+5}年  {title_suffix}\n'
                     f'（指数衰减模型，按路面类型×技术等级差异化衰减率）',
                     fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9, ncol=2)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

    path = os.path.join(output_dir, f'{county}_{base_year}_5年养护预测.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    total_km   = {fy: sum(year_data[fy]['km'].values())   for fy in forecast_years}
    total_cost = {fy: sum(year_data[fy]['cost'].values()) for fy in forecast_years}

    return {
        'path': path,
        'forecast_years': forecast_years,
        'year_data': year_data,
        'total_km': total_km,
        'total_cost': total_cost,
    }


# ═══════════════════════════════════════════════════════
# 11. 汇总入口：一次性生成所有图表
# ═══════════════════════════════════════════════════════
def generate_all_charts(data_dict: dict, output_dir: str,
                        target_county: str = None) -> dict:
    """
    生成所有图表，返回图表路径字典。

    Args:
        data_dict:     {county: DataFrame} 字典，可含 '全部' 键
        output_dir:    图表输出目录
        target_county: 主要分析的县份，None 表示分析所有县
    """
    charts = {}
    ensure_dir(output_dir)

    counties = [k for k in data_dict.keys() if k != '全部']
    primary  = [target_county] if (target_county and target_county in data_dict) else counties

    for county in primary:
        df = data_dict[county]
        if df.empty:
            continue

        latest_year = int(df['年份'].max()) if '年份' in df.columns else None
        charts[county] = {}

        # 1. 趋势图
        r = plot_trend(df, county, output_dir)
        if r:
            charts[county]['trend'] = r

        # 2. 等级分布（最新年份）
        r = plot_grade_distribution(df, county, output_dir, latest_year)
        if r:
            charts[county]['grade_dist'] = r

        # 3. 历年等级堆叠图
        r = plot_grade_yearly_stacked(df, county, output_dir)
        if r:
            charts[county]['grade_stacked'] = r

        # 4. 路面类型饼图
        r = plot_pavement_type(df, county, output_dir, latest_year)
        if r:
            charts[county]['pavement_type'] = r

        # 5. 技术等级分布
        r = plot_tech_grade(df, county, output_dir, latest_year)
        if r:
            charts[county]['tech_grade'] = r

        # 6. 养护需求分析
        maint = analyze_maintenance_need(df, latest_year)
        if maint:
            charts[county]['maintenance'] = maint

            r = plot_maintenance_bar(maint, county, output_dir, latest_year)
            if r:
                charts[county]['maintenance_chart'] = r

            # 7. 路线级养护汇总图
            r = plot_route_maintenance(maint, county, output_dir, latest_year)
            if r:
                charts[county]['route_maintenance_chart'] = r

        # 8. 5年养护预测图
        r = plot_5year_forecast(df, county, output_dir, latest_year)
        if r:
            charts[county]['forecast_5year'] = r

    # 9. 多县横向对比柱状图（动态，支持任意数量）
    if len(counties) > 1:
        all_df = data_dict.get('全部', pd.DataFrame())
        latest = None
        if not all_df.empty and '年份' in all_df.columns:
            latest = int(all_df['年份'].max())
        elif counties:
            for c in counties:
                d = data_dict[c]
                if '年份' in d.columns:
                    ly = int(d['年份'].max())
                    if latest is None or ly > latest:
                        latest = ly

        r = plot_county_bar_compare(data_dict, output_dir, latest)
        if r:
            charts['多县对比_柱状'] = r

    return charts
