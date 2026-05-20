# 公路路况分析系统

基于2021-2025年四县路况检测数据的智能分析与报告生成系统。

## 功能特性

- **数据加载**：支持2021-2025年五个年份的四县路况Excel文件，自动处理不同年份的列名差异
- **数据筛选**：按县份、年份、PQI等级、路面类型、PQI范围多条件筛选，支持导出
- **图表生成**：
  - 📈 年度趋势折线图（PQI/PCI/RQI）
  - 📊 PQI等级里程分布柱状图
  - 📊 历年等级比例堆叠柱状图
  - 🥧 路面类型里程饼图
  - 📊 技术等级里程分布图
  - 🔧 养护需求里程与费用估算图
  - 🕸️ 四县对比雷达图
- **AI报告**：调用大模型（支持OpenAI/DeepSeek/智谱/讯飞/通义等）自动撰写专业分析文字
- **Word报告**：生成包含封面、章节、图表、数据表的完整Word格式报告

## 快速启动

### 方式一：直接运行（需要Python环境）

```bash
# 首次运行：安装依赖
pip install -r requirements.txt

# 启动程序
python main.py
```

或直接双击 `安装并启动.bat`（Windows）

### 方式二：打包为exe（分发给无Python用户）

```bash
python build.py
```

打包完成后，将 `dist/公路路况分析系统/` 目录复制给用户，双击 `公路路况分析系统.exe` 即可运行。

## 使用流程

1. **数据配置**：点击"数据配置"标签，配置各年份Excel文件路径，点击"加载数据"
2. **数据筛选**：在"数据筛选"标签页，可按各条件筛选查看路段数据
3. **分析图表**：在"分析图表"标签页，选择分析县份和图表类型，生成图表
4. **AI配置**：在"AI报告"标签页，填写API Key和接口地址，测试连接
5. **生成报告**：在"生成报告"标签页，点击"一键生成完整报告"，等待完成

## AI接口配置

| 服务商 | Base URL | 模型示例 |
|--------|----------|----------|
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| 智谱 | https://open.bigmodel.cn/api/paas/v4 | glm-4 |
| 讯飞 | https://spark-api-open.xf-yun.com/v1 | generalv3.5 |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |

> 如不配置AI，报告中的分析文字将使用内置模板，数据和图表仍正常生成。

## 养护分级标准

| 类型 | 条件 | 参考单价 |
|------|------|---------|
| 路面改造 | PQI<60 或 PCI<60 | 200万元/km |
| 中修 | PQI 60-70 或 PCI 60-70 | 80万元/km |
| 预防养护 | PQI 70-80 或 PCI 70-80 | 20万元/km |
| 日常养护 | 其余路段 | 5万元/km |

## 文件结构

```
路况分析程序/
├── main.py              # 主程序（GUI界面）
├── src/
│   ├── data_loader.py   # 数据加载与清洗
│   ├── analyzer.py      # 数据分析与图表
│   ├── llm_writer.py    # AI文字生成
│   └── report_writer.py # Word报告生成
├── config.json          # 配置文件
├── requirements.txt     # Python依赖
├── build.py             # 打包脚本
├── 启动程序.bat         # Windows快捷启动
└── 安装并启动.bat       # 首次安装+启动
```
