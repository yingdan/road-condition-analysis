"""
PostgreSQL/PostGIS 数据库模块
用于存储和管理公路养护数据
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
import os


# ══════════════════════════════════════════════════════════════════════════════════════
# 数据库连接管理
# ══════════════════════════════════════════════════════════════════════════════════════

class DatabaseConfig:
    """数据库配置"""

    def __init__(self, host='localhost', port=5432, database='road_maintenance',
                 user='postgres', password='', schema='public'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'schema': self.schema
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def get_connection_string(self):
        """获取连接字符串"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class DatabaseManager:
    """PostgreSQL/PostGIS 数据库管理器"""

    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self.connection = None
        self._psycopg2_available = False
        self._try_import()

    def _try_import(self):
        """尝试导入psycopg2"""
        try:
            import psycopg2
            self.psycopg2 = psycopg2
            self._psycopg2_available = True
        except ImportError:
            self.psycopg2 = None
            self._psycopg2_available = False

    def connect(self) -> bool:
        """建立数据库连接"""
        if not self._psycopg2_available:
            print("psycopg2 not installed. Run: pip install psycopg2-binary")
            return False

        try:
            self.connection = self.psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str, params=None) -> bool:
        """执行SQL语句"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"SQL error: {e}")
            self.connection.rollback()
            return False

    def fetch(self, sql: str, params=None) -> Optional[List]:
        """查询数据"""
        if not self.connection:
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchall()
            cursor.close()
            return result
        except Exception as e:
            print(f"Query error: {e}")
            return None

    def fetch_dataframe(self, sql: str, params=None) -> Optional[pd.DataFrame]:
        """查询数据返回DataFrame"""
        if not self.connection:
            return None

        try:
            return pd.read_sql_query(sql, self.connection, params=params)
        except Exception as e:
            print(f"Query error: {e}")
            return None

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        sql = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
        """
        result = self.fetch(sql, (self.config.schema, table_name))
        return result and result[0][0]

    def get_postgis_version(self) -> Optional[str]:
        """获取PostGIS版本"""
        result = self.fetch("SELECT PostGIS_Version()")
        return result[0][0] if result else None


# ══════════════════════════════════════════════════════════════════════════════════════
# 数据表创建
# ══════════════════════════════════════════════════════════════════════════════════════

