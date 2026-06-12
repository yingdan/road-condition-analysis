"""
数据加载与清洗模块
兼容2021-2025年各年份不同格式的四县路况Excel表格
"""
import pandas as pd
import numpy as np
import os

# 各年份列名映射：统一映射到标准列名
COLUMN_MAPS = {
    2021: {
        '路线': '路线编码', '路段长度': '路段长度km', '路段宽度': '路面宽度',
    },
    2022: {
        '路线': '路线编码', '路段长度': '路段长度km', '路段宽度': '路面宽度',
    },
    2023: {
        '路段宽度': '路面宽度',  # 2023年列名是"路段宽度"
    },
    2024: {
        '路段宽度': '路面宽度',  # 2024年列名是"路段宽度"
    },
    2025: {
        '路段宽度': '路面宽度',  # 2025年列名是"路段宽度"
    },
}

# 核心字段：所有年份都尝试提取的字段
CORE_COLS = [
    '路线编码', '方向', '路段起点', '路段终点', '路段长度km',
    '政区名称', '养管单位', '技术等级', '路面类型',
    'PQI', 'PCI', 'RQI', '路面宽度',
]

# 附加字段（部分年份有，缺少时自动填充默认值）
EXTRA_COLS = [
    'PQI分级', 'PCI分级', 'RQI分级',
    'PBI', 'RDI', 'PWI',
    'DR', 'IRI', 'RD',
    '块修(m2)', '条修(m2)', '龟裂/破碎板(m2)', '松散/露骨(m2)', '坑槽(m2)', '横缝(m)', '纵缝(m)',
    '路龄', '交通量',           # 经济分析字段（AADT/路龄）
    '修建年份', '大修年份',     # 维护历史字段
    '日均交通量', '车道数',     # 交通荷载字段
]

# 剔除标记字段（用于过滤无效路段）
EXCLUDE_COLS_CANDIDATES = ['剔除路段', '剔除类型', '上报剔除', '现场剔除', '重复路段']

# PQI分级标准
def classify_pqi(val):
    if pd.isna(val): return '未知'
    if val >= 90: return '优'
    if val >= 80: return '良'
    if val >= 70: return '中'
    if val >= 60: return '次'
    return '差'

def classify_pci(val):
    if pd.isna(val): return '未知'
    if val >= 90: return '优'
    if val >= 80: return '良'
    if val >= 70: return '中'
    if val >= 60: return '次'
    return '差'

def classify_rqi(val):
    if pd.isna(val): return '未知'
    if val >= 95: return '优'
    if val >= 90: return '良'
    if val >= 85: return '中'
    if val >= 80: return '次'
    return '差'


