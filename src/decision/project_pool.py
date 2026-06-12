"""
工程项目库模块
按《公路养护决策技术规范》第8章和附录F实现项目库管理

功能：
1. 工程项目类定义
2. 项目库管理（增删改查）
3. 项目库导入导出
4. 年度建议计划生成
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# 1. 工程项目类定义
# ══════════════════════════════════════════════════════════════════════════════

class MaintenanceProject:
    """
    养护工程项目类

    按规范附录F的项目列表样表设计
    """

    # 项目状态枚举
    STATUS_PENDING = 'pending'       # 待审核
    STATUS_APPROVED = 'approved'     # 已批准
    STATUS_IMPLEMENTED = 'implemented'  # 已实施
    STATUS_COMPLETED = 'completed'   # 已完成
    STATUS_CANCELLED = 'cancelled'   # 已取消

    def __init__(self,
                 project_id: str = None,
                 route_code: str = None,
                 segment_start: str = None,
                 segment_end: str = None,
                 length: float = None,
                 facility_type: str = '路面',
                 pavement_type: str = None,
                 tech_grade: str = None,
                 current_condition: Dict = None,
                 maintenance_type: str = None,
                 maintenance_year: int = None,
                 estimated_cost: float = None,
                 priority_score: float = None,
                 status: str = STATUS_PENDING):
        """
        初始化工程项目

        参数:
            project_id: 项目编号
            route_code: 路线编码
            segment_start: 起点桩号
            segment_end: 终点桩号
            length: 长度(km)
            facility_type: 设施类型（路面/路基/桥隧/沿线设施）
            pavement_type: 路面类型（沥青/水泥）
            tech_grade: 技术等级
            current_condition: 当前技术状况 {'PQI': 80, 'PCI': 80, 'RQI': 80}
            maintenance_type: 养护类型（路面改造/预防性养护/日常养护）
            maintenance_year: 计划年度
            estimated_cost: 估算费用(万元)
            priority_score: 优先级评分
            status: 项目状态
        """
        self.project_id = project_id or self._generate_id()
        self.route_code = route_code or ''
        self.segment_start = segment_start or ''
        self.segment_end = segment_end or ''
        self.length = length or 0
        self.facility_type = facility_type
        self.pavement_type = pavement_type
        self.tech_grade = tech_grade
        self.current_condition = current_condition or {}
        self.maintenance_type = maintenance_type
        self.maintenance_year = maintenance_year
        self.estimated_cost = estimated_cost
        self.priority_score = priority_score
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    @staticmethod
    def _generate_id() -> str:
        """生成项目编号"""
        now = datetime.now()
        return f"PRJ-{now.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}"

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            '项目编号': self.project_id,
            '路线编码': self.route_code,
            '起点桩号': self.segment_start,
            '终点桩号': self.segment_end,
            '长度(km)': self.length,
            '设施类型': self.facility_type,
            '路面类型': self.pavement_type,
            '技术等级': self.tech_grade,
            '当前PQI': self.current_condition.get('PQI', ''),
            '当前PCI': self.current_condition.get('PCI', ''),
            '当前RQI': self.current_condition.get('RQI', ''),
            '养护类型': self.maintenance_type,
            '计划年度': self.maintenance_year,
            '估算费用(万元)': self.estimated_cost,
            '优先级评分': self.priority_score,
            '状态': self.status,
            '创建时间': self.created_at.strftime('%Y-%m-%d'),
            '更新时间': self.updated_at.strftime('%Y-%m-%d'),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MaintenanceProject':
        """从字典创建对象"""
        condition = {}
        for key in ['PQI', 'PCI', 'RQI', 'SCI', 'BCI', 'TCI', 'ISSI']:
            if key in data:
                condition[key] = data[key]

        return cls(
            project_id=data.get('项目编号'),
            route_code=data.get('路线编码'),
            segment_start=data.get('起点桩号'),
            segment_end=data.get('终点桩号'),
            length=data.get('长度(km)', data.get('路段长度(km)')),
            facility_type=data.get('设施类型', '路面'),
            pavement_type=data.get('路面类型'),
            tech_grade=data.get('技术等级'),
            current_condition=condition,
            maintenance_type=data.get('养护类型'),
            maintenance_year=data.get('计划年度'),
            estimated_cost=data.get('估算费用(万元)'),
            priority_score=data.get('优先级评分'),
            status=data.get('状态', cls.STATUS_PENDING),
        )

    def update(self, **kwargs):
        """更新项目属性"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


