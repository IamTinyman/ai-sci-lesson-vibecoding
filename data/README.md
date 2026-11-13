# 数据目录

原始下载放在 data/raw/，清洗、聚合与连接后的数据放在 data/processed/。所有数据文件和压缩包均被 Git 忽略。data/manifest.csv 只记录来源与版本元数据，纳入版本管理。

下载前确定所需日期范围并检查数据盘空间。每个文件记录来源 URL、获取时间、覆盖日期、天气站、文件大小和 SHA-256。请求参数保留在 URL 中，单位另行记录。当前 manifest 只有表头，尚未下载任何数据。

Divvy 按月保留历史行程文件。实时站点信息按快照记录获取时间，并在分析中核查历史 station_id、站点名称及坐标变化。数据使用遵守官方许可。

NOAA 首选 Chicago O'Hare 的 USW00094846，备选 Chicago Midway 的 USW00014819。需要检查 PRCP、SNWD、SNOW、AWND、TMAX、TMIN 的实际覆盖、单位、质量标志和缺失值。

日期连接使用明确记录的时区、日界线与聚合规则。探索需考虑 2020 年疫情影响，避免将不同阶段直接视为同一分布。

安装依赖与运行下载程序前，在项目根目录的 Bash 会话中 source scripts/project_env.sh，使临时文件和缓存也落在本项目数据盘目录。
