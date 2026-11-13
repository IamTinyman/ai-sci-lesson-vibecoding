# AI-SCI Lesson Vibe Coding

本项目使用 Chicago Divvy 共享单车行程与 NOAA 天气数据开展探索性分析，研究问题将在数据检查和探索后提出。

## 课程交付目标

- 完成至少三类分析任务，并提供完整、可复现的代码。
- 从数据中提出一个明确、可验证的研究假设。
- 设计并完成至少一项额外验证实验，报告结果与适用范围。
- 提供完整报告，记录分析、假设形成、实验设计、结果和 AI 使用情况。
- 提供 PPT，展示研究思路、发现与结论，重点呈现两张核心图。

## 数据来源与记录

- Divvy 行程与站点数据使用官方系统数据页，月度历史行程保留原始下载文件及时间范围。<https://divvybikes.com/system-data/>
- Divvy 实时站点信息使用官方 GBFS feed，并记录快照获取时间。实时快照不能直接替代历史站点映射。<https://gbfs.divvybikes.com/gbfs/2.3/gbfs.json>
- Divvy 数据使用遵守其数据许可，仓库只跟踪代码、文档和来源元数据。<https://divvybikes.com/data-license-agreement/>
- NOAA 使用 Daily Summaries，首选 O'Hare 站 USW00094846，备选 Midway 站 USW00014819。<https://www.ncei.noaa.gov/access/past-weather/>
- NOAA Access Data Service 提供按站点、日期、字段和单位请求数据的接口。<https://www.ncei.noaa.gov/access/search/documentation/data-service/>

每次下载均在 data/manifest.csv 记录 URL、下载时间、日期覆盖、站点、文件大小和 SHA-256。分析需检查 PRCP、SNWD、SNOW、AWND、TMAX、TMIN 的可用性、单位、质量标志与缺测。按 started_at 对齐天气日数据时记录时区和日界线。

探索中检查 2020 年疫情时期的结构变化，核查站点改名、迁移与 station_id 变化。日期范围和研究假设尚待数据探索确定。

## 项目结构

```text
.
├── AGENTS.md
├── HANDBOOK.md
├── data/
│   ├── README.md
│   ├── manifest.csv
│   ├── raw/
│   └── processed/
├── reports/
├── scripts/
│   └── project_env.sh
├── requirements.txt
└── .gitignore
```

原始数据与派生数据留在 data/ 下并被 Git 忽略。代码、文档和来源元数据纳入版本管理，报告、PPT 和核心图存放在 reports/。

## 运行环境

当前仅完成项目初始化，依赖尚未安装，数据尚未下载，分析尚未运行。服务器当前非交互 shell 的 PATH 中未找到 python 或 python3。建立隔离环境前，先定位可用 Python 解释器或在本项目目录内准备运行时。

后续在 Bash 中执行以下准备步骤，再使用已确认可用的 Python 解释器建立本项目 .venv。

```bash
cd /root/autodl-tmp/ai-sci
source scripts/project_env.sh
```

requirements.txt 列出初步分析依赖，实际采用的版本将在环境建立后记录。环境、依赖缓存、临时文件与输出均保留在数据盘项目目录。

执行前阅读 HANDBOOK.md。AI 辅助过程按实际操作记录，研究者的独立判断由研究者确认后写入报告。
