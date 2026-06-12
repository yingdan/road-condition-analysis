"""
PostGIS 地理信息展示模块
用于在地图上展示公路路况和养护信息
"""
import pandas as pd
import numpy as np
import os
import webbrowser
from typing import Dict, List, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════════════
# GIS地图生成器
# ══════════════════════════════════════════════════════════════════════════════════════

class GISMapGenerator:
    """基于Folium生成交互式GIS地图"""

    def __init__(self):
        self.folium_available = False
        self._check_import()

    def _check_import(self):
        """检查folium是否可用"""
        try:
            import folium
            from folium.plugins import MarkerCluster, MeasureControl
            self.folium = folium
            self.folium_available = True
        except ImportError:
            print("folium not installed. Run: pip install folium")
            self.folium = None

    def create_map(self, center: Tuple[float, float] = (23.9, 115.75),
                   zoom: int = 10) -> Optional:
        """创建地图对象"""
        if not self.folium_available:
            return None
        return self.folium.Map(location=center, zoom_start=zoom)

    def add_road_segments(self, df: pd.DataFrame,
                         color_by: str = 'pqi',
                         popup_fields: List[str] = None) -> Optional:
        """
        在地图上添加路段

        Args:
            df: 路段数据DataFrame，需包含 lat_start, lon_start, lat_end, lon_end
            color_by: 颜色字段 ('pqi', 'pci', 'rqi', 'grade')
            popup_fields: 弹窗显示的字段
        """
        if not self.folium_available or df is None or df.empty:
            return None

        if popup_fields is None:
            popup_fields = ['路线编码', 'PQI', 'PCI', 'RQI', '路面类型']

        m = self.create_map()

        for _, row in df.iterrows():
            # 检查是否有坐标
            if not all(col in row for col in ['lat_start', 'lon_start', 'lat_end', 'lon_end']):
                continue

            lat1, lon1 = row['lat_start'], row['lon_start']
            lat2, lon2 = row['lat_end'], row['lon_end']

            if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
                continue

            # 获取颜色
            color = self._get_color(row.get(color_by, 80), color_by)

            # 创建popup内容
            popup_text = self._create_popup(row, popup_fields)

            # 绘制线段
            locations = [[lat1, lon1], [lat2, lon2]]
            self.folium.PolyLine(
                locations,
                color=color,
                weight=5,
                popup=self.folium.Popup(popup_text, max_width=300)
            ).add_to(m)

        # 添加图例
        self._add_legend(m, color_by)

        return m

    def _get_color(self, value: float, metric: str) -> str:
        """根据指标值获取颜色"""
        if pd.isna(value):
            return '#808080'  # 灰色

        if metric in ['pqi', 'pci', 'rqi']:
            if value >= 90:
                return '#00FF00'  # 绿色
            elif value >= 80:
                return '#7FFF00'  # 黄绿色
            elif value >= 70:
                return '#FFFF00'  # 黄色
            elif value >= 60:
                return '#FF7F00'  # 橙色
            else:
                return '#FF0000'  # 红色
        elif metric == 'grade':
            colors = {
                '优': '#00FF00',
                '良': '#7FFF00',
                '中': '#FFFF00',
                '次': '#FF7F00',
                '差': '#FF0000'
            }
            return colors.get(str(value), '#808080')

        return '#0000FF'

    def _create_popup(self, row: pd.Series, fields: List[str]) -> str:
        """创建popup HTML内容"""
        html = '<div style="width:250px">'
        html += '<table style="width:100%">'

        field_names = {
            '路线编码': 'route_code',
            '路段起点': 'segment_start',
            '路段终点': 'segment_end',
            '长度km': 'length_km',
            '路面类型': 'pavement_type',
            'PQI': 'pqi',
            'PCI': 'pci',
            'RQI': 'rqi',
            'PQI分级': 'pqi_grade',
            '路面宽度': 'width_m',
            '技术等级': 'technical_grade',
            '县份': 'county',
            '年份': 'year'
        }

        for display_name in fields:
            col = field_names.get(display_name, display_name)
            value = row.get(col, 'N/A')
            if isinstance(value, float):
                value = f'{value:.1f}'
            html += f'<tr><td><b>{display_name}</b></td><td>{value}</td></tr>'

        html += '</table></div>'
        return html

    def _add_legend(self, m, metric: str):
        """添加图例"""
        if not self.folium_available:
            return

        legend_html = '''
        <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                    background-color: white; padding: 10px; border: 2px solid gray;
                    border-radius: 5px; font-size: 12px;">
            <div style="font-weight: bold; margin-bottom: 5px;">路面技术状况</div>
        '''

        if metric in ['pqi', 'pci', 'rqi']:
            legend_html += '''
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#00FF00; margin-right:5px;"></div>优(≥90)
                </div>
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#7FFF00; margin-right:5px;"></div>良(80-89)
                </div>
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#FFFF00; margin-right:5px;"></div>中(70-79)
                </div>
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#FF7F00; margin-right:5px;"></div>次(60-69)
                </div>
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#FF0000; margin-right:5px;"></div>差(<60)
                </div>
            '''
        else:
            legend_html += '''
                <div style="display:flex; align-items:center; margin:2px 0;">
                    <div style="width:20px; height:10px; background:#0000FF; margin-right:5px;"></div>路段
                </div>
            '''

        legend_html += '</div>'

        m.get_root().html.add_child(self.folium.Element(legend_html))

    def add_markers(self, df: pd.DataFrame,
                    lat_col: str = 'latitude',
                    lon_col: str = 'longitude',
                    popup_fields: List[str] = None):
        """添加标记点"""
        if not self.folium_available or df is None or df.empty:
            return None

        m = self.create_map()

        for _, row in df.iterrows():
            lat = row.get(lat_col)
            lon = row.get(lon_col)

            if pd.isna(lat) or pd.isna(lon):
                continue

            popup_text = self._create_popup(row, popup_fields or ['name', 'description'])

            self.folium.Marker(
                [lat, lon],
                popup=self.folium.Popup(popup_text, max_width=250)
            ).add_to(m)

        return m

    def save_map(self, m, filename: str = 'road_map.html'):
        """保存地图为HTML文件"""
        if m is None:
            return False

        output_path = os.path.join('output', filename)
        os.makedirs('output', exist_ok=True)
        m.save(output_path)
        return output_path

    def open_map(self, filename: str = 'road_map.html'):
        """在浏览器中打开地图"""
        filepath = os.path.join('output', filename)
        if os.path.exists(filepath):
            webbrowser.open(f'file://{os.path.abspath(filepath)}')


