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
    {'num': 4, 'label': '预测模型',     'desc': '衰减率与预测'},
    {'num': 5, 'label': '养护对策',     'desc': '阈值/回调/单价'},
    {'num': 6, 'label': '需求分析',     'desc': '养护需求与排序'},
    {'num': 7, 'label': '预算资金',     'desc': '资金优化分配'},
    {'num': 8, 'label': '项目库',       'desc': '中长期规划'},
    {'num': 9, 'label': '效益评估',     'desc': '评估与反馈'},
    {'num': 10,'label': 'GIS地图',      'desc': '路况可视化地图'},
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

    def _setup_style(self):
        s = ttk.Style(); s.theme_use('clam')
        s.configure('.', background=THEME['bg'], font=('Microsoft YaHei', 9))
        s.configure('Card.TFrame', background=THEME['card'], relief='solid', borderwidth=1)
        s.configure('Title.TLabel', font=('Microsoft YaHei', 15, 'bold'), foreground=THEME['text'])
        s.configure('Sub.TLabel', font=('Microsoft YaHei', 9), foreground=THEME['text_light'])
        s.configure('TNotebook', background=THEME['bg'])
        s.configure('TNotebook.Tab', font=('Microsoft YaHei', 10), padding=(10, 5))
        s.configure('TLabelframe', background=THEME['card'])
        s.configure('TLabelframe.Label', font=('Microsoft YaHei', 10, 'bold'), foreground=THEME['text'])

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
                btn.config(fg='white', font=('Microsoft YaHei', 10, 'bold'), bg=THEME['sidebar_active'])
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
        for i in range(1, 11):
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
                 bg=THEME['success'], fg='white', font=('Microsoft YaHei', 10, 'bold'),
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
        cols = ('路线编码','路段起点','路段终点','路段长度km','路面类型','PQI','PCI','RQI','PQI分级','年份','县份')
        tvf = tk.Frame(sf, bg=THEME['bg']); tvf.pack(fill='both', expand=True, padx=20, pady=5)
        self.data_tree = ttk.Treeview(tvf, columns=cols, show='headings', height=14)
        ws = {'路线编码':80,'路段起点':65,'路段终点':65,'路段长度km':65,'路面类型':75,'PQI':50,'PCI':50,'RQI':50,'PQI分级':50,'年份':40,'县份':50}
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
            for a in ['tech_county_cb','model_county_cb','demand_county_cb','budget_county_cb','map_county_cb']:
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
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10, 'bold'), padx=15, cursor='hand2').pack(side='left', padx=15)
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
        cols = ('道路类型','指标','均值','优良路率','次差路率','优里程','良里程','中里程','次里程','差里程','评定里程')
        tf1, tv1 = self._build_section_table(self.tech_sections['road_type'], cols, 5, ws={'道路类型':65,'指标':50,'均值':55,'优良路率':70,'次差路率':70,'优里程':55,'良里程':55,'中里程':55,'次里程':55,'差里程':55,'评定里程':70})
        for road in ['国道','省道']:
            rd = df[df['道路类型']==road]
            for idx, label in [('PQI','PQI'),('PCI','PCI'),('RQI','RQI')]:
                if idx not in rd.columns: continue
                t = rd['路段长度km'].sum()
                avg = rd[idx].mean() if not rd[idx].isna().all() else 0
                gr = rd[rd[idx]>=80]['路段长度km'].sum()/t*100 if t>0 else 0
                br = rd[rd[idx]<70]['路段长度km'].sum()/t*100 if t>0 else 0
                yl=rd[(rd[idx]>=90)&(rd[idx]<=100)]['路段长度km'].sum()
                lh=rd[(rd[idx]>=80)&(rd[idx]<90)]['路段长度km'].sum()
                z=rd[(rd[idx]>=70)&(rd[idx]<80)]['路段长度km'].sum()
                ci=rd[(rd[idx]>=60)&(rd[idx]<70)]['路段长度km'].sum()
                ch=rd[rd[idx]<60]['路段长度km'].sum()
                tv1.insert('','end',values=(road,label,f'{avg:.1f}',f'{gr:.1f}%',f'{br:.1f}%',f'{yl:.1f}',f'{lh:.1f}',f'{z:.1f}',f'{ci:.1f}',f'{ch:.1f}',f'{t:.1f}'))
        self._build_section_chart(self.tech_sections['road_type'], tv1, 'group_bar', title='国道/省道 × PQI/PCI/RQI 对比')

        # ── 表2: 路线评价 ──
        self._clear_section('route')
        cols2 = ('路线编码','PQI均值','PQI优良路率','PCI均值','PCI优良路率','RQI均值','RQI优良路率')
        tf2, tv2 = self._build_section_table(self.tech_sections['route'], cols2, 8, ws={'路线编码':90,'PQI均值':75,'PQI优良路率':90,'PCI均值':75,'PCI优良路率':90,'RQI均值':75,'RQI优良路率':90})
        for rt_code, rd in df.groupby('路线编码'):
            t = rd['路段长度km'].sum()
            vals = []
            for idx in ['PQI','PCI','RQI']:
                if idx in rd.columns:
                    avg = rd[idx].mean() if not rd[idx].isna().all() else 0
                    gr = rd[rd[idx]>=80]['路段长度km'].sum()/t*100 if t>0 else 0
                    vals += [f'{avg:.1f}', f'{gr:.1f}%']
                else:
                    vals += ['-','-']
            tv2.insert('','end',values=(rt_code, *vals))
        tv2.insert('','end',values=('全路网',*[v for _ in ['PQI','PCI','RQI'] for v in [f"{df['PQI'].mean():.1f}" if 'PQI' in df.columns else '-',f"{df[df['PQI']>=80]['路段长度km'].sum()/df['路段长度km'].sum()*100:.1f}%" if 'PQI' in df.columns else '-']]))
        self._build_section_chart(self.tech_sections['route'], tv2, 'line', title='各路线PQI/PCI/RQI对比')

        # ── 表3: 技术等级 ──
        self._clear_section('tech_grade')
        cols3 = ('技术等级','PQI均值','PQI优良路率','PCI均值','PCI优良路率','RQI均值','RQI优良路率')
        tf3, tv3 = self._build_section_table(self.tech_sections['tech_grade'], cols3, 5, ws={'技术等级':85,'PQI均值':80,'PQI优良路率':80,'PCI均值':80,'PCI优良路率':80,'RQI均值':80,'RQI优良路率':80})
        grade_map = {'一':'一级公路','二':'二级公路','三':'三级公路','四':'四级公路'}
        for key, grade in grade_map.items():
            rd = df[df['技术等级'].str.contains(key, na=False)] if '技术等级' in df.columns else pd.DataFrame()
            if rd.empty and '技术等级' in df.columns: rd = df[df['技术等级']==grade]
            if rd.empty: continue
            t = rd['路段长度km'].sum()
            if t == 0: t = 1
            vals = []
            for idx in ['PQI','PCI','RQI']:
                avg = rd[idx].mean() if idx in rd.columns and not rd[idx].isna().all() else 0
                gr = rd[rd[idx]>=80]['路段长度km'].sum()/t*100 if t>0 else 0
                vals += [f'{avg:.1f}',f'{gr:.1f}%']
            tv3.insert('','end',values=(grade, *vals))
        if not tv3.get_children():
            t = df['路段长度km'].sum(); t = t if t>0 else 1
            for idx in ['PQI','PCI','RQI']:
                avg = df[idx].mean() if idx in df.columns and not df[idx].isna().all() else 0
                gr = df[df[idx]>=80]['路段长度km'].sum()/t*100 if t>0 else 0
                tv3.insert('','end',values=('全路网', f'{avg:.1f}',f'{gr:.1f}%', '-','-', '-','-'))
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
            pqim = yd['PQI'].mean() if 'PQI' in yd.columns else 0
            pcim = yd['PCI'].mean() if 'PCI' in yd.columns else 0
            rqim = yd['RQI'].mean() if 'RQI' in yd.columns else 0
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
        tk.Button(rp, text='📋', font=('Microsoft YaHei', 7),
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
        tk.Button(bf, text='💾 导出图表', font=('Microsoft YaHei', 7),
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
        self._section_sub(parent, '技术指标(加权PQI+优良路率) + 经济指标(B/C+成本+ROI) — 短期/中期/长期')

        self.target_vars = {}
        horizons = [
            ('short', '短期目标 (1年)', '近期达标线'),
            ('mid',   '中期目标 (2-5年)', '中期规划目标'),
            ('long',  '长期目标 (5-10年)', '远期愿景目标'),
        ]
        # 默认目标：技术+经济双维度
        default_targets = {
            'short': {'国道_PQI':90,'国道_优良路率':92,'国道_BCR':1.2,'国道_km成本':50,
                      '省道_PQI':88,'省道_优良路率':88,'省道_BCR':1.1,'省道_km成本':55},
            'mid':   {'国道_PQI':92,'国道_优良路率':95,'国道_BCR':1.5,'国道_km成本':45,
                      '省道_PQI':90,'省道_优良路率':92,'省道_BCR':1.3,'省道_km成本':50},
            'long':  {'国道_PQI':94,'国道_优良路率':98,'国道_BCR':2.0,'国道_km成本':40,
                      '省道_PQI':93,'省道_优良路率':95,'省道_BCR':1.8,'省道_km成本':45},
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
            tk.Label(grd, text='经济→', bg=self._bg(gd), fg=THEME['success'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(5,5))
            for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['国道_BCR']),
                                       ('成本万/km','km成本',default_targets[hkey]['国道_km成本'])]:
                tk.Label(grd, text=f'{label} ', bg=self._bg(gd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=int(dv*100)) if suffix=='BCR' else tk.IntVar(value=dv)
                self.target_vars[f'{hkey}_国道_{suffix}'] = v
                w = 4 if suffix=='BCR' else 5
                ttk.Entry(grd, textvariable=v, width=w, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))
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
            tk.Label(srd, text='经济→', bg=self._bg(sd), fg=THEME['success'],
                    font=('Microsoft YaHei',8,'bold')).pack(side='left', padx=(5,5))
            for label, suffix, dv in [('B/C','BCR',default_targets[hkey]['省道_BCR']),
                                       ('成本万/km','km成本',default_targets[hkey]['省道_km成本'])]:
                tk.Label(srd, text=f'{label} ', bg=self._bg(sd), font=('Microsoft YaHei',9)).pack(side='left')
                v = tk.IntVar(value=int(dv*100)) if suffix=='BCR' else tk.IntVar(value=dv)
                self.target_vars[f'{hkey}_省道_{suffix}'] = v
                w = 4 if suffix=='BCR' else 5
                ttk.Entry(srd, textvariable=v, width=w, font=('Microsoft YaHei',9)).pack(side='left', padx=(0,8))

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
            # 经济指标(估算)
            width = rd['路面宽度'].mean() if '路面宽度' in rd.columns else 7
            est_cost = t * 1000 * width * 300 / 10000  # 估算养护投资(万元)
            from src.decision.cost_model import calc_bcr_ratio
            bcr = calc_bcr_ratio(rd, est_cost) if est_cost>0 else 0
            km_cost = est_cost / t if t>0 else 0

            for metric, cur_val, suffix in [
                ('加权PQI', w_pqi, 'PQI'), ('优良路率(%)', good_rate, '优良路率'),
                ('B/C比', bcr, 'BCR'), ('每km成本(万)', km_cost, 'km成本')
            ]:
                short_t = self.target_vars.get(f'short_{road}_{suffix}', tk.IntVar(value=0)).get()
                mid_t   = self.target_vars.get(f'mid_{road}_{suffix}', tk.IntVar(value=0)).get()
                long_t  = self.target_vars.get(f'long_{road}_{suffix}', tk.IntVar(value=0)).get()
                # B/C值以百分存储(×100)，需除以100显示
                if suffix == 'BCR':
                    cur_fmt = f'{cur_val:.2f}'
                    s_fmt = f'{short_t/100:.2f}'
                    m_fmt = f'{mid_t/100:.2f}'
                    l_fmt = f'{long_t/100:.2f}'
                else:
                    cur_fmt = f'{cur_val:.1f}'; s_fmt = f'{short_t}'; m_fmt = f'{mid_t}'; l_fmt = f'{long_t}'
                self.target_tree.insert('','end',values=('技术/经济',road,metric,cur_fmt,s_fmt,m_fmt,l_fmt))
        self.status_var.set('目标对比完成')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面4: 预测模型
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page4(self, parent):
        self._section_title(parent, '📈 性能预测模型')
        self._section_sub(parent, '使用指数衰减模型 PQI(t)=PQI₀×e^(-k×t)，基于历年数据回归标定')

        card = self._card(parent, '模型参数')
        r = self._row(card)
        tk.Label(r, text='县份：', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left')
        self.model_county_var = tk.StringVar(value='全部')
        self.model_county_cb = ttk.Combobox(r, textvariable=self.model_county_var, width=12, state='readonly', values=['全部'])
        self.model_county_cb.pack(side='left', padx=8)
        tk.Button(r, text='计算衰减率', command=self._calc_decay,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=12, cursor='hand2').pack(side='left', padx=10)
        tk.Button(r, text='5年预测', command=self._gen_prediction,
                 font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=5)
        tk.Button(r, text='养护计划', command=self._calc_maint_plan,
                 font=('Microsoft YaHei', 9), padx=8).pack(side='left', padx=5)

        # 衰减率表格
        card2 = self._card(parent, '衰减系数标定', expand=True)
        cols = ('路面类型','技术等级','PQI衰减k','PCI衰减k','RQI衰减k','样本数')
        self.decay_tree = ttk.Treeview(card2, columns=cols, show='headings', height=6)
        for c in cols: self.decay_tree.heading(c, text=c); self.decay_tree.column(c, width=110, anchor='center')
        self.decay_tree.pack(fill='both', expand=True)
        r = self._row(parent, 5)
        tk.Button(r, text='📥 导出', command=lambda:self._export_tree(self.decay_tree), font=('Microsoft YaHei',9)).pack(side='left', padx=20)

        # 预测结果表格
        card3 = self._card(parent, '预测/计划结果', expand=True)
        self.pred_tree = ttk.Treeview(card3, show='headings', height=8)
        self.pred_tree.pack(fill='both', expand=True)

    def _calc_decay(self):
        from src.decay_calculator import calculate_decay_rates, get_calibration_table
        df = self._get_data(self.model_county_var.get())
        if df.empty: return
        c = None if self.model_county_var.get()=='全部' else self.model_county_var.get()
        table = get_calibration_table(df, c)
        self.decay_tree.delete(*self.decay_tree.get_children())
        for row in table: self.decay_tree.insert('','end',values=row)
        self.mark_step_done(4); self.status_var.set('衰减率标定完成')

    def _gen_prediction(self):
        from src.decay_calculator import predict_5year_pqi
        df = self._get_data(self.model_county_var.get() or None)
        if df.empty: return
        c = None if self.model_county_var.get() in ['全部',''] else self.model_county_var.get()
        result = predict_5year_pqi(df, c)
        if result is not None and not result.empty:
            self._df_to_tree(self.pred_tree, result)
            self.status_var.set(f'5年预测完成 — {len(result)}条路线')

    def _calc_maint_plan(self):
        from src.decay_calculator import get_yearly_summary
        df = self._get_data(self.model_county_var.get() or None)
        if df.empty: return
        c = None if self.model_county_var.get() in ['全部',''] else self.model_county_var.get()
        result = get_yearly_summary(df, c)
        if result is not None and not result.empty:
            self._df_to_tree(self.pred_tree, result)
            self.status_var.set('养护计划计算完成')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面5: 养护对策
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page5(self, parent):
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

        self._section_title(sf, '⚙️ 养护对策模型')
        self._section_sub(sf, '配置养护触发阈值、养护后路面状况回调值及养护方案单价')

        # 一、触发阈值
        card = self._card(sf, '一、养护触发阈值')
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

        # 二、回调值
        card2 = self._card(sf, '二、养护后PQI/PCI/RQI回调值 — 养护后路面回升到的目标值')
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

        # 三、单价
        card3 = self._card(sf, '三、养护方案单价 — 用户自定义')
        self.price_vars = {}
        h4 = self._row(card3, 3)
        for t,w in [('养护类型',12),('路面类型',10),('单价(元/m²)',12)]:
            tk.Label(h4, text=t, width=w, bg=THEME['card'], font=('Microsoft YaHei',8,'bold')).pack(side='left')
        for m,pt,dp in [
            ('路面改造','沥青路面',319),('路面改造','水泥路面',299),
            ('预防性养护','沥青路面',160),('预防性养护','水泥路面',140),
            ('日常养护','沥青路面',30),('日常养护','水泥路面',25),
        ]:
            r = self._row(card3, 2)
            tk.Label(r, text=m, width=12, bg=THEME['card']).pack(side='left')
            tk.Label(r, text=pt, width=10, bg=THEME['card']).pack(side='left')
            v = tk.IntVar(value=dp); self.price_vars[f'{m}_{pt}'] = v
            ttk.Entry(r, textvariable=v, width=10).pack(side='left')

        # 按钮
        r = self._row(sf, 15)
        tk.Button(r, text='💾 保存全部配置', command=self._save_policy_config,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10, 'bold'),
                 padx=18, pady=4, cursor='hand2').pack(side='left', padx=20)
        tk.Button(r, text='↺ 恢复默认', command=self._reset_policy_config,
                 font=('Microsoft YaHei', 9), padx=12).pack(side='left', padx=5)

    def _save_policy_config(self):
        cfg = self.config
        cfg['triggers'] = {k:v.get() for k,v in self.trigger_vars.items()}
        cfg['callbacks'] = {k:v.get() for k,v in self.callback_vars.items()}
        cfg['prices'] = {k:v.get() for k,v in self.price_vars.items()}
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
    #  页面6: 需求分析
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page6(self, parent):
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

    def _run_demand(self):
        df = self._get_data(self.demand_county_var.get())
        if df.empty: return
        if '年份' in df.columns: df = df[df['年份']==df['年份'].max()]
        ty = int(self.demand_year_var.get())
        try:
            from src.decision.performance_models import calibrate_exponential_model
            all_df = pd.concat(self.data_cache.values(), ignore_index=True)
            dr = calibrate_exponential_model(all_df)
            result = analyze_demand(df, target_year=ty, decay_rates=dr)
            def cc(r):
                ln = r.get('路段长度(km)',1); mt = r.get('养护类型','日常养护'); pt = r.get('路面类型','沥青路面')
                pk = f'{mt}_{pt}'
                pr = self.price_vars[pk].get() if hasattr(self,'price_vars') and pk in self.price_vars else {'路面改造_沥青路面':319,'预防性养护_沥青路面':160,'日常养护_沥青路面':30}.get(pk,300)
                return round(ln*1000*7*pr/10000,2)
            result['路段长度(km)'] = result.apply(lambda r: r.get('路段长度(km)',1), axis=1)
            result['估算费用(万元)'] = result.apply(cc, axis=1)
            result['养护类型'] = result['养护类型'].fillna('日常养护')
            self.demand_result_df = result
            self._refresh_demand_tree(result, ty)
            self.demand_summary.config(text=f'总路段：{len(result)} | 路面改造：{len(result[result["养护类型"]=="路面改造"])} | 预防性养护：{len(result[result["养护类型"]=="预防性养护"])} | 日常养护：{len(result[result["养护类型"]=="日常养护"])}')
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
    #  页面7: 预算资金
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page7(self, parent):
        self._section_title(parent, '💰 养护预算与资金优化分配')
        self._section_sub(parent, '预算约束下的养护资金优化分配')

        card = self._card(parent, '预算配置')
        r = self._row(card)
        tk.Label(r, text='年度预算(万元)：', bg=THEME['card'], font=('Microsoft YaHei', 10)).pack(side='left')
        self.budget_var = tk.StringVar(value='5000')
        ttk.Entry(r, textvariable=self.budget_var, width=10, font=('Microsoft YaHei', 10)).pack(side='left', padx=8)
        tk.Label(r, text='分配方法：', bg=THEME['card'], font=('Microsoft YaHei', 9)).pack(side='left', padx=(15,0))
        self.alloc_method_var = tk.StringVar(value='优先序法')
        ttk.Combobox(r, textvariable=self.alloc_method_var, width=12, values=['优先序法','增量分析法','多目标优化']).pack(side='left', padx=8)
        tk.Button(r, text='▶ 执行资金分配', command=self._run_budget,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=12, cursor='hand2').pack(side='left', padx=15)
        tk.Button(r, text='📥 导出', command=self._export_budget, font=('Microsoft YaHei', 9)).pack(side='left', padx=5)

        card2 = self._card(parent, '资金分配方案', expand=True)
        cols = ('养护类型','项目数','需求资金(万元)','分配资金(万元)','满足率(%)')
        self.budget_tree = ttk.Treeview(card2, columns=cols, show='headings', height=5)
        for c in cols: self.budget_tree.heading(c, text=c); self.budget_tree.column(c, width=130, anchor='center')
        self.budget_tree.pack(fill='both', expand=True)
        self.budget_info = tk.Label(parent, text='', bg=THEME['bg'], fg=THEME['text_light'], font=('Microsoft YaHei', 9))
        self.budget_info.pack(anchor='w', padx=20)
        self.budget_result = None

    def _run_budget(self):
        if self.demand_result_df is None or self.demand_result_df.empty:
            messagebox.showwarning('提示','请先在"需求分析"中执行分析'); return
        try:
            from src.decision.budget_allocation import priority_allocation_by_type
            budget = float(self.budget_var.get())
            result = priority_allocation_by_type(self.demand_result_df, budget)
            self.budget_result = result
            self.budget_tree.delete(*self.budget_tree.get_children())
            for mt in ['路面改造','预防性养护','日常养护','总计']:
                if mt in result:
                    r = result[mt]
                    self.budget_tree.insert('','end',values=(mt,'-',f"{r.get('需求金额(万元)',0):.2f}",f"{r.get('分配预算(万元)',0):.2f}",f"{r.get('满足程度(%)',0):.1f}%"))
            self.budget_info.config(text=f'方法：{self.alloc_method_var.get()} | 预算：{budget}万元')
            self.mark_step_done(7); self.status_var.set('资金分配完成')
        except Exception as e:
            messagebox.showerror('错误', str(e))

    def _export_budget(self):
        self._export_tree(self.budget_tree)

    # ══════════════════════════════════════════════════════════════════════════
    #  页面8: 项目库
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page8(self, parent):
        self._section_title(parent, '📋 养护工程项目库')
        self._section_sub(parent, '中长期养护规划：养护工程项目库管理')

        card = self._card(parent)
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

    def _pool_refresh(self):
        self.pool_tree.delete(*self.pool_tree.get_children())
        if self.project_pool:
            for p in self.project_pool.projects:
                self.pool_tree.insert('','end',values=(p.project_id, p.route_code, p.maintenance_type or '',
                    p.maintenance_year or '', f'{p.length:.2f}' if p.length else '',
                    f'{p.estimated_cost:.2f}' if p.estimated_cost else '',
                    f'{p.priority_score:.1f}' if p.priority_score else '', p.status or ''))

    def _pool_import_demand(self):
        if self.demand_result_df is None or self.demand_result_df.empty:
            messagebox.showwarning('提示','请先执行需求分析'); return
        if MaintenanceProject and self.project_pool:
            for _, row in self.demand_result_df.iterrows():
                ln = row.get('路段长度(km)',1)
                p = MaintenanceProject(route_code=row.get('路线编码',''),
                    segment_start=str(row.get('路段起点','')), segment_end=str(row.get('路段终点','')),
                    length=ln, pavement_type=row.get('路面类型',''),
                    current_condition={'PQI':row.get('当前PQI',80)},
                    maintenance_type=row.get('养护类型',''),
                    maintenance_year=int(self.demand_year_var.get()),
                    estimated_cost=row.get('估算费用(万元)',ln*1000*7*300/10000),
                    priority_score=row.get('优先级评分',0))
                self.project_pool.add_project(p)
            self._pool_refresh()
            self.mark_step_done(8); self.status_var.set(f'已导入{len(self.demand_result_df)}个项目')

    def _pool_export(self):
        if not self.project_pool or not self.project_pool.projects: return
        path = filedialog.asksaveasfilename(title='导出', defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')], initialfile='养护工程项目库.xlsx')
        if path: self.project_pool.to_excel(path); messagebox.showinfo('成功','已导出')

    def _pool_import(self):
        path = filedialog.askopenfilename(title='导入', filetypes=[('Excel','*.xlsx')])
        if path and self.project_pool:
            self.project_pool.from_excel(path); self._pool_refresh()

    def _pool_clear(self):
        if messagebox.askyesno('确认','清空项目库？'):
            if self.project_pool: self.project_pool.projects.clear()
            self._pool_refresh()

    def _pool_gen_plan(self):
        from src.decision.project_pool import generate_annual_plan
        if not self.project_pool or not self.project_pool.projects:
            messagebox.showwarning('提示','项目库为空'); return
        plan = generate_annual_plan(self.project_pool, 2026, float(self.budget_var.get()))
        self._pool_refresh()
        messagebox.showinfo('完成', f"年度计划：{plan.get('项目数',0)}个项目 | 总费用：{plan.get('总费用(万元)',0)}万元")

    # ══════════════════════════════════════════════════════════════════════════
    #  页面9: 效益评估
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page9(self, parent):
        self._section_title(parent, '✅ 综合效益评估（技术+经济双维度）')
        self._section_sub(parent, '技术达标度 + 经济效益度 → 综合评分 → 不满足则调整后重新分析')

        card = self._card(parent)
        r = self._row(card)
        tk.Button(r, text='▶ 执行综合评估', command=self._run_benefit,
                 bg=THEME['accent'], fg='white', font=('Microsoft YaHei', 10), padx=15, cursor='hand2').pack(side='left')
        tk.Button(r, text='📥 导出报告', command=self._export_benefit, font=('Microsoft YaHei', 9)).pack(side='left', padx=10)
        tk.Button(r, text='⚠ 不满足？调整后重算', command=self._feedback_adjust,
                 bg=THEME['warning'], fg='white', font=('Microsoft YaHei', 10), padx=10, cursor='hand2').pack(side='left', padx=10)

        # 技术达标评估表
        card2 = self._card(parent, '技术达标评估', expand=True)
        cols = ('道路类型','指标','当前值','短期目标','中期目标','长期目标','达成')
        self.benefit_tech_tree = ttk.Treeview(card2, columns=cols, show='headings', height=5)
        for c in cols: self.benefit_tech_tree.heading(c, text=c); self.benefit_tech_tree.column(c, width=105, anchor='center')
        self.benefit_tech_tree.pack(fill='both', expand=True)

        # 经济效益评估表
        card3 = self._card(parent, '经济效益评估', expand=True)
        cols2 = ('道路类型','指标','当前值','目标值','达成')
        self.benefit_econ_tree = ttk.Treeview(card3, columns=cols2, show='headings', height=5)
        for c in cols2: self.benefit_econ_tree.heading(c, text=c); self.benefit_econ_tree.column(c, width=110, anchor='center')
        self.benefit_econ_tree.pack(fill='both', expand=True)

        # 综合评分
        card4 = self._card(parent, '综合评分')
        self.benefit_text = tk.Text(card4, height=6, wrap='word', font=('Consolas', 10))
        self.benefit_text.pack(fill='both', expand=True)

    def _run_benefit(self):
        if not self.data_cache:
            messagebox.showwarning('提示','请先加载数据'); return
        try:
            df_all = pd.concat(self.data_cache.values(), ignore_index=True)
            if '年份' in df_all.columns: df_all = df_all[df_all['年份']==df_all['年份'].max()]
            def rt(r):
                s = str(r); return '国道' if s.startswith('G') else ('省道' if s.startswith('S') else '其他')
            if '路线编码' in df_all.columns: df_all['道路类型'] = df_all['路线编码'].apply(rt)
            if '路段长度km' not in df_all.columns: df_all['路段长度km'] = 1.0

            from src.decision.cost_model import calc_weighted_pqi, calc_good_road_rate, calc_bcr_ratio, calc_km_cost, calc_comprehensive_score

            # 技术达标表
            self.benefit_tech_tree.delete(*self.benefit_tech_tree.get_children())
            tech_scores = {}
            for road in ['国道','省道']:
                rd = df_all[df_all['道路类型']==road]
                if rd.empty: continue
                t = rd['路段长度km'].sum()
                w_pqi = calc_weighted_pqi(rd)
                gr = calc_good_road_rate(rd)
                metrics = [('加权PQI', w_pqi, 'PQI'), ('优良路率(%)', gr, '优良路率')]
                road_score = 0; cnt = 0
                for metric, cur, suffix in metrics:
                    mid_t = self.target_vars.get(f'mid_{road}_{suffix}', tk.IntVar(value=0)).get() if hasattr(self,'target_vars') else 80
                    ok = '✓' if cur >= mid_t else '✗'
                    if ok == '✓': cnt += 1
                    self.benefit_tech_tree.insert('','end',values=(road,metric,f'{cur:.1f}',
                        f'{self.target_vars.get(f"short_{road}_{suffix}",tk.IntVar(value=0)).get() if hasattr(self,"target_vars") else "-"}',
                        f'{mid_t}',
                        f'{self.target_vars.get(f"long_{road}_{suffix}",tk.IntVar(value=0)).get() if hasattr(self,"target_vars") else "-"}',
                        ok))
                tech_scores[road] = (cnt / len(metrics) * 100) if metrics else 0

            # 经济效益表
            self.benefit_econ_tree.delete(*self.benefit_econ_tree.get_children())
            econ_scores = {}
            for road in ['国道','省道']:
                rd = df_all[df_all['道路类型']==road]
                if rd.empty: continue
                t = rd['路段长度km'].sum(); w = rd['路面宽度'].mean() if '路面宽度' in rd.columns else 7
                est_cost = t * 1000 * w * 300 / 10000
                bcr = calc_bcr_ratio(rd, est_cost)
                kmc = calc_km_cost(est_cost, rd)
                mid_bcr = self.target_vars.get(f'mid_{road}_BCR', tk.IntVar(value=150)).get()/100 if hasattr(self,'target_vars') else 1.5
                mid_kmc = self.target_vars.get(f'mid_{road}_km成本', tk.IntVar(value=50)).get() if hasattr(self,'target_vars') else 50
                metrics2 = [('B/C比', bcr, mid_bcr, 'higher'), ('每km成本(万)', kmc, mid_kmc, 'lower')]
                road_econ = 0; cnt2 = 0
                for metric, cur, target, direction in metrics2:
                    ok = '✓' if (direction=='higher' and cur>=target) or (direction=='lower' and cur<=target) else '✗'
                    if ok == '✓': cnt2 += 1
                    self.benefit_econ_tree.insert('','end',values=(road,metric,f'{cur:.2f}',f'{target}',ok))
                econ_scores[road] = (cnt2 / len(metrics2) * 100) if metrics2 else 0

            # 综合评分
            tech_avg = sum(tech_scores.values())/len(tech_scores) if tech_scores else 0
            econ_avg = sum(econ_scores.values())/len(econ_scores) if econ_scores else 0
            comp = calc_comprehensive_score(tech_avg, econ_avg)

            self.benefit_text.delete('1.0','end')
            self.benefit_text.insert('end', '='*50 + '\n')
            self.benefit_text.insert('end', '  综合效益评估结果（技术+经济双维度）\n')
            self.benefit_text.insert('end', '='*50 + '\n\n')
            self.benefit_text.insert('end', f'  技术达标得分：{comp["技术得分"]:.1f} / 100  (权重 {int(comp["技术权重"]*100)}%)\n')
            self.benefit_text.insert('end', f'  经济效益得分：{comp["经济得分"]:.1f} / 100  (权重 {int(comp["经济权重"]*100)}%)\n')
            self.benefit_text.insert('end', f'  ──────────────────────\n')
            self.benefit_text.insert('end', f'  综合得分：{comp["综合得分"]:.1f} / 100  等级：{comp["等级"]}\n')
            self.benefit_text.insert('end', f'  建议：{comp["建议"]}\n')
            if comp['综合得分'] < 75:
                self.benefit_text.insert('end', '\n  ⚠ 综合得分不足，请返回调整后重新评估\n')
            self.mark_step_done(9)
            self.status_var.set(f'综合评估完成 — {comp["等级"]} ({comp["综合得分"]:.0f}分)')
        except Exception as e:
            import traceback; traceback.print_exc()
            messagebox.showerror('错误', str(e))

    def _feedback_adjust(self):
        messagebox.showinfo('反馈调整',
            '请按以下步骤调整：\n\n'
            '1. 返回【3.目标设定】调整养护目标\n'
            '2. 返回【5.养护对策】调整触发阈值或单价\n'
            '3. 重新运行【6.需求分析】\n'
            '4. 重新运行【7.预算资金】\n'
            '5. 重新导入【8.项目库】\n'
            '6. 再次执行【9.效益评估】\n')
        self._switch_step(3)

    def _export_benefit(self):
        # 导出技术+经济两份表到一个Excel
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')], initialfile='综合评估.xlsx')
        if not path: return
        with pd.ExcelWriter(path) as writer:
            for prefix, tree in [('技术评估', self.benefit_tech_tree), ('经济评估', self.benefit_econ_tree)]:
                rows = [tree.item(it,'values') for it in tree.get_children()]
                if rows:
                    pd.DataFrame(rows, columns=tree['columns']).to_excel(writer, sheet_name=prefix, index=False)
        messagebox.showinfo('成功','综合评估报告已导出')

    # ══════════════════════════════════════════════════════════════════════════
    #  页面10: GIS地图
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page10(self, parent):
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