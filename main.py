# -*- coding: utf-8 -*-
"""
粤路公司公路养护需求预测系统 - 主GUI界面
基于tkinter构建，无需额外依赖
v2.0 - 2026-03-31
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

# ── 路径处理（兼容打包后的exe）──
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# 打包后src在_internal目录下
SRC_DIR = os.path.join(BASE_DIR, 'src')
if not os.path.exists(SRC_DIR):
    SRC_DIR = os.path.join(BASE_DIR, '_internal', 'src')
if not os.path.exists(SRC_DIR):
    SRC_DIR = BASE_DIR

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# 配置文件路径（确保在EXE所在目录，而不是临时目录）
if getattr(sys, 'frozen', False):
    # 打包后的EXE路径
    CONFIG_PATH = os.path.join(os.path.dirname(sys.executable), 'config.json')
else:
    # 开发模式下的路径
    CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

# ── 颜色主题 ──
THEME = {
    'bg': '#F0F4F8',
    'sidebar': '#1E3A5F',
    'sidebar_hover': '#2E5F9F',
    'accent': '#2E75B6',
    'accent_dark': '#1F497D',
    'success': '#27AE60',
    'warning': '#F39C12',
    'danger': '#E74C3C',
    'text': '#2C3E50',
    'text_light': '#7F8C8D',
    'card': '#FFFFFF',
    'border': '#DEE2E6',
}

# ── 尝试导入分析模块 ──
try:
    from src.analyzer import generate_all_charts
    from src.data_loader import load_all_data
    from src.report_writer import generate_word_report
    from src.decay_calculator import get_maintenance_callback, set_maintenance_callback
    from src.decay_calculator import get_trigger_model, set_trigger_model
except Exception as e:
    print(f"导入模块失败: {e}")
    import traceback
    traceback.print_exc()
    load_all_data = None
    generate_all_charts = None
    generate_word_report = None
    get_maintenance_callback = None
    set_maintenance_callback = None
    get_trigger_model = None
    set_trigger_model = None
    set_maintenance_callback = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('粤路慧养 v1.5')
        self.geometry('1200x750')
        self.configure(bg=THEME['bg'])
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), 'road_icon.ico')
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # 数据存储
        self.data_cache = {}
        self.filtered_df = None

        # 加载配置
        self.config = self._load_config()

        # UI变量
        self.llm_vars = {}
        self.llm_key_entry = None
        self.llm_key_toggle_btn = None
        self._llm_key_visible = False

        # 加载保存的养护回调参数（如果有）——必须在构建UI之前调用
        self._load_saved_callback()

        self._setup_style()
        self._build_ui()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _load_saved_callback(self):
        """加载保存的养护回调参数"""
        if not set_maintenance_callback:
            return
        
        saved_callback = self.config.get('maintenance_callback')
        if saved_callback:
            try:
                set_maintenance_callback(saved_callback)
                print(f"已加载保存的养护回调参数")
            except Exception as e:
                print(f"加载养护回调参数失败: {e}")

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Title.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground=THEME['text'])
        style.configure('Subtitle.TLabel', font=('Microsoft YaHei', 9), foreground=THEME['text_light'])
        style.configure('Card.TFrame', background=THEME['card'])
        style.configure('Primary.TButton', font=('Microsoft YaHei', 10), background=THEME['accent'], foreground='white')
        style.map('Primary.TButton', background=[('active', THEME['accent_dark'])])
        style.configure('Success.TButton', background=[('active', '#219A52')])
        style.configure('TEntry', fieldbackground='white', font=('Microsoft YaHei', 10))
        style.configure('TCombobox', fieldbackground='white', font=('Microsoft YaHei', 10))
        style.configure('TNotebook', background=THEME['bg'])
        style.configure('TNotebook.Tab', font=('Microsoft YaHei', 10), padding=(12, 6))
        style.configure('TProgressbar', troughcolor=THEME['border'], background=THEME['accent'])
    
    def _build_ui(self):
        # 顶部Banner
        header = tk.Frame(self, bg=THEME['accent_dark'], height=60)
        header.pack(fill='x')
        header.pack_propagate(False)

        tk.Label(header, text='  粤路慧养 v1.5',
                 bg=THEME['accent_dark'], fg='white',
                 font=('Microsoft YaHei', 15, 'bold')).pack(side='left', padx=20, pady=15)

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=0, pady=0)
        
        # Tab切换
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: 数据配置
        self.tab_data = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_data, text='  数据配置  ')
        self._build_data_tab(self.tab_data)
        
        # Tab 2: 数据筛选
        self.tab_filter = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_filter, text='  数据筛选  ')
        self._build_filter_tab(self.tab_filter)

        # Tab 2.5: 数据分析（衰减模型）
        self.tab_model = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_model, text='  数据分析  ')
        self._build_model_info_tab(self.tab_model)
        
        # Tab 3: 分析与图表
        self.tab_analysis = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_analysis, text='  分析图表  ')
        self._build_analysis_tab(self.tab_analysis)
        
        # Tab 4: AI报告配置
        self.tab_llm = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_llm, text='  AI报告  ')
        self._build_llm_tab(self.tab_llm)
        
        # Tab 5: 生成报告
        self.tab_report = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_report, text='  生成报告  ')
        self._build_report_tab(self.tab_report)
        
        # ── 底部状态栏 ──
        self.status_var = tk.StringVar(value='就绪')
        footer = tk.Frame(self, bg=THEME['border'], height=30)
        footer.pack(fill='x')
        footer.pack_propagate(False)
        
        tk.Label(footer, textvariable=self.status_var, bg=THEME['border'],
                 font=('Microsoft YaHei', 9), anchor='w').pack(side='left', padx=10)
        
        self.progressbar = ttk.Progressbar(footer, mode='indeterminate', length=150)
        self.progressbar.pack(side='right', padx=10, pady=4)

    # ════════════════════════════════════════
    # Tab 1: 数据配置
    # ════════════════════════════════════════
    def _build_data_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text='数据文件配置', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='配置各年份Excel文件路径，建议按年份分表存放', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 15))

        # 文件配置卡片
        file_card = ttk.LabelFrame(frame, text='数据文件', padding=15)
        file_card.pack(fill='x')

        self.file_vars = {}
        years = [2021, 2022, 2023, 2024, 2025]
        
        for year in years:
            row = ttk.Frame(file_card)
            row.pack(fill='x', pady=3)
            
            tk.Label(row, text=f'{year}年：', width=8).pack(side='left')
            
            var = tk.StringVar()
            self.file_vars[year] = var
            
            ttk.Entry(row, textvariable=var, width=45).pack(side='left', padx=5)
            ttk.Button(row, text='浏览', command=lambda y=year: self._browse_file(y),
                      width=8).pack(side='left')
        
        # 批量浏览按钮（放在数据文件框内）
        batch_row = ttk.Frame(file_card)
        batch_row.pack(fill='x', pady=(10, 0))
        tk.Button(batch_row, text='📂 批量浏览（自动匹配年份）', command=self._browse_files_multi,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2').pack(side='left')

        # 自动加载已有数据
        self._auto_load_config()

        # 加载按钮
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill='x', pady=15)
        
        ttk.Button(btn_row, text='加载数据', command=self._load_data,
                   style='Primary.TButton').pack(side='left')
        
        self.load_info_label = ttk.Label(frame, text='', foreground=THEME['text_light'])
        self.load_info_label.pack(anchor='w')

    def _auto_load_config(self):
        cfg = self.config.get('data_files', {})
        for year, path in cfg.items():
            if year.isdigit() and int(year) in self.file_vars:
                self.file_vars[int(year)].set(path)

    def _browse_file(self, year):
        path = filedialog.askopenfilename(
            title=f'选择{year}年数据文件',
            filetypes=[('Excel文件', '*.xlsx *.xls'), ('所有文件', '*.*')]
        )
        if path:
            self.file_vars[year].set(path)

    def _browse_files_multi(self):
        """批量浏览选择多个Excel文件，按文件名排序后自动匹配年份填入"""
        import re
        paths = filedialog.askopenfilenames(
            title='选择数据文件（可多选）',
            filetypes=[('Excel文件', '*.xlsx *.xls'), ('所有文件', '*.*')]
        )
        if not paths:
            return
        
        # 按文件名排序
        sorted_paths = sorted(paths, key=lambda p: os.path.basename(p))
        
        # 尝试从文件名中提取年份并匹配
        matched = 0
        unmatched = []
        for path in sorted_paths:
            filename = os.path.basename(path)
            # 提取文件名中的4位数字年份
            year_match = re.search(r'(20\d{2})', filename)
            if year_match:
                year = int(year_match.group(1))
                if year in self.file_vars:
                    self.file_vars[year].set(path)
                    matched += 1
                    continue
            unmatched.append(filename)
        
        if unmatched:
            tips = '\n'.join(f'  - {f}' for f in unmatched)
            messagebox.showinfo('批量浏览结果',
                f'已匹配 {matched} 个文件到对应年份。\n\n以下文件未能自动匹配年份，请手动设置：\n{tips}')
        else:
            messagebox.showinfo('批量浏览结果', f'已成功匹配 {matched} 个文件到对应年份。')

    def _load_data(self):
        self.progressbar.start(10)
        self.status_var.set('正在加载数据...')
        self.update()

        file_map = {}
        for year, var in self.file_vars.items():
            path = var.get().strip()
            if path and os.path.exists(path):
                file_map[year] = path

        if not file_map:
            messagebox.showwarning('提示', '请至少配置一个数据文件')
            self.progressbar.stop()
            self.status_var.set('就绪')
            return

        try:
            data = load_all_data(file_map)
            self.data_cache = data
            
            total = sum(len(df) for df in data.values())
            counties = sorted(set.union(*[set(df.get('县份', [])) for df in data.values() if '县份' in df.columns]))
            years = sorted(set.union(*[set(df.get('年份', [])) for df in data.values() if '年份' in df.columns]))
            
            info = f'加载成功：{total}条路段，{len(counties)}个县份（{", ".join(counties)}），年份{min(years)}-{max(years)}'
            self.load_info_label.config(text=info, foreground=THEME['success'])
            
            self._update_filter_options(counties, years)
            
        except Exception as e:
            messagebox.showerror('错误', f'加载失败：{str(e)}')
            self.load_info_label.config(text=f'加载失败：{str(e)}', foreground=THEME['danger'])

        self.progressbar.stop()
        self.status_var.set('就绪')

    def _update_filter_options(self, counties, years):
        county_values = ['全部'] + sorted(counties)
        year_values = ['全部'] + [str(y) for y in sorted(years)]

        self.filter_county_cb['values'] = county_values
        self.filter_year_cb['values'] = year_values
        self.analysis_county_cb['values'] = county_values
        self.report_county_cb['values'] = county_values + ['全部'] if '全部' not in county_values else county_values
        
        # 刷新数据分析Tab的县份下拉
        if hasattr(self, 'model_county_cb'):
            self.model_county_cb['values'] = county_values

        if counties:
            self.filter_county_var.set(counties[0])
            self.analysis_county_var.set(counties[0])
            if hasattr(self, 'report_county_var'):
                self.report_county_var.set(counties[0])
        if years:
            self.filter_year_var.set(str(int(max(years))))

    # ════════════════════════════════════════
    # Tab 2: 数据筛选
    # ════════════════════════════════════════
    def _build_filter_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text='数据筛选与预览', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='加载数据后，在此筛选查看具体路段数据', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 10))
        
        # 筛选条件行
        filter_card = ttk.LabelFrame(frame, text='筛选条件', padding=10)
        filter_card.pack(fill='x', pady=5)
        
        row1 = ttk.Frame(filter_card)
        row1.pack(fill='x', pady=3)
        
        ttk.Label(row1, text='县份：').pack(side='left')
        self.filter_county_var = tk.StringVar(value='全部')
        self.filter_county_cb = ttk.Combobox(row1, textvariable=self.filter_county_var, width=10, state='readonly')
        self.filter_county_cb['values'] = ['全部']   # 加载数据后自动更新
        self.filter_county_cb.pack(side='left', padx=(0, 15))
        
        ttk.Label(row1, text='年份：').pack(side='left')
        self.filter_year_var = tk.StringVar(value='全部')
        self.filter_year_cb = ttk.Combobox(row1, textvariable=self.filter_year_var, width=10, state='readonly')
        self.filter_year_cb['values'] = ['全部']   # 加载数据后自动更新
        self.filter_year_cb.pack(side='left', padx=(0, 15))
        
        ttk.Label(row1, text='PQI等级：').pack(side='left')
        self.filter_grade_var = tk.StringVar(value='全部')
        ttk.Combobox(row1, textvariable=self.filter_grade_var, width=8, state='readonly',
                     values=['全部', '优', '良', '中', '次', '差']).pack(side='left', padx=(0, 15))
        
        ttk.Label(row1, text='路面类型：').pack(side='left')
        self.filter_type_var = tk.StringVar(value='全部')
        self.filter_type_cb = ttk.Combobox(row1, textvariable=self.filter_type_var, width=12, state='readonly')
        self.filter_type_cb['values'] = ['全部', '沥青路面', '水泥路面']
        self.filter_type_cb.pack(side='left')
        
        row2 = ttk.Frame(filter_card)
        row2.pack(fill='x', pady=3)
        ttk.Label(row2, text='PQI范围：').pack(side='left')
        self.filter_pqi_min = tk.StringVar(value='0')
        self.filter_pqi_max = tk.StringVar(value='100')
        ttk.Entry(row2, textvariable=self.filter_pqi_min, width=6).pack(side='left')
        ttk.Label(row2, text=' ~ ').pack(side='left')
        ttk.Entry(row2, textvariable=self.filter_pqi_max, width=6).pack(side='left', padx=(0, 15))
        
        ttk.Button(row2, text='应用筛选', command=self._apply_filter,
                   style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(row2, text='↺ 重置', command=self._reset_filter).pack(side='left')
        tk.Button(row2, text='📥 导出筛选结果', command=self._export_filtered).pack(side='right')
        
        # 统计信息行
        self.filter_stats_label = ttk.Label(frame, text='请先加载数据', foreground=THEME['text_light'])
        self.filter_stats_label.pack(anchor='w', pady=5)
        
        # 数据表格
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True)
        
        columns = ('路线编码', '方向', '路段起点', '路段终点', '路段长度km', '路面宽度', '技术等级', '路面类型', 'PQI', 'PCI', 'RQI', 'PQI分级', '年份')
        self.data_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=18)
        
        col_widths = {'路线编码': 80, '方向': 45, '路段起点': 80, '路段终点': 80, '路段长度km': 80,
                      '路面宽度': 70, '技术等级': 80, '路面类型': 90, 'PQI': 60, 'PCI': 60, 'RQI': 60, 'PQI分级': 60, '年份': 50}
        for col in columns:
            self.data_tree.heading(col, text=col, command=lambda c=col: self._sort_tree(c))
            self.data_tree.column(col, width=col_widths.get(col, 80), anchor='center')
        
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.data_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.data_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        
        self._tree_sort_col = None
        self._tree_sort_rev = False

    def _apply_filter(self):
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return

        all_df = self.data_cache.get('全部', pd.DataFrame())
        if all_df.empty:
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)

        df = all_df.copy()

        county = self.filter_county_var.get()
        if county != '全部' and '县份' in df.columns:
            df = df[df['县份'] == county]

        year = self.filter_year_var.get()
        if year != '全部' and '年份' in df.columns:
            df = df[df['年份'] == int(year)]

        grade = self.filter_grade_var.get()
        if grade != '全部' and 'PQI分级' in df.columns:
            df = df[df['PQI分级'] == grade]

        ptype = self.filter_type_var.get()
        if ptype != '全部' and '路面类型' in df.columns:
            df = df[df['路面类型'] == ptype]

        pqi_min = float(self.filter_pqi_min.get() or 0)
        pqi_max = float(self.filter_pqi_max.get() or 100)
        if 'PQI' in df.columns:
            df = df[(df['PQI'] >= pqi_min) & (df['PQI'] <= pqi_max)]

        self.filtered_df = df

        total_km = df['路段长度km'].sum() if '路段长度km' in df.columns else 0
        avg_pqi = df['PQI'].mean() if 'PQI' in df.columns else 0
        self.filter_stats_label.config(
            text=f'筛选结果：{len(df)}条路段，{total_km:.1f}km，平均PQI {avg_pqi:.1f}',
            foreground=THEME['text']
        )

        self._refresh_tree(df)

    def _reset_filter(self):
        self.filter_county_var.set('全部')
        self.filter_year_var.set('全部')
        self.filter_grade_var.set('全部')
        self.filter_type_var.set('全部')
        self.filter_pqi_min.set('0')
        self.filter_pqi_max.set('100')
        self._apply_filter()

    def _refresh_tree(self, df):
        self.data_tree.delete(*self.data_tree.get_children())
        
        for _, row in df.head(500).iterrows():
            vals = []
            for col in ('路线编码', '方向', '路段起点', '路段终点', '路段长度km', '路面宽度',
                       '技术等级', '路面类型', 'PQI', 'PCI', 'RQI', 'PQI分级', '年份'):
                val = row.get(col, '')
                vals.append(f'{val:.2f}' if isinstance(val, float) else val)
            self.data_tree.insert('', 'end', values=vals)

    def _sort_tree(self, col):
        if not self.filtered_df is None:
            reverse = self._tree_sort_rev if self._tree_sort_col == col else False
            self._tree_sort_rev = not reverse
            self._tree_sort_col = col
            
            sorted_df = self.filtered_df.sort_values(by=col, ascending=not reverse)
            self._refresh_tree(sorted_df)

    def _export_filtered(self):
        if self.filtered_df is None or self.filtered_df.empty:
            messagebox.showwarning('提示', '没有可导出的数据')
            return

        path = filedialog.asksaveasfilename(
            title='导出筛选结果',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')],
            initialfile='筛选结果.xlsx'
        )
        if path:
            try:
                self.filtered_df.to_excel(path, index=False)
                messagebox.showinfo('成功', f'已导出到：{path}')
            except Exception as e:
                messagebox.showerror('错误', f'导出失败：{str(e)}')

    # ════════════════════════════════════════
    # Tab 2.5: 数据分析（衰减模型介绍 + 养护计划）
    # ════════════════════════════════════════
    def _build_model_info_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(frame, text='数据分析与养护计划', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='基于用户加载数据动态计算，按县份分别分析', 
                  style='Subtitle.TLabel').pack(anchor='w', pady=(0, 15))

        # ── 县份选择 ──
        county_frame = ttk.Frame(frame)
        county_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(county_frame, text='选择县份：').pack(side='left')
        self.model_county_var = tk.StringVar(value='全部')
        self.model_county_cb = ttk.Combobox(county_frame, textvariable=self.model_county_var,
                                              width=12, state='readonly')
        self.model_county_cb['values'] = ['全部']
        self.model_county_cb.pack(side='left', padx=10)
        ttk.Button(county_frame, text='刷新县份', command=self._refresh_model_counties,
                   style='Secondary.TButton').pack(side='left', padx=5)

        # ── 标签页：衰减率 | 5年预测 | 养护里程 | 养护资金 | 年度汇总 ──
        self.model_notebook = ttk.Notebook(frame)
        self.model_notebook.pack(fill='both', expand=True, pady=10)
        
        # Tab 1: 衰减率标定
        self._build_decay_rate_tab()
        
        # Tab 2: 5年PQI预测
        self._build_prediction_tab()
        
        # Tab 3: PQI-Proj. IMP（手动养护规划）
        self._build_pqi_proj_tab()
        
        # Tab 4: 养护里程
        self._build_mileage_tab()
        
        # Tab 5: 养护资金
        self._build_fund_tab()
        
        # Tab 6: 年度汇总
        self._build_yearly_summary_tab()

    def _refresh_model_counties(self):
        """刷新县份下拉列表"""
        if self.data_cache:
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)
            if '县份' in all_df.columns:
                counties = ['全部'] + sorted(all_df['县份'].unique().tolist())
                self.model_county_cb['values'] = counties
                self.model_county_var.set('全部')

    def _get_current_county(self):
        """获取当前选择的县份"""
        county = self.model_county_var.get()
        if county == '全部':
            return None
        return county

    # ── Tab 1: 衰减率标定 ──
    def _build_decay_rate_tab(self):
        self.decay_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(self.decay_frame, text=' 衰减率标定 ')
        
        # 介绍卡片
        intro_card = ttk.LabelFrame(self.decay_frame, text='模型介绍', padding=10)
        intro_card.pack(fill='x', pady=(0, 10))
        
        intro_text = """【指数衰减模型】PQI(t) = PQI₀ × exp(-k × t)

