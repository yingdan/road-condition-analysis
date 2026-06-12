"""
公路养护决策模块
按《公路养护决策技术规范》（JTG/T）框架设计
"""
from .performance_models import (
    exponential_decay_model,
    linear_decay_model,
    s_curve_model,
    MarkovModel,
    calibrate_model,
)
from .maintenance_demand import (
    analyze_demand,
    prioritize_demand,
    MAINTENANCE_TARGETS,
)
from .cost_model import (
    calculate_cost,
    life_cycle_cost_analysis,
    cost_benefit_analysis,
    UNIT_PRICES,
)
from .budget_allocation import (
    priority_allocation,
    incremental_analysis,
    multi_objective_optimization,
)
from .project_pool import (
    MaintenanceProject,
    ProjectPool,
    generate_annual_plan,
)

__all__ = [
    # 性能预测模型
    'exponential_decay_model',
    'linear_decay_model',
    's_curve_model',
    'markov_model',
    'calibrate_model',
    # 养护需求分析
    'analyze_demand',
    'prioritize_demand',
    'MAINTENANCE_TARGETS',
    # 费用模型
    'calculate_cost',
    'life_cycle_cost_analysis',
    'cost_benefit_analysis',
    'UNIT_PRICES',
    # 资金优化分配
    'priority_allocation',
    'incremental_analysis',
    'multi_objective_optimization',
    # 项目库
    'MaintenanceProject',
    'ProjectPool',
    'generate_annual_plan',
]