def load_year_sheet(filepath: str, year: int, sheet_name: str) -> pd.DataFrame:
    """加载单个年份单个县的sheet，清洗并标准化列名"""
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    
    # 列名重命名
    col_map = COLUMN_MAPS.get(year, {})
    df = df.rename(columns=col_map)
    
    # 过滤剔除路段
    for col in EXCLUDE_COLS_CANDIDATES:
        if col in df.columns:
            # 剔除标记为"上报剔除"或包含"剔除"关键词的行
            if col in ('剔除路段', '剔除类型'):
                mask = df[col].notna() & (df[col].astype(str).str.contains('剔除', na=False))
                df = df[~mask]
            elif col == '上报剔除':
                mask = df[col].notna() & (df[col].astype(str).str.contains('剔除', na=False))
                df = df[~mask]
            elif col == '重复路段':
                mask = df[col].notna() & (df[col].astype(str).str.len() > 0) & (df[col].astype(str) != 'nan')
                df = df[~mask]
    
    # 提取核心列
    available_core = [c for c in CORE_COLS if c in df.columns]
    available_extra = [c for c in EXTRA_COLS if c in df.columns]
    df = df[available_core + available_extra].copy()
    
    # 路段长度标准化
    if '路段长度km' in df.columns:
        df['路段长度km'] = pd.to_numeric(df['路段长度km'], errors='coerce')
    
    # 指标数值化
    for col in ['PQI', 'PCI', 'RQI', 'PBI', 'RDI', 'PWI', 'DR', 'IRI', 'RD']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 补充分级列（若原表无分级列则自动计算）
    if 'PQI分级' not in df.columns and 'PQI' in df.columns:
        df['PQI分级'] = df['PQI'].apply(classify_pqi)
    if 'PCI分级' not in df.columns and 'PCI' in df.columns:
        df['PCI分级'] = df['PCI'].apply(classify_pci)
    if 'RQI分级' not in df.columns and 'RQI' in df.columns:
        df['RQI分级'] = df['RQI'].apply(classify_rqi)

    # 经济分析字段：缺失时填充默认值
    # 路龄：默认根据修建年份或假设为5年
    if '路龄' not in df.columns:
        if '修建年份' in df.columns:
            df['路龄'] = year - pd.to_numeric(df['修建年份'], errors='coerce')
        else:
            df['路龄'] = 5
    # 交通量(AADT)：默认5000辆/天
    for col in ['交通量', '日均交通量']:
        if col in df.columns and '交通量' not in df.columns:
            df.rename(columns={col: '交通量'}, inplace=True)
    if '交通量' not in df.columns:
        df['交通量'] = 5000
    # 车道数：默认2车道
    if '车道数' not in df.columns:
        df['车道数'] = 2
    # 数值化
    for col in ['路龄', '交通量', '车道数']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna({'路龄':5,'交通量':5000,'车道数':2}[col])

    # 剔除PQI/PCI/RQI全为空的行
    df = df.dropna(subset=['PQI', 'PCI', 'RQI'], how='all')
    
    # 添加年份和县份标识
    df['年份'] = year
    df['县份'] = sheet_name
    
    return df.reset_index(drop=True)


def load_all_data(file_map: dict, counties: list = None) -> dict:
    """
    加载所有年份所有县份数据

    Args:
        file_map: {year(int or str): filepath} 字典
        counties: 要加载的县份列表，None表示加载全部

    Returns:
        {county_name: DataFrame(所有年份合并)} 字典
    """
    all_records = []
    county_set = set()

    for year_key, filepath in file_map.items():
        if not filepath or not os.path.exists(filepath):
            continue
        year = int(year_key)
        try:
            xl = pd.ExcelFile(filepath)
            sheets = xl.sheet_names
            for sheet in sheets:
                if counties and sheet not in counties:
                    continue
                county_set.add(sheet)
                try:
                    df = load_year_sheet(filepath, year, sheet)
                    all_records.append(df)
                except Exception as e:
                    print(f"Warning: Failed to load {year} {sheet}: {e}")
        except Exception as e:
            print(f"Warning: Cannot open file {filepath}: {e}")

    if not all_records:
        return {}

    merged = pd.concat(all_records, ignore_index=True)

    result = {}
    for county in county_set:
        result[county] = merged[merged['县份'] == county].reset_index(drop=True)
    result['全部'] = merged.reset_index(drop=True)

    return result


def get_available_sheets(filepath: str) -> list:
    """获取Excel文件中的工作表名称"""
    try:
        xl = pd.ExcelFile(filepath)
        return xl.sheet_names
    except:
        return []


def get_summary_stats(df: pd.DataFrame) -> dict:
    """获取数据集基本统计摘要"""
    if df.empty:
        return {}
    
    stats = {
        'total_segments': len(df),
        'total_length_km': df['路段长度km'].sum() if '路段长度km' in df.columns else 0,
        'years': sorted(df['年份'].unique().tolist()) if '年份' in df.columns else [],
        'counties': df['县份'].unique().tolist() if '县份' in df.columns else [],
    }
    
    for col in ['PQI', 'PCI', 'RQI']:
        if col in df.columns:
            stats[f'{col}_mean'] = round(df[col].mean(), 2)
            stats[f'{col}_min'] = round(df[col].min(), 2)
            stats[f'{col}_max'] = round(df[col].max(), 2)
    
    return stats