# ══════════════════════════════════════════════════════════════════════════════════════
# 桩号到坐标转换（简化版，需要实际的道路线数据）
# ══════════════════════════════════════════════════════════════════════════════════════

class RouteCoordinateMapper:
    """
    路线桩号与GPS坐标映射（简化实现）

    实际项目中需要：
    1. 导入道路中心线GIS数据
    2. 建立桩号与坐标的对应关系
    """

    def __init__(self):
        self.route_lines = {}  # route_code -> [(lat, lon), ...]

    def load_from_gis(self, gis_file: str):
        """从GIS文件加载路线数据（GeoJSON, Shapefile等）"""
        try:
            import geopandas as gpd
            gdf = gpd.read_file(gis_file)

            for _, row in gdf.iterrows():
                route_code = row.get('route_code', row.get('路线编码', 'UNKNOWN'))
                geom = row.geometry

                if geom.geom_type == 'LineString':
                    coords = [[lat, lon] for lon, lat in geom.coords]
                    self.route_lines[route_code] = coords

            return True
        except Exception as e:
            print(f"Failed to load GIS: {e}")
            return False

    def get_segment_coords(self, route_code: str,
                           start_km: float, end_km: float) -> Tuple:
        """
        根据桩号获取路段起终点坐标

        Args:
            route_code: 路线编码
            start_km: 起点公里数
            end_km: 终点公里数

        Returns:
            (lat_start, lon_start, lat_end, lon_end)
        """
        if route_code not in self.route_lines:
            return None, None, None, None

        coords = self.route_lines[route_code]
        if not coords:
            return None, None, None, None

        # 简化实现：取路线上对应桩号位置的坐标
        # 实际需要根据道路长度比例计算
        n = len(coords)

        # 假设路线总长度与坐标点数成比例
        start_idx = min(int(start_km / 100 * n), n - 1)
        end_idx = min(int(end_km / 100 * n), n - 1)

        lat_start = coords[start_idx][0]
        lon_start = coords[start_idx][1]
        lat_end = coords[end_idx][0]
        lon_end = coords[end_idx][1]

        return lat_start, lon_start, lat_end, lon_end

    def add_coordinates_to_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        为DataFrame添加坐标列

        需要df包含 route_code, km_start, km_end 列
        """
        if df is None or df.empty:
            return df

        df = df.copy()

        # 添加坐标列
        for col in ['lat_start', 'lon_start', 'lat_end', 'lon_end']:
            df[col] = None

        for idx, row in df.iterrows():
            route = row.get('路线编码', '')
            start = row.get('km_start', 0)
            end = row.get('km_end', 0)

            lat1, lon1, lat2, lon2 = self.get_segment_coords(route, start, end)

            df.at[idx, 'lat_start'] = lat1
            df.at[idx, 'lon_start'] = lon1
            df.at[idx, 'lat_end'] = lat2
            df.at[idx, 'lon_end'] = lon2

        return df


# ══════════════════════════════════════════════════════════════════════════════════════
# 地图模板生成
# ══════════════════════════════════════════════════════════════════════════════════════

def generate_condition_map(df: pd.DataFrame,
                          year: int = None,
                          output_file: str = '路况地图.html') -> str:
    """
    生成路况状况地图

    Args:
        df: 路况数据DataFrame
        year: 年份
        output_file: 输出文件名

    Returns:
        HTML文件路径
    """
    if df is None or df.empty:
        print("No data to display on map")
        return None

    generator = GISMapGenerator()

    # 过滤指定年份
    if year and '年份' in df.columns:
        df = df[df['年份'] == year]

    # 生成地图
    m = generator.create_map()

    # 添加路段
    m = generator.add_road_segments(df, color_by='pqi')

    # 保存
    if m:
        return generator.save_map(m, output_file)

    return None


def generate_maintenance_map(projects: List[Dict],
                           output_file: str = '养护项目地图.html') -> str:
    """生成养护项目分布地图"""
    if not projects:
        return None

    generator = GISMapGenerator()
    m = generator.create_map()

    for proj in projects:
        # 简化：假设项目有点位信息
        lat = proj.get('latitude')
        lon = proj.get('longitude')

        if lat and lon:
            maint_type = proj.get('maintenance_type', 'Unknown')
            route = proj.get('route_code', '')

            color = {
                '路面改造': '#FF0000',
                '预防性养护': '#FFFF00',
                '日常养护': '#00FF00'
            }.get(maint_type, '#808080')

            popup = f"""
            <b>项目: {proj.get('project_code', '')}</b><br>
            路线: {route}<br>
            养护类型: {maint_type}<br>
            年度: {proj.get('planned_year', '')}<br>
            费用: {proj.get('estimated_cost', 0)}万元
            """

            generator.folium.Marker(
                [lat, lon],
                popup=generator.folium.Popup(popup, max_width=250),
                icon=generator.folium.Icon(color=color)
            ).add_to(m)

    if m:
        return generator.save_map(m, output_file)

    return None


# ══════════════════════════════════════════════════════════════════════════════════════
# 批量导出地图
# ══════════════════════════════════════════════════════════════════════════════════════

def export_yearly_maps(df: pd.DataFrame, output_dir: str = 'output/maps'):
    """
    导出多年份路况地图

    Args:
        df: 包含多年数据的DataFrame，需有年份列
        output_dir: 输出目录

    Returns:
        生成的地图文件列表
    """
    os.makedirs(output_dir, exist_ok=True)

    if df is None or df.empty or '年份' not in df.columns:
        return []

    generated = []
    generator = GISMapGenerator()

    for year in sorted(df['年份'].unique()):
        year_df = df[df['年份'] == year]
        m = generator.add_road_segments(year_df, color_by='pqi')

        if m:
            filename = f'{output_dir}/{year}年路况地图.html'
            generator.save_map(m, filename)
            generated.append(filename)

    return generated