class RoadDataSchema:
    """公路数据表结构定义"""

    # 路段基础信息表
    ROAD_SEGMENT_SQL = """
    CREATE TABLE IF NOT EXISTS road_segments (
        id SERIAL PRIMARY KEY,
        route_code VARCHAR(50) NOT NULL,           -- 路线编码
        route_name VARCHAR(200),                   -- 路线名称
        segment_start VARCHAR(50),                 -- 起点桩号
        segment_end VARCHAR(50),                   -- 终点桩号
        length_km DECIMAL(10,3),                   -- 长度(km)
        width_m DECIMAL(6,2),                     -- 路面宽度(m)
        direction VARCHAR(10),                    -- 方向
        technical_grade VARCHAR(50),              -- 技术等级
        pavement_type VARCHAR(50),                -- 路面类型
        county VARCHAR(100),                       -- 县份
        municipality VARCHAR(100),                -- 养管单位

        -- 几何信息 (PostGIS)
        geom GEOMETRY(LineString, 4490),           -- 线型几何

        -- 元数据
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_segment UNIQUE (route_code, segment_start, segment_end)
    );
    """

    # 技术状况数据表
    PQI_DATA_SQL = """
    CREATE TABLE IF NOT EXISTS pqi_data (
        id SERIAL PRIMARY KEY,
        segment_id INTEGER REFERENCES road_segments(id),
        year INTEGER NOT NULL,                    -- 年份
        pqi DECIMAL(5,2),                        -- 路面技术状况指数
        pci DECIMAL(5,2),                        -- 路面损坏状况指数
        rqi DECIMAL(5,2),                        -- 路面行驶质量指数
        pbi DECIMAL(5,2),                        -- 路面车辙指数
        rdi DECIMAL(5,2),                        -- 路面车辙指数
        pwi DECIMAL(5,2),                        -- 路面磨耗指数
        sri DECIMAL(5,2),                        -- 路面抗滑性能指数

        -- 分级
        pqi_grade VARCHAR(10),                  -- PQI分级
        pci_grade VARCHAR(10),                   -- PCI分级
        rqi_grade VARCHAR(10),                  -- RQI分级

        -- 损坏数据
        block_repair DECIMAL(10,2),              -- 块修(m2)
        strip_repair DECIMAL(10,2),              -- 条修(m2)
        crack_repair DECIMAL(10,2),              -- 龟裂/破碎板(m2)
        loose_repair DECIMAL(10,2),              -- 松散/露骨(m2)
        pothole DECIMAL(10,2),                  -- 坑槽(m2)
        transverse_crack DECIMAL(10,2),          -- 横缝(m)
        longitudinal_crack DECIMAL(10,2),        -- 纵缝(m)

        -- 其他指标
        dr DECIMAL(10,2),                        -- 损坏率
        iri DECIMAL(10,4),                       -- 国际平整度指数
        rd DECIMAL(10,4),                        -- 车辙深度

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 养护记录表
    MAINTENANCE_RECORD_SQL = """
    CREATE TABLE IF NOT EXISTS maintenance_records (
        id SERIAL PRIMARY KEY,
        segment_id INTEGER REFERENCES road_segments(id),
        maintenance_year INTEGER,                 -- 养护年份
        maintenance_type VARCHAR(50),           -- 养护类型
        maintenance_date DATE,                  -- 养护日期
        cost DECIMAL(15,2),                     -- 费用(元)
        scope VARCHAR(200),                      -- 养护范围
        method VARCHAR(200),                     -- 养护方法
        effect_pqi DECIMAL(5,2),                -- 养护后PQI
        remarks TEXT,                            -- 备注

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 养护项目库表
    MAINTENANCE_PROJECT_SQL = """
    CREATE TABLE IF NOT EXISTS maintenance_projects (
        id SERIAL PRIMARY KEY,
        project_code VARCHAR(50) UNIQUE,        -- 项目编号
        route_code VARCHAR(50),                  -- 路线编码
        segment_start VARCHAR(50),                -- 起点桩号
        segment_end VARCHAR(50),                 -- 终点桩号
        length_km DECIMAL(10,3),                 -- 长度(km)

        facility_type VARCHAR(50),               -- 设施类型
        pavement_type VARCHAR(50),               -- 路面类型
        technical_grade VARCHAR(50),             -- 技术等级

        -- 当前状况
        current_pqi DECIMAL(5,2),
        current_pci DECIMAL(5,2),
        current_rqi DECIMAL(5,2),

        -- 项目信息
        maintenance_type VARCHAR(50),            -- 养护类型
        planned_year INTEGER,                    -- 计划年度
        estimated_cost DECIMAL(15,2),          -- 估算费用(万元)
        priority_score DECIMAL(5,1),             -- 优先级评分
        status VARCHAR(20) DEFAULT 'pending',    -- 状态

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # 索引创建SQL
    INDEXES_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_segments_route ON road_segments(route_code);",
        "CREATE INDEX IF NOT EXISTS idx_segments_county ON road_segments(county);",
        "CREATE INDEX IF NOT EXISTS idx_segments_geom ON road_segments USING GIST(geom);",
        "CREATE INDEX IF NOT EXISTS idx_pqi_year ON pqi_data(year);",
        "CREATE INDEX IF NOT EXISTS idx_pqi_segment ON pqi_data(segment_id);",
        "CREATE INDEX IF NOT EXISTS idx_projects_year ON maintenance_projects(planned_year);",
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON maintenance_projects(status);",
    ]

    @classmethod
    def initialize_database(cls, db: DatabaseManager) -> bool:
        """初始化数据库表结构"""
        if not db.connection:
            return False

        print("Initializing database tables...")

        # 创建表
        tables = [
            ("road_segments", cls.ROAD_SEGMENT_SQL),
            ("pqi_data", cls.PQI_DATA_SQL),
            ("maintenance_records", cls.MAINTENANCE_RECORD_SQL),
            ("maintenance_projects", cls.MAINTENANCE_PROJECT_SQL),
        ]

        for table_name, sql in tables:
            if db.execute(sql):
                print(f"  Created/verified table: {table_name}")
            else:
                print(f"  Failed to create table: {table_name}")
                return False

        # 创建索引
        for idx_sql in cls.INDEXES_SQL:
            db.execute(idx_sql)

        # 启用PostGIS扩展（如果需要）
        db.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

        print("Database initialization complete.")
        return True


# ══════════════════════════════════════════════════════════════════════════════════════
# 数据导入/导出
# ══════════════════════════════════════════════════════════════════════════════════════

class RoadDataImporter:
    """从Excel导入数据到数据库"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def import_excel_data(self, file_map: Dict[int, str],
                         counties: List[str] = None) -> Tuple[int, int]:
        """
        从Excel文件导入数据到数据库

        Returns:
            (导入路段数, 导入PQI记录数)
        """
        from src.data_loader import load_all_data

        # 加载Excel数据
        data_dict = load_all_data(file_map, counties)
        if not data_dict:
            return 0, 0

        all_df = data_dict.get('全部', pd.DataFrame())
        if all_df.empty:
            return 0, 0

        segment_count = 0
        pqi_count = 0

        # 按县份处理
        for county in data_dict.keys():
            if county == '全部':
                continue

            county_df = data_dict[county]
            seg_count, pq_count = self._import_county_data(county_df, county)
            segment_count += seg_count
            pqi_count += pq_count

        return segment_count, pqi_count

    def _import_county_data(self, df: pd.DataFrame, county: str) -> Tuple[int, int]:
        """导入单个县份的数据"""
        segment_count = 0
        pqi_count = 0

        # 按年份处理
        for year in df['年份'].unique():
            year_df = df[df['年份'] == year]

            for _, row in year_df.iterrows():
                # 插入或更新路段
                if self._upsert_segment(row, county):
                    segment_count += 1

                # 获取segment_id
                segment_id = self._get_segment_id(row)
                if segment_id:
                    # 插入PQI数据
                    if self._upsert_pqi_data(segment_id, row, int(year)):
                        pqi_count += 1

        return segment_count, pqi_count

    def _upsert_segment(self, row: pd.Series, county: str) -> bool:
        """插入或更新路段信息"""
        sql = """
        INSERT INTO road_segments (
            route_code, route_name, segment_start, segment_end,
            length_km, width_m, direction, technical_grade, pavement_type, county
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (route_code, segment_start, segment_end)
        DO UPDATE SET
            length_km = EXCLUDED.length_km,
            width_m = EXCLUDED.width_m,
            technical_grade = EXCLUDED.technical_grade,
            pavement_type = EXCLUDED.pavement_type,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            return self.db.execute(sql, (
                row.get('路线编码'),
                None,  # route_name
                row.get('路段起点'),
                row.get('路段终点'),
                row.get('路段长度km'),
                row.get('路面宽度'),
                row.get('方向'),
                row.get('技术等级'),
                row.get('路面类型'),
                county
            ))
        except Exception as e:
            print(f"Segment insert error: {e}")
            return False

    def _get_segment_id(self, row: pd.Series) -> Optional[int]:
        """获取路段ID"""
        sql = """
        SELECT id FROM road_segments
        WHERE route_code = %s AND segment_start = %s AND segment_end = %s
        LIMIT 1
        """
        result = self.db.fetch(sql, (
            row.get('路线编码'),
            row.get('路段起点'),
            row.get('路段终点')
        ))
        return result[0][0] if result else None

    def _upsert_pqi_data(self, segment_id: int, row: pd.Series, year: int) -> bool:
        """插入PQI数据"""
        sql = """
        INSERT INTO pqi_data (
            segment_id, year, pqi, pci, rqi, pbi, rdi, pwi, sri,
            pqi_grade, pci_grade, rqi_grade,
            block_repair, strip_repair, crack_repair, loose_repair, pothole,
            transverse_crack, longitudinal_crack, dr, iri, rd
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            return self.db.execute(sql, (
                segment_id, year,
                row.get('PQI'), row.get('PCI'), row.get('RQI'),
                row.get('PBI'), row.get('RDI'), row.get('PWI'), row.get('SRI'),
                row.get('PQI分级'), row.get('PCI分级'), row.get('RQI分级'),
                row.get('块修(m2)'), row.get('条修(m2)'),
                row.get('龟裂/破碎板(m2)'), row.get('松散/露骨(m2)'),
                row.get('坑槽(m2)'), row.get('横缝(m)'), row.get('纵缝(m)'),
                row.get('DR'), row.get('IRI'), row.get('RD')
            ))
        except Exception as e:
            print(f"PQI insert error: {e}")
            return False


class RoadDataExporter:
    """从数据库导出数据"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def export_to_dataframe(self, year: int = None,
                           county: str = None,
                           route_code: str = None) -> Optional[pd.DataFrame]:
        """导出数据到DataFrame"""
        sql = """
        SELECT
            s.route_code, s.segment_start, s.segment_end, s.length_km,
            s.width_m, s.direction, s.technical_grade, s.pavement_type,
            s.county,
            p.year, p.pqi, p.pci, p.rqi, p.pbi, p.rdi, p.pwi, p.sri,
            p.pqi_grade, p.pci_grade, p.rqi_grade
        FROM road_segments s
        JOIN pqi_data p ON s.id = p.segment_id
        WHERE 1=1
        """

        params = []
        if year:
            sql += " AND p.year = %s"
            params.append(year)
        if county:
            sql += " AND s.county = %s"
            params.append(county)
        if route_code:
            sql += " AND s.route_code = %s"
            params.append(route_code)

        sql += " ORDER BY s.route_code, p.year"

        return self.db.fetch_dataframe(sql, tuple(params) if params else None)

    def export_projects(self) -> Optional[pd.DataFrame]:
        """导出项目库"""
        sql = """
        SELECT
            project_code, route_code, segment_start, segment_end, length_km,
            facility_type, pavement_type, technical_grade,
            current_pqi, current_pci, current_rqi,
            maintenance_type, planned_year, estimated_cost, priority_score, status
        FROM maintenance_projects
        ORDER BY planned_year, priority_score DESC
        """
        return self.db.fetch_dataframe(sql)


# ══════════════════════════════════════════════════════════════════════════════════════
# 数据库配置管理
# ══════════════════════════════════════════════════════════════════════════════════════

CONFIG_FILE = 'db_config.json'

def save_db_config(config: DatabaseConfig):
    """保存数据库配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

def load_db_config() -> Optional[DatabaseConfig]:
    """加载数据库配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return DatabaseConfig.from_dict(json.load(f))
        except:
            pass
    return None