# ══════════════════════════════════════════════════════════════════════════════
# 2. 项目库管理类
# ══════════════════════════════════════════════════════════════════════════════

class ProjectPool:
    """
    工程项目库管理类

    支持：
    - 项目增删改查
    - 按条件筛选
    - 导入导出Excel
    - 优先级排序
    """

    def __init__(self):
        """初始化项目库"""
        self.projects: List[MaintenanceProject] = []
        self._counter = 0

    def add_project(self, project: MaintenanceProject) -> bool:
        """
        添加项目到项目库

        参数:
            project: 工程项目对象

        返回:
            是否添加成功
        """
        if not isinstance(project, MaintenanceProject):
            return False

        # 检查是否已存在
        for p in self.projects:
            if p.project_id == project.project_id:
                return False

        self.projects.append(project)
        self._counter += 1
        return True

    def add_from_dict(self, data: Dict) -> bool:
        """从字典添加项目"""
        project = MaintenanceProject.from_dict(data)
        return self.add_project(project)

    def remove_project(self, project_id: str) -> bool:
        """
        从项目库删除项目

        参数:
            project_id: 项目编号

        返回:
            是否删除成功
        """
        for i, p in enumerate(self.projects):
            if p.project_id == project_id:
                self.projects.pop(i)
                return True
        return False

    def update_project(self, project_id: str, **kwargs) -> bool:
        """
        更新项目属性

        参数:
            project_id: 项目编号
            **kwargs: 要更新的属性

        返回:
            是否更新成功
        """
        for p in self.projects:
            if p.project_id == project_id:
                p.update(**kwargs)
                return True
        return False

    def get_project(self, project_id: str) -> Optional[MaintenanceProject]:
        """获取指定项目"""
        for p in self.projects:
            if p.project_id == project_id:
                return p
        return None

    def filter_by_year(self, year: int) -> List[MaintenanceProject]:
        """按年份筛选项目"""
        return [p for p in self.projects if p.maintenance_year == year]

    def filter_by_type(self, maintenance_type: str) -> List[MaintenanceProject]:
        """按养护类型筛选"""
        return [p for p in self.projects if p.maintenance_type == maintenance_type]

    def filter_by_status(self, status: str) -> List[MaintenanceProject]:
        """按状态筛选"""
        return [p for p in self.projects if p.status == status]

    def filter_by_route(self, route_code: str) -> List[MaintenanceProject]:
        """按路线筛选"""
        return [p for p in self.projects if route_code in p.route_code]

    def sort_by_priority(self, descending: bool = True) -> List[MaintenanceProject]:
        """按优先级排序"""
        return sorted(
            self.projects,
            key=lambda x: x.priority_score or 0,
            reverse=descending
        )

    def sort_by_year(self, descending: bool = True) -> List[MaintenanceProject]:
        """按年份排序"""
        return sorted(
            self.projects,
            key=lambda x: x.maintenance_year or 0,
            reverse=descending
        )

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        if not self.projects:
            return pd.DataFrame()

        data = [p.to_dict() for p in self.projects]
        return pd.DataFrame(data)

    def to_excel(self, filepath: str, sheet_name: str = '项目库') -> bool:
        """
        导出项目库到Excel

        参数:
            filepath: 文件路径
            sheet_name: 工作表名称

        返回:
            是否导出成功
        """
        try:
            df = self.to_dataframe()
            if df.empty:
                return False
            df.to_excel(filepath, sheet_name=sheet_name, index=False)
            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False

    def from_excel(self, filepath: str, sheet_name: str = None) -> bool:
        """
        从Excel导入项目库

        参数:
            filepath: 文件路径
            sheet_name: 工作表名称，None则读取第一个sheet

        返回:
            是否导入成功
        """
        try:
            if sheet_name:
                df = pd.read_excel(filepath, sheet_name=sheet_name)
            else:
                df = pd.read_excel(filepath)

            self.projects.clear()
            for _, row in df.iterrows():
                project = MaintenanceProject.from_dict(row.to_dict())
                self.projects.append(project)

            return True
        except Exception as e:
            print(f"导入失败: {e}")
            return False

    def get_summary(self) -> Dict:
        """获取项目库汇总信息"""
        if not self.projects:
            return {}

        total_cost = sum(p.estimated_cost or 0 for p in self.projects)
        total_length = sum(p.length or 0 for p in self.projects)

        # 按年份统计
        by_year = {}
        for p in self.projects:
            year = p.maintenance_year
            if year not in by_year:
                by_year[year] = {'count': 0, 'cost': 0, 'length': 0}
            by_year[year]['count'] += 1
            by_year[year]['cost'] += p.estimated_cost or 0
            by_year[year]['length'] += p.length or 0

        # 按养护类型统计
        by_type = {}
        for p in self.projects:
            mtype = p.maintenance_type
            if mtype not in by_type:
                by_type[mtype] = {'count': 0, 'cost': 0, 'length': 0}
            by_type[mtype]['count'] += 1
            by_type[mtype]['cost'] += p.estimated_cost or 0
            by_type[mtype]['length'] += p.length or 0

        # 按状态统计
        by_status = {}
        for p in self.projects:
            status = p.status
            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

        return {
            '总项目数': len(self.projects),
            '总里程(km)': round(total_length, 2),
            '总费用(万元)': round(total_cost, 2),
            '按年份': by_year,
            '按养护类型': by_type,
            '按状态': by_status,
        }

    def merge(self, other_pool: 'ProjectPool') -> int:
        """
        合并另一个项目库

        参数:
            other_pool: 另一个项目库

        返回:
            合并的项目数
        """
        merged = 0
        for p in other_pool.projects:
            if self.add_project(p):
                merged += 1
        return merged