【标定方法】同一路段需有多于一年的数据，路段按路线编码+起点+终点匹配；剔除养护干预点（相邻两年上升>2分）；线性化拟合后取中位数"""
        ttk.Label(intro_card, text=intro_text, justify='left', font=('Microsoft YaHei', 9),
                  foreground=THEME['text']).pack(anchor='w')
        
        # 计算按钮 + 导出按钮
        btn_frame = ttk.Frame(self.decay_frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text='计算衰减率', command=self._calculate_decay_rates,
                   style='Primary.TButton').pack(side='left')
        self.calc_status_label = ttk.Label(btn_frame, text='请先加载数据', 
                                            foreground=THEME['text_light'], font=('Microsoft YaHei', 9))
        self.calc_status_label.pack(side='left', padx=15)
        
        # 导出和复制按钮
        tk.Button(btn_frame, text='📥 导出Excel', command=self._export_decay_excel).pack(side='left', padx=5)
        tk.Button(btn_frame, text='📋 复制', command=self._copy_decay_to_clipboard).pack(side='left')
        
        # 衰减率表格
        table_card = ttk.LabelFrame(self.decay_frame, text='衰减系数标定结果', padding=10)
        table_card.pack(fill='both', expand=True)
        
        cols = ('路面类型', '技术等级', 'PQI衰减系数k', 'PCI衰减系数k', 'RQI衰减系数k', '有效样本数')
        self.decay_tree = ttk.Treeview(table_card, columns=cols, show='headings', height=10)
        
        col_widths = {'路面类型': 90, '技术等级': 80, 'PQI衰减系数k': 110, 
                      'PCI衰减系数k': 110, 'RQI衰减系数k': 110, '有效样本数': 90}
        for col in cols:
            self.decay_tree.heading(col, text=col)
            self.decay_tree.column(col, width=col_widths[col], anchor='center')
        
        vsb = ttk.Scrollbar(table_card, orient='vertical', command=self.decay_tree.yview)
        self.decay_tree.configure(yscrollcommand=vsb.set)
        self.decay_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # 初始提示
        self.decay_tree.insert('', 'end', values=('', '', '请加载数据后点击计算', '', '', ''))
        
        # 关键发现
        self.insight_card = ttk.LabelFrame(self.decay_frame, text='关键发现', padding=10)
        self.insight_card.pack(fill='x', pady=(10, 0))
        self.insight_text_var = tk.StringVar(value='加载数据并计算后显示关键发现')
        ttk.Label(self.insight_card, textvariable=self.insight_text_var, justify='left', 
                  font=('Microsoft YaHei', 9), foreground=THEME['text']).pack(anchor='w')

    # ── Tab 2: 5年PQI预测 ──
    def _build_prediction_tab(self):
        # 外层容器（用于添加滚动条）
        outer_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(outer_frame, text=' 5年PQI预测 ')
        
        # Canvas + Scrollbar 实现垂直滚动
        pred_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        pred_vsb = ttk.Scrollbar(outer_frame, orient='vertical', command=pred_canvas.yview)
        pred_canvas.configure(yscrollcommand=pred_vsb.set)
        pred_vsb.pack(side='right', fill='y')
        pred_canvas.pack(side='left', fill='both', expand=True)
        
        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            pred_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        pred_canvas.bind_all('<MouseWheel>', _on_mousewheel, add='+')
        self._pred_canvas = pred_canvas  # 保存引用以便解绑
        
        # 内层可滚动框架
        self.pred_frame = ttk.Frame(pred_canvas)
        pred_canvas.create_window((0, 0), window=self.pred_frame, anchor='nw')
        self.pred_frame.bind('<Configure>', lambda e: pred_canvas.configure(scrollregion=pred_canvas.bbox('all')))
        
        # 按钮 + 导出复制
        btn_frame = ttk.Frame(self.pred_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text='生成5年预测表', command=self._generate_prediction,
                   style='Primary.TButton').pack(side='left')
        tk.Button(btn_frame, text='📥 导出Excel', command=self._export_prediction_excel).pack(side='left', padx=5)
        tk.Button(btn_frame, text='📋 复制', command=self._copy_prediction_to_clipboard).pack(side='left')
        
        # 表格（使用Frame包裹以便使用grid布局）
        table_frame = ttk.Frame(self.pred_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        table_label = ttk.LabelFrame(table_frame, text='各线路5年PQI/PCI/RQI预测值', padding=10)
        table_label.pack(fill='both', expand=True)
        
        self.pred_tree = ttk.Treeview(table_label, show='headings', height=12)
        
        # 滚动条（垂直+水平）
        vsb = ttk.Scrollbar(table_label, orient='vertical', command=self.pred_tree.yview)
        hsb = ttk.Scrollbar(table_label, orient='horizontal', command=self.pred_tree.xview)
        self.pred_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # 表格 + 滚动条布局
        self.pred_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        # 配置grid权重
        table_label.grid_rowconfigure(0, weight=1)
        table_label.grid_columnconfigure(0, weight=1)
        
        # 初始提示
        self.pred_tree.insert('', 'end', values=('请先加载数据并点击生成按钮',))
        
        # ════════════════════════════════════════
        # 养护触发模型参数（可选启用/禁用）
        # ════════════════════════════════════════
        trigger_card = ttk.LabelFrame(self.pred_frame, text='养护触发模型参数（可手动调整）', padding=10)
        trigger_card.pack(fill='x', padx=10, pady=(0, 10))
        
        # 启用/禁用开关
        trigger_top = ttk.Frame(trigger_card)
        trigger_top.pack(fill='x', pady=(0, 5))
        
        self.trigger_enabled_var = tk.BooleanVar(value=True)
        self.trigger_check = tk.Checkbutton(
            trigger_top, text='启用养护触发模型（生成预测时根据触发条件判断养护类型并回调）',
            variable=self.trigger_enabled_var, font=('Microsoft YaHei', 9),
            command=self._on_trigger_toggle)
        self.trigger_check.pack(side='left')
        
        # 年度配置：按年份设置是否启用养护触发
        yearly_frame = ttk.Frame(trigger_card)
        yearly_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Label(yearly_frame, text='年度养护触发配置：', font=('Microsoft YaHei', 9, 'bold')).pack(side='left', padx=(0, 5))
        
        self.yearly_trigger_vars = {}
        for year in range(2026, 2031):
            var = tk.BooleanVar(value=True)
            self.yearly_trigger_vars[year] = var
            chk = tk.Checkbutton(
                yearly_frame, text=f'{year}年', variable=var, font=('Microsoft YaHei', 9),
                width=10)
            chk.pack(side='left', padx=2)
        
        # 触发模型参数容器（启用时显示，禁用时灰化）
        self.trigger_params_frame = ttk.Frame(trigger_card)
        self.trigger_params_frame.pack(fill='x')
        
        # 加载当前触发模型配置
        current_trigger = {}
        if get_trigger_model:
            try:
                current_trigger = get_trigger_model()
            except:
                pass
        
        self.trigger_vars = {}
        
        # ── 路面改造条件 ──
        reform_label = ttk.Label(self.trigger_params_frame, text='【路面改造条件】满足任一指标即触发',
                                  font=('Microsoft YaHei', 9, 'bold'))
        reform_label.pack(anchor='w', pady=(5, 1))
        
        # 路面改造参数表头
        reform_header = ttk.Frame(self.trigger_params_frame)
        reform_header.pack(fill='x', padx=5, pady=2)
        headers = ['路面类型', '技术等级', 'PCI阈值', 'PCI参与', 'PQI阈值', 'PQI参与', 'RQI阈值', 'RQI参与']
        col_widths = [10, 10, 6, 6, 6, 6, 6, 6]
        for h, w in zip(headers, col_widths):
            ttk.Label(reform_header, text=h, width=w, anchor='center',
                      font=('Microsoft YaHei', 8, 'bold')).pack(side='left', padx=6)
        
        # 路面改造参数行
        reform_rows = [
            ('沥青路面', '一级公路', True, True, True),
            ('沥青路面', '二级及以下', True, True, True),
            ('水泥路面', '一级公路', True, True, False),
            ('水泥路面', '二级及以下', True, True, False),
        ]
        for ptype, grade, pci_on, pqi_on, rqion in reform_rows:
            row_f = ttk.Frame(self.trigger_params_frame)
            row_f.pack(fill='x', padx=5, pady=0)
            
            ttk.Label(row_f, text=ptype, width=10, anchor='center').pack(side='left', padx=2)
            ttk.Label(row_f, text=grade, width=10, anchor='center').pack(side='left', padx=2)
            
            cfg = current_trigger.get('路面改造', {}).get(ptype, {}).get(grade, {})
            
            pci_var = tk.IntVar(value=cfg.get('PCI', 80))
            pci_on_var = tk.BooleanVar(value=cfg.get('PCI启用', pci_on))
            pqi_var = tk.IntVar(value=cfg.get('PQI', 80))
            pqi_on_var = tk.BooleanVar(value=cfg.get('PQI启用', pqi_on))
            rqi_var = tk.IntVar(value=cfg.get('RQI', 80))
            rqion_var = tk.BooleanVar(value=cfg.get('RQI启用', rqion))
            
            self.trigger_vars[f'改造_{ptype}_{grade}_PCI'] = pci_var
            self.trigger_vars[f'改造_{ptype}_{grade}_PCI启用'] = pci_on_var
            self.trigger_vars[f'改造_{ptype}_{grade}_PQI'] = pqi_var
            self.trigger_vars[f'改造_{ptype}_{grade}_PQI启用'] = pqi_on_var
            self.trigger_vars[f'改造_{ptype}_{grade}_RQI'] = rqi_var
            self.trigger_vars[f'改造_{ptype}_{grade}_RQI启用'] = rqion_var
            
            pci_entry = ttk.Entry(row_f, textvariable=pci_var, width=6)
            pci_entry.pack(side='left', padx=2)
            pci_check = tk.Checkbutton(row_f, text='', variable=pci_on_var, width=6,
                                        command=lambda e=pci_entry, v=pci_on_var: e.configure(
                                            state='normal' if v.get() else 'disabled'))
            pci_check.pack(side='left', padx=2)
            if not pci_on_var.get():
                pci_entry.configure(state='disabled')
                
            pqi_entry = ttk.Entry(row_f, textvariable=pqi_var, width=6)
            pqi_entry.pack(side='left', padx=2)
            pqi_check = tk.Checkbutton(row_f, text='', variable=pqi_on_var, width=6,
                                        command=lambda e=pqi_entry, v=pqi_on_var: e.configure(
                                            state='normal' if v.get() else 'disabled'))
            pqi_check.pack(side='left', padx=2)
            if not pqi_on_var.get():
                pqi_entry.configure(state='disabled')
                
            rqi_entry = ttk.Entry(row_f, textvariable=rqi_var, width=6)
            rqi_entry.pack(side='left', padx=2)
            rqi_check = tk.Checkbutton(row_f, text='', variable=rqion_var, width=6,
                                        command=lambda e=rqi_entry, v=rqion_var: e.configure(
                                            state='normal' if v.get() else 'disabled'))
            rqi_check.pack(side='left', padx=2)
            if not rqion_var.get():
                rqi_entry.configure(state='disabled')
        
        # ── 预防养护条件 ──
        prev_label = ttk.Label(self.trigger_params_frame, text='【预防养护条件】不满足路面改造时，需同时满足',
                                font=('Microsoft YaHei', 9, 'bold'))
        prev_label.pack(anchor='w', pady=(8, 2))
        
        # 预防养护参数表头
        prev_header = ttk.Frame(self.trigger_params_frame)
        prev_header.pack(fill='x', padx=5, pady=2)
        prev_headers = ['路面类型', '技术等级', 'PCI低', 'PCI高', 'PCI参与', 'RQI低', 'RQI高', 'RQI参与', 'PQI≥', 'PQI参与']
        prev_widths = [10, 10, 5, 5, 6, 5, 5, 6, 5, 6]
        for h, w in zip(prev_headers, prev_widths):
            ttk.Label(prev_header, text=h, width=w, anchor='center',
                      font=('Microsoft YaHei', 8, 'bold')).pack(side='left', padx=6)
        
        # 预防养护参数行
        prev_rows = [
            ('沥青路面', '一级公路', 80, 90, True, 80, 90, True, 80, True),
            ('沥青路面', '二级及以下', 78, 85, True, 78, 85, True, 75, True),
            ('水泥路面', '一级公路', 80, 90, True, 60, 85, False, 80, True),
            ('水泥路面', '二级及以下', 78, 85, True, 60, 85, False, 75, True),
        ]
        for ptype, grade, pci_lo, pci_hi, pci_on, rqi_lo, rqi_hi, rqi_on, pqi_min, pqi_on in prev_rows:
            row_f = ttk.Frame(self.trigger_params_frame)
            row_f.pack(fill='x', padx=5, pady=0)
            
            ttk.Label(row_f, text=ptype, width=10, anchor='center').pack(side='left', padx=2)
            ttk.Label(row_f, text=grade, width=10, anchor='center').pack(side='left', padx=2)
            
            cfg = current_trigger.get('预防性养护', {}).get(ptype, {}).get(grade, {})
            
            pci_lo_var = tk.IntVar(value=cfg.get('PCI低', pci_lo))
            pci_hi_var = tk.IntVar(value=cfg.get('PCI高', pci_hi))
            pci_on_var = tk.BooleanVar(value=cfg.get('PCI启用', pci_on))
            rqi_lo_var = tk.IntVar(value=cfg.get('RQI低', rqi_lo))
            rqi_hi_var = tk.IntVar(value=cfg.get('RQI高', rqi_hi))
            rqi_on_var = tk.BooleanVar(value=cfg.get('RQI启用', rqi_on))
            pqi_var = tk.IntVar(value=cfg.get('PQI', pqi_min))
            pqi_on_var = tk.BooleanVar(value=cfg.get('PQI启用', pqi_on))
            
            self.trigger_vars[f'预防_{ptype}_{grade}_PCI低'] = pci_lo_var
            self.trigger_vars[f'预防_{ptype}_{grade}_PCI高'] = pci_hi_var
            self.trigger_vars[f'预防_{ptype}_{grade}_PCI启用'] = pci_on_var
            self.trigger_vars[f'预防_{ptype}_{grade}_RQI低'] = rqi_lo_var
            self.trigger_vars[f'预防_{ptype}_{grade}_RQI高'] = rqi_hi_var
            self.trigger_vars[f'预防_{ptype}_{grade}_RQI启用'] = rqi_on_var
            self.trigger_vars[f'预防_{ptype}_{grade}_PQI'] = pqi_var
            self.trigger_vars[f'预防_{ptype}_{grade}_PQI启用'] = pqi_on_var
            
            pci_lo_entry = ttk.Entry(row_f, textvariable=pci_lo_var, width=5)
            pci_lo_entry.pack(side='left', padx=2)
            pci_hi_entry = ttk.Entry(row_f, textvariable=pci_hi_var, width=5)
            pci_hi_entry.pack(side='left', padx=2)
            pci_check = tk.Checkbutton(row_f, text='', variable=pci_on_var, width=6,
                                       command=lambda lo=pci_lo_entry, hi=pci_hi_entry, v=pci_on_var: (
                                           lo.configure(state='normal' if v.get() else 'disabled'),
                                           hi.configure(state='normal' if v.get() else 'disabled')))
            pci_check.pack(side='left', padx=6)
            if not pci_on_var.get():
                pci_lo_entry.configure(state='disabled')
                pci_hi_entry.configure(state='disabled')
            
            rqi_lo_entry = ttk.Entry(row_f, textvariable=rqi_lo_var, width=5)
            rqi_lo_entry.pack(side='left', padx=2)
            rqi_hi_entry = ttk.Entry(row_f, textvariable=rqi_hi_var, width=5)
            rqi_hi_entry.pack(side='left', padx=2)
            rqi_check = tk.Checkbutton(row_f, text='', variable=rqi_on_var, width=6,
                                       command=lambda lo=rqi_lo_entry, hi=rqi_hi_entry, v=rqi_on_var: (
                                           lo.configure(state='normal' if v.get() else 'disabled'),
                                           hi.configure(state='normal' if v.get() else 'disabled')))
            rqi_check.pack(side='left', padx=6)
            if not rqi_on_var.get():
                rqi_lo_entry.configure(state='disabled')
                rqi_hi_entry.configure(state='disabled')
            
            pqi_entry = ttk.Entry(row_f, textvariable=pqi_var, width=5)
            pqi_entry.pack(side='left', padx=2)
            pqi_check = tk.Checkbutton(row_f, text='', variable=pqi_on_var, width=6,
                                       command=lambda e=pqi_entry, v=pqi_on_var: e.configure(
                                           state='normal' if v.get() else 'disabled'))
            pqi_check.pack(side='left', padx=6)
            if not pqi_on_var.get():
                pqi_entry.configure(state='disabled')
        
        # 触发模型按钮
        trigger_btn_frame = ttk.Frame(trigger_card)
        trigger_btn_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(trigger_btn_frame, text='保存触发参数', command=self._save_trigger_config,
                   style='Primary.TButton', width=13).pack(side='left', padx=5)
        ttk.Button(trigger_btn_frame, text='恢复默认', command=self._reset_trigger_config,
                   style='Primary.TButton', width=10).pack(side='left', padx=5)
        
        # 养护回调参数配置
        callback_card = ttk.LabelFrame(self.pred_frame, text='养护后PQI回调参数（可手动调整）', padding=10)
        callback_card.pack(fill='x', padx=10, pady=(0, 10))

        # 回调参数变量
        self.callback_vars = {}
        
        # 定义回调参数配置项
        callback_fields = [
            ('路面改造-沥青PQI', '路面改造', '沥青路面', 'PQI'),
            ('路面改造-沥青PCI', '路面改造', '沥青路面', 'PCI'),
            ('路面改造-沥青RQI', '路面改造', '沥青路面', 'RQI'),
            ('路面改造-水泥PQI', '路面改造', '水泥路面', 'PQI'),
            ('路面改造-水泥PCI', '路面改造', '水泥路面', 'PCI'),
            ('路面改造-水泥RQI', '路面改造', '水泥路面', 'RQI'),
            ('预防养护-沥青PQI', '预防性养护', '沥青路面', 'PQI'),
            ('预防养护-沥青PCI', '预防性养护', '沥青路面', 'PCI'),
            ('预防养护-沥青RQI', '预防性养护', '沥青路面', 'RQI'),
            ('预防养护-水泥PQI', '预防性养护', '水泥路面', 'PQI'),
            ('预防养护-水泥PCI', '预防性养护', '水泥路面', 'PCI'),
            ('预防养护-水泥RQI', '预防性养护', '水泥路面', 'RQI'),
        ]

        # 加载当前配置
        current_callback = {}
        if get_maintenance_callback:
            try:
                current_callback = get_maintenance_callback()
            except:
                pass

        # 创建输入框（两列布局）
        for i, (label, maint_type, ptype, idx) in enumerate(callback_fields):
            row = i // 2
            col = i % 2
            
            if i % 2 == 0:
                callback_row = ttk.Frame(callback_card)
                callback_row.pack(fill='x', pady=2)
            
            field_frame = ttk.Frame(callback_row)
            field_frame.pack(side='left', padx=15, pady=2)
            
            tk.Label(field_frame, text=f'{label}：', width=14).pack(side='left')
            
            var = tk.IntVar()
            # 从当前配置获取值，如果没有则用默认值
            default_val = current_callback.get(maint_type, {}).get(ptype, {}).get(idx, 90)
            var.set(default_val)
            self.callback_vars[f'{maint_type}_{ptype}_{idx}'] = var
            
            ttk.Entry(field_frame, textvariable=var, width=6).pack(side='left')

        # 回调参数按钮
        callback_btn_frame = ttk.Frame(self.pred_frame)
        callback_btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        tk.Button(callback_btn_frame, text='💾 保存回调参数', command=self._save_callback_config,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=15).pack(side='left', padx=5)
        tk.Button(callback_btn_frame, text='↺ 恢复默认', command=self._reset_callback_config,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=12).pack(side='left')

    # ── Tab 3: PQI-Proj. IMP（手动养护规划）──
    def _build_pqi_proj_tab(self):
        outer_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(outer_frame, text=' PQI-Proj. IMP ')
        
        pred_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        pred_vsb = ttk.Scrollbar(outer_frame, orient='vertical', command=pred_canvas.yview)
        pred_canvas.configure(yscrollcommand=pred_vsb.set)
        pred_vsb.pack(side='right', fill='y')
        pred_canvas.pack(side='left', fill='both', expand=True)
        
        def _on_mousewheel(event):
            pred_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        pred_canvas.bind_all('<MouseWheel>', _on_mousewheel, add='+')
        
        self.pqi_proj_frame = ttk.Frame(pred_canvas)
        pred_canvas.create_window((0, 0), window=self.pqi_proj_frame, anchor='nw')
        self.pqi_proj_frame.bind('<Configure>', lambda e: pred_canvas.configure(scrollregion=pred_canvas.bbox('all')))
        
        btn_frame = ttk.Frame(self.pqi_proj_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text='生成5年预测表', command=self._generate_pqi_proj,
                   style='Primary.TButton').pack(side='left')
        tk.Button(btn_frame, text='📥 导出Excel', command=self._export_pqi_proj_excel).pack(side='left', padx=5)
        tk.Button(btn_frame, text='📋 复制', command=self._copy_pqi_proj_to_clipboard).pack(side='left')
        
        table_frame = ttk.Frame(self.pqi_proj_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        table_label = ttk.LabelFrame(table_frame, text='各线路5年PQI/PCI/RQI预测值（手动养护规划）', padding=10)
        table_label.pack(fill='both', expand=True)
        
        self.pqi_proj_tree = ttk.Treeview(table_label, show='headings', height=12)
        
        vsb = ttk.Scrollbar(table_label, orient='vertical', command=self.pqi_proj_tree.yview)
        hsb = ttk.Scrollbar(table_label, orient='horizontal', command=self.pqi_proj_tree.xview)
        self.pqi_proj_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.pqi_proj_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        table_label.grid_rowconfigure(0, weight=1)
        table_label.grid_columnconfigure(0, weight=1)
        
        self.pqi_proj_tree.insert('', 'end', values=('请先加载数据并点击生成按钮',))
        
        manual_plan_card = ttk.LabelFrame(self.pqi_proj_frame, text='手动养护规划（指定路段进行养护）', padding=10)
        manual_plan_card.pack(fill='x', padx=10, pady=(0, 10))
        
        plan_row1 = ttk.Frame(manual_plan_card)
        plan_row1.pack(fill='x', pady=5)
        
        ttk.Label(plan_row1, text='路线编码：', width=10).pack(side='left')
        self.manual_route_var = tk.StringVar()
        ttk.Entry(plan_row1, textvariable=self.manual_route_var, width=15).pack(side='left', padx=5)
        
        ttk.Label(plan_row1, text='路段起点：', width=10).pack(side='left')
        self.manual_start_var = tk.StringVar()
        ttk.Entry(plan_row1, textvariable=self.manual_start_var, width=12).pack(side='left', padx=5)
        
        ttk.Label(plan_row1, text='路段终点：', width=10).pack(side='left')
        self.manual_end_var = tk.StringVar()
        ttk.Entry(plan_row1, textvariable=self.manual_end_var, width=12).pack(side='left', padx=5)
        
        plan_row2 = ttk.Frame(manual_plan_card)
        plan_row2.pack(fill='x', pady=5)
        
        ttk.Label(plan_row2, text='养护年份：', width=10).pack(side='left')
        self.manual_year_var = tk.StringVar(value='2026')
        ttk.Combobox(plan_row2, textvariable=self.manual_year_var, values=[str(y) for y in range(2026, 2031)], width=8).pack(side='left', padx=5)
        
        ttk.Label(plan_row2, text='养护类型：', width=10).pack(side='left')
        self.manual_maint_type_var = tk.StringVar(value='预防性养护')
        ttk.Combobox(plan_row2, textvariable=self.manual_maint_type_var, values=['路面改造', '预防性养护'], width=10).pack(side='left', padx=5)
        
        ttk.Button(plan_row2, text='添加养护规划', command=self._add_manual_maintenance,
                   style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(plan_row2, text='清空规划', command=self._clear_manual_maintenance,
                   style='Primary.TButton').pack(side='left', padx=5)
        
        # 提示：如果不填写路段起终点，则对整个路线进行养护规划
        hint_label = ttk.Label(manual_plan_card, text='提示：如果不填写路段起终点，则对整个路线进行养护规划', 
                               font=('Microsoft YaHei', 8), foreground='#666666')
        hint_label.pack(anchor='w', pady=(5, 0))
        
        self.manual_plan_list = ttk.LabelFrame(self.pqi_proj_frame, text='已添加的手动养护规划', padding=10)
        self.manual_plan_list.pack(fill='x', padx=10, pady=(0, 10))
        
        manual_plan_frame = ttk.Frame(self.manual_plan_list)
        manual_plan_frame.pack(fill='both', expand=True)
        
        self.manual_plan_tree = ttk.Treeview(manual_plan_frame, columns=('路线编码', '路段起点', '路段终点', '年份', '养护类型'), show='headings', height=5)
        self.manual_plan_tree.heading('路线编码', text='路线编码')
        self.manual_plan_tree.heading('路段起点', text='路段起点')
        self.manual_plan_tree.heading('路段终点', text='路段终点')
        self.manual_plan_tree.heading('年份', text='年份')
        self.manual_plan_tree.heading('养护类型', text='养护类型')
        self.manual_plan_tree.column('路线编码', width=70, anchor='center')
        self.manual_plan_tree.column('路段起点', width=70, anchor='center')
        self.manual_plan_tree.column('路段终点', width=70, anchor='center')
        self.manual_plan_tree.column('年份', width=60, anchor='center')
        self.manual_plan_tree.column('养护类型', width=80, anchor='center')
        self.manual_plan_tree.grid(row=0, column=0)
        
        manual_plan_vscroll = ttk.Scrollbar(manual_plan_frame, orient='vertical', command=self.manual_plan_tree.yview)
        manual_plan_vscroll.grid(row=0, column=1, sticky='ns')
        self.manual_plan_tree.configure(yscrollcommand=manual_plan_vscroll.set)
        
        manual_plan_frame.grid_rowconfigure(0, weight=1)
        
        self.manual_plan_tree.bind('<<TreeviewSelect>>', self._on_manual_plan_select)
        
        self.manual_plans = []
        
        good_road_frame = ttk.Frame(self.pqi_proj_frame)
        good_road_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        good_road_btn_frame = ttk.Frame(good_road_frame)
        good_road_btn_frame.pack(fill='x', pady=(0, 5))
        tk.Button(good_road_btn_frame, text='📥 导出PQI优良路率', command=self._export_pqi_proj_good_road_excel).pack(side='left', padx=5)
        tk.Button(good_road_btn_frame, text='📋 复制PQI优良路率', command=self._copy_pqi_proj_good_road_to_clipboard).pack(side='left')
        
        good_road_label = ttk.LabelFrame(good_road_frame, text='PQI优良路率', padding=10)
        good_road_label.pack(fill='both', expand=True)
        
        self.pqi_proj_good_road_tree = ttk.Treeview(good_road_label, show='headings', height=8)
        vsb = ttk.Scrollbar(good_road_label, orient='vertical', command=self.pqi_proj_good_road_tree.yview)
        self.pqi_proj_good_road_tree.configure(yscrollcommand=vsb.set)
        self.pqi_proj_good_road_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.pqi_proj_good_road_tree.insert('', 'end', values=('请先生成5年预测表',))
        
        callback_card = ttk.LabelFrame(self.pqi_proj_frame, text='养护后PQI回调参数（可手动调整）', padding=10)
        callback_card.pack(fill='x', padx=10, pady=(0, 10))
        
        self.pqi_proj_callback_vars = {}
        
        callback_fields = [
            ('路面改造-沥青PQI', '路面改造', '沥青路面', 'PQI'),
            ('路面改造-沥青PCI', '路面改造', '沥青路面', 'PCI'),
            ('路面改造-沥青RQI', '路面改造', '沥青路面', 'RQI'),
            ('路面改造-水泥PQI', '路面改造', '水泥路面', 'PQI'),
            ('路面改造-水泥PCI', '路面改造', '水泥路面', 'PCI'),
            ('路面改造-水泥RQI', '路面改造', '水泥路面', 'RQI'),
            ('预防养护-沥青PQI', '预防性养护', '沥青路面', 'PQI'),
            ('预防养护-沥青PCI', '预防性养护', '沥青路面', 'PCI'),
            ('预防养护-沥青RQI', '预防性养护', '沥青路面', 'RQI'),
            ('预防养护-水泥PQI', '预防性养护', '水泥路面', 'PQI'),
            ('预防养护-水泥PCI', '预防性养护', '水泥路面', 'PCI'),
            ('预防养护-水泥RQI', '预防性养护', '水泥路面', 'RQI'),
        ]
        
        current_callback = {}
        if get_maintenance_callback:
            try:
                current_callback = get_maintenance_callback()
            except:
                pass
        
        for i, (label, maint_type, ptype, idx) in enumerate(callback_fields):
            row = i // 2
            col = i % 2
            
            if i % 2 == 0:
                callback_row = ttk.Frame(callback_card)
                callback_row.pack(fill='x', pady=2)
            
            field_frame = ttk.Frame(callback_row)
            field_frame.pack(side='left', padx=15, pady=2)
            
            tk.Label(field_frame, text=f'{label}：', width=14).pack(side='left')
            
            var = tk.IntVar()
            default_val = current_callback.get(maint_type, {}).get(ptype, {}).get(idx, 90)
            var.set(default_val)
            self.pqi_proj_callback_vars[f'{maint_type}_{ptype}_{idx}'] = var
            
            ttk.Entry(field_frame, textvariable=var, width=6).pack(side='left')
        
        callback_btn_frame = ttk.Frame(self.pqi_proj_frame)
        callback_btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        tk.Button(callback_btn_frame, text='💾 保存回调参数', command=self._save_pqi_proj_callback_config,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=15).pack(side='left', padx=5)
        tk.Button(callback_btn_frame, text='↺ 恢复默认', command=self._reset_pqi_proj_callback_config,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=12).pack(side='left')
    
    # ── Tab 4: 养护里程 ──
    def _build_mileage_tab(self):
        self.mileage_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(self.mileage_frame, text=' 养护里程 ')
        
        # 创建带滚动条的容器
        canvas = tk.Canvas(self.mileage_frame)
        vsb = ttk.Scrollbar(self.mileage_frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        
        # 内容框架
        content_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        
        content_frame.bind('<Configure>', on_configure)
        
        # 模式选择
        mode_frame = ttk.Frame(content_frame)
        mode_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(mode_frame, text='计算模式：', font=('Microsoft YaHei', 9, 'bold')).pack(side='left')
        
        self.mileage_mode_var = tk.StringVar(value='auto')
        ttk.Radiobutton(mode_frame, text='自动养护触发', variable=self.mileage_mode_var, value='auto').pack(side='left', padx=10)
        ttk.Radiobutton(mode_frame, text='手动养护规划', variable=self.mileage_mode_var, value='manual').pack(side='left', padx=10)
        
        # 按钮框架
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text='生成养护里程表', command=self._generate_mileage,
                   style='Primary.TButton').pack(side='left')
        
        # 表格1：自动养护触发
        table_card1 = ttk.LabelFrame(content_frame, text='各线路5年养护里程（公里）- 自动养护触发', padding=10)
        table_card1.pack(fill='x', padx=10, pady=(0, 5))
        
        btn_frame1 = ttk.Frame(table_card1)
        btn_frame1.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame1, text='📥 导出Excel', command=lambda: self._export_mileage_excel('auto')).pack(side='left', padx=5)
        tk.Button(btn_frame1, text='📋 复制', command=lambda: self._copy_mileage_to_clipboard('auto')).pack(side='left')
        
        self.mileage_tree_auto = ttk.Treeview(table_card1, show='headings', height=10)
        vsb1 = ttk.Scrollbar(table_card1, orient='vertical', command=self.mileage_tree_auto.yview)
        self.mileage_tree_auto.configure(yscrollcommand=vsb1.set)
        self.mileage_tree_auto.pack(side='left', fill='both', expand=True)
        vsb1.pack(side='right', fill='y')
        
        self.mileage_tree_auto.insert('', 'end', values=('请点击生成按钮',))
        
        # 表格2：手动养护规划
        table_card2 = ttk.LabelFrame(content_frame, text='各线路5年养护里程（公里）- 手动养护规划', padding=10)
        table_card2.pack(fill='x', padx=10, pady=(0, 5))
        
        btn_frame2 = ttk.Frame(table_card2)
        btn_frame2.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame2, text='📥 导出Excel', command=lambda: self._export_mileage_excel('manual')).pack(side='left', padx=5)
        tk.Button(btn_frame2, text='📋 复制', command=lambda: self._copy_mileage_to_clipboard('manual')).pack(side='left')
        
        self.mileage_tree_manual = ttk.Treeview(table_card2, show='headings', height=10)
        vsb2 = ttk.Scrollbar(table_card2, orient='vertical', command=self.mileage_tree_manual.yview)
        self.mileage_tree_manual.configure(yscrollcommand=vsb2.set)
        self.mileage_tree_manual.pack(side='left', fill='both', expand=True)
        vsb2.pack(side='right', fill='y')
        
        self.mileage_tree_manual.insert('', 'end', values=('请点击生成按钮',))
        
        # 表格3：详细路段养护类型（自动养护触发）
        table_card3 = ttk.LabelFrame(content_frame, text='各线路各路段年度养护类型明细 - 自动养护触发', padding=10)
        table_card3.pack(fill='x', padx=10, pady=(0, 10))
        
        btn_frame3 = ttk.Frame(table_card3)
        btn_frame3.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame3, text='📥 导出Excel', command=self._export_mileage_segment_excel).pack(side='left', padx=5)
        tk.Button(btn_frame3, text='📋 复制', command=self._copy_mileage_segment_to_clipboard).pack(side='left')
        
        self.mileage_segment_tree = ttk.Treeview(table_card3, show='headings', height=10)
        vsb3 = ttk.Scrollbar(table_card3, orient='vertical', command=self.mileage_segment_tree.yview)
        hsb3 = ttk.Scrollbar(table_card3, orient='horizontal', command=self.mileage_segment_tree.xview)
        self.mileage_segment_tree.configure(yscrollcommand=vsb3.set, xscrollcommand=hsb3.set)
        self.mileage_segment_tree.pack(side='left', fill='both', expand=True)
        vsb3.pack(side='right', fill='y')
        hsb3.pack(side='bottom', fill='x')
        
        self.mileage_segment_tree.insert('', 'end', values=('请点击生成按钮',))

    # ── Tab 5: 养护资金 ──
    def _build_fund_tab(self):
        self.fund_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(self.fund_frame, text=' 养护资金 ')
        
        # 模式选择
        mode_frame = ttk.Frame(self.fund_frame)
        mode_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(mode_frame, text='计算模式：', font=('Microsoft YaHei', 9, 'bold')).pack(side='left')
        
        self.fund_mode_var = tk.StringVar(value='auto')
        ttk.Radiobutton(mode_frame, text='自动养护触发', variable=self.fund_mode_var, value='auto').pack(side='left', padx=10)
        ttk.Radiobutton(mode_frame, text='手动养护规划', variable=self.fund_mode_var, value='manual').pack(side='left', padx=10)
        
        # 按钮框架
        btn_frame = ttk.Frame(self.fund_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        tk.Button(btn_frame, text='💰 生成养护资金表', command=self._generate_fund,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2').pack(side='left')
        
        # 表格1：自动养护触发
        table_card1 = ttk.LabelFrame(self.fund_frame, text='各线路5年养护资金（万元）- 自动养护触发', padding=10)
        table_card1.pack(fill='both', expand=True, padx=10, pady=(0, 5))
        
        btn_frame1 = ttk.Frame(table_card1)
        btn_frame1.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame1, text='📥 导出Excel', command=lambda: self._export_fund_excel('auto')).pack(side='left', padx=5)
        tk.Button(btn_frame1, text='📋 复制', command=lambda: self._copy_fund_to_clipboard('auto')).pack(side='left')
        
        self.fund_tree_auto = ttk.Treeview(table_card1, show='headings', height=10)
        vsb = ttk.Scrollbar(table_card1, orient='vertical', command=self.fund_tree_auto.yview)
        self.fund_tree_auto.configure(yscrollcommand=vsb.set)
        self.fund_tree_auto.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.fund_tree_auto.insert('', 'end', values=('请点击生成按钮',))
        
        # 表格2：手动养护规划
        table_card2 = ttk.LabelFrame(self.fund_frame, text='各线路5年养护资金（万元）- 手动养护规划', padding=10)
        table_card2.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        btn_frame2 = ttk.Frame(table_card2)
        btn_frame2.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame2, text='📥 导出Excel', command=lambda: self._export_fund_excel('manual')).pack(side='left', padx=5)
        tk.Button(btn_frame2, text='📋 复制', command=lambda: self._copy_fund_to_clipboard('manual')).pack(side='left')
        
        self.fund_tree_manual = ttk.Treeview(table_card2, show='headings', height=10)
        vsb = ttk.Scrollbar(table_card2, orient='vertical', command=self.fund_tree_manual.yview)
        self.fund_tree_manual.configure(yscrollcommand=vsb.set)
        self.fund_tree_manual.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.fund_tree_manual.insert('', 'end', values=('请点击生成按钮',))

    # ── Tab 6: 年度汇总 ──
    def _build_yearly_summary_tab(self):
        self.yearly_frame = ttk.Frame(self.model_notebook)
        self.model_notebook.add(self.yearly_frame, text=' 年度汇总 ')
        
        # 模式选择
        mode_frame = ttk.Frame(self.yearly_frame)
        mode_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(mode_frame, text='计算模式：', font=('Microsoft YaHei', 9, 'bold')).pack(side='left')
        
        self.yearly_mode_var = tk.StringVar(value='auto')
        ttk.Radiobutton(mode_frame, text='自动养护触发', variable=self.yearly_mode_var, value='auto').pack(side='left', padx=10)
        ttk.Radiobutton(mode_frame, text='手动养护规划', variable=self.yearly_mode_var, value='manual').pack(side='left', padx=10)
        
        # 按钮框架
        btn_frame = ttk.Frame(self.yearly_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        tk.Button(btn_frame, text='📋 生成年度汇总表', command=self._generate_yearly_summary,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2').pack(side='left', padx=5)
        
        # 表格1：自动养护触发
        table_card1 = ttk.LabelFrame(self.yearly_frame, text='每年路面改造与预防养护汇总 - 自动养护触发', padding=10)
        table_card1.pack(fill='both', expand=True, padx=10, pady=(0, 5))
        
        btn_frame1 = ttk.Frame(table_card1)
        btn_frame1.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame1, text='📥 导出Excel', command=lambda: self._export_yearly_excel('auto')).pack(side='left', padx=5)
        tk.Button(btn_frame1, text='📋 复制', command=lambda: self._copy_yearly_to_clipboard('auto')).pack(side='left')
        
        self.yearly_tree_auto = ttk.Treeview(table_card1, show='headings', height=8)
        vsb = ttk.Scrollbar(table_card1, orient='vertical', command=self.yearly_tree_auto.yview)
        self.yearly_tree_auto.configure(yscrollcommand=vsb.set)
        self.yearly_tree_auto.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.yearly_tree_auto.insert('', 'end', values=('请点击生成按钮',))
        
        # 表格2：手动养护规划
        table_card2 = ttk.LabelFrame(self.yearly_frame, text='每年路面改造与预防养护汇总 - 手动养护规划', padding=10)
        table_card2.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        btn_frame2 = ttk.Frame(table_card2)
        btn_frame2.pack(fill='x', pady=(0, 5))
        tk.Button(btn_frame2, text='📥 导出Excel', command=lambda: self._export_yearly_excel('manual')).pack(side='left', padx=5)
        tk.Button(btn_frame2, text='📋 复制', command=lambda: self._copy_yearly_to_clipboard('manual')).pack(side='left')
        
        self.yearly_tree_manual = ttk.Treeview(table_card2, show='headings', height=8)
        vsb = ttk.Scrollbar(table_card2, orient='vertical', command=self.yearly_tree_manual.yview)
        self.yearly_tree_manual.configure(yscrollcommand=vsb.set)
        self.yearly_tree_manual.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.yearly_tree_manual.insert('', 'end', values=('请点击生成按钮',))

    def _calculate_decay_rates(self):
        """动态计算衰减率（支持按县计算）"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先在"数据配置"中加载数据')
            return
        
        # 合并所有数据
        all_df = self.data_cache.get('全部', pd.DataFrame())
        if all_df.empty:
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)
        
        if all_df.empty:
            messagebox.showwarning('提示', '没有可分析的数据')
            return
        
        # 检查必要列
        required = ['路线编码', '路段起点', '路段终点', '年份', 'PQI', '路面类型', '技术等级']
        missing = [c for c in required if c not in all_df.columns]
        if missing:
            messagebox.showwarning('提示', f'数据缺少必要列：{missing}')
            return
        
        # 获取当前选择的县
        county = self._get_current_county()
        county_text = f"（{county}）" if county else "（全部）"
        
        self.calc_status_label.config(text='正在计算...', foreground=THEME['text_light'])
        self.update()
        
        try:
            from src.decay_calculator import calculate_decay_rates
            
            results = calculate_decay_rates(all_df, county)
            
            # 清空表格
            for item in self.decay_tree.get_children():
                self.decay_tree.delete(item)
            
            if results:
                grade_order = {'一级公路': 1, '二级公路': 2, '三级公路': 3, '四级公路': 4}
                sorted_keys = sorted(results.keys(), key=lambda x: (x[0], grade_order.get(x[1], 5)))
                
                total_samples = 0
                for key in sorted_keys:
                    vals = results[key]
                    pqi_k = f"{vals['PQI']:.4f}" if vals['PQI'] else '-'
                    pci_k = f"{vals['PCI']:.4f}" if vals['PCI'] else '-'
                    rqi_k = f"{vals['RQI']:.4f}" if vals['RQI'] else '-'
                    samples = vals['样本数']
                    total_samples += samples
                    
                    self.decay_tree.insert('', 'end', values=(key[0], key[1], pqi_k, pci_k, rqi_k, str(samples)))
                
                self.calc_status_label.config(
                    text=f'计算完成{county_text}，共{total_samples}个有效样本', 
                    foreground=THEME['success']
                )
                
                self._update_insights(results, county)
                
            else:
                self.decay_tree.insert('', 'end', values=('', '', '样本不足，无法计算', '', '', ''))
                self.calc_status_label.config(text='样本不足', foreground=THEME['warning'])
                self.insight_text_var.set('样本不足，无法生成关键发现')
                
        except Exception as e:
            messagebox.showerror('错误', f'计算失败：{str(e)}')
            import traceback
            traceback.print_exc()
            self.calc_status_label.config(text='计算失败', foreground=THEME['danger'])

    def _generate_prediction(self):
        """生成5年PQI预测表"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        # 自动同步UI上的触发模型参数（无需用户手动点保存）
        if hasattr(self, '_collect_trigger_config') and set_trigger_model:
            try:
                config = self._collect_trigger_config()
                set_trigger_model(config)
            except:
                pass
        
        all_df = pd.concat(self.data_cache.values(), ignore_index=True)
        if all_df.empty:
            return
        
        county = self._get_current_county()
        
        try:
            from src.decay_calculator import predict_5year_pqi, calculate_good_road_rate
            
            df_result = predict_5year_pqi(all_df, county)
            
            # 计算优良路率
            good_road_df = calculate_good_road_rate(all_df, county)
            
            # 设置表格列
            self.pred_tree.delete(*self.pred_tree.get_children())
            self.pred_tree['columns'] = list(df_result.columns)
            for col in df_result.columns:
                self.pred_tree.heading(col, text=col)
                # 计算列宽：中文字符宽度约10像素，英文约6像素
                col_width = len(str(col)) * 8 + 10
                for _, row in df_result.iterrows():
                    cell_text = str(row.get(col, ''))
                    cn_chars = sum(1 for c in cell_text if '\u4e00' <= c <= '\u9fff')
                    en_chars = len(cell_text) - cn_chars
                    cell_width = cn_chars * 10 + en_chars * 6 + 10
                    col_width = max(col_width, cell_width)
                # 限制最大宽度为100
                col_width = min(col_width, 100)
                self.pred_tree.column(col, width=col_width, minwidth=40, anchor='center', stretch=False)
            
            # 填充数据
            for _, row in df_result.iterrows():
                vals = [str(row.get(col, '')) for col in df_result.columns]
                self.pred_tree.insert('', 'end', values=vals)
            
            # 显示优良路率
            if not good_road_df.empty:
                # 先删除已有的优良路率卡片（如果存在）
                if hasattr(self, 'good_road_frame') and self.good_road_frame.winfo_exists():
                    self.good_road_frame.destroy()
                
                # 创建优良路率显示卡片
                self.good_road_frame = ttk.LabelFrame(self.pred_frame, text='PQI优良路率', padding=10)
                self.good_road_frame.pack(fill='x', padx=10, pady=(10, 0))
                
                # 添加导出和复制按钮
                btn_frame = ttk.Frame(self.good_road_frame)
                btn_frame.pack(fill='x', pady=(0, 10))
                tk.Button(btn_frame, text='📥 导出Excel', 
                          command=lambda df=good_road_df: self._export_good_road_excel(df)).pack(side='left', padx=5)
                tk.Button(btn_frame, text='📋 复制到剪贴板', 
                          command=lambda df=good_road_df: self._copy_good_road_to_clipboard(df)).pack(side='left', padx=5)
                
                # 创建表格
                good_road_tree = ttk.Treeview(self.good_road_frame, show='headings', height=6)
                good_road_tree['columns'] = list(good_road_df.columns)
                for col in good_road_df.columns:
                    good_road_tree.heading(col, text=col)
                    # 计算列宽：中文字符宽度约10像素，英文约6像素
                    col_width = len(str(col)) * 8 + 10
                    for _, row in good_road_df.iterrows():
                        cell_text = str(row.get(col, ''))
                        cn_chars = sum(1 for c in cell_text if '\u4e00' <= c <= '\u9fff')
                        en_chars = len(cell_text) - cn_chars
                        cell_width = cn_chars * 10 + en_chars * 6 + 10
                        col_width = max(col_width, cell_width)
                    # 限制最大宽度为100
                    col_width = min(col_width, 100)
                    good_road_tree.column(col, width=col_width, minwidth=40, anchor='center', stretch=False)
                
                # 填充数据
                for _, row in good_road_df.iterrows():
                    vals = [str(row.get(col, '')) for col in good_road_df.columns]
                    good_road_tree.insert('', 'end', values=vals)
                
                # 添加滚动条
                vsb = ttk.Scrollbar(self.good_road_frame, orient='vertical', command=good_road_tree.yview)
                good_road_tree.configure(yscrollcommand=vsb.set)
                good_road_tree.pack(side='left', fill='both', expand=True)
                vsb.pack(side='right', fill='y')
                
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')

    def _generate_mileage(self):
        """生成养护里程表（双模式）"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        # 自动同步UI上的触发模型参数
        if hasattr(self, '_collect_trigger_config') and set_trigger_model:
            try:
                config = self._collect_trigger_config()
                set_trigger_model(config)
            except:
                pass
        
        all_df = pd.concat(self.data_cache.values(), ignore_index=True)
        if all_df.empty:
            return
        
        county = self._get_current_county()
        
        try:
            from src.decay_calculator import calculate_maintenance_plan, calculate_maintenance_plan_with_manual
            
            # 获取手动养护规划
            manual_plans = []
            if hasattr(self, 'manual_plans'):
                manual_plans = self.manual_plans
            
            # 生成自动养护触发表格
            self._generate_mileage_table(self.mileage_tree_auto, all_df, county, mode='auto', manual_plans=[])
            
            # 生成手动养护规划表格
            self._generate_mileage_table(self.mileage_tree_manual, all_df, county, mode='manual', manual_plans=manual_plans)
            
            # 生成详细路段养护类型表（自动养护触发）
            self._generate_mileage_segment_table(all_df, county)
            
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')
    
    def _generate_mileage_table(self, tree, df, county, mode='auto', manual_plans=None):
        """生成单个养护里程表格"""
        from src.decay_calculator import calculate_maintenance_plan, calculate_maintenance_plan_with_manual
        
        if manual_plans is None:
            manual_plans = []
        
        if mode == 'auto':
            plan = calculate_maintenance_plan(df, county)
        else:
            plan = calculate_maintenance_plan_with_manual(df, county, manual_plans)
        
        cols = ['路线', '2026改造', '2026预防', '2027改造', '2027预防', '2028改造', '2028预防', 
                '2029改造', '2029预防', '2030改造', '2030预防', '改造小计', '预防小计', '总计']
        tree.delete(*tree.get_children())
        tree['columns'] = cols
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=70, anchor='center')
        
        total_renovate = {y: 0 for y in range(2026, 2031)}
        total_prevent = {y: 0 for y in range(2026, 2031)}
        
        for route, data in plan.items():
            row = [route]
            route_renovate = 0
            route_prevent = 0
            for year in range(2026, 2031):
                ren = data['里程'][year].get('路面改造', 0)
                pre = data['里程'][year].get('预防性养护', 0)
                row.append(f'{ren:.2f}' if ren else '-')
                row.append(f'{pre:.2f}' if pre else '-')
                route_renovate += ren
                route_prevent += pre
                total_renovate[year] += ren
                total_prevent[year] += pre
            
            row.append(f'{route_renovate:.2f}')
            row.append(f'{route_prevent:.2f}')
            row.append(f'{route_renovate + route_prevent:.2f}')
            tree.insert('', 'end', values=row)
        
        total_row = ['总计']
        grand_renovate = 0
        grand_prevent = 0
        for year in range(2026, 2031):
            total_row.append(f'{total_renovate[year]:.2f}')
            total_row.append(f'{total_prevent[year]:.2f}')
            grand_renovate += total_renovate[year]
            grand_prevent += total_prevent[year]
        total_row.append(f'{grand_renovate:.2f}')
        total_row.append(f'{grand_prevent:.2f}')
        total_row.append(f'{grand_renovate + grand_prevent:.2f}')
        tree.insert('', 'end', values=total_row)

    def _generate_mileage_segment_table(self, df, county):
        """生成详细路段养护类型表"""
        from src.decay_calculator import get_segment_maintenance_plan
        
        result_df = get_segment_maintenance_plan(df, county)
        
        cols = ['路线编码', '路段起点', '路段终点', '路段长度(km)', '路面类型', '技术等级', '年份', '养护类型']
        self.mileage_segment_tree.delete(*self.mileage_segment_tree.get_children())
        self.mileage_segment_tree['columns'] = cols
        for col in cols:
            self.mileage_segment_tree.heading(col, text=col)
            if col == '路段长度(km)':
                self.mileage_segment_tree.column(col, width=70, anchor='center')
            elif col == '年份':
                self.mileage_segment_tree.column(col, width=60, anchor='center')
            else:
                self.mileage_segment_tree.column(col, width=80, anchor='center')
        
        if result_df.empty:
            self.mileage_segment_tree.insert('', 'end', values=('暂无数据',))
            self.mileage_segment_df = pd.DataFrame()
            return
        
        # 按路线编码和年份排序
        result_df = result_df.sort_values(by=['路线编码', '年份', '路段起点'])
        
        for _, row in result_df.iterrows():
            vals = [
                str(row.get('路线编码', '')),
                str(row.get('路段起点', '')),
                str(row.get('路段终点', '')),
                f"{row.get('路段长度(km)', 0):.3f}",
                str(row.get('路面类型', '')),
                str(row.get('技术等级', '')),
                str(row.get('年份', '')),
                str(row.get('养护类型', ''))
            ]
            self.mileage_segment_tree.insert('', 'end', values=vals)
        
        # 保存数据用于导出
        self.mileage_segment_df = result_df

    def _export_mileage_segment_excel(self):
        """导出详细路段养护类型表到Excel"""
        if not hasattr(self, 'mileage_segment_df') or self.mileage_segment_df.empty:
            messagebox.showwarning('提示', '没有可导出的数据')
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx'), ('CSV文件', '*.csv')]
        )
        if not file_path:
            return
        
        try:
            if file_path.endswith('.csv'):
                self.mileage_segment_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                self.mileage_segment_df.to_excel(file_path, index=False)
            messagebox.showinfo('成功', '导出成功！')
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_mileage_segment_to_clipboard(self):
        """复制详细路段养护类型表到剪贴板"""
        if not hasattr(self, 'mileage_segment_df') or self.mileage_segment_df.empty:
            messagebox.showwarning('提示', '没有可复制的数据')
            return
        
        try:
            self.mileage_segment_df.to_clipboard(index=False)
            messagebox.showinfo('成功', '已复制到剪贴板！')
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _generate_fund(self):
        """生成养护资金表（双模式）"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        all_df = pd.concat(self.data_cache.values(), ignore_index=True)
        if all_df.empty:
            return
        
        county = self._get_current_county()
        
        try:
            from src.decay_calculator import calculate_maintenance_plan, calculate_maintenance_plan_with_manual
            
            manual_plans = []
            if hasattr(self, 'manual_plans'):
                manual_plans = self.manual_plans
            
            # 生成自动养护触发资金表
            self._generate_fund_table(self.fund_tree_auto, all_df, county, mode='auto', manual_plans=[])
            
            # 生成手动养护规划资金表
            self._generate_fund_table(self.fund_tree_manual, all_df, county, mode='manual', manual_plans=manual_plans)
            
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')
    
    def _generate_fund_table(self, tree, df, county, mode='auto', manual_plans=None):
        """生成单个养护资金表格"""
        from src.decay_calculator import calculate_maintenance_plan, calculate_maintenance_plan_with_manual
        
        if manual_plans is None:
            manual_plans = []
        
        if mode == 'auto':
            plan = calculate_maintenance_plan(df, county)
        else:
            plan = calculate_maintenance_plan_with_manual(df, county, manual_plans)
        
        cols = ['路线', '2026改造', '2026预防', '2027改造', '2027预防', '2028改造', '2028预防', 
                '2029改造', '2029预防', '2030改造', '2030预防', '改造小计', '预防小计', '总计(万元)']
        tree.delete(*tree.get_children())
        tree['columns'] = cols
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=70, anchor='center')
        
        total_renovate = {y: 0 for y in range(2026, 2031)}
        total_prevent = {y: 0 for y in range(2026, 2031)}
        
        for route, data in plan.items():
            row = [route]
            route_renovate = 0
            route_prevent = 0
            for year in range(2026, 2031):
                ren = data['资金'][year].get('路面改造', 0)
                pre = data['资金'][year].get('预防性养护', 0)
                row.append(f'{ren/10000:.2f}' if ren else '-')
                row.append(f'{pre/10000:.2f}' if pre else '-')
                route_renovate += ren
                route_prevent += pre
                total_renovate[year] += ren
                total_prevent[year] += pre
            
            row.append(f'{route_renovate/10000:.2f}')
            row.append(f'{route_prevent/10000:.2f}')
            row.append(f'{(route_renovate + route_prevent)/10000:.2f}')
            tree.insert('', 'end', values=row)
        
        total_row = ['总计']
        grand_renovate = 0
        grand_prevent = 0
        for year in range(2026, 2031):
            total_row.append(f'{total_renovate[year]/10000:.2f}')
            total_row.append(f'{total_prevent[year]/10000:.2f}')
            grand_renovate += total_renovate[year]
            grand_prevent += total_prevent[year]
        total_row.append(f'{grand_renovate/10000:.2f}')
        total_row.append(f'{grand_prevent/10000:.2f}')
        total_row.append(f'{(grand_renovate + grand_prevent)/10000:.2f}')
        tree.insert('', 'end', values=total_row)

    def _generate_yearly_summary(self):
        """生成年度汇总表（双模式）"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        all_df = pd.concat(self.data_cache.values(), ignore_index=True)
        if all_df.empty:
            return
        
        county = self._get_current_county()
        
        try:
            from src.decay_calculator import get_yearly_summary, get_yearly_summary_with_manual
            
            manual_plans = []
            if hasattr(self, 'manual_plans'):
                manual_plans = self.manual_plans
            
            # 生成自动养护触发年度汇总表
            df_auto = get_yearly_summary(all_df, county)
            self._generate_yearly_summary_table(self.yearly_tree_auto, df_auto)
            
            # 生成手动养护规划年度汇总表
            df_manual = get_yearly_summary_with_manual(all_df, county, manual_plans)
            self._generate_yearly_summary_table(self.yearly_tree_manual, df_manual)
            
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')
    
    def _generate_yearly_summary_table(self, tree, df_result):
        """生成单个年度汇总表格"""
        tree.delete(*tree.get_children())
        tree['columns'] = list(df_result.columns)
        for col in df_result.columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')
        
        for _, row in df_result.iterrows():
            vals = [str(row.get(col, '')) for col in df_result.columns]
            tree.insert('', 'end', values=vals)

    def _update_insights(self, results: dict, county: str = None):
        """根据计算结果更新关键发现"""
        insights = []
        county_text = f"（{county}县）" if county else "（全部县）"
        
        # 统计
        pqi_rates = [v['PQI'] for v in results.values() if v['PQI']]
        if pqi_rates:
            avg_pqi_k = sum(pqi_rates) / len(pqi_rates)
            insights.append(f'• {county_text}平均PQI年衰减系数：{avg_pqi_k:.4f}')
        
        # 找最大和最小
        if pqi_rates:
            max_k = max(pqi_rates)
            min_k = min(pqi_rates)
            for key, v in results.items():
                if v['PQI'] == max_k:
                    insights.append(f'• PQI衰减最快：{key[0]}{key[1]} (k={max_k:.4f})')
                if v['PQI'] == min_k:
                    insights.append(f'• PQI衰减最慢：{key[0]}{key[1]} (k={min_k:.4f})')
        
        # PCI vs RQI 对比
        pci_rates = [v['PCI'] for v in results.values() if v['PCI']]
        rqi_rates = [v['RQI'] for v in results.values() if v['RQI']]
        if pci_rates and rqi_rates:
            avg_pci = sum(pci_rates) / len(pci_rates)
            avg_rqi = sum(rqi_rates) / len(rqi_rates)
            if avg_pci > avg_rqi * 2:
                insights.append(f'• PCI衰减显著快于RQI（破损快于平整度下降）')
        
        if insights:
            self.insight_text_var.set('\n'.join(insights))
        else:
            self.insight_text_var.set('数据不足以生成关键发现')

    # ════════════════════════════════════════
    # Tab 3: 分析图表
    # ════════════════════════════════════════
    def _build_analysis_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text='数据分析与图表生成', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='选择分析对象和图表类型，点击生成按钮', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 10))
        
        opt_card = ttk.LabelFrame(frame, text='分析选项', padding=10)
        opt_card.pack(fill='x', pady=5)
        
        row = ttk.Frame(opt_card)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text='分析县份：').pack(side='left')
        self.analysis_county_var = tk.StringVar(value='全部')
        self.analysis_county_cb = ttk.Combobox(row, textvariable=self.analysis_county_var,
                                                width=12, state='readonly')
        self.analysis_county_cb['values'] = ['全部']   # 加载数据后自动更新
        self.analysis_county_cb.pack(side='left', padx=(0, 20))
        
        ttk.Label(row, text='图表输出目录：').pack(side='left')
        self.chart_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.chart_dir_var, width=35).pack(side='left', padx=5)
        ttk.Button(row, text='浏览', command=self._browse_chart_dir, width=8).pack(side='left', padx=5)
        
        # 图表类型选择
        chart_card = ttk.LabelFrame(frame, text='图表类型', padding=10)
        chart_card.pack(fill='x', pady=10)
        
        self.chart_vars = {}
        chart_types = [
            '养护需求预测', '5年养护预测', 'PQI趋势折线图', '路线养护汇总',
            'PQI等级分布', '历年等级堆叠', '路面类型饼图', '技术等级分布',
            '多县横向柱状'
        ]
        
        for i, ctype in enumerate(chart_types):
            var = tk.BooleanVar(value=True)
            self.chart_vars[ctype] = var
            cb = ttk.Checkbutton(chart_card, text=ctype, variable=var)
            cb.grid(row=i//3, column=i%3, sticky='w', padx=10, pady=3)
        
        # 生成按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        
        ttk.Button(btn_frame, text='生成图表', command=self._generate_charts,
                  style='Primary.TButton').pack(side='left')
        
        # 日志输出
        log_card = ttk.LabelFrame(frame, text='生成日志', padding=5)
        log_card.pack(fill='both', expand=True, pady=(10, 0))
        
        self.analysis_log = tk.Text(log_card, height=12, font=('Consolas', 9))
        self.analysis_log.pack(fill='both', expand=True)
        
    def _browse_chart_dir(self):
        path = filedialog.askdirectory(title='选择图表输出目录')
        if path:
            self.chart_dir_var.set(path)

    def _generate_charts(self):
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return

        chart_dir = self.chart_dir_var.get().strip()
        if not chart_dir:
            chart_dir = os.path.join(BASE_DIR, 'output')
        
        os.makedirs(chart_dir, exist_ok=True)

        county = self.analysis_county_var.get()
        
        # 传递完整的数据字典给generate_all_charts
        self.analysis_log.delete('1.0', 'end')
        self.analysis_log.insert('end', f'正在生成图表...\n')
        self.update()

        try:
            results = generate_all_charts(self.data_cache, chart_dir, county if county != '全部' else None)
            
            count = 0
            for county_name, charts in results.items():
                for chart_name, chart_path in charts.items():
                    self.analysis_log.insert('end', f'{county_name}-{chart_name}: {chart_path}\n')
                    count += 1
            
            self.analysis_log.insert('end', f'\n共生成 {count} 个图表\n')
            messagebox.showinfo('完成', f'图表已保存到：{chart_dir}')
            
        except Exception as e:
            self.analysis_log.insert('end', f'错误：{str(e)}\n')
            messagebox.showerror('错误', str(e))

    # ════════════════════════════════════════
    # Tab 4: AI报告配置
    # ════════════════════════════════════════
    def _build_llm_tab(self, parent):
        print("DEBUG: _build_llm_tab 开始执行")
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        print(f"DEBUG: frame 创建成功: {frame}")
        
        ttk.Label(frame, text='AI大模型配置', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='配置大模型API以生成智能报告', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 15))

        # API配置
        print("DEBUG: 创建 api_card")
        api_card = ttk.LabelFrame(frame, text='API配置', padding=15)
        api_card.pack(fill='x')
        print(f"DEBUG: api_card 创建成功: {api_card}")

        fields = [
            ('API Key：', 'llm_key', '', True),
            ('接口地址(Base URL)：', 'llm_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1', False),
            ('模型名称：', 'llm_model', 'qwen-plus', False),
        ]

        for label, key, default, is_pwd in fields:
            row = ttk.Frame(api_card)
            row.pack(fill='x', pady=5)
            
            tk.Label(row, text=label, width=18).pack(side='left')
            
            var = tk.StringVar(value=default)
            self.llm_vars[key] = var
            
            if is_pwd:
                self.llm_key_entry = ttk.Entry(row, textvariable=var, width=50, show='*')
                self.llm_key_entry.pack(side='left')
            else:
                ttk.Entry(row, textvariable=var, width=50).pack(side='left')
            
            if key == 'llm_key':
                self.llm_key_toggle_btn = tk.Button(
                    row,
                    text='显示',
                    width=4,
                    command=self._toggle_pwd,
                    bg=THEME['accent'],
                    fg='white',
                    font=('Microsoft YaHei', 8)
                )
                self.llm_key_toggle_btn.pack(side='left', padx=5)

        # 加载已有配置
        llm_cfg = self.config.get('llm', {})
        if 'llm_key' in self.llm_vars:
            self.llm_vars['llm_key'].set(llm_cfg.get('api_key', ''))
            self.llm_vars['llm_url'].set(llm_cfg.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))
            self.llm_vars['llm_model'].set(llm_cfg.get('model', 'qwen-plus'))

        # 测试按钮和结果显示
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=15)
        
        tk.Button(btn_frame, text='🔗 测试连接', command=self._test_llm,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=12).pack(side='left')
        tk.Button(btn_frame, text='💾 保存配置', command=self._save_llm_config,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=12).pack(side='left', padx=10)
        
        # 测试结果显示（设置背景色与主题一致）
        self.llm_test_label = tk.Label(btn_frame, text='', font=('Microsoft YaHei', 9),
                                        bg=THEME['bg'])
        self.llm_test_label.pack(side='left', padx=20)

        # 报告设置
        title_card = ttk.LabelFrame(frame, text='报告设置', padding=15)
        title_card.pack(fill='x', pady=(15, 0))

        tk.Label(title_card, text='报告标题：').pack(anchor='w')
        self.report_title_var = tk.StringVar(value='公路养护需求分析报告')
        ttk.Entry(title_card, textvariable=self.report_title_var, width=50).pack(anchor='w', pady=5)

        tk.Label(title_card, text='报告摘要（AI参考）：').pack(anchor='w', pady=(10, 0))
        self.report_summary_text = tk.Text(title_card, height=10, width=70)
        self.report_summary_text.pack(anchor='w', pady=5)
        
        # 自动填充摘要按钮（放在报告设置框内）
        tk.Button(title_card, text='📝 摘要自动生成（基于已分析数据）', 
                   command=self._auto_fill_summary,
                   bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9),
                   padx=10, pady=3, cursor='hand2', width=25).pack(anchor='w', pady=5)

    def _toggle_pwd(self):
        """切换 API Key 的显示/隐藏状态"""
        if not self.llm_key_entry:
            return

        self._llm_key_visible = not self._llm_key_visible
        self.llm_key_entry.configure(show='' if self._llm_key_visible else '*')
        if self.llm_key_toggle_btn:
            self.llm_key_toggle_btn.configure(text='隐藏' if self._llm_key_visible else '显示')

    def _get_all_data_df(self):
        """获取去重后的全量数据，避免把“全部”与各县数据重复拼接。"""
        if not self.data_cache:
            return pd.DataFrame()

        all_df = self.data_cache.get('全部')
        if all_df is not None and not all_df.empty:
            return all_df.copy()

        frames = [
            df for county, df in self.data_cache.items()
            if county != '全部' and df is not None and not df.empty
        ]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _get_summary_source(self):
        """优先使用当前分析县份，其次使用报告县份，最后回退到全部数据。"""
        county = None

        if hasattr(self, 'model_county_var'):
            model_county = self.model_county_var.get().strip()
            if model_county and model_county != '全部':
                county = model_county

        if county is None and hasattr(self, 'report_county_var'):
            report_county = self.report_county_var.get().strip()
            if report_county and report_county != '全部':
                county = report_county

        if county and county in self.data_cache:
            df = self.data_cache[county].copy()
            county_label = county
        else:
            df = self._get_all_data_df()
            county_label = '全部'

        return county_label, df

    def _test_llm(self):
        api_key = self.llm_vars.get('llm_key', tk.StringVar()).get()
        base_url = self.llm_vars.get('llm_url', tk.StringVar()).get()
        model = self.llm_vars.get('llm_model', tk.StringVar()).get()

        if not api_key:
            self.llm_test_label.config(text='请输入API Key', foreground=THEME['danger'])
            return

        self.llm_test_label.config(text='正在测试...', foreground=THEME['text_light'])
        self.update()

        try:
            import openai
            # 检查openai版本，1.0+使用OpenAI类
            if hasattr(openai, 'OpenAI'):
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
            else:
                # 旧版本兼容
                openai.api_key = api_key
                openai.api_base = base_url
                client = openai
            
            response = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': '你好'}],
                max_tokens=20
            )
            
            self.llm_test_label.config(text='连接成功！', foreground=THEME['success'])
            
        except Exception as e:
            self.llm_test_label.config(text=f'连接失败：{str(e)}', foreground=THEME['danger'])

    def _auto_fill_summary(self):
        """根据当前加载的数据自动填充报告摘要"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        try:
            county, df = self._get_summary_source()
            if df.empty:
                messagebox.showwarning('提示', '当前没有可用于生成摘要的数据')
                return
            
            # 获取数据基本信息
            years = sorted(df['年份'].unique()) if '年份' in df.columns else []
            latest_year = max(years) if years else None
            
            # 获取衰减率标定结果
            from src.decay_calculator import calculate_decay_rates, get_yearly_summary
            decay_rates = calculate_decay_rates(df, county if county != '全部' else None)
            
            # 获取年度养护汇总
            yearly_summary = get_yearly_summary(df, county if county != '全部' else None)
            
            # 计算基本统计
            total_length = df[df['年份'] == latest_year]['路段长度km'].sum() if latest_year and '路段长度km' in df.columns else 0
            total_segments = len(df[df['年份'] == latest_year]) if latest_year else 0
            
            # 构建摘要文本
            summary_parts = []
            
            # 1. 模型介绍
            summary_parts.append("【模型介绍】")
            summary_parts.append("本报告采用指数衰减模型预测PQI、PCI、RQI未来5年的变化趋势。")
            summary_parts.append("模型公式：PQI_t = PQI_0 × exp(-k × t)，其中k为年衰减系数，t为年数。")
            summary_parts.append("衰减系数基于2021-2025年实测数据标定，剔除养护干预路段后取中位数。")
            summary_parts.append("")
            
            # 2. 参数标定结果
            summary_parts.append("【参数标定结果】")
            if decay_rates:
                summary_parts.append("按路面类型×技术等级的PQI年衰减系数(k)：")
                for (ptype, grade), vals in decay_rates.items():
                    k_val = vals.get('PQI', '-')
                    if k_val != '-':
                        summary_parts.append(f"  • {ptype}-{grade}: k={k_val}")
            else:
                summary_parts.append("使用默认衰减系数（未检测到足够的历史数据用于标定）。")
            summary_parts.append("")
            
            # 3. 数据概况
            summary_parts.append("【数据概况】")
            summary_parts.append(f"分析县份：{county}")
            summary_parts.append(f"数据年份：{'、'.join(str(y) for y in years)}年")
            if latest_year:
                summary_parts.append(f"{latest_year}年检测路段：{total_segments}段，总里程{total_length:.1f}km")
            summary_parts.append("")
            
            # 4. 养护需求预测
            summary_parts.append("【养护需求预测（2026-2030）】")
            if not yearly_summary.empty:
                total_fund = yearly_summary[yearly_summary['年份']=='总计']['资金总计(万元)'].values
                if len(total_fund) > 0:
                    summary_parts.append(f"未来5年预计养护资金总需求：{total_fund[0]:.1f}万元")
                
                # 各年资金分布
                summary_parts.append("各年度资金分配：")
                for _, row in yearly_summary.iterrows():
                    if row['年份'] != '总计':
                        fund_total = row.get('资金总计(万元)', 0)
                        summary_parts.append(f"  • {int(row['年份'])}年：{fund_total:.1f}万元")
            summary_parts.append("")
            
            # 5. 养护触发条件
            summary_parts.append("【养护触发条件】")
            summary_parts.append("路面改造：")
            summary_parts.append("  • 水泥路面一级公路：PCI<80 或 PQI<80")
            summary_parts.append("  • 水泥路面二级及以下：PCI<75 或 PQI<75")
            summary_parts.append("  • 沥青路面一级公路：PCI<80 或 RQI<80 或 PQI<80")
            summary_parts.append("  • 沥青路面二级及以下：PCI<75 或 RQI<75 或 PQI<75")
            summary_parts.append("预防养护：不满足路面改造条件，且指标处于中等水平的路段")
            summary_parts.append("")
            
            # 6. 主要发现（待AI生成时补充）
            summary_parts.append("【主要发现与建议】")
            summary_parts.append("（此处内容由AI根据上述数据自动生成，包括：）")
            summary_parts.append("- 路面技术状况总体评价")
            summary_parts.append("- 历年变化趋势分析")
            summary_parts.append("- 重点养护路段识别")
            summary_parts.append("- 资金分配优化建议")
            
            # 填充到文本框
            self.report_summary_text.delete('1.0', 'end')
            self.report_summary_text.insert('1.0', '\n'.join(summary_parts))

            if hasattr(self, 'report_county_var'):
                self.report_county_var.set(county)
            
            messagebox.showinfo('成功', '报告摘要已自动填充\n您可以根据需要修改后生成报告')
            
        except Exception as e:
            messagebox.showerror('错误', f'填充摘要失败：{str(e)}')

    def _save_llm_config(self):
        config = self._load_config()
        config['llm'] = {
            'api_key': self.llm_vars.get('llm_key', tk.StringVar()).get(),
            'base_url': self.llm_vars.get('llm_url', tk.StringVar()).get(),
            'model': self.llm_vars.get('llm_model', tk.StringVar()).get(),
        }
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        messagebox.showinfo('成功', '配置已保存')

    def _save_callback_config(self):
        """保存养护回调参数配置"""
        if not set_maintenance_callback:
            messagebox.showerror('错误', '无法保存回调参数')
            return
        
        try:
            config = {}
            for key, var in self.callback_vars.items():
                parts = key.split('_')
                maint_type = parts[0]
                ptype = parts[1]
                idx = parts[2]
                
                if maint_type not in config:
                    config[maint_type] = {}
                if ptype not in config[maint_type]:
                    config[maint_type][ptype] = {}
                
                config[maint_type][ptype][idx] = var.get()
            
            set_maintenance_callback(config)
            
            # 同时保存到配置文件
            cfg = self._load_config()
            cfg['maintenance_callback'] = config
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo('成功', '养护回调参数已保存')
            
        except Exception as e:
            messagebox.showerror('错误', f'保存失败：{str(e)}')

    def _reset_callback_config(self):
        """重置养护回调参数为默认值"""
        if not set_maintenance_callback:
            messagebox.showerror('错误', '无法重置回调参数')
            return
        
        try:
            set_maintenance_callback(None)  # None表示重置为默认值
            
            # 更新界面显示
            default_callback = {
                '路面改造': {
                    '沥青路面': {'PQI': 92, 'PCI': 92, 'RQI': 93},
                    '水泥路面': {'PQI': 88, 'PCI': 88, 'RQI': 90},
                },
                '预防性养护': {
                    '沥青路面': {'PQI': 89, 'PCI': 89, 'RQI': 91},
                    '水泥路面': {'PQI': 86, 'PCI': 86, 'RQI': 88},
                },
            }
            
            for key, var in self.callback_vars.items():
                parts = key.split('_')
                maint_type = parts[0]
                ptype = parts[1]
                idx = parts[2]
                var.set(default_callback[maint_type][ptype][idx])
            
            # 清除配置文件中的设置
            cfg = self._load_config()
            cfg.pop('maintenance_callback', None)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo('成功', '已恢复默认参数')
            
        except Exception as e:
            messagebox.showerror('错误', f'重置失败：{str(e)}')

    # ── 养护触发模型参数管理 ──
    
    def _on_trigger_toggle(self):
        """启用/禁用养护触发模型时，灰化/恢复参数输入框和年度配置勾选框"""
        enabled = self.trigger_enabled_var.get()
        state = 'normal' if enabled else 'disabled'
        for child in self.trigger_params_frame.winfo_children():
            self._set_children_state(child, state)
        
        # 同时控制年度配置勾选框的状态
        for year_var in self.yearly_trigger_vars.values():
            chk = year_var.get_widget() if hasattr(year_var, 'get_widget') else None
            if chk:
                chk.config(state=state)
    
    def _set_children_state(self, widget, state):
        """递归设置子组件的state"""
        try:
            if isinstance(widget, (ttk.Entry,)):
                widget.configure(state=state)
        except:
            pass
        for child in widget.winfo_children():
            if isinstance(child, tk.Checkbutton):
                child.configure(state=state)
            elif isinstance(child, ttk.Entry):
                child.configure(state=state)
            else:
                self._set_children_state(child, state)
    
    def _collect_trigger_config(self):
        """从UI收集触发模型参数，返回配置字典"""
        config = {
            '启用': self.trigger_enabled_var.get(),
            '年度配置': {},
            '路面改造': {}, 
            '预防性养护': {},
        }
        
        # 年度配置（按年份设置是否启用养护触发）
        for year in range(2026, 2031):
            config['年度配置'][year] = self.yearly_trigger_vars[year].get()
        
        # 路面改造参数
        for ptype in ['沥青路面', '水泥路面']:
            config['路面改造'][ptype] = {}
            for grade in ['一级公路', '二级及以下']:
                prefix = f'改造_{ptype}_{grade}'
                config['路面改造'][ptype][grade] = {
                    'PCI': self.trigger_vars[f'{prefix}_PCI'].get(),
                    'PCI启用': self.trigger_vars[f'{prefix}_PCI启用'].get(),
                    'PQI': self.trigger_vars[f'{prefix}_PQI'].get(),
                    'PQI启用': self.trigger_vars[f'{prefix}_PQI启用'].get(),
                    'RQI': self.trigger_vars[f'{prefix}_RQI'].get(),
                    'RQI启用': self.trigger_vars[f'{prefix}_RQI启用'].get(),
                }
        
        # 预防养护参数
        for ptype in ['沥青路面', '水泥路面']:
            config['预防性养护'][ptype] = {}
            for grade in ['一级公路', '二级及以下']:
                prefix = f'预防_{ptype}_{grade}'
                config['预防性养护'][ptype][grade] = {
                    'PCI低': self.trigger_vars[f'{prefix}_PCI低'].get(),
                    'PCI高': self.trigger_vars[f'{prefix}_PCI高'].get(),
                    'PCI启用': self.trigger_vars[f'{prefix}_PCI启用'].get(),
                    'RQI低': self.trigger_vars[f'{prefix}_RQI低'].get(),
                    'RQI高': self.trigger_vars[f'{prefix}_RQI高'].get(),
                    'RQI启用': self.trigger_vars[f'{prefix}_RQI启用'].get(),
                    'PQI': self.trigger_vars[f'{prefix}_PQI'].get(),
                    'PQI启用': self.trigger_vars[f'{prefix}_PQI启用'].get(),
                }
        
        return config
    
    def _save_trigger_config(self):
        """保存养护触发模型参数"""
        if not set_trigger_model:
            messagebox.showerror('错误', '无法保存触发参数')
            return
        
        try:
            config = self._collect_trigger_config()
            set_trigger_model(config)
            # 如果已有预测数据，询问是否重新生成
            if self.data_cache and self.pred_tree.get_children() and \
               self.pred_tree.item(self.pred_tree.get_children()[0])['values'] and \
               self.pred_tree.item(self.pred_tree.get_children()[0])['values'][0] != '请先加载数据并点击生成按钮':
                if messagebox.askyesno('成功', '养护触发模型参数已保存，是否重新生成预测？'):
                    self._generate_prediction()
            else:
                messagebox.showinfo('成功', '养护触发模型参数已保存')
        except Exception as e:
            messagebox.showerror('错误', f'保存失败：{str(e)}')
    
    def _reset_trigger_config(self):
        """重置养护触发模型参数为默认值"""
        if not set_trigger_model:
            messagebox.showerror('错误', '无法重置触发参数')
            return
        
        try:
            set_trigger_model(None)  # 恢复默认
            default = get_trigger_model()
            
            # 更新启用状态
            self.trigger_enabled_var.set(default.get('启用', True))
            
            # 更新路面改造参数
            for ptype in ['沥青路面', '水泥路面']:
                for grade in ['一级公路', '二级及以下']:
                    cfg = default.get('路面改造', {}).get(ptype, {}).get(grade, {})
                    prefix = f'改造_{ptype}_{grade}'
                    self.trigger_vars[f'{prefix}_PCI'].set(cfg.get('PCI', 80))
                    self.trigger_vars[f'{prefix}_PCI启用'].set(cfg.get('PCI启用', True))
                    self.trigger_vars[f'{prefix}_PQI'].set(cfg.get('PQI', 80))
                    self.trigger_vars[f'{prefix}_PQI启用'].set(cfg.get('PQI启用', True))
                    self.trigger_vars[f'{prefix}_RQI'].set(cfg.get('RQI', 80))
                    self.trigger_vars[f'{prefix}_RQI启用'].set(cfg.get('RQI启用', False))
            
            # 更新预防养护参数
            default_prev = {
                ('沥青路面', '一级公路'): (80, 90, 80, 90, 80),
                ('沥青路面', '二级及以下'): (78, 85, 78, 85, 75),
                ('水泥路面', '一级公路'): (80, 90, 60, 85, 80),
                ('水泥路面', '二级及以下'): (78, 85, 60, 85, 75),
            }
            for (ptype, grade), (pci_lo, pci_hi, rqi_lo, rqi_hi, pqi) in default_prev.items():
                prefix = f'预防_{ptype}_{grade}'
                self.trigger_vars[f'{prefix}_PCI低'].set(pci_lo)
                self.trigger_vars[f'{prefix}_PCI高'].set(pci_hi)
                self.trigger_vars[f'{prefix}_RQI低'].set(rqi_lo)
                self.trigger_vars[f'{prefix}_RQI高'].set(rqi_hi)
                self.trigger_vars[f'{prefix}_PQI'].set(pqi)
            
            self._on_trigger_toggle()
            messagebox.showinfo('成功', '已恢复默认触发参数')
            
        except Exception as e:
            messagebox.showerror('错误', f'重置失败：{str(e)}')

    # ════════════════════════════════════════
    # 导出Excel和复制到剪贴板功能
    # ════════════════════════════════════════
    def _export_mileage_excel(self, mode='auto'):
        """导出养护里程表到Excel"""
        tree = self.mileage_tree_auto if mode == 'auto' else self.mileage_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成养护里程表')
            return
        
        try:
            import pandas as pd
            
            cols = tree['columns']
            rows = []
            for item in tree.get_children():
                rows.append(tree.item(item, 'values'))
            
            if not rows:
                messagebox.showwarning('提示', '没有数据可导出')
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile=f'养护里程表_{"自动触发" if mode == "auto" else "手动规划"}.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_mileage_to_clipboard(self, mode='auto'):
        """复制养护里程表到剪贴板"""
        tree = self.mileage_tree_auto if mode == 'auto' else self.mileage_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成养护里程表')
            return
        
        try:
            cols = tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in tree.get_children():
                row = tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _export_fund_excel(self, mode='auto'):
        """导出养护资金表到Excel"""
        tree = self.fund_tree_auto if mode == 'auto' else self.fund_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成养护资金表')
            return
        
        try:
            import pandas as pd
            
            cols = tree['columns']
            rows = []
            for item in tree.get_children():
                rows.append(tree.item(item, 'values'))
            
            if not rows:
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile=f'养护资金表_{"自动触发" if mode == "auto" else "手动规划"}.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_fund_to_clipboard(self, mode='auto'):
        """复制养护资金表到剪贴板"""
        tree = self.fund_tree_auto if mode == 'auto' else self.fund_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成养护资金表')
            return
        
        try:
            cols = tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in tree.get_children():
                row = tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _export_yearly_excel(self, mode='auto'):
        """导出年度汇总表到Excel"""
        tree = self.yearly_tree_auto if mode == 'auto' else self.yearly_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成年度汇总表')
            return
        
        try:
            import pandas as pd
            
            cols = tree['columns']
            rows = []
            for item in tree.get_children():
                rows.append(tree.item(item, 'values'))
            
            if not rows:
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile=f'年度汇总表_{"自动触发" if mode == "auto" else "手动规划"}.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_yearly_to_clipboard(self, mode='auto'):
        """复制年度汇总表到剪贴板"""
        tree = self.yearly_tree_auto if mode == 'auto' else self.yearly_tree_manual
        if not tree.get_children():
            messagebox.showwarning('提示', '请先生成年度汇总表')
            return
        
        try:
            cols = tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in tree.get_children():
                row = tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _export_decay_excel(self):
        """导出衰减率标定表到Excel"""
        if not self.decay_tree.get_children():
            messagebox.showwarning('提示', '请先计算衰减率')
            return
        
        try:
            import pandas as pd
            
            cols = self.decay_tree['columns']
            rows = []
            for item in self.decay_tree.get_children():
                rows.append(self.decay_tree.item(item, 'values'))
            
            if not rows:
                messagebox.showwarning('提示', '没有数据可导出')
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile='衰减率标定表.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_decay_to_clipboard(self):
        """复制衰减率标定表到剪贴板"""
        if not self.decay_tree.get_children():
            messagebox.showwarning('提示', '请先计算衰减率')
            return
        
        try:
            cols = self.decay_tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in self.decay_tree.get_children():
                row = self.decay_tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _export_prediction_excel(self):
        """导出5年PQI预测表到Excel"""
        if not self.pred_tree.get_children():
            messagebox.showwarning('提示', '请先生成5年预测表')
            return
        
        try:
            import pandas as pd
            
            cols = self.pred_tree['columns']
            rows = []
            for item in self.pred_tree.get_children():
                rows.append(self.pred_tree.item(item, 'values'))
            
            if not rows:
                messagebox.showwarning('提示', '没有数据可导出')
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile='5年PQI预测表.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_prediction_to_clipboard(self):
        """复制5年PQI预测表到剪贴板"""
        if not self.pred_tree.get_children():
            messagebox.showwarning('提示', '请先生成5年预测表')
            return
        
        try:
            cols = self.pred_tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in self.pred_tree.get_children():
                row = self.pred_tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    # ════════════════════════════════════════
    # Tab 5: 生成报告
    # ════════════════════════════════════════
    def _build_report_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text='生成Word报告', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='基于筛选数据生成完整的Word分析报告', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 15))

        # 报告选项
        opt_card = ttk.LabelFrame(frame, text='报告选项', padding=15)
        opt_card.pack(fill='x')

        row = ttk.Frame(opt_card)
        row.pack(fill='x', pady=5)
        
        tk.Label(row, text='报告县份：').pack(side='left')
        self.report_county_var = tk.StringVar(value='全部')
        self.report_county_cb = ttk.Combobox(row, textvariable=self.report_county_var,
                                             width=12, state='readonly')
        self.report_county_cb['values'] = ['全部']   # 加载数据后自动更新
        self.report_county_cb.pack(side='left', padx=(0, 20))

        tk.Label(row, text='输出文件：').pack(side='left')
        self.report_path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.report_path_var, width=30).pack(side='left', padx=5)
        ttk.Button(row, text='浏览', command=self._browse_report_path, width=8).pack(side='left')

        # 生成按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=20)
        
        ttk.Button(btn_frame, text='生成报告', command=self._generate_report,
                   style='Primary.TButton').pack(side='left')

        # 报告预览
        preview_card = ttk.LabelFrame(frame, text='报告预览', padding=10)
        preview_card.pack(fill='both', expand=True)

        self.report_preview_text = tk.Text(preview_card, height=20, font=('Microsoft YaHei', 10))
        self.report_preview_text.pack(fill='both', expand=True)

    def _browse_report_path(self):
        path = filedialog.asksaveasfilename(
            title='保存报告',
            defaultextension='.docx',
            filetypes=[('Word文档', '*.docx')],
            initialfile=f'公路养护需求分析报告.docx'
        )
        if path:
            self.report_path_var.set(path)

    def _generate_report(self):
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return

        report_path = self.report_path_var.get().strip()
        if not report_path:
            report_path = os.path.join(BASE_DIR, 'output', '公路养护需求分析报告.docx')

        county = self.report_county_var.get()
        if county != '全部':
            df = self.data_cache.get(county, pd.DataFrame())
            if df.empty:
                df = self._get_all_data_df()
                df = df[df.get('县份', '') == county]
        else:
            df = self._get_all_data_df()

        title = self.report_title_var.get()
        summary = self.report_summary_text.get('1.0', 'end').strip()

        api_key = self.llm_vars.get('llm_key', tk.StringVar()).get()
        base_url = self.llm_vars.get('llm_url', tk.StringVar()).get()
        model = self.llm_vars.get('llm_model', tk.StringVar()).get()

        # 收集表格数据
        table_data = {}
        
        # 年度趋势数据
        if hasattr(self, 'decay_tree') and self.decay_tree.get_children():
            trend_data = []
            for item in self.decay_tree.get_children():
                values = self.decay_tree.item(item)['values']
                if values and len(values) > 1:
                    trend_data.append(values)
            if trend_data:
                table_data['yearly_trend'] = pd.DataFrame(trend_data)
        
        # 养护里程数据
        if hasattr(self, 'mileage_tree') and self.mileage_tree.get_children():
            maint_data = []
            for item in self.mileage_tree.get_children():
                values = self.mileage_tree.item(item)['values']
                if values:
                    maint_data.append(values)
            if maint_data:
                table_data['maintenance'] = pd.DataFrame(maint_data)
        
        # 预测数据
        if hasattr(self, 'pred_tree') and self.pred_tree.get_children():
            pred_data = []
            for item in self.pred_tree.get_children():
                values = self.pred_tree.item(item)['values']
                if values:
                    pred_data.append(values)
            if pred_data:
                table_data['prediction'] = pd.DataFrame(pred_data)
        
        # 等级分布数据
        if not df.empty:
            if 'PQI' in df.columns:
                def get_grade(pqi):
                    if pd.isna(pqi):
                        return '未知'
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
                
                df['PQI等级'] = df['PQI'].apply(get_grade)
                grade_dist = df.groupby('PQI等级')['路段长度km'].sum().reset_index()
                grade_dist.columns = ['等级', '里程(km)']
                table_data['grade_dist'] = grade_dist

        # 收集图表路径
        chart_paths = {}
        output_dir = os.path.join(BASE_DIR, 'output')
        
        # 检查是否有生成的图表
        chart_files = {
            'trend': f'{county}_年度趋势.png',
            'grade_dist': f'{county}_PQI等级分布.png',
            'grade_stacked': f'{county}_历年等级堆叠.png',
            'pavement_type': f'{county}_路面类型.png',
            'tech_grade': f'{county}_技术等级.png',
            'maintenance': f'{county}_养护需求.png',
            'prediction': f'{county}_5年预测.png'
        }
        
        for key, filename in chart_files.items():
            filepath = os.path.join(output_dir, 'charts', filename)
            if os.path.exists(filepath):
                chart_paths[key] = filepath

        self.status_var.set('正在生成报告...')
        self.progressbar.start(10)
        self.update()

        try:
            result = generate_word_report(
                df, report_path, title=title, summary=summary,
                api_key=api_key, base_url=base_url, model=model,
                table_data=table_data, chart_paths=chart_paths,
                progress_callback=lambda msg: self.status_var.set(msg)
            )

            self.report_preview_text.delete('1.0', 'end')
            self.report_preview_text.insert('1.0', result)

            messagebox.showinfo('成功', f'报告已保存到：{report_path}')
            
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')

        self.progressbar.stop()
        self.status_var.set('就绪')

    def _export_segment_plan_excel(self, df):
        """导出路段级养护计划到Excel"""
        if df.empty:
            messagebox.showinfo('提示', '没有可导出的数据')
            return
        
        path = filedialog.asksaveasfilename(
            title='导出路段级养护计划',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')],
            initialfile='路段级养护计划.xlsx'
        )
        if path:
            try:
                df.to_excel(path, index=False)
                messagebox.showinfo('成功', f'已导出到：{path}')
            except Exception as e:
                messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_segment_plan_to_clipboard(self, df):
        """复制路段级养护计划到剪贴板"""
        if df.empty:
            messagebox.showinfo('提示', '没有可复制的数据')
            return
        
        try:
            # 将DataFrame转换为剪贴板格式
            clipboard_content = df.to_csv(sep='\t', index=False)
            self.clipboard_clear()
            self.clipboard_append(clipboard_content)
            messagebox.showinfo('成功', '已复制到剪贴板')
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')

    def _export_good_road_excel(self, df):
        """导出PQI优良路率预测到Excel"""
        if df.empty:
            messagebox.showinfo('提示', '没有可导出的数据')
            return
        
        path = filedialog.asksaveasfilename(
            title='导出PQI优良路率预测',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')],
            initialfile='PQI优良路率预测.xlsx'
        )
        if path:
            try:
                df.to_excel(path, index=False)
                messagebox.showinfo('成功', f'已导出到：{path}')
            except Exception as e:
                messagebox.showerror('错误', f'导出失败：{str(e)}')

    def _copy_good_road_to_clipboard(self, df):
        """复制PQI优良路率预测到剪贴板"""
        if df.empty:
            messagebox.showinfo('提示', '没有可复制的数据')
            return
        
        try:
            # 将DataFrame转换为剪贴板格式
            clipboard_content = df.to_csv(sep='\t', index=False)
            self.clipboard_clear()
            self.clipboard_append(clipboard_content)
            messagebox.showinfo('成功', '已复制到剪贴板')
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')


    # ════════════════════════════════════════
    # PQI-Proj. IMP 手动养护规划方法
    # ════════════════════════════════════════
    def _generate_pqi_proj(self):
        """生成PQI-Proj. IMP预测表（手动养护规划）"""
        if not self.data_cache:
            messagebox.showwarning('提示', '请先加载数据')
            return
        
        try:
            county = self.filter_county_var.get()
            
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)
            if county != '全部' and '县份' in all_df.columns:
                df = all_df[all_df['县份'] == county].copy()
            else:
                df = all_df.copy()
            
            from src.decay_calculator import predict_5year_pqi_with_manual_plan
            
            result_df = predict_5year_pqi_with_manual_plan(df, county, self.manual_plans)
            
            if result_df.empty:
                self.pqi_proj_tree.delete(*self.pqi_proj_tree.get_children())
                self.pqi_proj_tree.insert('', 'end', values=('没有数据',))
                return
            
            self.pqi_proj_tree.delete(*self.pqi_proj_tree.get_children())
            self.pqi_proj_tree['columns'] = list(result_df.columns)
            for col in result_df.columns:
                self.pqi_proj_tree.heading(col, text=col)
                col_width = len(str(col)) * 8 + 10
                for _, row in result_df.iterrows():
                    cell_text = str(row.get(col, ''))
                    cn_chars = sum(1 for c in cell_text if '\u4e00' <= c <= '\u9fff')
                    en_chars = len(cell_text) - cn_chars
                    cell_width = cn_chars * 10 + en_chars * 6 + 10
                    col_width = max(col_width, cell_width)
                col_width = min(col_width, 100)
                self.pqi_proj_tree.column(col, width=col_width, minwidth=40, anchor='center', stretch=False)
            
            for _, row in result_df.iterrows():
                values = [str(row.get(col, '')) for col in result_df.columns]
                self.pqi_proj_tree.insert('', 'end', values=values)
            
            self._update_pqi_proj_good_road_rate()
            
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{str(e)}')
    
    def _update_pqi_proj_good_road_rate(self):
        """更新PQI优良路率"""
        if not self.data_cache:
            return
        
        try:
            county = self.filter_county_var.get()
            df = self.filtered_df
            
            from src.decay_calculator import calculate_good_road_rate_with_manual_plan
            
            good_road_df = calculate_good_road_rate_with_manual_plan(df, county, self.manual_plans)
            
            self.pqi_proj_good_road_tree.delete(*self.pqi_proj_good_road_tree.get_children())
            
            if good_road_df.empty:
                self.pqi_proj_good_road_tree.insert('', 'end', values=('没有数据',))
                return
            
            cols = ['年份', '道路类型', 'PQI≥80的路段里程(km)', '总里程(km)', '优良路率(%)']
            self.pqi_proj_good_road_tree['columns'] = cols
            for col in cols:
                self.pqi_proj_good_road_tree.heading(col, text=col)
                col_width = len(str(col)) * 8 + 10
                for _, row in good_road_df.iterrows():
                    cell_text = str(row.get(col, ''))
                    cn_chars = sum(1 for c in cell_text if '\u4e00' <= c <= '\u9fff')
                    en_chars = len(cell_text) - cn_chars
                    cell_width = cn_chars * 10 + en_chars * 6 + 10
                    col_width = max(col_width, cell_width)
                col_width = min(col_width, 150)
                self.pqi_proj_good_road_tree.column(col, width=col_width, minwidth=40, anchor='center', stretch=False)
            
            for _, row in good_road_df.iterrows():
                self.pqi_proj_good_road_tree.insert('', 'end', values=(
                    row['年份'],
                    row['道路类型'],
                    row['PQI≥80的路段里程(km)'],
                    row['总里程(km)'],
                    row['优良路率(%)']
                ))
            
        except Exception as e:
            messagebox.showerror('错误', f'计算优良路率失败：{str(e)}')
    
    def _add_manual_maintenance(self):
        """添加或修改手动养护规划"""
        route = self.manual_route_var.get().strip()
        start = self.manual_start_var.get().strip()
        end = self.manual_end_var.get().strip()
        year = self.manual_year_var.get().strip()
        maint_type = self.manual_maint_type_var.get()
        
        if not route:
            messagebox.showwarning('提示', '请输入路线编码')
            return
        
        if year not in [str(y) for y in range(2026, 2031)]:
            messagebox.showwarning('提示', '年份必须在2026-2030之间')
            return
        
        plan = {
            'route': route,
            'start': start,
            'end': end,
            'year': int(year),
            'maint_type': maint_type
        }
        
        selected_items = self.manual_plan_tree.selection()
        if selected_items:
            selected_item = selected_items[0]
            for i, existing_plan in enumerate(self.manual_plans):
                if existing_plan == self._get_plan_from_tree_item(selected_item):
                    self.manual_plans[i] = plan
                    self.manual_plan_tree.item(selected_item, values=(route, start if start else '全部', end if end else '全部', year, maint_type))
                    return
        else:
            if plan not in self.manual_plans:
                self.manual_plans.append(plan)
                self.manual_plan_tree.insert('', 'end', values=(route, start if start else '全部', end if end else '全部', year, maint_type))
            else:
                messagebox.showwarning('提示', '该养护规划已存在')
    
    def _get_plan_from_tree_item(self, item_id):
        """从Treeview项获取规划字典"""
        values = self.manual_plan_tree.item(item_id, 'values')
        if values:
            return {
                'route': values[0],
                'start': values[1] if values[1] != '全部' else '',
                'end': values[2] if values[2] != '全部' else '',
                'year': int(values[3]),
                'maint_type': values[4]
            }
        return None
    
    def _on_manual_plan_select(self, event):
        """选择手动养护规划时自动填充表单"""
        selected_items = self.manual_plan_tree.selection()
        if selected_items:
            selected_item = selected_items[0]
            values = self.manual_plan_tree.item(selected_item, 'values')
            if values:
                self.manual_route_var.set(values[0])
                self.manual_start_var.set(values[1] if values[1] != '全部' else '')
                self.manual_end_var.set(values[2] if values[2] != '全部' else '')
                self.manual_year_var.set(values[3])
                self.manual_maint_type_var.set(values[4])
    
    def _clear_manual_maintenance(self):
        """清空手动养护规划"""
        self.manual_plans.clear()
        self.manual_plan_tree.delete(*self.manual_plan_tree.get_children())
        messagebox.showinfo('成功', '已清空所有养护规划')
    
    def _export_pqi_proj_excel(self):
        """导出PQI-Proj. IMP预测表到Excel"""
        if not self.pqi_proj_tree.get_children():
            messagebox.showwarning('提示', '请先生成预测表')
            return
        
        try:
            import pandas as pd
            
            cols = self.pqi_proj_tree['columns']
            rows = []
            for item in self.pqi_proj_tree.get_children():
                rows.append(self.pqi_proj_tree.item(item, 'values'))
            
            if not rows:
                messagebox.showwarning('提示', '没有数据可导出')
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile='PQI-Proj_IMP预测表.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')
    
    def _copy_pqi_proj_to_clipboard(self):
        """复制PQI-Proj. IMP预测表到剪贴板"""
        if not self.pqi_proj_tree.get_children():
            messagebox.showwarning('提示', '请先生成预测表')
            return
        
        try:
            cols = self.pqi_proj_tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in self.pqi_proj_tree.get_children():
                row = self.pqi_proj_tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')
    
    def _export_pqi_proj_good_road_excel(self):
        """导出PQI-Proj. IMP优良路率到Excel"""
        if not self.pqi_proj_good_road_tree.get_children():
            messagebox.showwarning('提示', '请先生成预测表')
            return
        
        try:
            import pandas as pd
            
            cols = self.pqi_proj_good_road_tree['columns']
            rows = []
            for item in self.pqi_proj_good_road_tree.get_children():
                rows.append(self.pqi_proj_good_road_tree.item(item, 'values'))
            
            if not rows:
                messagebox.showwarning('提示', '没有数据可导出')
                return
            
            df = pd.DataFrame(rows, columns=cols)
            
            file_path = filedialog.asksaveasfilename(
                title='保存Excel文件',
                defaultextension='.xlsx',
                filetypes=[('Excel文件', '*.xlsx')],
                initialfile='PQI-Proj_IMP优良路率.xlsx'
            )
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo('成功', f'已导出到：{file_path}')
                
        except Exception as e:
            messagebox.showerror('错误', f'导出失败：{str(e)}')
    
    def _copy_pqi_proj_good_road_to_clipboard(self):
        """复制PQI-Proj. IMP优良路率到剪贴板"""
        if not self.pqi_proj_good_road_tree.get_children():
            messagebox.showwarning('提示', '请先生成预测表')
            return
        
        try:
            cols = self.pqi_proj_good_road_tree['columns']
            header = '\t'.join(cols)
            
            lines = [header]
            for item in self.pqi_proj_tree.get_children():
                row = self.pqi_proj_good_road_tree.item(item, 'values')
                lines.append('\t'.join(str(v) for v in row))
            
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            
            messagebox.showinfo('成功', '已复制到剪贴板')
            
        except Exception as e:
            messagebox.showerror('错误', f'复制失败：{str(e)}')
    
    def _save_pqi_proj_callback_config(self):
        """保存PQI-Proj回调参数配置"""
        if not set_maintenance_callback:
            messagebox.showerror('错误', '无法保存回调参数')
            return
        
        try:
            config = {}
            for key, var in self.pqi_proj_callback_vars.items():
                parts = key.split('_')
                maint_type = parts[0]
                ptype = parts[1]
                idx = parts[2]
                
                if maint_type not in config:
                    config[maint_type] = {}
                if ptype not in config[maint_type]:
                    config[maint_type][ptype] = {}
                
                config[maint_type][ptype][idx] = var.get()
            
            set_maintenance_callback(config)
            
            cfg = self._load_config()
            cfg['maintenance_callback'] = config
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo('成功', '养护回调参数已保存')
            
        except Exception as e:
            messagebox.showerror('错误', f'保存失败：{str(e)}')
    
    def _reset_pqi_proj_callback_config(self):
        """重置PQI-Proj回调参数为默认值"""
        if not set_maintenance_callback:
            messagebox.showerror('错误', '无法重置回调参数')
            return
        
        try:
            set_maintenance_callback(None)
            
            default_callback = {
                '路面改造': {
                    '沥青路面': {'PQI': 92, 'PCI': 92, 'RQI': 93},
                    '水泥路面': {'PQI': 88, 'PCI': 88, 'RQI': 90},
                },
                '预防性养护': {
                    '沥青路面': {'PQI': 89, 'PCI': 89, 'RQI': 91},
                    '水泥路面': {'PQI': 86, 'PCI': 86, 'RQI': 88},
                },
            }
            
            for key, var in self.pqi_proj_callback_vars.items():
                parts = key.split('_')
                maint_type = parts[0]
                ptype = parts[1]
                idx = parts[2]
                var.set(default_callback.get(maint_type, {}).get(ptype, {}).get(idx, 90))
            
            messagebox.showinfo('成功', '已恢复默认回调参数')
            
        except Exception as e:
            messagebox.showerror('错误', f'重置失败：{str(e)}')


if __name__ == '__main__':
    app = App()
    app.mainloop()
