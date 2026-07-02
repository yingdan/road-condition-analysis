# -*- coding: utf-8 -*-
"""
公路养护决策系统 — 粤路慧养 v2.0
流程：数据评定→目标→对策→需求/预算/资金→项目库→效益评估→反馈调整
"""
import os, sys, json, random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

def get_base_dir():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
BASE_DIR = get_base_dir()
SRC_DIR = os.path.join(BASE_DIR, 'src')
if not os.path.exists(SRC_DIR): SRC_DIR = os.path.join(BASE_DIR, '_internal', 'src')
sys.path.insert(0, SRC_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

# ── 颜色主题（现代化配色）──
THEME = {
    'bg': '#F5F7FA',              # 主背景
    'sidebar': '#2E75B6',          # 侧边栏浅蓝
    'sidebar_active': '#1F497D',   # 当前步骤深蓝
    'sidebar_done': '#27AE60',     # 已完成步骤
    'sidebar_hover': '#3D8BD0',   # 悬停（微亮）
    'sidebar_hover_border': '#FFFFFF',  # 悬停左侧指示线
    'accent': '#2E75B6',           # 主色调
    'accent_light': '#E8F0FE',     # 浅色
    'success': '#219A52',          # 成功绿
    'warning': '#E67E22',          # 警告橙
    'danger': '#C0392B',           # 危险红
    'text': '#2C3E50',
    'text_light': '#7F8C8D',
    'card': '#FFFFFF',
    'card_border': '#E1E5EB',
    'divider': '#EDF0F4',
}

# ── 图表导出辅助 ──
class ExportHelper:
    @staticmethod
    def export(fig):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(title='导出图表', defaultextension='.png',
                                            filetypes=[('PNG','*.png'),('PDF','*.pdf')], initialfile='chart.png')
        if path: fig.savefig(path, dpi=150, bbox_inches='tight'); messagebox.showinfo('成功','图表已导出')

# ── 导入 ──
try:
    from src.data_loader import load_all_data
    from src.decay_calculator import (get_maintenance_callback, set_maintenance_callback,
                                       get_trigger_model, set_trigger_model)
    from src.decision.performance_models import calibrate_model
    from src.decision.maintenance_demand import analyze_demand
    from src.decision.budget_allocation import priority_allocation
    from src.decision.project_pool import ProjectPool, MaintenanceProject
    from src.decision.benefit_analysis import generate_benefit_report
except Exception as e:
    print(f"Import failed: {e}")
    for obj in ['load_all_data','calibrate_model','analyze_demand','priority_allocation',
                'ProjectPool','MaintenanceProject','generate_benefit_report',
                'get_maintenance_callback','set_maintenance_callback','get_trigger_model','set_trigger_model']:
        globals()[obj] = None

# ── 侧边栏步骤定义 ──
STEPS = [
    {'num': 1, 'label': '数据管理',     'desc': '加载和筛选数据'},
    {'num': 2, 'label': '现状评定',     'desc': '技术状况评价'},
    {'num': 3, 'label': '目标设定',     'desc': '养护目标配置'},
    {'num': 4, 'label': '对策模型',     'desc': '衰减/阈值/单价'},
    {'num': 5, 'label': '需求分析',     'desc': '预测/需求/计划'},
    {'num': 6, 'label': '投资规划',     'desc': '经济与优化'},
    {'num': 7, 'label': 'GIS地图',      'desc': '路况可视化'},
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('粤路慧养 v2.0 — 公路养护决策系统')
        self.geometry('1280x820')
        self.minsize(1000, 650)
        self.configure(bg=THEME['bg'])
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 图标
        ip = os.path.join(BASE_DIR, 'road_icon.ico')
        if os.path.exists(ip): self.iconbitmap(ip)

        # 数据
        self.data_cache = {}; self.filtered_df = None; self.demand_result_df = None
        self.project_pool = ProjectPool() if ProjectPool else None
        self.config = self._load_config()
        self._load_saved_callback()

        self._setup_style()
        self._build_sidebar()
        self._build_content_area()
        self._restore_saved_settings()  # 恢复已保存的参数

        # 默认选中步骤1
        self._switch_step(1)

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return {}

    def _load_saved_callback(self):
        if set_maintenance_callback and self.config.get('maintenance_callback'):
            set_maintenance_callback(self.config['maintenance_callback'])

    def _restore_saved_settings(self):
        """将config.json中保存的参数恢复到UI控件"""
        cfg = self.config
        # 恢复目标
        if 'targets' in cfg and hasattr(self,'target_vars'):
            for k,v in cfg['targets'].items():
                if k in self.target_vars:
                    try: self.target_vars[k].set(v)
                    except: pass
        # 恢复触发阈值
        if 'triggers' in cfg and hasattr(self,'trigger_vars'):
            for k,v in cfg['triggers'].items():
                if k in self.trigger_vars:
                    try:
                        self.trigger_vars[k].set(v)
                        if '_启用' in k: print(f'[RESTORE] {k} = {v}')
                    except: pass
        # 恢复回调值
        if 'callbacks' in cfg and hasattr(self,'callback_vars'):
            for k,v in cfg['callbacks'].items():
                if k in self.callback_vars:
                    try: self.callback_vars[k].set(v)
                    except: pass
        # 恢复单价
        if 'prices' in cfg and hasattr(self,'price_vars'):
            for k,v in cfg['prices'].items():
                if k in self.price_vars:
                    try: self.price_vars[k].set(v)
                    except: pass
        # 恢复排序权重
        if 'priority_weights' in cfg and hasattr(self,'priority_vars'):
            for k,v in cfg['priority_weights'].items():
                if k in self.priority_vars:
                    try: self.priority_vars[k].set(v)
                    except: pass

    def _setup_style(self):
        s = ttk.Style(); s.theme_use('clam')
        s.configure('.', background=THEME['bg'], font=('Microsoft YaHei', 9))
        s.configure('Card.TFrame', background=THEME['card'], relief='solid', borderwidth=1)
        s.configure('Title.TLabel', font=('Microsoft YaHei', 15, 'bold'), foreground=THEME['text'])
        s.configure('Sub.TLabel', font=('Microsoft YaHei', 9), foreground=THEME['text_light'])
        s.configure('TNotebook', background=THEME['bg'])
        s.configure('TNotebook.Tab', font=('Microsoft YaHei', 10), padding=(10, 5))
        s.configure('TLabelframe', background=THEME['card'])
        s.configure('TLabelframe.Label', font=('Microsoft YaHei', 10), foreground=THEME['text'])

    # ══════════════════════════════════════════════════════════════════════════
    #  左侧边栏
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = tk.Frame(self, bg=THEME['sidebar'], width=200)
        self.sidebar.grid(row=0, column=0, sticky='ns')
        self.sidebar.grid_propagate(False)

        # Logo区域
        logo = tk.Frame(self.sidebar, bg=THEME['sidebar'], height=100)
        logo.pack(fill='x'); logo.pack_propagate(False)
        tk.Label(logo, text='粤路慧养', bg=THEME['sidebar'], fg='white',
                 font=('Microsoft YaHei', 20, 'bold')).pack(pady=(25,2))
        tk.Label(logo, text='公路养护决策系统 v2.0', bg=THEME['sidebar'], fg='#D0E0F0',
                 font=('Microsoft YaHei', 9)).pack()

        tk.Frame(self.sidebar, bg=THEME['sidebar_active'], height=1).pack(fill='x', padx=15)

        # 步骤列表
        steps_frame = tk.Frame(self.sidebar, bg=THEME['sidebar'])
        steps_frame.pack(fill='both', expand=True, padx=0, pady=10)

        self.step_buttons = {}
        self.step_indicators = {}
        for s in STEPS:
            btn_frame = tk.Frame(steps_frame, bg=THEME['sidebar'], cursor='hand2')
            btn_frame.pack(fill='x', pady=1)

            # 状态指示器
            indicator = tk.Canvas(btn_frame, width=8, height=8, bg=THEME['sidebar'],
                                  highlightthickness=0)
            indicator.pack(side='left', padx=(18, 8), pady=18)
            indicator.create_oval(1, 1, 7, 7, fill='#7AB8E0', outline='')
            self.step_indicators[s['num']] = indicator

            # 文字
            txt = tk.Label(btn_frame, text=f"  {s['num']}. {s['label']}",
                          bg=THEME['sidebar'], fg='white', font=('Microsoft YaHei', 10),
                          anchor='w', cursor='hand2')
            txt.pack(side='left', fill='x', expand=True, pady=10)
            self.step_buttons[s['num']] = txt

            # 事件：悬停时帧+文字+指示器一起变色
            def on_enter(e, f=btn_frame, t=txt, ind=indicator, n=s['num']):
                if not hasattr(self, '_active_step') or self._active_step != n:
                    f.configure(bg=THEME['sidebar_hover'])
                    t.configure(bg=THEME['sidebar_hover'])
                    ind.configure(bg=THEME['sidebar_hover'])

            def on_leave(e, f=btn_frame, t=txt, ind=indicator, n=s['num']):
                if not hasattr(self, '_active_step') or self._active_step != n:
                    f.configure(bg=THEME['sidebar'])
                    t.configure(bg=THEME['sidebar'])
                    ind.configure(bg=THEME['sidebar'])

            for w in [btn_frame, txt]:
                w.bind('<Button-1>', lambda e, n=s['num']: self._switch_step(n))
                w.bind('<Enter>', on_enter)
                w.bind('<Leave>', on_leave)

        # 底部状态
        tk.Frame(self.sidebar, bg=THEME['sidebar_active'], height=1).pack(fill='x', padx=15)
        btm = tk.Frame(self.sidebar, bg=THEME['sidebar'], height=50)
        btm.pack(fill='x', pady=10)
        self.sidebar_status = tk.Label(btm, text='准备就绪', bg=THEME['sidebar'], fg='#D0E0F0',
                                        font=('Microsoft YaHei', 9))
        self.sidebar_status.pack()

    def _switch_step(self, step_num):
        """切换当前步骤"""
        self._active_step = step_num
        # 更新侧边栏高亮
        for n, btn in self.step_buttons.items():
            if n == step_num:
                btn.config(fg='white', font=('Microsoft YaHei', 10), bg=THEME['sidebar_active'])
                btn.master.configure(bg=THEME['sidebar_active'])
                self.step_indicators[n].configure(bg=THEME['sidebar_active'])
                self.step_indicators[n].delete('all')
                self.step_indicators[n].create_oval(1, 1, 7, 7, fill='white', outline='white')
            else:
                btn.config(fg='#D0E0F0', font=('Microsoft YaHei', 10), bg=THEME['sidebar'])
                btn.master.configure(bg=THEME['sidebar'])
                self.step_indicators[n].configure(bg=THEME['sidebar'])
                self.step_indicators[n].delete('all')
                if hasattr(self, 'completed_steps') and n in self.completed_steps:
                    self.step_indicators[n].create_oval(1, 1, 7, 7, fill=THEME['success'], outline=THEME['success'])
                else:
                    self.step_indicators[n].create_oval(1, 1, 7, 7, fill='#5A9BD5', outline='')

        # 隐藏所有页面（footer 除外，它始终在底部）
        current = getattr(self, '_current_page', None)
        if current is not None:
            current.pack_forget()

        # 显示对应内容（footer 之前）
        page = getattr(self, f'_page{step_num}')
        page.pack(fill='both', expand=True, before=self.content_footer)
        page.pack_propagate(False)  # 禁止子控件影响容器尺寸
        self._current_page = page

        # 更新侧边栏状态
        s = STEPS[step_num-1]
        self.sidebar_status.config(text=f'{s["label"]} — {s["desc"]}')

    def mark_step_done(self, step_num):
        """标记步骤完成"""
        if not hasattr(self, 'completed_steps'):
            self.completed_steps = set()
        self.completed_steps.add(step_num)
        self.step_indicators[step_num].delete('all')
        self.step_indicators[step_num].configure(bg=THEME['sidebar'])
        self.step_indicators[step_num].create_oval(1, 1, 7, 7, fill=THEME['success'], outline=THEME['success'])

    # ══════════════════════════════════════════════════════════════════════════
    #  右侧内容区
    # ══════════════════════════════════════════════════════════════════════════
    def _build_content_area(self):
        self.content_area = tk.Frame(self, bg=THEME['bg'])
        self.content_area.grid(row=0, column=1, sticky='nsew')

        # 创建10个页面的容器Frame
        for i in range(1, 8):
            page = tk.Frame(self.content_area, bg=THEME['bg'])
            setattr(self, f'_page{i}', page)
            # 构建对应内容
            getattr(self, f'_build_page{i}')(page)

        # 底部状态栏
        self.content_footer = tk.Frame(self.content_area, bg=THEME['card_border'], height=28)
        self.content_footer.pack(side='bottom', fill='x')
        footer = self.content_footer
        footer.pack_propagate(False)
        self.status_var = tk.StringVar(value='就绪 — 请先加载数据')
        tk.Label(footer, textvariable=self.status_var, bg=THEME['card_border'],
                 font=('Microsoft YaHei', 9), anchor='w').pack(side='left', padx=15)

    # ── 通用卡片容器 ──
    def _card(self, parent, title='', pady=8, expand=False):
        """创建标准卡片容器"""
        f = tk.Frame(parent, bg=THEME['card'], highlightbackground=THEME['card_border'],
                     highlightthickness=1, padx=20, pady=15)
        f.pack(fill='both' if expand else 'x', expand=expand, padx=20, pady=pady)
        if title:
            tk.Label(f, text=title, bg=THEME['card'], fg=THEME['text'],
                    font=('Microsoft YaHei', 12, 'bold'), anchor='w').pack(fill='x', pady=(0,10))
        return f

    def _bg(self, widget):
        """安全获取widget背景色"""
        try: return widget.cget('background')
        except:
            try: return widget.cget('bg')
            except: return THEME['card']

    def _row(self, parent, pady=5):
        f = tk.Frame(parent, bg=self._bg(parent), highlightthickness=0)
        f.pack(fill='x', pady=pady)
        return f

    def _section_title(self, parent, text):
        tk.Label(parent, text=text, bg=self._bg(parent), fg=THEME['text'],
                font=('Microsoft YaHei', 14, 'bold')).pack(anchor='w', pady=(15,3))

    def _section_sub(self, parent, text):
        tk.Label(parent, text=text, bg=self._bg(parent), fg=THEME['text_light'],
                font=('Microsoft YaHei', 9)).pack(anchor='w', pady=(0,10))

    # ══════════════════════════════════════════════════════════════════════════
    #  页面1: 数据管理 (Excel智能识别 + 数据库连接)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page1(self, parent):
        # 可滚动
        cvs = tk.Canvas(parent, bg=THEME['bg'], highlightthickness=0)
        sv_bar = ttk.Scrollbar(parent, orient='vertical', command=cvs.yview)
        cvs.configure(yscrollcommand=sv_bar.set)
        sv_bar.pack(side='right', fill='y'); cvs.pack(side='left', fill='both', expand=True)
        sf = tk.Frame(cvs, bg=THEME['bg'])
        win_id = cvs.create_window((0,0), window=sf, anchor='nw', tags=('sframe',))
        def _on_cvs_cfg(e):
            cvs.itemconfig(win_id, width=e.width)
            cvs.configure(scrollregion=cvs.bbox('all'))
        cvs.bind('<Configure>', _on_cvs_cfg)
        sf.bind('<Configure>', lambda e: cvs.configure(scrollregion=cvs.bbox('all')))

        self._section_title(sf, '📂 数据管理')
        self._section_sub(sf, 'Excel智能识别导入 + PostgreSQL/PostGIS数据库连接')

        # ── Excel智能识别导入 ──
        card = self._card(sf, '📁 Excel智能识别导入')
        tk.Label(card, text='支持自动识别文件年份和Sheet名称，智能匹配列名映射',
                 bg=THEME['card'], fg=THEME['text_light'], font=('Microsoft YaHei', 9)).pack(anchor='w', pady=(0,8))

        self.file_vars = {}
        for year in [2021, 2022, 2023, 2024, 2025]:
            r = self._row(card, 4)
            tk.Label(r, text=f'{year}年', width=8, bg=THEME['card'],
                    font=('Microsoft YaHei', 9, 'bold')).pack(side='left')
            self.file_vars[year] = tk.StringVar()
            ttk.Entry(r, textvariable=self.file_vars[year], width=40, font=('Microsoft YaHei', 9)).pack(side='left', padx=8)
            tk.Button(r, text='浏览', command=lambda y=year: self._browse_file(y),
                     bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9), padx=8, cursor='hand2').pack(side='left')

        r = self._row(card, 6)
        tk.Button(r, text='📂 批量识别', command=self._browse_folder,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9), padx=12, cursor='hand2').pack(side='left', padx=3)
        tk.Button(r, text='🚀 加载数据', command=self._load_data,
                 bg=THEME['success'], fg='white', font=('Microsoft YaHei', 10),
                 padx=15, pady=3, cursor='hand2').pack(side='left', padx=5)
        self.load_info = tk.Label(r, text='点击"批量识别"或逐项选择文件后加载', bg=THEME['card'],
                                  fg=THEME['text_light'], font=('Microsoft YaHei', 9))
        self.load_info.pack(side='left', padx=10)

        # ── 数据库连接 ──
        card_db = self._card(sf, '🗄️ 数据库连接 (PostgreSQL/PostGIS)')
        r1 = self._row(card_db, 3)
        for lbl, v, w in [('Host','localhost',14),('Port','5432',6),('DB','road_maintenance',14)]:
            tk.Label(r1, text=lbl+':', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(0,2))
            setattr(self, f'db_{lbl.lower()}_var', tk.StringVar(value=v))
            ttk.Entry(r1, textvariable=getattr(self, f'db_{lbl.lower()}_var'), width=w, font=('Microsoft YaHei', 9)).pack(side='left', padx=(0,8))
        r2 = self._row(card_db, 3)
        for lbl, v, w in [('User','postgres',14),('Pass','',14)]:
            tk.Label(r2, text=lbl+':', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(0,2))
            setattr(self, f'db_{lbl.lower()}_var', tk.StringVar(value=v))
            ttk.Entry(r2, textvariable=getattr(self, f'db_{lbl.lower()}_var'), width=w,
                      show='*' if lbl=='Pass' else '', font=('Microsoft YaHei', 9)).pack(side='left', padx=(0,8))
        r3 = self._row(card_db, 5)
        tk.Button(r3, text='🔌 连接数据库', command=self._db_connect,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9), padx=10, cursor='hand2').pack(side='left', padx=3)
        self.db_status = tk.Label(r3, text='未连接', bg=THEME['card'], fg=THEME['text_light'], font=('Microsoft YaHei', 9))
        self.db_status.pack(side='left', padx=10)
        tk.Button(r3, text='初始化表', command=self._db_init, font=('Microsoft YaHei', 9)).pack(side='left', padx=3)
        tk.Button(r3, text='同步到数据库', command=self._db_sync, font=('Microsoft YaHei', 9)).pack(side='left', padx=3)
        self.db_text = tk.Text(card_db, height=3, wrap='word', font=('Consolas', 8))
        self.db_text.pack(fill='x', pady=(5,0))

        # ── 数据筛选 ──
        card2 = self._card(sf, '🔎 数据筛选与预览', expand=True)
        r1 = self._row(card2, 4)
        tk.Label(r1, text='县份', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(0,3))
        self.filter_county_var = tk.StringVar(value='全部')
        self.filter_county_cb = ttk.Combobox(r1, textvariable=self.filter_county_var, width=10, state='readonly', values=['全部'])
        self.filter_county_cb.pack(side='left')
        tk.Label(r1, text='年份', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(10,3))
        self.filter_year_var = tk.StringVar(value='全部')
        self.filter_year_cb = ttk.Combobox(r1, textvariable=self.filter_year_var, width=6, state='readonly', values=['全部'])
        self.filter_year_cb.pack(side='left')
        tk.Label(r1, text='PQI等级', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(10,3))
        self.filter_grade_var = tk.StringVar(value='全部')
        ttk.Combobox(r1, textvariable=self.filter_grade_var, width=6, state='readonly',
                     values=['全部','优','良','中','次','差']).pack(side='left')
        tk.Label(r1, text='类型', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(10,3))
        self.filter_type_var = tk.StringVar(value='全部')
        ttk.Combobox(r1, textvariable=self.filter_type_var, width=10, state='readonly',
                     values=['全部','沥青路面','水泥路面']).pack(side='left')
        r2 = self._row(card2, 6)
        tk.Button(r2, text='🔍 筛选', command=self._apply_filter,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9), padx=12, cursor='hand2').pack(side='left', padx=3)
        tk.Button(r2, text='↺ 重置', command=self._reset_filter, font=('Microsoft YaHei', 9)).pack(side='left', padx=3)
        tk.Button(r2, text='📥 导出Excel', command=self._export_filtered, font=('Microsoft YaHei', 9)).pack(side='right', padx=3)
        self.filter_stats = tk.Label(r2, text='', bg=THEME['card'], fg=THEME['text_light'], font=('Microsoft YaHei', 9))
        self.filter_stats.pack(side='left', padx=15)

        # 数据表格
        cols = ('路线编码','路段起点','路段终点','路段长度km','路面类型','技术等级','PQI','PCI','RQI','PQI分级','年份','县份','交通量','车道数','路龄')
        tvf = tk.Frame(sf, bg=THEME['bg']); tvf.pack(fill='both', expand=True, padx=20, pady=5)
        self.data_tree = ttk.Treeview(tvf, columns=cols, show='headings', height=14)
        ws = {'路线编码':70,'路段起点':55,'路段终点':55,'路段长度km':55,'路面类型':65,'技术等级':60,'PQI':45,'PCI':45,'RQI':45,'PQI分级':45,'年份':35,'县份':45,'交通量':52,'车道数':45,'路龄':40}
        for c in cols:
            self.data_tree.heading(c, text=c); self.data_tree.column(c, width=ws.get(c,55), anchor='center')
        sv = ttk.Scrollbar(tvf, orient='vertical', command=self.data_tree.yview)
        sh = ttk.Scrollbar(tvf, orient='horizontal', command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=sv.set, xscrollcommand=sh.set)
        self.data_tree.pack(side='left', fill='both', expand=True)
        sv.pack(side='right', fill='y'); sh.pack(side='bottom', fill='x')

        self._auto_load_config()

    def _auto_load_config(self):
        cfg = self.config.get('data_files', {})
        for y, p in cfg.items():
            if y.isdigit() and int(y) in self.file_vars: self.file_vars[int(y)].set(p)

    def _browse_file(self, year):
        path = filedialog.askopenfilename(title=f'选择{year}年数据', filetypes=[('Excel','*.xlsx *.xls')])
        if path: self.file_vars[year].set(path)

    def _browse_folder(self):
        """批量识别：选择文件夹或文件，自动匹配年份"""
        import re
        path = filedialog.askdirectory(title='选择包含Excel文件的文件夹', mustexist=True)
        if not path:
            paths = filedialog.askopenfilenames(title='选择多个Excel文件', filetypes=[('Excel','*.xlsx *.xls')])
            if not paths: return
            matched = 0
            for p in sorted(paths):
                fn = os.path.basename(p)
                ym = re.search(r'(20\d{2})', fn)
                year = int(ym.group(1)) if ym and int(ym.group(1)) in self.file_vars else None
                if year and not self.file_vars[year].get():
                    self.file_vars[year].set(p); matched += 1
                elif year:
                    # Already set, try next best match
                    for y in range(2021,2026):
                        if not self.file_vars[y].get():
                            self.file_vars[y].set(p)
                            matched += 1; break
            messagebox.showinfo('批量识别', f'已完成：匹配{matched}个文件')
            return
        # Scan folder
        matched = 0
        for root, dirs, files in os.walk(path):
            for fn in sorted(files):
                if not fn.endswith(('.xlsx','.xls')): continue
                fm = os.path.join(root, fn)
                ym = re.search(r'(20\d{2})', fn)
                year = int(ym.group(1)) if ym and int(ym.group(1)) in self.file_vars else None
                if year and not self.file_vars[year].get():
                    self.file_vars[year].set(fm); matched += 1
                elif year:
                    for y in range(2021,2026):
                        if not self.file_vars[y].get():
                            self.file_vars[y].set(fm)
                            matched += 1; break
        messagebox.showinfo('批量识别', f'文件夹扫描完成：匹配{matched}个文件')
        self.load_info.config(text=f'已识别{matched}个文件，可点击"加载数据"', fg=THEME['success'])

    def _load_data(self):
        file_map = {}
        for y, v in self.file_vars.items():
            p = v.get().strip()
            if p and os.path.exists(p): file_map[y] = p
        if not file_map:
            messagebox.showwarning('提示','请至少配置一个数据文件'); return
        self.status_var.set('正在加载数据...'); self.update()
        try:
            data = load_all_data(file_map)
            self.data_cache = data
            all_df = data.get('全部', pd.DataFrame())
            counties = sorted(all_df['县份'].unique().tolist()) if '县份' in all_df.columns else []
            years = sorted(all_df['年份'].unique().tolist()) if '年份' in all_df.columns else []
            self.load_info.config(text=f'✓ 成功加载 {len(all_df)} 条记录 | {len(counties)} 个县份 | {min(years)}-{max(years)} 年', fg=THEME['success'])
            cv = ['全部']+sorted(counties); yv = ['全部']+[str(y) for y in sorted(years)]
            self.filter_county_cb['values'] = cv; self.filter_year_cb['values'] = yv
            # 更新所有页面的县份下拉
            for a in ['tech_county_cb','model_county_cb','demand_county_cb','benefit_county_cb','map_county_cb','dp_county_cb']:
                if hasattr(self, a): getattr(self, a)['values'] = cv
            if counties:
                self.filter_county_var.set(counties[0])
                for a in ['tech_county_var','demand_county_var']:
                    if hasattr(self, a): getattr(self, a).set('全部')
            if years: self.filter_year_var.set(str(max(years)))
            self.status_var.set(f'数据加载完成 — {len(all_df)}条记录')
            self.mark_step_done(1)
        except Exception as e:
            messagebox.showerror('错误', str(e))

    def _apply_filter(self):
        if not self.data_cache: return
        df = pd.concat(self.data_cache.values(), ignore_index=True)
        c = self.filter_county_var.get()
        if c != '全部' and '县份' in df.columns: df = df[df['县份'] == c]
        y = self.filter_year_var.get()
        if y != '全部' and '年份' in df.columns: df = df[df['年份'] == int(y)]
        g = self.filter_grade_var.get()
        if g != '全部' and 'PQI分级' in df.columns: df = df[df['PQI分级'] == g]
        p = self.filter_type_var.get()
        if p != '全部' and '路面类型' in df.columns: df = df[df['路面类型'] == p]
        self.filtered_df = df
        km = df['路段长度km'].sum() if '路段长度km' in df.columns else 0
        self.filter_stats.config(text=f'{len(df)}条 | {km:.1f}km')
        self.data_tree.delete(*self.data_tree.get_children())
        for _, row in df.head(500).iterrows():
            vals = [f'{row.get(c,""):.2f}' if isinstance(row.get(c,''),float) else str(row.get(c,''))
                    for c in self.data_tree['columns']]
            self.data_tree.insert('','end',values=vals)

    def _reset_filter(self):
        for v in [self.filter_county_var, self.filter_year_var, self.filter_grade_var, self.filter_type_var]:
            v.set('全部')
        self._apply_filter()

    def _export_filtered(self):
        if self.filtered_df is None or self.filtered_df.empty:
            messagebox.showwarning('提示','没有可导出数据'); return
        path = filedialog.asksaveasfilename(title='导出', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
        if path: self.filtered_df.to_excel(path, index=False); messagebox.showinfo('成功','已导出')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面2: 现状评定（4张评价表 + 图表）
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page2(self, parent):
        # 顶部分析参数栏
        top = tk.Frame(parent, bg=THEME['bg'])
        top.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(top, text='📊 现状数据评定分析', bg=THEME['bg'], fg=THEME['text'],
                font=('Microsoft YaHei', 14, 'bold')).pack(anchor='w')
        r = tk.Frame(top, bg=THEME['bg']); r.pack(fill='x', pady=5)
        tk.Label(r, text='县份', bg=THEME['bg'], font=('Microsoft YaHei', 9)).pack(side='left')
        self.tech_county_var = tk.StringVar(value='全部')
        self.tech_county_cb = ttk.Combobox(r, textvariable=self.tech_county_var, width=10, state='readonly', values=['全部'])
        self.tech_county_cb.pack(side='left', padx=5)
        tk.Label(r, text='基准年', bg=THEME['bg'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.tech_year_var = tk.StringVar(value='2025')
        ttk.Combobox(r, textvariable=self.tech_year_var, width=6, values=['2021','2022','2023','2024','2025']).pack(side='left', padx=5)
        tk.Button(r, text='▶ 执行分析', command=self._run_tech,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=15, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='📥 导出全部', command=self._export_tech_all, font=('Microsoft YaHei', 9)).pack(side='right', padx=5)

        # 可拖拽调整的4栏区域
        self.tech_pw = tk.PanedWindow(parent, orient='vertical', bg=THEME['card_border'],
                                       sashwidth=4, sashrelief='raised')
        self.tech_pw.pack(fill='both', expand=True, padx=15, pady=(5,10))

        self.tech_sections = {}
        for key, title in [('road_type','表1. 等级评价 — 按国道/省道 × 指标'),('route','表2. 路线评价 — 按路线编号'),
                           ('tech_grade','表3. 技术等级评价 — 按公路等级 × 指标'),('year','表4. 年度趋势 — 按年份')]:
            sec = ttk.LabelFrame(self.tech_pw, text=title, padding=5)
            self.tech_pw.add(sec, height=200)
            self.tech_sections[key] = sec

        # 预加载数据
        if self.data_cache:
            self._run_tech()

    def _run_tech(self):
        df = self._get_data(self.tech_county_var.get())
        if df.empty: return
        year = int(self.tech_year_var.get())
        if '年份' in df.columns: df = df[df['年份'] == year]
        if '路段长度km' not in df.columns: df['路段长度km'] = 1.0
        def rt(r): return '国道' if str(r)[:1]=='G' else ('省道' if str(r)[:1]=='S' else '其他')
        if '路线编码' in df.columns: df['道路类型'] = df['路线编码'].apply(rt)
        pk = {'国': '国道', '省': '省道'}

        # ── 表1: 等级评价 ──
        self._clear_section('road_type')
        cols = ('道路类型','指标','加权均值','优良路率','次差路率','优里程','良里程','中里程','次里程','差里程','评定里程')
        tf1, tv1 = self._build_section_table(self.tech_sections['road_type'], cols, 5, ws={'道路类型':65,'指标':50,'加权均值':58,'优良路率':68,'次差路率':68,'优里程':55,'良里程':55,'中里程':55,'次里程':55,'差里程':55,'评定里程':68})
        # 分级阈值: PQI/PCI vs RQI 不同
        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            if rd.empty: continue
            for idx, label in [('PQI','PQI'),('PCI','PCI'),('RQI','RQI')]:
                if idx not in rd.columns: continue
                t = rd['路段长度km'].sum()
                # 加权均值
                wavg = (rd[idx] * rd['路段长度km']).sum() / t if t > 0 else 0
                # PQI/PCI/RQI 统一分级: 优≥90 良≥80 中≥70 次≥60 差<60
                y, l, z, c = 90, 80, 70, 60
                gr_thr, br_thr = 80, 60          # 优良≥80, 次差<60
                gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100 if t > 0 else 0
                br = rd[rd[idx] < br_thr]['路段长度km'].sum() / t * 100 if t > 0 else 0
                yl = rd[(rd[idx] >= y) & (rd[idx] <= 100)]['路段长度km'].sum()
                lh = rd[(rd[idx] >= l) & (rd[idx] < y)]['路段长度km'].sum()
                zh = rd[(rd[idx] >= z) & (rd[idx] < l)]['路段长度km'].sum()
                ci = rd[(rd[idx] >= c) & (rd[idx] < z)]['路段长度km'].sum()
                ch = rd[rd[idx] < c]['路段长度km'].sum()
                tv1.insert('','end',values=(road, label, f'{wavg:.1f}', f'{gr:.1f}%', f'{br:.1f}%',
                    f'{yl:.1f}', f'{lh:.1f}', f'{zh:.1f}', f'{ci:.1f}', f'{ch:.1f}', f'{t:.1f}'))
        self._build_section_chart(self.tech_sections['road_type'], tv1, 'group_bar', title='国道/省道 × PQI/PCI/RQI 对比')

        # ── 表2: 路线评价 ──
        self._clear_section('route')
        cols2 = ('路线编码','PQI加权均值','PQI优良路率','PCI加权均值','PCI优良路率','RQI加权均值','RQI优良路率')
        tf2, tv2 = self._build_section_table(self.tech_sections['route'], cols2, 8, ws={'路线编码':90,'PQI加权均值':85,'PQI优良路率':85,'PCI加权均值':85,'PCI优良路率':85,'RQI加权均值':85,'RQI优良路率':85})
        for rt_code, rd in df.groupby('路线编码'):
            t = rd['路段长度km'].sum()
            if t == 0: t = 1
            vals = []
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',80)]:
                if idx in rd.columns:
                    wavg = (rd[idx] * rd['路段长度km']).sum() / t
                    gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100
                    vals += [f'{wavg:.1f}', f'{gr:.1f}%']
                else:
                    vals += ['-','-']
            tv2.insert('','end',values=(rt_code, *vals))
        # 全路网汇总
        t_all = df['路段长度km'].sum()
        overall = []
        for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',90)]:
            if idx in df.columns:
                wavg = (df[idx] * df['路段长度km']).sum() / t_all if t_all > 0 else 0
                gr = df[df[idx] >= gr_thr]['路段长度km'].sum() / t_all * 100 if t_all > 0 else 0
                overall += [f'{wavg:.1f}', f'{gr:.1f}%']
            else:
                overall += ['-','-']
        tv2.insert('','end',values=('全路网', *overall))
        self._build_section_chart(self.tech_sections['route'], tv2, 'line', title='各路线PQI/PCI/RQI对比')

        # ── 表3: 技术等级 ──
        self._clear_section('tech_grade')
        cols3 = ('技术等级','PQI加权均值','PQI优良路率','PCI加权均值','PCI优良路率','RQI加权均值','RQI优良路率')
        tf3, tv3 = self._build_section_table(self.tech_sections['tech_grade'], cols3, 5, ws={'技术等级':85,'PQI加权均值':85,'PQI优良路率':80,'PCI加权均值':85,'PCI优良路率':80,'RQI加权均值':85,'RQI优良路率':80})
        grade_map = {'一':'一级公路','二':'二级公路','三':'三级公路','四':'四级公路'}
        for key, grade in grade_map.items():
            rd = df[df['技术等级'].str.contains(key, na=False)] if '技术等级' in df.columns else pd.DataFrame()
            if rd.empty and '技术等级' in df.columns: rd = df[df['技术等级']==grade]
            if rd.empty: continue
            t = rd['路段长度km'].sum()
            if t == 0: t = 1
            vals = []
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',90)]:
                if idx in rd.columns and not rd[idx].isna().all():
                    wavg = (rd[idx] * rd['路段长度km']).sum() / t
                    gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100
                    vals += [f'{wavg:.1f}', f'{gr:.1f}%']
                else:
                    vals += ['-','-']
            tv3.insert('','end',values=(grade, *vals))
        if not tv3.get_children():
            t = df['路段长度km'].sum(); t = t if t>0 else 1
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',80)]:
                wavg = (df[idx] * df['路段长度km']).sum() / t if idx in df.columns else 0
                gr = df[df[idx] >= gr_thr]['路段长度km'].sum() / t * 100 if idx in df.columns and t>0 else 0
                tv3.insert('','end',values=('全路网', f'{wavg:.1f}',f'{gr:.1f}%', '-','-', '-','-'))
        self._build_section_chart(self.tech_sections['tech_grade'], tv3, 'combo', title='技术等级对比')

        # ── 表4: 年度趋势 ──
        self._clear_section('year')
        cols4 = ('年份','PQI均值','PCI均值','RQI均值','PQI优良路率')
        tf4, tv4 = self._build_section_table(self.tech_sections['year'], cols4, 6, ws={'年份':55,'PQI均值':78,'PCI均值':78,'RQI均值':78,'PQI优良路率':88})
        all_df = pd.concat(self.data_cache.values(), ignore_index=True) if self.data_cache else df
        if '路段长度km' not in all_df.columns: all_df['路段长度km'] = 1.0
        years_data = sorted(all_df['年份'].unique()) if '年份' in all_df.columns else [year]
        if not years_data: years_data = [year]
        for y in years_data:
            yi = int(y) if str(y).isdigit() else y
            yd = all_df[all_df['年份']==y] if '年份' in all_df.columns else df
            if yd.empty: continue
            t = yd['路段长度km'].sum()
            if t == 0: t = 1
            pqim = (yd['PQI'] * yd['路段长度km']).sum() / t if 'PQI' in yd.columns else 0
            pcim = (yd['PCI'] * yd['路段长度km']).sum() / t if 'PCI' in yd.columns else 0
            rqim = (yd['RQI'] * yd['路段长度km']).sum() / t if 'RQI' in yd.columns else 0
            gr = yd[yd['PQI']>=80]['路段长度km'].sum()/t*100 if 'PQI' in yd.columns and t>0 else 0
            tv4.insert('','end',values=(yi, f'{pqim:.1f}', f'{pcim:.1f}', f'{rqim:.1f}', f'{gr:.1f}%'))
        self._build_section_chart(self.tech_sections['year'], tv4, 'line', title='年度趋势')

        self.mark_step_done(2)
        self.status_var.set(f'现状评定完成 — {len(df)}条记录')

    def _clear_section(self, key):
        """彻底清除section内的所有子控件"""
        sec = self.tech_sections[key]
        for w in list(sec.winfo_children()):
            w.destroy()
        sec.update_idletasks()

    def _build_section_table(self, parent, cols, height, ws=None):
        """在parent左侧创建表格(自适应高度)"""
        tvf = tk.Frame(parent, bg=THEME['card'])
        tvf.pack(side='left', fill='both', expand=True, padx=(0,2))
        tv = ttk.Treeview(tvf, columns=cols, show='headings', height=height)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=ws.get(c,60) if ws else 60, anchor='center')
        rp = tk.Frame(tvf, bg=THEME['card'])
        rp.pack(side='right', fill='y')
        sv = ttk.Scrollbar(rp, orient='vertical', command=tv.yview)
        sv.pack(side='top', fill='y', expand=True)
        tk.Button(rp, text='📋', font=('Microsoft YaHei', 9),
                 command=lambda t=tv: self._copy_tree(t), padx=3).pack(side='bottom', pady=(2,0))
        tv.configure(yscrollcommand=sv.set)
        tv.pack(side='left', fill='both', expand=True)
        return tvf, tv

    def _build_section_chart(self, parent, tv, chart_type, title='图表'):
        """在parent右侧创建图表"""
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import matplotlib.pyplot as plt
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei','SimHei']
            plt.rcParams['axes.unicode_minus'] = False
        except ImportError:
            return

        try:
            self._do_chart(parent, tv, chart_type, title)
        except Exception as e:
            import traceback; traceback.print_exc()
            tk.Label(parent, text=f'图表错误: {e}', fg=THEME['danger'], bg=THEME['card'],
                     font=('Microsoft YaHei', 8)).pack(side='right', padx=10)

    def _do_chart(self, parent, tv, chart_type, title):
        """实际绘制图表"""
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.pyplot as plt
        cf = tk.Frame(parent, bg=THEME['card'])
        cf.pack(side='right', fill='both', expand=True, padx=(2,0))

        headers = tv['columns']
        rows = [tv.item(it,'values') for it in tv.get_children()]
        if not rows: return

        labels = [str(r[0]) for r in rows]
        fig = Figure(figsize=(8, 5.5), dpi=80, facecolor=THEME['card'])
        ax = fig.add_subplot(111)
        ax.set_facecolor(THEME['card'])

        if chart_type == 'group_bar' and len(rows) <= 12:
            road_types = sorted(set(str(r[0]) for r in rows))
            indicators = sorted(set(str(r[1]) for r in rows), key=lambda x: {'PQI':0,'PCI':1,'RQI':2}.get(x,9))
            data = {}
            for r in rows:
                idx, rd, v = str(r[1]), str(r[0]), float(str(r[2]).replace('%','')) if r[2]!='-' else 0
                if idx not in data: data[idx] = {}
                data[idx][rd] = v
            x = range(len(indicators))
            nbars = len(road_types)
            w = 0.6 / nbars if nbars > 1 else 0.4
            colors_road = {'国道':'#2E75B6','省道':'#27AE60'}
            for j, rd in enumerate(road_types):
                vals = [data.get(idx, {}).get(rd, 0) for idx in indicators]
                bars = ax.bar([i + (j - (nbars-1)/2) * w for i in x], vals, w, label=rd, color=colors_road.get(rd,'#888'), zorder=2)
                for bar in bars:
                    h = bar.get_height()
                    if h > 0: ax.text(bar.get_x() + bar.get_width()/2, h + max(vals)*0.02, f'{h:.1f}', ha='center', va='bottom', fontsize=6)
            ax.set_xticks(x); ax.set_xticklabels(indicators, fontsize=8)
            ax.legend(loc='upper left', fontsize=7)

        elif chart_type == 'combo' and len(rows) <= 12:
            num_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['均值'])]
            pct_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['路率'])]
            mean_colors = {'PQI均值':'#2E75B6','PCI均值':'#27AE60','RQI均值':'#E67E22'}
            pct_colors = {'PQI优良路率':'#C0392B','PCI优良路率':'#8E44AD','RQI优良路率':'#D35400'}
            x = range(len(labels))
            total_bars = len(num_cols)
            wb = 0.6 / total_bars if total_bars else 0.3
            for j, ci in enumerate(num_cols):
                vals = [float(str(r[ci]).replace('%','')) if r[ci] != '-' else 0 for r in rows]
                col = mean_colors.get(headers[ci], f'C{j}')
                bars = ax.bar([i + (j - (total_bars-1)/2) * wb for i in x], vals, wb, label=headers[ci], color=col, zorder=2)
                for bar in bars:
                    h = bar.get_height()
                    if h > 0: ax.text(bar.get_x() + bar.get_width()/2, h + max(vals)*0.02, f'{h:.1f}', ha='center', va='bottom', fontsize=5.5)
            if pct_cols:
                ax2 = ax.twinx(); ax2.set_facecolor(THEME['card'])
                for j, ci in enumerate(pct_cols):
                    pv = [float(str(r[ci]).replace('%','')) if r[ci]!='-' else 0 for r in rows]
                    col = pct_colors.get(headers[ci], f'C{3+j}')
                    ax2.plot(x, pv, 'o-', color=col, label=headers[ci], markersize=5, linewidth=1.5, zorder=5)
                    for xi, yv in zip(x, pv):
                        ax2.annotate(f'{yv:.1f}%', (xi, yv), textcoords='offset points', xytext=(0,8), ha='center', fontsize=6, color=col)
                ax2.set_ylabel('优良路率 (%)', fontsize=7); ax2.tick_params(labelsize=6)
                h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
                ax.legend(h1+h2, l1+l2, loc='upper left', fontsize=6)
            ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=25)

        elif chart_type == 'line':
            # 检测X轴数据：可转数字用数值，否则按标签序号
            numeric_x = True
            try: _ = float(str(rows[0][0]))
            except: numeric_x = False
            if numeric_x:
                xv = [float(str(r[0])) for r in rows]
            else:
                xv = list(range(len(rows)))
            num_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['均值','路率'])]
            COLORS = ['#2E75B6','#E67E22','#27AE60','#C0392B','#8E44AD','#D35400']
            STYLES = ['o-','s--','D:','^-.','v--','*:']
            for j, ci in enumerate(num_cols):
                yv = [float(str(r[ci]).replace('%','')) if r[ci]!='-' else 0 for r in rows]
                ax.plot(xv, yv, STYLES[j%6], color=COLORS[j%6], label=headers[ci], markersize=4, linewidth=1.2, zorder=2)
                for xi, yi in zip(xv, yv):
                    ax.annotate(f'{yi:.1f}', (xi, yi), textcoords='offset points', xytext=(0,8), ha='center', fontsize=5.5, color=COLORS[j%6])
            ax.legend(fontsize=6)
            if numeric_x:
                try: ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
                except: pass
            else:
                ax.set_xticks(xv)
                ax.set_xticklabels(labels, fontsize=6, rotation=45)

        ax.set_title(title, fontsize=9, fontweight='bold')
        ax.tick_params(labelsize=7)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, cf)
        canvas.draw(); canvas.get_tk_widget().pack(fill='both', expand=True)
        # 导出按钮
        bf = tk.Frame(cf, bg=THEME['card']); bf.pack(fill='x')
        tk.Button(bf, text='💾 导出图表', font=('Microsoft YaHei', 9),
                 command=lambda f=fig: ExportHelper.export(f)).pack(side='left')

    def _copy_tree(self, tv):
        """复制Treeview内容到剪贴板"""
        headers = '\t'.join(tv['columns'])
        lines = [headers]
        for it in tv.get_children():
            row = '\t'.join(str(v) for v in tv.item(it, 'values'))
            lines.append(row)
        text = '\n'.join(lines)
        self.clipboard_clear(); self.clipboard_append(text)
        messagebox.showinfo('成功', '已复制到剪贴板')

    def _export_tech_all(self):
        path = filedialog.asksaveasfilename(title='导出评定结果', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')], initialfile='现状评定.xlsx')
        if not path: return
        with pd.ExcelWriter(path) as writer:
            for key, sec in self.tech_sections.items():
                for w in sec.winfo_children():
                    if isinstance(w, tk.Frame):
                        for tw in w.winfo_children():
                            if isinstance(tw, ttk.Treeview) and tw.winfo_children():
                                rows = [tw.item(it,'values') for it in tw.get_children()]
                                if rows:
                                    pd.DataFrame(rows, columns=tw['columns']).to_excel(writer, sheet_name=key[:30], index=False)
                                break
        messagebox.showinfo('成功','已导出全部评定结果')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面3: 目标设定
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page3(self, parent):
        self._section_title(parent, '🎯 养护目标设定')
        self._section_sub(parent, '技术目标(加权PQI+优良路率) — 短期/中期/长期 | B/C和成本为参考值')

        self.target_vars = {}
        horizons = [
            ('short', '短期目标 (1年)', '近期达标线'),
            ('mid',   '中期目标 (2-5年)', '中期规划目标'),
            ('long',  '长期目标 (5-10年)', '远期愿景目标'),
        ]
        # 默认目标：技术+经济双维度
        default_targets = {
            'short': {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':1.2,'国道_km成本':50,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.1,'省道_km成本':55},
            'mid':   {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':1.5,'国道_km成本':45,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.3,'省道_km成本':50},
            'long':  {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':2.0,'国道_km成本':40,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.8,'省道_km成本':45},
        }

        for hkey, htitle, hdesc in horizons:
            f = ttk.LabelFrame(parent, text=f'{htitle} — {hdesc}', padding=10)
            f.pack(fill='x', padx=15, pady=5)
            r = self._row(f)
            # 国道
            gd = ttk.LabelFrame(r, text='普通国道', padding=5)
            gd.pack(side='left', fill='x', expand=True, padx=(0,10))
            grd = tk.Frame(gd, bg=self._bg(gd)); grd.pack(fill='x')
            tk.Label(grd, text='技术→', bg=self._bg(gd), fg=THEME['accent'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(0,5))
            for label, suffix, dv in [('PQI','PQI',default_targets[hkey]['国道_PQI']),
                                       ('优良路率%','优良路率',default_targets[hkey]['国道_优良路率'])]:
                tk.Label(grd, text=f'{label} ', bg=self._bg(gd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=dv); self.target_vars[f'{hkey}_国道_{suffix}'] = v
                ttk.Entry(grd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            # 短期只显示技术指标，中/长期增加参考值
            if hkey != 'short':
                tk.Label(grd, text='参考→', bg=self._bg(gd), fg=THEME['text_light'],
                        font=('Microsoft YaHei',8)).pack(side='left', padx=(5,5))
                for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['国道_BCR']),
                                           ('成本万/km','km成本',default_targets[hkey]['国道_km成本'])]:
                    tk.Label(grd, text=f'{label} ', bg=self._bg(gd), font=('Microsoft YaHei',9)).pack(side='left')
                    if suffix == 'BCR':
                        v = tk.StringVar(value=str(dv))
                    else:
                        v = tk.IntVar(value=dv)
                    self.target_vars[f'{hkey}_国道_{suffix}'] = v
                    ttk.Entry(grd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            # 省道
            sd = ttk.LabelFrame(r, text='普通省道', padding=5)
            sd.pack(side='left', fill='x', expand=True)
            srd = tk.Frame(sd, bg=self._bg(sd)); srd.pack(fill='x')
            tk.Label(srd, text='技术→', bg=self._bg(sd), fg=THEME['accent'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(0,5))
            for label, suffix, dv in [('PQI','PQI',default_targets[hkey]['省道_PQI']),
                                       ('优良路率%','优良路率',default_targets[hkey]['省道_优良路率'])]:
                tk.Label(srd, text=f'{label} ', bg=self._bg(sd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=dv); self.target_vars[f'{hkey}_省道_{suffix}'] = v
                ttk.Entry(srd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            if hkey != 'short':
                tk.Label(srd, text='参考→', bg=self._bg(sd), fg=THEME['text_light'],
                        font=('Microsoft YaHei',8)).pack(side='left', padx=(5,5))
            if hkey != 'short':
                for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['省道_BCR']),
                                           ('成本万/km','km成本',default_targets[hkey]['省道_km成本'])]:
                    tk.Label(srd, text=f'{label} ', bg=self._bg(sd), font=('Microsoft YaHei',9)).pack(side='left')
                    if suffix == 'BCR':
                        v = tk.StringVar(value=str(dv))
                    else:
                        v = tk.IntVar(value=dv)
                    self.target_vars[f'{hkey}_省道_{suffix}'] = v
                    ttk.Entry(srd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))

        # 按钮 + 对比表
        r = self._row(parent, 12)
        tk.Button(r, text='💾 保存目标', command=self._save_targets,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=15, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='🔄 对比现状', command=self._compare_targets,
                 font=('Microsoft YaHei', 10), padx=10).pack(side='left', padx=5)

        card2 = ttk.LabelFrame(parent, text='📊 目标 vs 现状对比', padding=10)
        card2.pack(fill='both', expand=True, padx=15, pady=5)
        cols = ('维度','道路','指标','当前值','短期目标','中期目标','长期目标')
        self.target_tree = ttk.Treeview(card2, columns=cols, show='headings', height=10)
        for i,c in enumerate(cols):
            self.target_tree.heading(c, text=c)
            self.target_tree.column(c, width=105, anchor='center')
        self.target_tree.pack(fill='both', expand=True)

    def _save_targets(self):
        cfg = self.config
        cfg['targets'] = {k:v.get() for k,v in self.target_vars.items()}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.mark_step_done(3)
        self.status_var.set('短期/中期/长期养护目标已保存')
        messagebox.showinfo('成功','养护目标已保存到配置文件')

    def _compare_targets(self):
        df = self._get_data('全部')
        if df.empty: return
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        def rt(r):
            if pd.isna(r): return '其他'
            s = str(r); return '国道' if s.startswith('G') else ('省道' if s.startswith('S') else '其他')
        if '路线编码' in df.columns: df['道路类型'] = df['路线编码'].apply(rt)
        if '路段长度km' not in df.columns: df['路段长度km'] = 1.0
        self.target_tree.delete(*self.target_tree.get_children())

        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            if rd.empty: continue
            t = rd['路段长度km'].sum()
            # 技术指标
            w_pqi = (rd['PQI'] * rd['路段长度km']).sum() / t if t>0 else 0
            good_len = rd[rd['PQI']>=80]['路段长度km'].sum() if 'PQI' in rd.columns else 0
            good_rate = good_len/t*100 if t>0 else 0
            # 经济指标(年均养护成本估算)
            width = rd['路面宽度'].mean() if '路面宽度' in rd.columns else 7
            # 年均养护成本 = 日常保养 + 预防 + 改造 按比例加权
            # 日常30元/m² × 80% + 预防160元/m² × 15% + 改造319元/m² × 5%
            avg_unit = 30*0.8 + 160*0.15 + 319*0.05  # ≈ 64元/m²
            annual_cost = t * 1000 * width * avg_unit / 10000  # 年养护费(万元)
            km_cost = annual_cost / t  # 每公里年均成本(万元/km)
            from src.decision.cost_model import calc_bcr_ratio
            bcr = calc_bcr_ratio(rd, annual_cost) if annual_cost>0 else 0

            for metric, cur_val, suffix, is_target in [
                ('加权PQI', w_pqi, 'PQI', True), ('优良路率(%)', good_rate, '优良路率', True),
                ('B/C比(参考)', bcr, 'BCR', False), ('每km成本(万,参考)', km_cost, 'km成本', False)
            ]:
                if is_target:
                    short_t = self.target_vars.get(f'short_{road}_{suffix}', tk.IntVar(value=0)).get()
                    mid_t   = self.target_vars.get(f'mid_{road}_{suffix}', tk.IntVar(value=0)).get()
                    long_t  = self.target_vars.get(f'long_{road}_{suffix}', tk.IntVar(value=0)).get()
                    if suffix == 'BCR':
                        cur_fmt = f'{cur_val:.2f}'
                        s_fmt = f'{float(short_t):.2f}'
                        m_fmt = f'{float(mid_t):.2f}'
                        l_fmt = f'{float(long_t):.2f}'
                    else:
                        cur_fmt = f'{cur_val:.1f}'; s_fmt = f'{short_t}'; m_fmt = f'{mid_t}'; l_fmt = f'{long_t}'
                else:
                    cur_fmt = f'{cur_val:.2f}' if suffix == 'BCR' else f'{cur_val:.1f}'
                    s_fmt = m_fmt = l_fmt = '参考'
                self.target_tree.insert('','end',values=('技术/经济',road,metric,cur_fmt,s_fmt,m_fmt,l_fmt))
        self.status_var.set('目标对比完成')

    # ══════════════════════════════════════════════════════════════════════════
    def _build_page4(self, parent):
        # 可滚动
        cvs = tk.Canvas(parent, bg=THEME['bg'], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=cvs.yview)
        cvs.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y'); cvs.pack(side='left', fill='both', expand=True)
        sf = tk.Frame(cvs, bg=THEME['bg'])
        wid = cvs.create_window((0,0), window=sf, anchor='nw', tags=('sframe',))
        def _cfg(e):
            cvs.itemconfig(wid, width=e.width)
            cvs.configure(scrollregion=cvs.bbox('all'))
        cvs.bind('<Configure>', _cfg)
        sf.bind('<Configure>', lambda e: cvs.configure(scrollregion=cvs.bbox('all')))

        self._section_title(sf, '⚙️ 对策模型')
        self._section_sub(sf, '四个模型统一配置面板')

        # 一、衰减率标定
        card0 = self._card(sf, '一、衰减率标定 — PQI(t)=PQI₀×e^(-k×t)')
        r = self._row(card0)
        tk.Label(r, text='县份：', bg=THEME['card'], font=('Microsoft YaHei',9)).pack(side='left')
        self.model_county_var = tk.StringVar(value='全部')
        self.model_county_cb = ttk.Combobox(r, textvariable=self.model_county_var, width=12, state='readonly', values=['全部'])
        self.model_county_cb.pack(side='left', padx=8)
        tk.Button(r, text='计算衰减率', command=self._calc_decay, bg=THEME['accent'], fg='white',
                 font=('Microsoft YaHei',9), padx=10, cursor='hand2').pack(side='left', padx=8)
        cols = ('路面类型','技术等级','PQI衰减k','PCI衰减k','RQI衰减k','样本数')
        self.decay_tree = ttk.Treeview(card0, columns=cols, show='headings', height=5)
        for c in cols: self.decay_tree.heading(c, text=c); self.decay_tree.column(c, width=100, anchor='center')
        self.decay_tree.pack(fill='x', pady=(5,0))

        # 二、触发阈值
        card = self._card(sf, '二、养护触发阈值')
        self.trigger_vars = {}
        tk.Label(card, text='【路面改造】满足任一条件即触发', bg=THEME['card'],
                fg=THEME['accent'], font=('Microsoft YaHei', 9, 'bold')).pack(anchor='w')
        h = self._row(card, 3)
        for t,w in [('路面类型',10),('技术等级',10),('PCI',6),('PQI',6),('RQI',6)]:
            tk.Label(h, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,g, dpci,dpqi,drqi in [
            ('路面改造','沥青路面','一级公路',80,80,80),('路面改造','沥青路面','二级及以下',75,75,75),
            ('路面改造','水泥路面','一级公路',80,80,80),('路面改造','水泥路面','二级及以下',75,75,75),
        ]:
            r = self._row(card, 2)
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=g, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PCI',dpci),('PQI',dpqi),('RQI',drqi)]:
                v = tk.IntVar(value=dv); self.trigger_vars[f'{m}_{pt}_{g}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=6).pack(side='left')
                en = tk.BooleanVar(value=True)
                self.trigger_vars[f'{m}_{pt}_{g}_{idx}_启用'] = en
                tk.Checkbutton(r, text='', variable=en, bg=THEME['card'], width=2).pack(side='left')

        tk.Label(card, text='【预防性养护】不满足路面改造时，条件触发', bg=THEME['card'],
                fg=THEME['success'], font=('Microsoft YaHei', 9, 'bold')).pack(anchor='w', pady=(10,0))
        h2 = self._row(card, 3)
        for t,w in [('路面类型',10),('技术等级',10),('PCI下限',7),('PCI上限',7),('PQI≥',5)]:
            tk.Label(h2, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,g, plo,phi,pqi in [
            ('预防性养护','沥青路面','一级公路',80,90,80),('预防性养护','沥青路面','二级及以下',78,85,75),
            ('预防性养护','水泥路面','一级公路',80,90,80),('预防性养护','水泥路面','二级及以下',78,85,75),
        ]:
            r = self._row(card, 2)
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=g, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PCI低',plo),('PCI高',phi),('PQI',pqi)]:
                v = tk.IntVar(value=dv); self.trigger_vars[f'{m}_{pt}_{g}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=6).pack(side='left')
                en = tk.BooleanVar(value=True)
                self.trigger_vars[f'{m}_{pt}_{g}_{idx}_启用'] = en
                tk.Checkbutton(r, text='', variable=en, bg=THEME['card'], width=2).pack(side='left')

        # 三、回调值
        card2 = self._card(sf, '三、养护后PQI/PCI/RQI回调值')
        self.callback_vars = {}
        h3 = self._row(card2, 3)
        for t,w in [('养护类型',12),('路面类型',10),('PQI回升值',9),('PCI回升值',9),('RQI回升值',9)]:
            tk.Label(h3, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,dpqi,dpci,drqi in [
            ('路面改造','沥青路面',92,92,93),('路面改造','水泥路面',88,88,90),
            ('预防性养护','沥青路面',89,89,91),('预防性养护','水泥路面',86,86,88),
        ]:
            r = self._row(card2, 2)
            tk.Label(r, text=m, width=12, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PQI',dpqi),('PCI',dpci),('RQI',drqi)]:
                v = tk.IntVar(value=dv); self.callback_vars[f'{m}_{pt}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=8).pack(side='left')

        # 四、养护方案单价明细表（双击单价可编辑）
        card3 = self._card(sf, '四、养护方案单价明细（双击单价可编辑）')
        card3.configure(height=300)
        cols_p = ('路面类型','养护工程','技术等级','养护方案','单价')
        self.price_tree = ttk.Treeview(card3, columns=cols_p, show='headings', height=15)
        for ct,w in [('路面类型',70),('养护工程',80),('技术等级',70),('养护方案',320),('单价',70)]:
            self.price_tree.heading(ct, text=ct); self.price_tree.column(ct, width=w, anchor='w' if ct=='养护方案' else 'center')
        sv_p = ttk.Scrollbar(card3, orient='vertical', command=self.price_tree.yview)
        self.price_tree.configure(yscrollcommand=sv_p.set)
        self.price_tree.pack(side='left', fill='both', expand=True); sv_p.pack(side='right', fill='y')
        self.price_vars = {}
        for pt,mt,tg,plan,price in [
            ('沥青路面','结构性修复','一级','4cm GAC-13(改性)+6cm GAC-20(改性)+1cm同步碎石封层+基层处理(30%)',326),
            ('沥青路面','结构性修复','二级','4cm GAC-13(改性)+6cm GAC-20+1cm同步碎石封层+基层处理(30%)',319),
            ('沥青路面','结构性修复','三级','4cm GAC-13(改性)+6cm GAC-20+1cm同步碎石封层+基层处理(30%)',319),
            ('沥青路面','功能性修复','一级','5cm GAC-13(改性)+1cm同步碎石封层+病害处理(10%)',161),
            ('沥青路面','功能性修复','二级','4cm GAC-13(改性)+改性乳化沥青粘层+病害处理(10%)',109),
            ('沥青路面','功能性修复','三级','4cm GAC-13(改性)+改性乳化沥青粘层+病害处理(10%)',109),
            ('沥青路面','预防养护','一级','1.2cm冷拌超粘微表处+表层病害处理(5%)',48),
            ('沥青路面','预防养护','二级','1.2cm冷拌超粘微表处+表层病害处理(5%)',30),
            ('沥青路面','预防养护','三级','1cm微表处+表层病害处理(5%)',30),
            ('水泥路面','结构性修复','一级','水泥:碎石化+封层+C40砼32cm / 沥青:共振+封层+10cmGAC25+6cmGAC20+4cmGAC13',268),
            ('水泥路面','结构性修复','二级','水泥:碎石化+封层+C40砼30cm / 沥青:共振+封层+10cmGAC25+4cmGAC13',253),
            ('水泥路面','结构性修复','三级','水泥:碎石化+封层+C40砼28cm / 沥青:共振+封层+8cmGAC25+4cmGAC13',238),
            ('水泥路面','功能性修复','一级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',161),
            ('水泥路面','功能性修复','二级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',160),
            ('水泥路面','功能性修复','三级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',157),
            ('沥青路面','日常养护','全部','日常保养维护',30),
            ('水泥路面','日常养护','全部','日常保养维护',25),
        ]:
            self.price_tree.insert('','end',values=(pt,mt,tg,plan,str(price)))
            self.price_vars[f'{mt}_{pt}_{tg}'] = tk.IntVar(value=price)
        self.price_tree.bind('<Double-1>', self._on_price_dclick)

        # 按钮
        r = self._row(sf, 15)
        tk.Button(r, text='💾 保存全部配置', command=self._save_policy_config,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10),
                 padx=18, pady=4, cursor='hand2').pack(side='left', padx=20)
        tk.Button(r, text='↺ 恢复默认', command=self._reset_policy_config,
                 font=('Microsoft YaHei', 9), padx=12).pack(side='left', padx=5)

    def _calc_decay(self):
        from src.decay_calculator import get_calibration_table
        df = self._get_data(self.model_county_var.get() if hasattr(self,'model_county_var') else '全部')
        if df.empty: return
        cty = None if self.model_county_var.get()=='全部' else self.model_county_var.get()
        table = get_calibration_table(df, cty)
        self.decay_tree.delete(*self.decay_tree.get_children())
        for row in table: self.decay_tree.insert('','end',values=row)
        self.status_var.set('衰减率标定完成')

    def _on_price_dclick(self, event):
        if self.price_tree.identify_region(event.x,event.y) != 'cell': return
        if self.price_tree.identify_column(event.x) != '#5': return
        item = self.price_tree.identify_row(event.y)
        if not item: return
        vals = self.price_tree.item(item,'values')
        bbox = self.price_tree.bbox(item,'#5')
        if not bbox: return
        e = ttk.Entry(self.price_tree, width=8)
        e.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        e.insert(0,''.join(c for c in str(vals[4]) if c.isdigit()))
        e.select_range(0,'end'); e.focus_set()
        def save(ev=None):
            e.destroy()
            nv = e.get().strip()
            if nv and nv.isdigit():
                nv2 = list(vals); nv2[4] = nv
                self.price_tree.item(item,values=nv2)
                pt,mt,tg = vals[0],vals[1],vals[2]
                for pk in [f'{mt}_{pt}_{tg}']:
                    if pk in self.price_vars: self.price_vars[pk].set(int(nv))
        e.bind('<Return>',save); e.bind('<FocusOut>',save)

    def _save_policy_config(self):
        cfg = self.config
        cfg['triggers'] = {k:v.get() for k,v in self.trigger_vars.items()}
        cfg['callbacks'] = {k:v.get() for k,v in self.callback_vars.items()}
        cfg['prices'] = {k:v.get() for k,v in self.price_vars.items()}
        if hasattr(self, 'priority_vars'):
            cfg['priority_weights'] = {k:v.get() for k,v in self.priority_vars.items()}
        if set_maintenance_callback:
            cb = {}
            for ks, var in self.callback_vars.items():
                ps = ks.split('_'); mt=ps[0]; pt=ps[1]; idx=ps[2]
                if mt not in cb: cb[mt] = {}
                if pt not in cb[mt]: cb[mt][pt] = {}
                cb[mt][pt][idx] = var.get()
            set_maintenance_callback(cb); cfg['maintenance_callback'] = cb
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.mark_step_done(5)
        self.status_var.set('养护对策配置已保存')
        messagebox.showinfo('成功','养护对策配置已保存！\n\n- 触发阈值\n- 回调值\n- 单价\n\n参数即时生效，可执行需求分析。')

    def _reset_policy_config(self):
        if not messagebox.askyesno('确认','确定恢复默认？'): return
        for k,v in {
            '路面改造_沥青路面_一级公路_PCI':80,'路面改造_沥青路面_一级公路_PQI':80,'路面改造_沥青路面_一级公路_RQI':80,
            '路面改造_沥青路面_二级及以下_PCI':75,'路面改造_沥青路面_二级及以下_PQI':75,'路面改造_沥青路面_二级及以下_RQI':75,
            '路面改造_水泥路面_一级公路_PCI':80,'路面改造_水泥路面_一级公路_PQI':80,'路面改造_水泥路面_一级公路_RQI':80,
            '路面改造_水泥路面_二级及以下_PCI':75,'路面改造_水泥路面_二级及以下_PQI':75,'路面改造_水泥路面_二级及以下_RQI':75,
            '预防性养护_沥青路面_一级公路_PCI低':80,'预防性养护_沥青路面_一级公路_PCI高':90,'预防性养护_沥青路面_一级公路_PQI':80,
            '预防性养护_沥青路面_二级及以下_PCI低':78,'预防性养护_沥青路面_二级及以下_PCI高':85,'预防性养护_沥青路面_二级及以下_PQI':75,
            '预防性养护_水泥路面_一级公路_PCI低':80,'预防性养护_水泥路面_一级公路_PCI高':90,'预防性养护_水泥路面_一级公路_PQI':80,
            '预防性养护_水泥路面_二级及以下_PCI低':78,'预防性养护_水泥路面_二级及以下_PCI高':85,'预防性养护_水泥路面_二级及以下_PQI':75,
        }.items():
            if k in self.trigger_vars: self.trigger_vars[k].set(v)
        for k,v in {
            '路面改造_沥青路面_PQI':92,'路面改造_沥青路面_PCI':92,'路面改造_沥青路面_RQI':93,
            '路面改造_水泥路面_PQI':88,'路面改造_水泥路面_PCI':88,'路面改造_水泥路面_RQI':90,
            '预防性养护_沥青路面_PQI':89,'预防性养护_沥青路面_PCI':89,'预防性养护_沥青路面_RQI':91,
            '预防性养护_水泥路面_PQI':86,'预防性养护_水泥路面_PCI':86,'预防性养护_水泥路面_RQI':88,
        }.items():
            if k in self.callback_vars: self.callback_vars[k].set(v)
        for k,v in {
            '路面改造_沥青路面':319,'路面改造_水泥路面':299,'预防性养护_沥青路面':160,'预防性养护_水泥路面':140,
            '日常养护_沥青路面':30,'日常养护_水泥路面':25,
        }.items():
            if k in self.price_vars: self.price_vars[k].set(v)
        self.status_var.set('已恢复默认配置')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面5: 需求分析
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page5(self, parent):
        self._section_title(parent, '🔍 养护需求分析')
        self._section_sub(parent, '基于预测模型和养护对策，分析路网养护需求并排序')

        card = self._card(parent, '分析参数')
        r = self._row(card)
        tk.Label(r, text='县份：', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left')
        self.demand_county_var = tk.StringVar(value='全部')
        self.demand_county_cb = ttk.Combobox(r, textvariable=self.demand_county_var, width=12, state='readonly', values=['全部'])
        self.demand_county_cb.pack(side='left', padx=8)
        tk.Label(r, text='目标年份：', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.demand_year_var = tk.StringVar(value='2026')
        ttk.Combobox(r, textvariable=self.demand_year_var, values=[str(y) for y in range(2026,2031)], width=6).pack(side='left', padx=5)
        tk.Button(r, text='▶ 执行需求分析', command=self._run_demand,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=12, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='📋 优先排序', command=self._prioritize_demand,
                 font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=5)
        tk.Button(r, text='📥 导出', command=self._export_demand,
                 font=('Microsoft YaHei', 9), padx=8).pack(side='right')

        # 各线路加权均值表（年份横向）
        card_route = self._card(parent)
        cols_route = ('路线编码','里程(km)', '26PQI','26PCI','26RQI','27PQI','27PCI','27RQI','28PQI','28PCI','28RQI','29PQI','29PCI','29RQI','30PQI','30PCI','30RQI')
        self.route_avg_tree = ttk.Treeview(card_route, columns=cols_route, show='headings', height=6)
        for c in cols_route: self.route_avg_tree.heading(c, text=c); self.route_avg_tree.column(c, width=55, anchor='center')
        self.route_avg_tree.column('路线编码', width=70); self.route_avg_tree.column('里程(km)', width=60)
        self.route_avg_tree.pack(fill='both', expand=True)

        card2 = self._card(parent, '养护需求列表', 3, expand=True)
        cols = ('路线编码','路段起点','路段终点','里程(km)','当前PQI','预测PQI','养护类型','触发条件','费用(万元)','优先级')
        self.demand_tree = ttk.Treeview(card2, columns=cols, show='headings', height=12)
        ws = {'路线编码':85,'路段起点':65,'路段终点':65,'里程(km)':60,'当前PQI':60,'预测PQI':60,'养护类型':80,'触发条件':180,'费用(万元)':75,'优先级':55}
        for c in cols: self.demand_tree.heading(c, text=c); self.demand_tree.column(c, width=ws.get(c,70), anchor='center')
        sv = ttk.Scrollbar(card2, orient='vertical', command=self.demand_tree.yview)
        sh = ttk.Scrollbar(card2, orient='horizontal', command=self.demand_tree.xview)
        self.demand_tree.configure(yscrollcommand=sv.set, xscrollcommand=sh.set)
        self.demand_tree.pack(side='left', fill='both', expand=True)
        sv.pack(side='right', fill='y'); sh.pack(side='bottom', fill='x')
        self.demand_summary = tk.Label(parent, text='', bg=THEME['bg'], fg=THEME['text'], font=('Microsoft YaHei', 9))
        self.demand_summary.pack(anchor='w', padx=20, pady=3)

        # 多年需求汇总表
        cols_yr = ('年份','改造(km)','预防(km)','日常(km)','合计(km)')
        self.demand_year_tree = ttk.Treeview(parent, columns=cols_yr, show='headings', height=6)
        for c in cols_yr: self.demand_year_tree.heading(c, text=c); self.demand_year_tree.column(c, width=90, anchor='center')
        self.demand_year_tree.pack(fill='x', padx=20, pady=5)

    def _run_demand(self):
        df = self._get_data(self.demand_county_var.get())
        if df.empty: return
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        ty = int(self.demand_year_var.get())
        try:
            from src.decision.performance_models import calibrate_exponential_model
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)
            dr = calibrate_exponential_model(all_df)
            # 确保PCI/RQI列存在
            for c in ['PCI','RQI']:
                if c not in df.columns: df[c] = df['PQI'] if 'PQI' in df.columns else 80
            enabled_flags = {}
            if hasattr(self,'trigger_vars'):
                for k,v in self.trigger_vars.items():
                    if '_启用' in k:
                        enabled_flags[k] = bool(v.get())
            print(f'[LOG] enabled_flags count={len(enabled_flags)}')
            if enabled_flags:
                pqi_on = enabled_flags.get('路面改造_沥青路面_一级公路_PQI_启用', True)
                print(f'[LOG] PQI_启用(沥青/一级)={pqi_on}')
            result = analyze_demand(df, target_year=ty, decay_rates=dr, enabled=enabled_flags)
            def cc(r):
                ln = r.get('路段长度(km)',1); mt = r.get('养护类型','日常养护'); pt = r.get('路面类型','沥青路面')
                pk = f'{mt}_{pt}'
                pr = self.price_vars[pk].get() if hasattr(self,'price_vars') and pk in self.price_vars else {'路面改造_沥青路面':319,'预防性养护_沥青路面':160,'日常养护_沥青路面':30}.get(pk,300)
                return round(ln*1000*7*pr/10000,2)
            result['路段长度(km)'] = result.apply(lambda r: r.get('路段长度(km)',1), axis=1)
            result['估算费用(万元)'] = result.apply(cc, axis=1)
            result['养护类型'] = result['养护类型'].fillna('日常养护')
            self.demand_result_df = result
            import numpy as np
            base_df = df.copy()
            self.demand_multi_year = {}
            self.demand_snapshots = {}  # 每年末的base_df快照（含PQI/PCI/RQI）
            county_name = self.demand_county_var.get() if hasattr(self,'demand_county_var') else '全部'
            prev_result = None
            for yr in range(ty, 2031):
                # 上年修复路段根据对策模型回调PQI（衰减由analyze_demand内部处理）
                cb = {}
                if hasattr(self,'callback_vars'):
                    for k,v in self.callback_vars.items(): cb[k] = v.get()
                if prev_result is not None and not prev_result.empty and yr > ty:
                    # 所有路段 PQI/PCI/RQI 衰减1年
                    for idx in base_df.index:
                        ptype = str(base_df.at[idx,'路面类型']); tgrade = str(base_df.at[idx,'技术等级'])
                        dk = dr.get((ptype,tgrade),{})
                        for col in ['PQI','PCI','RQI']:
                            if col in base_df.columns:
                                k_val = dk.get(col,0.015) or 0.015
                                base_df.at[idx,col] = max(0, base_df.at[idx,col]*np.exp(-k_val))
                    # 修复路段回调
                    for _, row in prev_result.iterrows():
                        mt = row.get('养护类型',''); pt = row.get('路面类型','沥青路面')
                        if mt in ('路面改造','预防性养护'):
                            m = ((base_df['路线编码']==row['路线编码'])&(base_df['路段起点'].astype(str)==str(row['路段起点']))&(base_df['路段终点'].astype(str)==str(row['路段终点'])))
                            if m.any():
                                for col in ['PQI','PCI','RQI']:
                                    new_val = cb.get(f'{mt}_{pt}_{col}', 92 if mt=='路面改造' else 89)
                                    base_df.loc[m,col] = new_val
                yr_df = analyze_demand(base_df, target_year=2026, decay_rates=dr, enabled=enabled_flags)
                yr_df['路段长度(km)'] = yr_df.apply(lambda r: r.get('路段长度(km)',1), axis=1)
                yr_df['养护类型'] = yr_df['养护类型'].fillna('日常养护')
                # 计算费用（使用对策模型单价）
                def calc(row):
                    ln=row.get('路段长度(km)',1); mt=row.get('养护类型','日常养护'); pt=row.get('路面类型','沥青路面')
                    tg=row.get('技术等级','二级公路')
                    type_map={'路面改造':'结构性修复','预防性养护':'预防养护'}
                    mt_k=type_map.get(mt,'日常养护')
                    tg_k='一级' if '一' in str(tg) else ('二级' if '二' in str(tg) else '三级')
                    pk=f'{mt_k}_{pt}_{tg_k}'
                    pr=300
                    if hasattr(self,'price_vars') and pk in self.price_vars: pr=self.price_vars[pk].get()
                    return round(ln*1000*7*pr/10000,2)
                yr_df['估算费用(万元)'] = yr_df.apply(calc, axis=1)
                self.demand_multi_year[yr] = yr_df
                self.demand_snapshots[yr] = base_df.copy()  # 快照当前base_df
                prev_result = yr_df
                rk = yr_df[yr_df['养护类型']=='路面改造']['路段长度(km)'].sum()
                pk = yr_df[yr_df['养护类型']=='预防性养护']['路段长度(km)'].sum()
                dk = yr_df[yr_df['养护类型']=='日常养护']['路段长度(km)'].sum() if '日常养护' in yr_df['养护类型'].values else 0
                print(f'[DEMAND-{county_name}] {yr}: reform={rk:.1f}km prevent={pk:.1f}km (total={len(yr_df)}条)')
            # 填充多年汇总表
            self.demand_year_tree.delete(*self.demand_year_tree.get_children())
            for yr in sorted(self.demand_multi_year.keys()):
                ydf = self.demand_multi_year[yr]
                rk = ydf[ydf['养护类型']=='路面改造']['路段长度(km)'].sum()
                pk = ydf[ydf['养护类型']=='预防性养护']['路段长度(km)'].sum()
                dk = ydf[ydf['养护类型']=='日常养护']['路段长度(km)'].sum() if '日常养护' in ydf['养护类型'].values else 0
                self.demand_year_tree.insert('','end',values=(f'{yr}年',f'{rk:.1f}',f'{pk:.1f}',f'{dk:.1f}',f'{rk+pk+dk:.1f}'))
            # 各线路加权均值（年份横向）
            self.route_avg_tree.delete(*self.route_avg_tree.get_children())
            for route, group in df.groupby('路线编码'):
                rd0 = group; t = rd0['路段长度km'].sum()
                if t <= 0: continue
                vals = [route, f'{t:.1f}']
                for yr in range(ty, 2031):
                    if yr in self.demand_snapshots:
                        snap = self.demand_snapshots[yr]
                        sr = snap[snap['路线编码']==route]
                        for col in ['PQI','PCI','RQI']:
                            if col in sr.columns and sr['路段长度km'].sum() > 0:
                                wv = (sr[col]*sr['路段长度km']).sum()/sr['路段长度km'].sum()
                                vals.append(f'{wv:.1f}')
                            else:
                                vals.append('-')
                self.route_avg_tree.insert('','end',values=vals)
            self._refresh_demand_tree(result, ty)
            def km_of(df, mt):
                s = df[df['养护类型']==mt]['路段长度(km)'].sum() if '路段长度(km)' in df.columns else len(df[df['养护类型']==mt])
                return f'{s:.1f}km'
            self.demand_summary.config(text=f'总路段：{len(result)}条({result["路段长度(km)"].sum() if "路段长度(km)" in result.columns else 0:.1f}km) | 路面改造：{len(result[result["养护类型"]=="路面改造"])}条({km_of(result,"路面改造")}) | 预防性养护：{len(result[result["养护类型"]=="预防性养护"])}条({km_of(result,"预防性养护")}) | 日常养护：{len(result[result["养护类型"]=="日常养护"])}条({km_of(result,"日常养护")})')
            self.mark_step_done(6)
            self.status_var.set(f'需求分析完成 — {len(result)}个需求')
        except Exception as e:
            messagebox.showerror('错误', str(e))

    def _prioritize_demand(self):
        if self.demand_result_df is None or self.demand_result_df.empty: return
        from src.decision.maintenance_demand import prioritize_demand
        self.demand_result_df = prioritize_demand(self.demand_result_df)
        self._refresh_demand_tree(self.demand_result_df, int(self.demand_year_var.get()))
        self.status_var.set('需求已按优先级排序')

    def _refresh_demand_tree(self, result, ty):
        self.demand_tree.delete(*self.demand_tree.get_children())
        for _, row in result.iterrows():
            self.demand_tree.insert('','end',values=(
                row.get('路线编码',''), row.get('路段起点',''), row.get('路段终点',''),
                f"{row.get('路段长度(km)',1):.2f}", f"{row.get('当前PQI',0):.1f}",
                f"{row.get(f'{ty}年预测PQI',0):.1f}", row.get('养护类型',''),
                row.get('触发原因',''), f"{row.get('估算费用(万元)',0):.2f}",
                f"{row.get('优先级评分',0):.1f}"))

    def _export_demand(self):
        if self.demand_result_df is None or self.demand_result_df.empty:
            messagebox.showwarning('提示','请先执行需求分析'); return
        path = filedialog.asksaveasfilename(title='导出', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
        if path: self.demand_result_df.to_excel(path, index=False); messagebox.showinfo('成功','已导出')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面6: 项目库库
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page6(self, parent):
        self._section_title(parent, '📊 投资规划')
        self._section_sub(parent, '经济指标 + 多年动态优化（约束 vs 无约束）+ 项目库')

        # 县份选择
        r0 = self._row(parent)
        tk.Label(r0, text='选择区域：', bg=THEME['bg'], font=('Microsoft YaHei',9)).pack(side='left')
        self.dp_county_var = tk.StringVar(value='全部')
        self.dp_county_cb = ttk.Combobox(r0, textvariable=self.dp_county_var, width=12, state='readonly', values=['全部'])
        self.dp_county_cb.pack(side='left', padx=5)
        self.dp_county_label = tk.Label(r0, text='', bg=THEME['bg'], fg=THEME['accent'], font=('Microsoft YaHei',9,'bold'))
        self.dp_county_label.pack(side='left', padx=10)

        # 经济指标面板
        card_econ = self._card(parent)
        r_econ = self._row(card_econ)
        tk.Button(r_econ, text='计算经济指标', command=self._run_invest_econ, bg=THEME['accent'],
                 fg='white', font=('Microsoft YaHei',9), padx=10).pack(side='left')
        cols_econ = ('道路类型','加权PQI','优良路率','交通量','路龄','年养护费(万)','每km成本','B/C','单位PQI提升','LCC-NPV(万)')
        self.benefit_tree = ttk.Treeview(card_econ, columns=cols_econ, show='headings', height=4)
        for ct in cols_econ: self.benefit_tree.heading(ct, text=ct); self.benefit_tree.column(ct, width=92, anchor='center')
        self.benefit_tree.pack(fill='both', expand=True, pady=(5,0))

        # 多年动态优化
        card_opt = self._card(parent, '多年动态优化')
        c1 = self._row(card_opt)
        tk.Label(c1, text='规划年限：', bg=THEME['card'], font=('Microsoft YaHei',9)).pack(side='left')
        self.dp_years_var = tk.IntVar(value=5)
        ttk.Entry(c1, textvariable=self.dp_years_var, width=5).pack(side='left', padx=(0,15))
        self.dp_constraint_var = tk.BooleanVar(value=True)
        tk.Checkbutton(c1, text='资金均衡', variable=self.dp_constraint_var,
                      bg=THEME['card'], font=('Microsoft YaHei',8)).pack(side='left', padx=5)
        tk.Label(c1, text='均衡程度%：', bg=THEME['card'], font=('Microsoft YaHei',8)).pack(side='left')
        self.dp_balance_var = tk.IntVar(value=50)
        tk.Scale(c1, from_=0, to=100, resolution=5, orient='horizontal',
                variable=self.dp_balance_var, length=150, showvalue=True).pack(side='left', padx=5)
        tk.Button(c1, text='执行优化', command=self._run_dynamic_planning,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei',10), padx=12, cursor='hand2').pack(side='right')
        cols_dp = ('年份','改造需求(km)','预防需求(km)','计划改造(km)','计划预防(km)','计划投入(万元)')
        self.dp_tree = ttk.Treeview(card_opt, columns=cols_dp, show='headings', height=6)
        for ct in cols_dp: self.dp_tree.heading(ct, text=ct); self.dp_tree.column(ct, width=130, anchor='center')
        self.dp_tree.pack(fill='both', expand=True, pady=(5,0))

        # 年度项目库
        card_proj = self._card(parent, '年度项目库（路面改造+预防养护）', expand=True)
        rp = self._row(card_proj)
        tk.Label(rp, text='生成年份：', bg=THEME['card'], font=('Microsoft YaHei',9)).pack(side='left')
        self.proj_year_var = tk.IntVar(value=2026)
        for y in range(2026,2031):
            tk.Radiobutton(rp, text=str(y), variable=self.proj_year_var, value=y,
                          bg=THEME['card']).pack(side='left', padx=5)
        tk.Button(rp, text='生成项目库', command=self._gen_year_projects,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei',9), padx=10, cursor='hand2').pack(side='left', padx=10)
        tk.Button(rp, text='导出Excel', command=lambda: self._export_tree(self.proj_detail_tree),
                 font=('Microsoft YaHei',9)).pack(side='left', padx=5)
        cols_pd = ('路线','起点桩号','终点桩号','长度(km)','路面类型','技术等级','PQI','PCI','RQI','养护类型')
        self.proj_detail_tree = ttk.Treeview(card_proj, columns=cols_pd, show='headings', height=8)
        for c in cols_pd: self.proj_detail_tree.heading(c, text=c); self.proj_detail_tree.column(c, width=75, anchor='center')
        sv_pd = ttk.Scrollbar(card_proj, orient='vertical', command=self.proj_detail_tree.yview)
        self.proj_detail_tree.configure(yscrollcommand=sv_pd.set)
        self.proj_detail_tree.pack(side='left', fill='both', expand=True)
        sv_pd.pack(side='right', fill='y')

        # 项目库
        card = self._card(parent, '工程项目库')
        r = self._row(card)
        tk.Button(r, text='📥 从需求导入', command=self._pool_import_demand,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 9), padx=10, cursor='hand2').pack(side='left', padx=3)
        tk.Button(r, text='📤 导出', command=self._pool_export, font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=3)
        tk.Button(r, text='📥 导入', command=self._pool_import, font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=3)
        tk.Button(r, text='🗑️ 清空', command=self._pool_clear, font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=3)
        tk.Button(r, text='📋 年度计划', command=self._pool_gen_plan, font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=3)

        card2 = self._card(parent, '项目列表', 3, expand=True)
        cols = ('项目编号','路线编码','养护类型','计划年度','里程(km)','估算费用(万元)','优先级','状态')
        self.pool_tree = ttk.Treeview(card2, columns=cols, show='headings', height=15)
        ws = {'项目编号':140,'路线编码':85,'养护类型':80,'计划年度':65,'里程(km)':65,'估算费用(万元)':90,'优先级':55,'状态':60}
        for c in cols: self.pool_tree.heading(c, text=c); self.pool_tree.column(c, width=ws.get(c,65), anchor='center')
        sv = ttk.Scrollbar(card2, orient='vertical', command=self.pool_tree.yview)
        self.pool_tree.configure(yscrollcommand=sv.set)
        self.pool_tree.pack(side='left', fill='both', expand=True)
        sv.pack(side='right', fill='y')

    def _run_invest_econ(self):
        df = self._get_data('全部')
        if df.empty: return
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        if '路段长度km' not in df.columns: df['路段长度km'] = 1.0
        def rt(r):
            s = str(r); return '国道' if s.startswith('G') else ('省道' if s.startswith('S') else '其他')
        if '路线编码' in df.columns: df['道路类型'] = df['路线编码'].apply(rt)
        from src.decision.cost_model import calc_weighted_pqi, calc_good_road_rate, calc_bcr_ratio, calc_unit_pqi_cost, calc_km_cost, calc_lcc
        self.benefit_tree.delete(*self.benefit_tree.get_children())
        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            if rd.empty: continue
            t = rd['路段长度km'].sum(); w = rd['路面宽度'].mean() if '路面宽度' in rd.columns else 7
            avg_unit = 30*0.8 + 160*0.15 + 319*0.05
            ac = t * 1000 * w * avg_unit / 10000
            self.benefit_tree.insert('','end',values=(road, f'{calc_weighted_pqi(rd):.1f}', f'{calc_good_road_rate(rd):.1f}%',
                int(rd['交通量'].mean()) if '交通量' in rd.columns else 5000,
                f'{rd["路龄"].mean():.1f}' if '路龄' in rd.columns else '5.0',
                f'{ac:.0f}', f'{calc_km_cost(ac,rd):.1f}', f'{calc_bcr_ratio(rd,ac):.2f}',
                f'{calc_unit_pqi_cost(rd,ac):.2f}', f'{calc_lcc(rd)["NPV(万元)"]:.0f}'))
        self.status_var.set('经济指标计算完成')

    def _calc_seg_decay(self, segs):
        """计算逐路段衰减系数 k = 0.015 × 路龄因子 × 交通量因子"""
        import numpy as np
        k_base = 0.015
        age = segs['路龄'].values if '路龄' in segs.columns else np.full(len(segs), 5.0)
        aadt = segs['交通量'].values if '交通量' in segs.columns else np.full(len(segs), 5000.0)
        age = np.nan_to_num(age.astype(float), nan=5.0)
        aadt = np.nan_to_num(aadt.astype(float), nan=5000.0)
        age_factor = 1 + (age - 5) * 0.03
        traffic_factor = 1 + (aadt / 5000 - 1) * 0.25
        age_factor = np.clip(age_factor, 0.5, 2.0)
        traffic_factor = np.clip(traffic_factor, 0.5, 2.0)
        k_arr = k_base * age_factor * traffic_factor
        return np.clip(k_arr, 0.005, 0.05)

    def _cluster_segments(self, segs, need_mask):
        """将需要养护的路段按路线+连续桩号聚类，返回聚类列表"""
        import pandas as pd
        clusters = []
        need_df = segs[need_mask].copy()
        if need_df.empty:
            return clusters
        # 按路线编码分组
        for route, group in need_df.groupby('路线编码'):
            # 按路段起点排序
            group = group.sort_values('路段起点')
            # 贪心聚类：连续桩号合并
            current_cluster = None
            for _, row in group.iterrows():
                if current_cluster is None:
                    current_cluster = {
                        'route': route,
                        'segments': [row.name],
                        'length': row['路段长度km'],
                        'cost': row['路段长度km'] * 1000 * row['路面宽度'] * 319 / 10000,
                        'benefit': row.get('benefit', 0),
                        'start': str(row.get('路段起点', '')),
                        'end': str(row.get('路段终点', '')),
                    }
                else:
                    # 检查是否连续（当前段起点 ≈ 上一段终点）
                    try:
                        prev_end = float(str(current_cluster['end']).replace('K','').replace('+',''))
                        curr_start = float(str(row.get('路段起点','')).replace('K','').replace('+',''))
                        is_contiguous = abs(curr_start - prev_end) < 0.2  # 200m间隙内算连续
                    except:
                        is_contiguous = False
                    if is_contiguous:
                        current_cluster['segments'].append(row.name)
                        current_cluster['length'] += row['路段长度km']
                        current_cluster['cost'] += row['路段长度km'] * 1000 * row['路面宽度'] * 319 / 10000
                        current_cluster['benefit'] += row.get('benefit', 0)
                        current_cluster['end'] = str(row.get('路段终点', ''))
                    else:
                        clusters.append(current_cluster)
                        current_cluster = {
                            'route': route,
                            'segments': [row.name],
                            'length': row['路段长度km'],
                            'cost': row['路段长度km'] * 1000 * row['路面宽度'] * 319 / 10000,
                            'benefit': row.get('benefit', 0),
                            'start': str(row.get('路段起点', '')),
                            'end': str(row.get('路段终点', '')),
                        }
            if current_cluster:
                clusters.append(current_cluster)
        # 计算每个聚类的BCR
        for cl in clusters:
            cl['bcr'] = cl['benefit'] / cl['cost'] if cl['cost'] > 0 else 0
        return clusters

    def _run_dynamic_planning(self):
        county = self.dp_county_var.get() if hasattr(self,'dp_county_var') else '全部'
        df = self._get_data(county)
        if df.empty: messagebox.showwarning('提示','请先加载数据'); return
        if self.demand_result_df is None or self.demand_result_df.empty:
            messagebox.showwarning('提示','请先在需求分析中执行分析'); return
        import numpy as np
        self.dp_county_label.config(text=f'当前: {county}')
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        for col in ['路段长度km','交通量','车道数','路面宽度','PQI','路龄']:
            dv = {'路段长度km':1,'交通量':5000,'车道数':2,'路面宽度':7,'PQI':80,'路龄':5}[col]
            if col not in df.columns: df[col] = dv
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(dv)
        years = self.dp_years_var.get()
        use_balance = self.dp_constraint_var.get() if hasattr(self,'dp_constraint_var') else True
        balance = self.dp_balance_var.get() if hasattr(self,'dp_balance_var') else 50
        segs = df; total_km = segs['路段长度km'].sum()
        k_arr = self._calc_seg_decay(segs)
        pm = {v: i for i, v in enumerate(segs.index)}
        # 优先使用多年度需求分析结果
        has_multi = hasattr(self,'demand_multi_year') and self.demand_multi_year
        dm_year1 = self.demand_multi_year.get(2026, self.demand_result_df) if has_multi else self.demand_result_df
        dm_reform_km = dm_year1[dm_year1['养护类型']=='路面改造']['路段长度(km)'].sum() if '路段长度(km)' in dm_year1.columns else 0
        dm_prevent_km = dm_year1[dm_year1['养护类型']=='预防性养护']['路段长度(km)'].sum() if '路段长度(km)' in dm_year1.columns else 0
        print(f'[DP] multi_year keys: {list(self.demand_multi_year.keys()) if has_multi else "NONE"}')
        print(f'[DP] Year 2026 reform_km from dm={dm_reform_km:.1f} prevent={dm_prevent_km:.1f}')
        if has_multi:
            for y, ydf in self.demand_multi_year.items():
                rk = ydf[ydf['养护类型']=='路面改造']['路段长度(km)'].sum()
                pk = ydf[ydf['养护类型']=='预防性养护']['路段长度(km)'].sum()
                print(f'[DP]   {y}: reform={rk:.1f}km prevent={pk:.1f}km')
        self.dp_tree.delete(*self.dp_tree.get_children())

        # 统一表头
        cols = ('年份','改造需求(km)','改造经费(万)','预防需求(km)','预防经费(万)','合计(km)','合计经费(万)','目标对比')
        self.dp_tree['columns'] = cols
        for c in cols: self.dp_tree.heading(c, text=c); self.dp_tree.column(c, width=88, anchor='center')
        target_pqi = 90; target_rate = 88
        if hasattr(self,'target_vars'):
            target_pqi = self.target_vars.get('mid_国道_PQI', tk.IntVar(value=90)).get()
            target_rate = self.target_vars.get('mid_国道_优良路率', tk.IntVar(value=88)).get()
        self.dp_tree.column('目标对比', width=180)
        for yr in range(2026, 2026+years):
            if has_multi and yr in self.demand_multi_year:
                ydf = self.demand_multi_year[yr]
                rk = ydf[ydf['养护类型']=='路面改造']['路段长度(km)'].sum()
                rc = ydf[ydf['养护类型']=='路面改造']['估算费用(万元)'].sum() if '估算费用(万元)' in ydf.columns else 0
                pk = ydf[ydf['养护类型']=='预防性养护']['路段长度(km)'].sum()
                pc = ydf[ydf['养护类型']=='预防性养护']['估算费用(万元)'].sum() if '估算费用(万元)' in ydf.columns else 0
            else:
                rk=dm_reform_km; rc=0; pk=dm_prevent_km; pc=0
            if use_balance:
                i = yr - 2026; ratio = 1 - (balance/100)*(1 - (i/(years-1 if years>1 else 1)))
                rk *= ratio; rc *= ratio; pk *= ratio; pc *= ratio
            # 估算PQI和优良路率
            total_plan = rk + pk
            est_pqi = min(95, int(85 + total_plan*0.03))
            est_rate = min(98, int(80 + total_plan*0.08))
            pqi_ok = '✓' if est_pqi >= target_pqi else '✗'
            rate_ok = '✓' if est_rate >= target_rate else '✗'
            contrast = f'PQI估{est_pqi}/{target_pqi}{pqi_ok} 路率估{est_rate}%/{target_rate}%{rate_ok}'
            self.dp_tree.insert('','end',values=(f'{yr}年',f'{rk:.1f}',f'{rc:.0f}',f'{pk:.1f}',f'{pc:.0f}',
                f'{rk+pk:.1f}',f'{rc+pc:.0f}',contrast))
        self.status_var.set(f'动态规划完成 - {years}年')

    def _apply_filter(self):
        if not self.data_cache: return
        df = pd.concat(self.data_cache.values(), ignore_index=True)
        c = self.filter_county_var.get()
        if c != '全部' and '县份' in df.columns: df = df[df['县份'] == c]
        y = self.filter_year_var.get()
        if y != '全部' and '年份' in df.columns: df = df[df['年份'] == int(y)]
        g = self.filter_grade_var.get()
        if g != '全部' and 'PQI分级' in df.columns: df = df[df['PQI分级'] == g]
        p = self.filter_type_var.get()
        if p != '全部' and '路面类型' in df.columns: df = df[df['路面类型'] == p]
        self.filtered_df = df
        km = df['路段长度km'].sum() if '路段长度km' in df.columns else 0
        self.filter_stats.config(text=f'{len(df)}条 | {km:.1f}km')
        self.data_tree.delete(*self.data_tree.get_children())
        for _, row in df.head(500).iterrows():
            vals = [f'{row.get(c,""):.2f}' if isinstance(row.get(c,''),float) else str(row.get(c,''))
                    for c in self.data_tree['columns']]
            self.data_tree.insert('','end',values=vals)

    def _reset_filter(self):
        for v in [self.filter_county_var, self.filter_year_var, self.filter_grade_var, self.filter_type_var]:
            v.set('全部')
        self._apply_filter()

    def _export_filtered(self):
        if self.filtered_df is None or self.filtered_df.empty:
            messagebox.showwarning('提示','没有可导出数据'); return
        path = filedialog.asksaveasfilename(title='导出', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
        if path: self.filtered_df.to_excel(path, index=False); messagebox.showinfo('成功','已导出')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面2: 现状评定（4张评价表 + 图表）
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page2(self, parent):
        # 顶部分析参数栏
        top = tk.Frame(parent, bg=THEME['bg'])
        top.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(top, text='📊 现状数据评定分析', bg=THEME['bg'], fg=THEME['text'],
                font=('Microsoft YaHei', 14, 'bold')).pack(anchor='w')
        r = tk.Frame(top, bg=THEME['bg']); r.pack(fill='x', pady=5)
        tk.Label(r, text='县份', bg=THEME['bg'], font=('Microsoft YaHei', 9)).pack(side='left')
        self.tech_county_var = tk.StringVar(value='全部')
        self.tech_county_cb = ttk.Combobox(r, textvariable=self.tech_county_var, width=10, state='readonly', values=['全部'])
        self.tech_county_cb.pack(side='left', padx=5)
        tk.Label(r, text='基准年', bg=THEME['bg'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.tech_year_var = tk.StringVar(value='2025')
        ttk.Combobox(r, textvariable=self.tech_year_var, width=6, values=['2021','2022','2023','2024','2025']).pack(side='left', padx=5)
        tk.Button(r, text='▶ 执行分析', command=self._run_tech,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=15, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='📥 导出全部', command=self._export_tech_all, font=('Microsoft YaHei', 9)).pack(side='right', padx=5)

        # 可拖拽调整的4栏区域
        self.tech_pw = tk.PanedWindow(parent, orient='vertical', bg=THEME['card_border'],
                                       sashwidth=4, sashrelief='raised')
        self.tech_pw.pack(fill='both', expand=True, padx=15, pady=(5,10))

        self.tech_sections = {}
        for key, title in [('road_type','表1. 等级评价 — 按国道/省道 × 指标'),('route','表2. 路线评价 — 按路线编号'),
                           ('tech_grade','表3. 技术等级评价 — 按公路等级 × 指标'),('year','表4. 年度趋势 — 按年份')]:
            sec = ttk.LabelFrame(self.tech_pw, text=title, padding=5)
            self.tech_pw.add(sec, height=200)
            self.tech_sections[key] = sec

        # 预加载数据
        if self.data_cache:
            self._run_tech()

    def _run_tech(self):
        df = self._get_data(self.tech_county_var.get())
        if df.empty: return
        year = int(self.tech_year_var.get())
        if '年份' in df.columns: df = df[df['年份'] == year]
        if '路段长度km' not in df.columns: df['路段长度km'] = 1.0
        def rt(r): return '国道' if str(r)[:1]=='G' else ('省道' if str(r)[:1]=='S' else '其他')
        if '路线编码' in df.columns: df['道路类型'] = df['路线编码'].apply(rt)
        pk = {'国': '国道', '省': '省道'}

        # ── 表1: 等级评价 ──
        self._clear_section('road_type')
        cols = ('道路类型','指标','加权均值','优良路率','次差路率','优里程','良里程','中里程','次里程','差里程','评定里程')
        tf1, tv1 = self._build_section_table(self.tech_sections['road_type'], cols, 5, ws={'道路类型':65,'指标':50,'加权均值':58,'优良路率':68,'次差路率':68,'优里程':55,'良里程':55,'中里程':55,'次里程':55,'差里程':55,'评定里程':68})
        # 分级阈值: PQI/PCI vs RQI 不同
        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            if rd.empty: continue
            for idx, label in [('PQI','PQI'),('PCI','PCI'),('RQI','RQI')]:
                if idx not in rd.columns: continue
                t = rd['路段长度km'].sum()
                # 加权均值
                wavg = (rd[idx] * rd['路段长度km']).sum() / t if t > 0 else 0
                # PQI/PCI/RQI 统一分级: 优≥90 良≥80 中≥70 次≥60 差<60
                y, l, z, c = 90, 80, 70, 60
                gr_thr, br_thr = 80, 60          # 优良≥80, 次差<60
                gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100 if t > 0 else 0
                br = rd[rd[idx] < br_thr]['路段长度km'].sum() / t * 100 if t > 0 else 0
                yl = rd[(rd[idx] >= y) & (rd[idx] <= 100)]['路段长度km'].sum()
                lh = rd[(rd[idx] >= l) & (rd[idx] < y)]['路段长度km'].sum()
                zh = rd[(rd[idx] >= z) & (rd[idx] < l)]['路段长度km'].sum()
                ci = rd[(rd[idx] >= c) & (rd[idx] < z)]['路段长度km'].sum()
                ch = rd[rd[idx] < c]['路段长度km'].sum()
                tv1.insert('','end',values=(road, label, f'{wavg:.1f}', f'{gr:.1f}%', f'{br:.1f}%',
                    f'{yl:.1f}', f'{lh:.1f}', f'{zh:.1f}', f'{ci:.1f}', f'{ch:.1f}', f'{t:.1f}'))
        self._build_section_chart(self.tech_sections['road_type'], tv1, 'group_bar', title='国道/省道 × PQI/PCI/RQI 对比')

        # ── 表2: 路线评价 ──
        self._clear_section('route')
        cols2 = ('路线编码','PQI加权均值','PQI优良路率','PCI加权均值','PCI优良路率','RQI加权均值','RQI优良路率')
        tf2, tv2 = self._build_section_table(self.tech_sections['route'], cols2, 8, ws={'路线编码':90,'PQI加权均值':85,'PQI优良路率':85,'PCI加权均值':85,'PCI优良路率':85,'RQI加权均值':85,'RQI优良路率':85})
        for rt_code, rd in df.groupby('路线编码'):
            t = rd['路段长度km'].sum()
            if t == 0: t = 1
            vals = []
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',80)]:
                if idx in rd.columns:
                    wavg = (rd[idx] * rd['路段长度km']).sum() / t
                    gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100
                    vals += [f'{wavg:.1f}', f'{gr:.1f}%']
                else:
                    vals += ['-','-']
            tv2.insert('','end',values=(rt_code, *vals))
        # 全路网汇总
        t_all = df['路段长度km'].sum()
        overall = []
        for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',90)]:
            if idx in df.columns:
                wavg = (df[idx] * df['路段长度km']).sum() / t_all if t_all > 0 else 0
                gr = df[df[idx] >= gr_thr]['路段长度km'].sum() / t_all * 100 if t_all > 0 else 0
                overall += [f'{wavg:.1f}', f'{gr:.1f}%']
            else:
                overall += ['-','-']
        tv2.insert('','end',values=('全路网', *overall))
        self._build_section_chart(self.tech_sections['route'], tv2, 'line', title='各路线PQI/PCI/RQI对比')

        # ── 表3: 技术等级 ──
        self._clear_section('tech_grade')
        cols3 = ('技术等级','PQI加权均值','PQI优良路率','PCI加权均值','PCI优良路率','RQI加权均值','RQI优良路率')
        tf3, tv3 = self._build_section_table(self.tech_sections['tech_grade'], cols3, 5, ws={'技术等级':85,'PQI加权均值':85,'PQI优良路率':80,'PCI加权均值':85,'PCI优良路率':80,'RQI加权均值':85,'RQI优良路率':80})
        grade_map = {'一':'一级公路','二':'二级公路','三':'三级公路','四':'四级公路'}
        for key, grade in grade_map.items():
            rd = df[df['技术等级'].str.contains(key, na=False)] if '技术等级' in df.columns else pd.DataFrame()
            if rd.empty and '技术等级' in df.columns: rd = df[df['技术等级']==grade]
            if rd.empty: continue
            t = rd['路段长度km'].sum()
            if t == 0: t = 1
            vals = []
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',90)]:
                if idx in rd.columns and not rd[idx].isna().all():
                    wavg = (rd[idx] * rd['路段长度km']).sum() / t
                    gr = rd[rd[idx] >= gr_thr]['路段长度km'].sum() / t * 100
                    vals += [f'{wavg:.1f}', f'{gr:.1f}%']
                else:
                    vals += ['-','-']
            tv3.insert('','end',values=(grade, *vals))
        if not tv3.get_children():
            t = df['路段长度km'].sum(); t = t if t>0 else 1
            for idx, gr_thr in [('PQI',80),('PCI',80),('RQI',80)]:
                wavg = (df[idx] * df['路段长度km']).sum() / t if idx in df.columns else 0
                gr = df[df[idx] >= gr_thr]['路段长度km'].sum() / t * 100 if idx in df.columns and t>0 else 0
                tv3.insert('','end',values=('全路网', f'{wavg:.1f}',f'{gr:.1f}%', '-','-', '-','-'))
        self._build_section_chart(self.tech_sections['tech_grade'], tv3, 'combo', title='技术等级对比')

        # ── 表4: 年度趋势 ──
        self._clear_section('year')
        cols4 = ('年份','PQI均值','PCI均值','RQI均值','PQI优良路率')
        tf4, tv4 = self._build_section_table(self.tech_sections['year'], cols4, 6, ws={'年份':55,'PQI均值':78,'PCI均值':78,'RQI均值':78,'PQI优良路率':88})
        all_df = pd.concat(self.data_cache.values(), ignore_index=True) if self.data_cache else df
        if '路段长度km' not in all_df.columns: all_df['路段长度km'] = 1.0
        years_data = sorted(all_df['年份'].unique()) if '年份' in all_df.columns else [year]
        if not years_data: years_data = [year]
        for y in years_data:
            yi = int(y) if str(y).isdigit() else y
            yd = all_df[all_df['年份']==y] if '年份' in all_df.columns else df
            if yd.empty: continue
            t = yd['路段长度km'].sum()
            if t == 0: t = 1
            pqim = (yd['PQI'] * yd['路段长度km']).sum() / t if 'PQI' in yd.columns else 0
            pcim = (yd['PCI'] * yd['路段长度km']).sum() / t if 'PCI' in yd.columns else 0
            rqim = (yd['RQI'] * yd['路段长度km']).sum() / t if 'RQI' in yd.columns else 0
            gr = yd[yd['PQI']>=80]['路段长度km'].sum()/t*100 if 'PQI' in yd.columns and t>0 else 0
            tv4.insert('','end',values=(yi, f'{pqim:.1f}', f'{pcim:.1f}', f'{rqim:.1f}', f'{gr:.1f}%'))
        self._build_section_chart(self.tech_sections['year'], tv4, 'line', title='年度趋势')

        self.mark_step_done(2)
        self.status_var.set(f'现状评定完成 — {len(df)}条记录')

    def _clear_section(self, key):
        """彻底清除section内的所有子控件"""
        sec = self.tech_sections[key]
        for w in list(sec.winfo_children()):
            w.destroy()
        sec.update_idletasks()

    def _build_section_table(self, parent, cols, height, ws=None):
        """在parent左侧创建表格(自适应高度)"""
        tvf = tk.Frame(parent, bg=THEME['card'])
        tvf.pack(side='left', fill='both', expand=True, padx=(0,2))
        tv = ttk.Treeview(tvf, columns=cols, show='headings', height=height)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=ws.get(c,60) if ws else 60, anchor='center')
        rp = tk.Frame(tvf, bg=THEME['card'])
        rp.pack(side='right', fill='y')
        sv = ttk.Scrollbar(rp, orient='vertical', command=tv.yview)
        sv.pack(side='top', fill='y', expand=True)
        tk.Button(rp, text='📋', font=('Microsoft YaHei', 9),
                 command=lambda t=tv: self._copy_tree(t), padx=3).pack(side='bottom', pady=(2,0))
        tv.configure(yscrollcommand=sv.set)
        tv.pack(side='left', fill='both', expand=True)
        return tvf, tv

    def _build_section_chart(self, parent, tv, chart_type, title='图表'):
        """在parent右侧创建图表"""
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import matplotlib.pyplot as plt
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei','SimHei']
            plt.rcParams['axes.unicode_minus'] = False
        except ImportError:
            return

        try:
            self._do_chart(parent, tv, chart_type, title)
        except Exception as e:
            import traceback; traceback.print_exc()
            tk.Label(parent, text=f'图表错误: {e}', fg=THEME['danger'], bg=THEME['card'],
                     font=('Microsoft YaHei', 8)).pack(side='right', padx=10)

    def _do_chart(self, parent, tv, chart_type, title):
        """实际绘制图表"""
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.pyplot as plt
        cf = tk.Frame(parent, bg=THEME['card'])
        cf.pack(side='right', fill='both', expand=True, padx=(2,0))

        headers = tv['columns']
        rows = [tv.item(it,'values') for it in tv.get_children()]
        if not rows: return

        labels = [str(r[0]) for r in rows]
        fig = Figure(figsize=(8, 5.5), dpi=80, facecolor=THEME['card'])
        ax = fig.add_subplot(111)
        ax.set_facecolor(THEME['card'])

        if chart_type == 'group_bar' and len(rows) <= 12:
            road_types = sorted(set(str(r[0]) for r in rows))
            indicators = sorted(set(str(r[1]) for r in rows), key=lambda x: {'PQI':0,'PCI':1,'RQI':2}.get(x,9))
            data = {}
            for r in rows:
                idx, rd, v = str(r[1]), str(r[0]), float(str(r[2]).replace('%','')) if r[2]!='-' else 0
                if idx not in data: data[idx] = {}
                data[idx][rd] = v
            x = range(len(indicators))
            nbars = len(road_types)
            w = 0.6 / nbars if nbars > 1 else 0.4
            colors_road = {'国道':'#2E75B6','省道':'#27AE60'}
            for j, rd in enumerate(road_types):
                vals = [data.get(idx, {}).get(rd, 0) for idx in indicators]
                bars = ax.bar([i + (j - (nbars-1)/2) * w for i in x], vals, w, label=rd, color=colors_road.get(rd,'#888'), zorder=2)
                for bar in bars:
                    h = bar.get_height()
                    if h > 0: ax.text(bar.get_x() + bar.get_width()/2, h + max(vals)*0.02, f'{h:.1f}', ha='center', va='bottom', fontsize=6)
            ax.set_xticks(x); ax.set_xticklabels(indicators, fontsize=8)
            ax.legend(loc='upper left', fontsize=7)

        elif chart_type == 'combo' and len(rows) <= 12:
            num_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['均值'])]
            pct_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['路率'])]
            mean_colors = {'PQI均值':'#2E75B6','PCI均值':'#27AE60','RQI均值':'#E67E22'}
            pct_colors = {'PQI优良路率':'#C0392B','PCI优良路率':'#8E44AD','RQI优良路率':'#D35400'}
            x = range(len(labels))
            total_bars = len(num_cols)
            wb = 0.6 / total_bars if total_bars else 0.3
            for j, ci in enumerate(num_cols):
                vals = [float(str(r[ci]).replace('%','')) if r[ci] != '-' else 0 for r in rows]
                col = mean_colors.get(headers[ci], f'C{j}')
                bars = ax.bar([i + (j - (total_bars-1)/2) * wb for i in x], vals, wb, label=headers[ci], color=col, zorder=2)
                for bar in bars:
                    h = bar.get_height()
                    if h > 0: ax.text(bar.get_x() + bar.get_width()/2, h + max(vals)*0.02, f'{h:.1f}', ha='center', va='bottom', fontsize=5.5)
            if pct_cols:
                ax2 = ax.twinx(); ax2.set_facecolor(THEME['card'])
                for j, ci in enumerate(pct_cols):
                    pv = [float(str(r[ci]).replace('%','')) if r[ci]!='-' else 0 for r in rows]
                    col = pct_colors.get(headers[ci], f'C{3+j}')
                    ax2.plot(x, pv, 'o-', color=col, label=headers[ci], markersize=5, linewidth=1.5, zorder=5)
                    for xi, yv in zip(x, pv):
                        ax2.annotate(f'{yv:.1f}%', (xi, yv), textcoords='offset points', xytext=(0,8), ha='center', fontsize=6, color=col)
                ax2.set_ylabel('优良路率 (%)', fontsize=7); ax2.tick_params(labelsize=6)
                h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
                ax.legend(h1+h2, l1+l2, loc='upper left', fontsize=6)
            ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=25)

        elif chart_type == 'line':
            # 检测X轴数据：可转数字用数值，否则按标签序号
            numeric_x = True
            try: _ = float(str(rows[0][0]))
            except: numeric_x = False
            if numeric_x:
                xv = [float(str(r[0])) for r in rows]
            else:
                xv = list(range(len(rows)))
            num_cols = [i for i,h in enumerate(headers) if any(k in h for k in ['均值','路率'])]
            COLORS = ['#2E75B6','#E67E22','#27AE60','#C0392B','#8E44AD','#D35400']
            STYLES = ['o-','s--','D:','^-.','v--','*:']
            for j, ci in enumerate(num_cols):
                yv = [float(str(r[ci]).replace('%','')) if r[ci]!='-' else 0 for r in rows]
                ax.plot(xv, yv, STYLES[j%6], color=COLORS[j%6], label=headers[ci], markersize=4, linewidth=1.2, zorder=2)
                for xi, yi in zip(xv, yv):
                    ax.annotate(f'{yi:.1f}', (xi, yi), textcoords='offset points', xytext=(0,8), ha='center', fontsize=5.5, color=COLORS[j%6])
            ax.legend(fontsize=6)
            if numeric_x:
                try: ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
                except: pass
            else:
                ax.set_xticks(xv)
                ax.set_xticklabels(labels, fontsize=6, rotation=45)

        ax.set_title(title, fontsize=9, fontweight='bold')
        ax.tick_params(labelsize=7)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, cf)
        canvas.draw(); canvas.get_tk_widget().pack(fill='both', expand=True)
        # 导出按钮
        bf = tk.Frame(cf, bg=THEME['card']); bf.pack(fill='x')
        tk.Button(bf, text='💾 导出图表', font=('Microsoft YaHei', 9),
                 command=lambda f=fig: ExportHelper.export(f)).pack(side='left')

    def _copy_tree(self, tv):
        """复制Treeview内容到剪贴板"""
        headers = '\t'.join(tv['columns'])
        lines = [headers]
        for it in tv.get_children():
            row = '\t'.join(str(v) for v in tv.item(it, 'values'))
            lines.append(row)
        text = '\n'.join(lines)
        self.clipboard_clear(); self.clipboard_append(text)
        messagebox.showinfo('成功', '已复制到剪贴板')

    def _export_tech_all(self):
        path = filedialog.asksaveasfilename(title='导出评定结果', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')], initialfile='现状评定.xlsx')
        if not path: return
        with pd.ExcelWriter(path) as writer:
            for key, sec in self.tech_sections.items():
                for w in sec.winfo_children():
                    if isinstance(w, tk.Frame):
                        for tw in w.winfo_children():
                            if isinstance(tw, ttk.Treeview) and tw.winfo_children():
                                rows = [tw.item(it,'values') for it in tw.get_children()]
                                if rows:
                                    pd.DataFrame(rows, columns=tw['columns']).to_excel(writer, sheet_name=key[:30], index=False)
                                break
        messagebox.showinfo('成功','已导出全部评定结果')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面3: 目标设定
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page3(self, parent):
        self._section_title(parent, '🎯 养护目标设定')
        self._section_sub(parent, '技术目标(加权PQI+优良路率) — 短期/中期/长期 | B/C和成本为参考值')

        self.target_vars = {}
        horizons = [
            ('short', '短期目标 (1年)', '近期达标线'),
            ('mid',   '中期目标 (2-5年)', '中期规划目标'),
            ('long',  '长期目标 (5-10年)', '远期愿景目标'),
        ]
        # 默认目标：技术+经济双维度
        default_targets = {
            'short': {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':1.2,'国道_km成本':50,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.1,'省道_km成本':55},
            'mid':   {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':1.5,'国道_km成本':45,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.3,'省道_km成本':50},
            'long':  {'国道_PQI':90,'国道_优良路率':88,'国道_BCR':2.0,'国道_km成本':40,
                      '省道_PQI':85,'省道_优良路率':80,'省道_BCR':1.8,'省道_km成本':45},
        }

        for hkey, htitle, hdesc in horizons:
            f = ttk.LabelFrame(parent, text=f'{htitle} — {hdesc}', padding=10)
            f.pack(fill='x', padx=15, pady=5)
            r = self._row(f)
            # 国道
            gd = ttk.LabelFrame(r, text='普通国道', padding=5)
            gd.pack(side='left', fill='x', expand=True, padx=(0,10))
            grd = tk.Frame(gd, bg=self._bg(gd)); grd.pack(fill='x')
            tk.Label(grd, text='技术→', bg=self._bg(gd), fg=THEME['accent'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(0,5))
            for label, suffix, dv in [('PQI','PQI',default_targets[hkey]['国道_PQI']),
                                       ('优良路率%','优良路率',default_targets[hkey]['国道_优良路率'])]:
                tk.Label(grd, text=f'{label} ', bg=self._bg(gd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=dv); self.target_vars[f'{hkey}_国道_{suffix}'] = v
                ttk.Entry(grd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            # 短期只显示技术指标，中/长期增加参考值
            if hkey != 'short':
                tk.Label(grd, text='参考→', bg=self._bg(gd), fg=THEME['text_light'],
                        font=('Microsoft YaHei',8)).pack(side='left', padx=(5,5))
                for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['国道_BCR']),
                                           ('成本万/km','km成本',default_targets[hkey]['国道_km成本'])]:
                    tk.Label(grd, text=f'{label} ', bg=self._bg(gd), font=('Microsoft YaHei',9)).pack(side='left')
                    if suffix == 'BCR':
                        v = tk.StringVar(value=str(dv))
                    else:
                        v = tk.IntVar(value=dv)
                    self.target_vars[f'{hkey}_国道_{suffix}'] = v
                    ttk.Entry(grd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            # 省道
            sd = ttk.LabelFrame(r, text='普通省道', padding=5)
            sd.pack(side='left', fill='x', expand=True)
            srd = tk.Frame(sd, bg=self._bg(sd)); srd.pack(fill='x')
            tk.Label(srd, text='技术→', bg=self._bg(sd), fg=THEME['accent'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(0,5))
            for label, suffix, dv in [('PQI','PQI',default_targets[hkey]['省道_PQI']),
                                       ('优良路率%','优良路率',default_targets[hkey]['省道_优良路率'])]:
                tk.Label(srd, text=f'{label} ', bg=self._bg(sd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=dv); self.target_vars[f'{hkey}_省道_{suffix}'] = v
                ttk.Entry(srd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
            if hkey != 'short':
                tk.Label(srd, text='参考→', bg=self._bg(sd), fg=THEME['text_light'],
                        font=('Microsoft YaHei',8)).pack(side='left', padx=(5,5))
            if hkey != 'short':
                for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['省道_BCR']),
                                           ('成本万/km','km成本',default_targets[hkey]['省道_km成本'])]:
                    tk.Label(srd, text=f'{label} ', bg=self._bg(sd), font=('Microsoft YaHei',9)).pack(side='left')
                    if suffix == 'BCR':
                        v = tk.StringVar(value=str(dv))
                    else:
                        v = tk.IntVar(value=dv)
                    self.target_vars[f'{hkey}_省道_{suffix}'] = v
                    ttk.Entry(srd, textvariable=v, width=5, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))

        # 按钮 + 对比表
        r = self._row(parent, 12)
        tk.Button(r, text='💾 保存目标', command=self._save_targets,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=15, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='🔄 对比现状', command=self._compare_targets,
                 font=('Microsoft YaHei', 10), padx=10).pack(side='left', padx=5)

        card2 = ttk.LabelFrame(parent, text='📊 目标 vs 现状对比', padding=10)
        card2.pack(fill='both', expand=True, padx=15, pady=5)
        cols = ('维度','道路','指标','当前值','短期目标','中期目标','长期目标')
        self.target_tree = ttk.Treeview(card2, columns=cols, show='headings', height=10)
        for i,c in enumerate(cols):
            self.target_tree.heading(c, text=c)
            self.target_tree.column(c, width=105, anchor='center')
        self.target_tree.pack(fill='both', expand=True)

    def _save_targets(self):
        cfg = self.config
        cfg['targets'] = {k:v.get() for k,v in self.target_vars.items()}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.mark_step_done(3)
        self.status_var.set('短期/中期/长期养护目标已保存')
        messagebox.showinfo('成功','养护目标已保存到配置文件')

    def _compare_targets(self):
        df = self._get_data('全部')
        if df.empty: return
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        def rt(r):
            if pd.isna(r): return '其他'
            s = str(r); return '国道' if s.startswith('G') else ('省道' if s.startswith('S') else '其他')
        if '路线编码' in df.columns: df['道路类型'] = df['路线编码'].apply(rt)
        if '路段长度km' not in df.columns: df['路段长度km'] = 1.0
        self.target_tree.delete(*self.target_tree.get_children())

        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            if rd.empty: continue
            t = rd['路段长度km'].sum()
            # 技术指标
            w_pqi = (rd['PQI'] * rd['路段长度km']).sum() / t if t>0 else 0
            good_len = rd[rd['PQI']>=80]['路段长度km'].sum() if 'PQI' in rd.columns else 0
            good_rate = good_len/t*100 if t>0 else 0
            # 经济指标(年均养护成本估算)
            width = rd['路面宽度'].mean() if '路面宽度' in rd.columns else 7
            # 年均养护成本 = 日常保养 + 预防 + 改造 按比例加权
            # 日常30元/m² × 80% + 预防160元/m² × 15% + 改造319元/m² × 5%
            avg_unit = 30*0.8 + 160*0.15 + 319*0.05  # ≈ 64元/m²
            annual_cost = t * 1000 * width * avg_unit / 10000  # 年养护费(万元)
            km_cost = annual_cost / t  # 每公里年均成本(万元/km)
            from src.decision.cost_model import calc_bcr_ratio
            bcr = calc_bcr_ratio(rd, annual_cost) if annual_cost>0 else 0

            for metric, cur_val, suffix, is_target in [
                ('加权PQI', w_pqi, 'PQI', True), ('优良路率(%)', good_rate, '优良路率', True),
                ('B/C比(参考)', bcr, 'BCR', False), ('每km成本(万,参考)', km_cost, 'km成本', False)
            ]:
                if is_target:
                    short_t = self.target_vars.get(f'short_{road}_{suffix}', tk.IntVar(value=0)).get()
                    mid_t   = self.target_vars.get(f'mid_{road}_{suffix}', tk.IntVar(value=0)).get()
                    long_t  = self.target_vars.get(f'long_{road}_{suffix}', tk.IntVar(value=0)).get()
                    if suffix == 'BCR':
                        cur_fmt = f'{cur_val:.2f}'
                        s_fmt = f'{float(short_t):.2f}'
                        m_fmt = f'{float(mid_t):.2f}'
                        l_fmt = f'{float(long_t):.2f}'
                    else:
                        cur_fmt = f'{cur_val:.1f}'; s_fmt = f'{short_t}'; m_fmt = f'{mid_t}'; l_fmt = f'{long_t}'
                else:
                    cur_fmt = f'{cur_val:.2f}' if suffix == 'BCR' else f'{cur_val:.1f}'
                    s_fmt = m_fmt = l_fmt = '参考'
                self.target_tree.insert('','end',values=('技术/经济',road,metric,cur_fmt,s_fmt,m_fmt,l_fmt))
        self.status_var.set('目标对比完成')

    # ══════════════════════════════════════════════════════════════════════════
    def _build_page4(self, parent):
        # 可滚动
        cvs = tk.Canvas(parent, bg=THEME['bg'], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=cvs.yview)
        cvs.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y'); cvs.pack(side='left', fill='both', expand=True)
        sf = tk.Frame(cvs, bg=THEME['bg'])
        wid = cvs.create_window((0,0), window=sf, anchor='nw', tags=('sframe',))
        def _cfg(e):
            cvs.itemconfig(wid, width=e.width)
            cvs.configure(scrollregion=cvs.bbox('all'))
        cvs.bind('<Configure>', _cfg)
        sf.bind('<Configure>', lambda e: cvs.configure(scrollregion=cvs.bbox('all')))

        self._section_title(sf, '⚙️ 对策模型')
        self._section_sub(sf, '四个模型统一配置面板')

        # 一、衰减率标定
        card0 = self._card(sf, '一、衰减率标定 — PQI(t)=PQI₀×e^(-k×t)')
        r = self._row(card0)
        tk.Label(r, text='县份：', bg=THEME['card'], font=('Microsoft YaHei',9)).pack(side='left')
        self.model_county_var = tk.StringVar(value='全部')
        self.model_county_cb = ttk.Combobox(r, textvariable=self.model_county_var, width=12, state='readonly', values=['全部'])
        self.model_county_cb.pack(side='left', padx=8)
        tk.Button(r, text='计算衰减率', command=self._calc_decay, bg=THEME['accent'], fg='white',
                 font=('Microsoft YaHei',9), padx=10, cursor='hand2').pack(side='left', padx=8)
        cols = ('路面类型','技术等级','PQI衰减k','PCI衰减k','RQI衰减k','样本数')
        self.decay_tree = ttk.Treeview(card0, columns=cols, show='headings', height=5)
        for c in cols: self.decay_tree.heading(c, text=c); self.decay_tree.column(c, width=100, anchor='center')
        self.decay_tree.pack(fill='x', pady=(5,0))

        # 二、触发阈值
        card = self._card(sf, '二、养护触发阈值')
        self.trigger_vars = {}
        tk.Label(card, text='【路面改造】满足任一条件即触发', bg=THEME['card'],
                fg=THEME['accent'], font=('Microsoft YaHei', 9, 'bold')).pack(anchor='w')
        h = self._row(card, 3)
        for t,w in [('路面类型',10),('技术等级',10),('PCI',6),('PQI',6),('RQI',6)]:
            tk.Label(h, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,g, dpci,dpqi,drqi in [
            ('路面改造','沥青路面','一级公路',80,80,80),('路面改造','沥青路面','二级及以下',75,75,75),
            ('路面改造','水泥路面','一级公路',80,80,80),('路面改造','水泥路面','二级及以下',75,75,75),
        ]:
            r = self._row(card, 2)
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=g, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PCI',dpci),('PQI',dpqi),('RQI',drqi)]:
                v = tk.IntVar(value=dv); self.trigger_vars[f'{m}_{pt}_{g}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=6).pack(side='left')
                en = tk.BooleanVar(value=True)
                self.trigger_vars[f'{m}_{pt}_{g}_{idx}_启用'] = en
                tk.Checkbutton(r, text='', variable=en, bg=THEME['card'], width=2).pack(side='left')

        tk.Label(card, text='【预防性养护】不满足路面改造时，条件触发', bg=THEME['card'],
                fg=THEME['success'], font=('Microsoft YaHei', 9, 'bold')).pack(anchor='w', pady=(10,0))
        h2 = self._row(card, 3)
        for t,w in [('路面类型',10),('技术等级',10),('PCI下限',7),('PCI上限',7),('PQI≥',5)]:
            tk.Label(h2, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,g, plo,phi,pqi in [
            ('预防性养护','沥青路面','一级公路',80,90,80),('预防性养护','沥青路面','二级及以下',78,85,75),
            ('预防性养护','水泥路面','一级公路',80,90,80),('预防性养护','水泥路面','二级及以下',78,85,75),
        ]:
            r = self._row(card, 2)
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=g, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PCI低',plo),('PCI高',phi),('PQI',pqi)]:
                v = tk.IntVar(value=dv); self.trigger_vars[f'{m}_{pt}_{g}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=6).pack(side='left')
                en = tk.BooleanVar(value=True)
                self.trigger_vars[f'{m}_{pt}_{g}_{idx}_启用'] = en
                tk.Checkbutton(r, text='', variable=en, bg=THEME['card'], width=2).pack(side='left')

        # 三、回调值
        card2 = self._card(sf, '三、养护后PQI/PCI/RQI回调值')
        self.callback_vars = {}
        h3 = self._row(card2, 3)
        for t,w in [('养护类型',12),('路面类型',10),('PQI回升值',9),('PCI回升值',9),('RQI回升值',9)]:
            tk.Label(h3, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,dpqi,dpci,drqi in [
            ('路面改造','沥青路面',92,92,93),('路面改造','水泥路面',88,88,90),
            ('预防性养护','沥青路面',89,89,91),('预防性养护','水泥路面',86,86,88),
        ]:
            r = self._row(card2, 2)
            tk.Label(r, text=m, width=12, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            for idx,dv in [('PQI',dpqi),('PCI',dpci),('RQI',drqi)]:
                v = tk.IntVar(value=dv); self.callback_vars[f'{m}_{pt}_{idx}'] = v
                ttk.Entry(r, textvariable=v, width=8).pack(side='left')

        # 四、养护方案单价明细表（双击单价可编辑）
        card3 = self._card(sf, '四、养护方案单价明细（双击单价可编辑）')
        card3.configure(height=300)
        cols_p = ('路面类型','养护工程','技术等级','养护方案','单价')
        self.price_tree = ttk.Treeview(card3, columns=cols_p, show='headings', height=15)
        for ct,w in [('路面类型',70),('养护工程',80),('技术等级',70),('养护方案',320),('单价',70)]:
            self.price_tree.heading(ct, text=ct); self.price_tree.column(ct, width=w, anchor='w' if ct=='养护方案' else 'center')
        sv_p = ttk.Scrollbar(card3, orient='vertical', command=self.price_tree.yview)
        self.price_tree.configure(yscrollcommand=sv_p.set)
        self.price_tree.pack(side='left', fill='both', expand=True); sv_p.pack(side='right', fill='y')
        self.price_vars = {}
        for pt,mt,tg,plan,price in [
            ('沥青路面','结构性修复','一级','4cm GAC-13(改性)+6cm GAC-20(改性)+1cm同步碎石封层+基层处理(30%)',326),
            ('沥青路面','结构性修复','二级','4cm GAC-13(改性)+6cm GAC-20+1cm同步碎石封层+基层处理(30%)',319),
            ('沥青路面','结构性修复','三级','4cm GAC-13(改性)+6cm GAC-20+1cm同步碎石封层+基层处理(30%)',319),
            ('沥青路面','功能性修复','一级','5cm GAC-13(改性)+1cm同步碎石封层+病害处理(10%)',161),
            ('沥青路面','功能性修复','二级','4cm GAC-13(改性)+改性乳化沥青粘层+病害处理(10%)',109),
            ('沥青路面','功能性修复','三级','4cm GAC-13(改性)+改性乳化沥青粘层+病害处理(10%)',109),
            ('沥青路面','预防养护','一级','1.2cm冷拌超粘微表处+表层病害处理(5%)',48),
            ('沥青路面','预防养护','二级','1.2cm冷拌超粘微表处+表层病害处理(5%)',30),
            ('沥青路面','预防养护','三级','1cm微表处+表层病害处理(5%)',30),
            ('水泥路面','结构性修复','一级','水泥:碎石化+封层+C40砼32cm / 沥青:共振+封层+10cmGAC25+6cmGAC20+4cmGAC13',268),
            ('水泥路面','结构性修复','二级','水泥:碎石化+封层+C40砼30cm / 沥青:共振+封层+10cmGAC25+4cmGAC13',253),
            ('水泥路面','结构性修复','三级','水泥:碎石化+封层+C40砼28cm / 沥青:共振+封层+8cmGAC25+4cmGAC13',238),
            ('水泥路面','功能性修复','一级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',161),
            ('水泥路面','功能性修复','二级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',160),
            ('水泥路面','功能性修复','三级','6cm GAC-13(改性)(含1cm调平)+1cm同步碎石封层+换板(10%)',157),
            ('沥青路面','日常养护','全部','日常保养维护',30),
            ('水泥路面','日常养护','全部','日常保养维护',25),
        ]:
            self.price_tree.insert('','end',values=(pt,mt,tg,plan,str(price)))
            self.price_vars[f'{mt}_{pt}_{tg}'] = tk.IntVar(value=price)
        self.price_tree.bind('<Double-1>', self._on_price_dclick)

        # 按钮
        r = self._row(sf, 15)
        tk.Button(r, text='💾 保存全部配置', command=self._save_policy_config,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10),
                 padx=18, pady=4, cursor='hand2').pack(side='left', padx=20)
        tk.Button(r, text='↺ 恢复默认', command=self._reset_policy_config,
                 font=('Microsoft YaHei', 9), padx=12).pack(side='left', padx=5)

    def _calc_decay(self):
        from src.decay_calculator import get_calibration_table
        df = self._get_data(self.model_county_var.get() if hasattr(self,'model_county_var') else '全部')
        if df.empty: return
        cty = None if self.model_county_var.get()=='全部' else self.model_county_var.get()
        table = get_calibration_table(df, cty)
        self.decay_tree.delete(*self.decay_tree.get_children())
        for row in table: self.decay_tree.insert('','end',values=row)
        self.status_var.set('衰减率标定完成')

    def _on_price_dclick(self, event):
        if self.price_tree.identify_region(event.x,event.y) != 'cell': return
        if self.price_tree.identify_column(event.x) != '#5': return
        item = self.price_tree.identify_row(event.y)
        if not item: return
        vals = self.price_tree.item(item,'values')
        bbox = self.price_tree.bbox(item,'#5')
        if not bbox: return
        e = ttk.Entry(self.price_tree, width=8)
        e.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        e.insert(0,''.join(c for c in str(vals[4]) if c.isdigit()))
        e.select_range(0,'end'); e.focus_set()
        def save(ev=None):
            e.destroy()
            nv = e.get().strip()
            if nv and nv.isdigit():
                nv2 = list(vals); nv2[4] = nv
                self.price_tree.item(item,values=nv2)
                pt,mt,tg = vals[0],vals[1],vals[2]
                for pk in [f'{mt}_{pt}_{tg}']:
                    if pk in self.price_vars: self.price_vars[pk].set(int(nv))
        e.bind('<Return>',save); e.bind('<FocusOut>',save)

    def _save_policy_config(self):
        cfg = self.config
        cfg['triggers'] = {k:v.get() for k,v in self.trigger_vars.items()}
        cfg['callbacks'] = {k:v.get() for k,v in self.callback_vars.items()}
        cfg['prices'] = {k:v.get() for k,v in self.price_vars.items()}
        if hasattr(self, 'priority_vars'):
            cfg['priority_weights'] = {k:v.get() for k,v in self.priority_vars.items()}
        if set_maintenance_callback:
            cb = {}
            for ks, var in self.callback_vars.items():
                ps = ks.split('_'); mt=ps[0]; pt=ps[1]; idx=ps[2]
                if mt not in cb: cb[mt] = {}
                if pt not in cb[mt]: cb[mt][pt] = {}
                cb[mt][pt][idx] = var.get()
            set_maintenance_callback(cb); cfg['maintenance_callback'] = cb
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.mark_step_done(5)
        self.status_var.set('养护对策配置已保存')
        messagebox.showinfo('成功','养护对策配置已保存！\n\n- 触发阈值\n- 回调值\n- 单价\n\n参数即时生效，可执行需求分析。')

    def _reset_policy_config(self):
        if not messagebox.askyesno('确认','确定恢复默认？'): return
        for k,v in {
            '路面改造_沥青路面_一级公路_PCI':80,'路面改造_沥青路面_一级公路_PQI':80,'路面改造_沥青路面_一级公路_RQI':80,
            '路面改造_沥青路面_二级及以下_PCI':75,'路面改造_沥青路面_二级及以下_PQI':75,'路面改造_沥青路面_二级及以下_RQI':75,
            '路面改造_水泥路面_一级公路_PCI':80,'路面改造_水泥路面_一级公路_PQI':80,'路面改造_水泥路面_一级公路_RQI':80,
            '路面改造_水泥路面_二级及以下_PCI':75,'路面改造_水泥路面_二级及以下_PQI':75,'路面改造_水泥路面_二级及以下_RQI':75,
            '预防性养护_沥青路面_一级公路_PCI低':80,'预防性养护_沥青路面_一级公路_PCI高':90,'预防性养护_沥青路面_一级公路_PQI':80,
            '预防性养护_沥青路面_二级及以下_PCI低':78,'预防性养护_沥青路面_二级及以下_PCI高':85,'预防性养护_沥青路面_二级及以下_PQI':75,
            '预防性养护_水泥路面_一级公路_PCI低':80,'预防性养护_水泥路面_一级公路_PCI高':90,'预防性养护_水泥路面_一级公路_PQI':80,
            '预防性养护_水泥路面_二级及以下_PCI低':78,'预防性养护_水泥路面_二级及以下_PCI高':85,'预防性养护_水泥路面_二级及以下_PQI':75,
        }.items():
            if k in self.trigger_vars: self.trigger_vars[k].set(v)
        for k,v in {
            '路面改造_沥青路面_PQI':92,'路面改造_沥青路面_PCI':92,'路面改造_沥青路面_RQI':93,
            '路面改造_水泥路面_PQI':88,'路面改造_水泥路面_PCI':88,'路面改造_水泥路面_RQI':90,
            '预防性养护_沥青路面_PQI':89,'预防性养护_沥青路面_PCI':89,'预防性养护_沥青路面_RQI':91,
            '预防性养护_水泥路面_PQI':86,'预防性养护_水泥路面_PCI':86,'预防性养护_水泥路面_RQI':88,
        }.items():
            if k in self.callback_vars: self.callback_vars[k].set(v)
        for k,v in {
            '路面改造_沥青路面':319,'路面改造_水泥路面':299,'预防性养护_沥青路面':160,'预防性养护_水泥路面':140,
            '日常养护_沥青路面':30,'日常养护_水泥路面':25,
        }.items():
            if k in self.price_vars: self.price_vars[k].set(v)
        self.status_var.set('已恢复默认配置')

    # ══════════════════════════════════════════════════════════════════════════
    #  工具方法
    # ══════════════════════════════════════════════════════════════════════════
    def _gen_year_projects(self):
        yr = self.proj_year_var.get()
        if hasattr(self,'demand_multi_year') and yr in self.demand_multi_year:
            ydf = self.demand_multi_year[yr]; self.proj_detail_tree.delete(*self.proj_detail_tree.get_children())
            for _, row in ydf.iterrows():
                mt = row.get('养护类型','')
                if mt in ('路面改造','预防性养护'):
                    self.proj_detail_tree.insert('','end',values=(
                        row.get('路线编码',''), row.get('路段起点',''), row.get('路段终点',''),
                        f'{row.get("路段长度(km)",1):.3f}', row.get('路面类型',''), row.get('技术等级',''),
                        f'{row.get("当前PQI",0):.1f}', '-', '-', mt))
            self.status_var.set(f'{yr}年项目库已生成({len(ydf)}条)')
        else: messagebox.showwarning('提示','请先执行需求分析')

    def _run_total_optimization(self):
        if self.demand_result_df is None or self.demand_result_df.empty:
            messagebox.showwarning('提示','请先执行需求分析'); return

    def _pool_refresh(self):
        self.pool_tree.delete(*self.pool_tree.get_children())
        if self.project_pool:
            for p in self.project_pool.projects:
                self.pool_tree.insert('','end',values=(p.project_id, p.route_code, p.maintenance_type or '',
                    p.maintenance_year or '', f'{p.length:.2f}' if p.length else '',
                    f'{p.estimated_cost:.2f}' if p.estimated_cost else '',
                    f'{p.priority_score:.1f}' if p.priority_score else '', p.status or ''))

    def _pool_import_demand(self):
        if self.demand_result_df is None or self.demand_result_df.empty: return
        if self.project_pool:
            for _, row in self.demand_result_df.iterrows():
                ln = row.get('路段长度(km)',1)
                self.project_pool.add_project(MaintenanceProject(
                    route_code=row.get('路线编码',''), segment_start=str(row.get('路段起点','')),
                    segment_end=str(row.get('路段终点','')), length=ln,
                    pavement_type=row.get('路面类型',''), current_condition={'PQI':row.get('当前PQI',80)},
                    maintenance_type=row.get('养护类型',''), maintenance_year=2026,
                    estimated_cost=row.get('估算费用(万元)',0), priority_score=row.get('优先级评分',0)))
            self._pool_refresh()

    def _pool_export(self):
        if not self.project_pool or not self.project_pool.projects: return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')], initialfile='项目库.xlsx')
        if path: self.project_pool.to_excel(path); messagebox.showinfo('成功','已导出')

    def _pool_import(self):
        path = filedialog.askopenfilename(filetypes=[('Excel','*.xlsx')])
        if path and self.project_pool: self.project_pool.from_excel(path); self._pool_refresh()

    def _pool_clear(self):
        if messagebox.askyesno('确认','清空项目库?'):
            if self.project_pool: self.project_pool.projects.clear(); self._pool_refresh()

    def _pool_gen_plan(self):
        from src.decision.project_pool import generate_annual_plan
        if not self.project_pool or not self.project_pool.projects: return
        plan = generate_annual_plan(self.project_pool, 2026, 5000)
        self._pool_refresh(); messagebox.showinfo('完成',f'{plan.get("项目数",0)}个项目')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面7: GIS地图
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page7(self, parent):
        self._section_title(parent, '🌍 GIS地图展示')
        self._section_sub(parent, '基于Folium交互式地图，按PQI/PCI/RQI着色展示路况')

        card = self._card(parent, '地图参数', expand=True)
        r = self._row(card, 5)
        tk.Label(r, text='县份', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left')
        self.map_county_var = tk.StringVar(value='全部')
        self.map_county_cb = ttk.Combobox(r, textvariable=self.map_county_var, width=10, state='readonly', values=['全部'])
        self.map_county_cb.pack(side='left', padx=8)
        tk.Label(r, text='年份', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.map_year_var = tk.StringVar(value='2025')
        ttk.Combobox(r, textvariable=self.map_year_var, width=6, values=['2021','2022','2023','2024','2025']).pack(side='left', padx=5)
        tk.Label(r, text='着色', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.map_color_var = tk.StringVar(value='PQI')
        ttk.Combobox(r, textvariable=self.map_color_var, width=6, values=['PQI','PCI','RQI']).pack(side='left', padx=5)
        tk.Button(r, text='🗺️ 生成地图', command=self._gen_map,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=12, cursor='hand2').pack(side='left', padx=20)

        self.map_text = tk.Text(card, height=10, wrap='word', font=('Microsoft YaHei', 9))
        self.map_text.pack(fill='both', expand=True, pady=(10,0))
        self.map_text.insert('1.0','点击"生成地图"创建交互式路况地图\n\n需要安装依赖：pip install folium\n地图将生成为HTML文件，可在浏览器中打开查看。')

    def _db_connect(self):
        try:
            from src.database import DatabaseManager, DatabaseConfig
            self.db_mgr = DatabaseManager(DatabaseConfig(
                host=self.db_host_var.get(), port=int(self.db_port_var.get()),
                database=self.db_db_var.get(), user=self.db_user_var.get(), password=self.db_pass_var.get()))
            if self.db_mgr.connect():
                self.db_status.config(text='✓ 已连接', fg=THEME['success'])
                self.db_text.insert('end','数据库连接成功\n')
        except Exception as e:
            self.db_text.insert('end',f'连接失败：{e}\n')

    def _db_init(self):
        if not hasattr(self,'db_mgr'): return
        from src.database import RoadDataSchema
        if RoadDataSchema.initialize_database(self.db_mgr): self.db_text.insert('end','表结构初始化完成\n')

    def _db_import(self):
        if not hasattr(self,'db_mgr'): return
        from src.database import RoadDataImporter
        fm = {y:v.get().strip() for y,v in self.file_vars.items() if v.get().strip() and os.path.exists(v.get().strip())}
        imp = RoadDataImporter(self.db_mgr); s,p = imp.import_excel_data(fm)
        self.db_text.insert('end',f'导入：{s}路段, {p}PQI记录\n')

    def _db_sync(self):
        """同步：从Excel加载数据并导入数据库"""
        if not hasattr(self,'db_mgr'):
            messagebox.showwarning('提示','请先连接数据库'); return
        if not self.data_cache:
            messagebox.showwarning('提示','请先加载Excel数据'); return
        self._db_import()
        messagebox.showinfo('同步完成', 'Excel数据已同步到数据库')
        self.db_text.insert('end','数据同步完成\n')

    def _gen_map(self):
        if not self.data_cache: return
        try:
            from src.gis_map import GISMapGenerator
            g = GISMapGenerator()
            county = self.map_county_var.get()
            df = pd.concat(self.data_cache.values(), ignore_index=True) if county=='全部' else self.data_cache.get(county, pd.DataFrame())
            year = self.map_year_var.get()
            if year and '年份' in df.columns: df = df[df['年份']==int(year)]
            bmap = {'五华':(23.78,115.75),'蕉岭':(24.67,116.17),'和平':(24.47,114.94),'东源':(23.78,114.74)}
            blat, blon = bmap.get(county, (23.88,115.36))
            if 'lat_start' not in df.columns:
                df['lat_start'] = [blat+random.uniform(-0.05,0.05) for _ in range(len(df))]
                df['lon_start'] = [blon+random.uniform(-0.05,0.05) for _ in range(len(df))]
                df['lat_end'] = [blat+random.uniform(-0.05,0.05) for _ in range(len(df))]
                df['lon_end'] = [blon+random.uniform(-0.05,0.05) for _ in range(len(df))]
            m = g.add_road_segments(df, color_by=self.map_color_var.get().lower())
            if m:
                path = g.save_map(m, f'map_{county}_{year}.html')
                self.map_text.delete('1.0','end')
                self.map_text.insert('1.0',f'地图已生成：{path}\n{len(df)}个路段\n\n在文件管理器中打开查看')
                self.status_var.set('地图生成完成')
            else:
                self.map_text.insert('end','需要安装：pip install folium\n')
        except Exception as e:
            self.map_text.insert('end',f'错误：{e}\n')

    # ══════════════════════════════════════════════════════════════════════════
    #  工具方法
    # ══════════════════════════════════════════════════════════════════════════
    def _get_data(self, county):
        if not self.data_cache:
            messagebox.showwarning('提示','请先加载数据'); return pd.DataFrame()
        if county == '全部': return pd.concat(self.data_cache.values(), ignore_index=True)
        return self.data_cache.get(county, pd.DataFrame())

    def _export_tree(self, tree):
        if not tree.get_children(): return
        path = filedialog.asksaveasfilename(title='导出', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
        if path:
            rows = [tree.item(it,'values') for it in tree.get_children()]
            pd.DataFrame(rows, columns=tree['columns']).to_excel(path, index=False)
            messagebox.showinfo('成功','已导出')

    def _df_to_tree(self, tree, df):
        tree.delete(*tree.get_children())
        tree['columns'] = list(df.columns); tree['show'] = 'headings'
        for c in df.columns:
            tree.heading(c, text=c); tree.column(c, width=90, anchor='center')
        for _, row in df.iterrows():
            tree.insert('','end',values=[f'{v:.2f}' if isinstance(v,float) else str(v) for v in row])


if __name__ == '__main__':
    app = App()
    app.mainloop()