# ══════════════════════════════════════════════════════════════════════════════
# 3. 年度建议计划生成
# ══════════════════════════════════════════════════════════════════════════════

def generate_annual_plan(project_pool: ProjectPool,
                          year: int,
                          annual_budget: float = None,
                          sort_by: str = 'priority') -> Dict:
    """
    根据项目库生成年度养护建议计划

    参数:
        project_pool: 项目库
        year: 目标年份
        annual_budget: 年度预算（万元），None表示不限制
        sort_by: 排序依据 ('priority'/'cost'/'year')

    返回:
        年度计划字典
    """
    # 筛选本年度项目
    year_projects = project_pool.filter_by_year(year)

    if not year_projects:
        return {
            '年份': year,
            '项目数': 0,
            '总里程(km)': 0,
            '总费用(万元)': 0,
            '预算': annual_budget or '不限',
            'projects': [],
        }

    # 排序
    if sort_by == 'priority':
        year_projects = sorted(
            year_projects,
            key=lambda x: x.priority_score or 0,
            reverse=True
        )
    elif sort_by == 'cost':
        year_projects = sorted(
            year_projects,
            key=lambda x: x.estimated_cost or 0,
            reverse=True
        )

    # 按预算筛选
    if annual_budget:
        selected = []
        remaining = annual_budget
        for p in year_projects:
            cost = p.estimated_cost or 0
            if cost <= remaining:
                selected.append(p)
                remaining -= cost
        year_projects = selected

    # 计算汇总
    total_length = sum(p.length or 0 for p in year_projects)
    total_cost = sum(p.estimated_cost or 0 for p in year_projects)

    # 按养护类型分组
    by_type = {}
    for p in year_projects:
        mtype = p.maintenance_type
        if mtype not in by_type:
            by_type[mtype] = {'count': 0, 'cost': 0, 'length': 0}
        by_type[mtype]['count'] += 1
        by_type[mtype]['cost'] += p.estimated_cost or 0
        by_type[mtype]['length'] += p.length or 0

    return {
        '年份': year,
        '项目数': len(year_projects),
        '总里程(km)': round(total_length, 2),
        '总费用(万元)': round(total_cost, 2),
        '预算(万元)': annual_budget,
        '剩余预算(万元)': round((annual_budget - total_cost) if annual_budget else 0, 2),
        '按养护类型': by_type,
        'projects': [p.to_dict() for p in year_projects],
    }


def generate_multiyear_plan(project_pool: ProjectPool,
                              years: List[int],
                              budgets: Dict[int, float] = None) -> pd.DataFrame:
    """
    生成多年养护建议计划表

    参数:
        project_pool: 项目库
        years: 年份列表
        budgets: 年度预算字典 {年份: 预算(万元)}

    返回:
        多年计划DataFrame
    """
    if budgets is None:
        budgets = {}

    results = []
    for year in years:
        plan = generate_annual_plan(
            project_pool,
            year,
            budgets.get(year),
            sort_by='priority'
        )

        results.append({
            '年份': year,
            '项目数': plan['项目数'],
            '总里程(km)': plan['总里程(km)'],
            '总费用(万元)': plan['总费用(万元)'],
            '预算(万元)': plan.get('预算(万元)', ''),
            '满足程度': f"{round(plan['总费用(万元)'] / plan['预算(万元)'] * 100, 1)}%"
                        if plan.get('预算(万元)') else '不限',
        })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# 4. 项目库与需求对接
# ══════════════════════════════════════════════════════════════════════════════

def create_project_pool_from_demand(demand_df: pd.DataFrame,
                                     unit_prices: Dict = None) -> ProjectPool:
    """
    从养护需求分析结果创建项目库

    参数:
        demand_df: 养护需求DataFrame（来自maintenance_demand.analyze_demand）
        unit_prices: 单价字典

    返回:
        项目库对象
    """
    if demand_df is None or demand_df.empty:
        return ProjectPool()

    if unit_prices is None:
        from .cost_model import UNIT_PRICES
        unit_prices = UNIT_PRICES

    pool = ProjectPool()

    for _, row in demand_df.iterrows():
        maint_type = row.get('养护类型', '日常养护')
        ptype = row.get('路面类型', '沥青路面')
        length = row.get('路段长度(km)', 1.0)
        width = row.get('路面宽度', 7)
        price = unit_prices.get(ptype, {}).get(maint_type, 300)
        cost = length * 1000 * width * price / 10000

        # 创建项目
        project = MaintenanceProject(
            route_code=row.get('路线编码', ''),
            segment_start=row.get('路段起点', ''),
            segment_end=row.get('路段终点', ''),
            length=length,
            facility_type='路面',
            pavement_type=ptype,
            tech_grade=row.get('技术等级', ''),
            current_condition={
                'PQI': row.get('当前PQI', ''),
                'PCI': row.get('当前PQI', ''),  # 简化
                'RQI': row.get('当前PQI', ''),
            },
            maintenance_type=maint_type,
            maintenance_year=int(row.get('年份', 2026)),
            estimated_cost=round(cost, 2),
            priority_score=row.get('优先级评分', 0),
            status=MaintenanceProject.STATUS_PENDING,
        )

        pool.add_project(project)

    return pool


# ══════════════════════════════════════════════════════════════════════════════
# 5. 项目库验证
# ══════════════════════════════════════════════════════════════════════════════

def validate_project_pool(pool: ProjectPool) -> Dict:
    """
    验证项目库的完整性和一致性

    参数:
        pool: 项目库

    返回:
        验证结果字典
    """
    issues = []
    warnings = []

    # 检查必填字段
    required_fields = ['route_code', 'maintenance_type', 'maintenance_year', 'estimated_cost']
    for p in pool.projects:
        for field in required_fields:
            if not getattr(p, field, None):
                issues.append(f"项目{p.project_id}缺少{field}")

    # 检查费用合理性
    for p in pool.projects:
        if p.estimated_cost and p.estimated_cost > 10000:
            warnings.append(f"项目{p.project_id}费用超过1亿元，请确认")
        if p.estimated_cost and p.estimated_cost < 0.1:
            warnings.append(f"项目{p.project_id}费用低于0.1万元，请确认")

    # 检查年份范围
    current_year = datetime.now().year
    for p in pool.projects:
        if p.maintenance_year and (p.maintenance_year < current_year or p.maintenance_year > current_year + 10):
            warnings.append(f"项目{p.project_id}计划年份异常")

    # 检查重复项目
    route_segments = {}
    for p in pool.projects:
        key = f"{p.route_code}_{p.segment_start}_{p.segment_end}_{p.maintenance_year}"
        if key in route_segments:
            warnings.append(f"项目{p.project_id}与{route_segments[key]}重复")
        route_segments[key] = p.project_id

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'project_count': len(pool.projects),
    }