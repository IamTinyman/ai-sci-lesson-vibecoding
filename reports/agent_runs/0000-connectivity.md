# 0000 协作入口与远程连通性检查报告

- 关联方案：`plans/0000-collaboration-bootstrap.md`
- 执行者：本机 DeepSeek Harness 下游会话（模型标识 deepseek-v4.1-flash），本机调度入口 `/Users/tinyman/BUPT/PHD/2026_2027_1/ai-sci`
- 服务器 SSH 别名 codex-gpu，登录用户 root（本机 SSH 配置免交互认证）
- 服务器项目目录：`/root/autodl-tmp/ai-sci`
- 执行日期：2026-11-13；查询时段 2026-11-13 20:40:24 至 20:41:39（Asia/Shanghai，UTC+08:00，服务器默认时区同为 Asia/Shanghai）
- 操作性质：只读检查。未下载数据、未安装依赖、未运行分析、未调用 GPU 计算、未修改既有文件、未提交或推送。

## 1. 连接与身份

命令：

```
ssh -o BatchMode=yes -o ConnectTimeout=20 codex-gpu 'hostname; whoami; id; pwd; realpath .; uname -a'
```

输出（2026-11-13 20:40:24 CST）：

```
autodl-container-61v0gdep2p-6a3a4e72
root
uid=0(root) gid=0(root) groups=0(root)
/root/autodl-tmp/ai-sci
/root/autodl-tmp/ai-sci
Linux autodl-container-61v0gdep2p-6a3a4e72 5.15.0-78-generic #85-Ubuntu SMP Fri Jul 7 15:25:09 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux
```

SSH 连接本身成功，首个只读命令退出码 0。

## 2. 项目路径

| 检查项 | 命令 | 结果 | 查询时间（Asia/Shanghai） |
| --- | --- | --- | --- |
| 当前目录 | `pwd` | `/root/autodl-tmp/ai-sci` | 2026-11-13 20:40:24 |
| 规范化路径 | `realpath .` | `/root/autodl-tmp/ai-sci` | 2026-11-13 20:40:24 |
| 项目根列表 | `ls -la` | 含 `.git/`、`AGENTS.md`、`HANDBOOK.md`、`README.md`、`data/`、`docs/`、`plans/`、`reports/`、`scripts/`、`requirements.txt`、`.cache/`、`.tmp/`、`.gitignore` | 2026-11-13 20:40:24 |

工作目录与手册规定的固定目录一致；全部检查均在该目录内执行。

## 3. Git 分支、状态与最新提交

命令：

```
git --version
git branch --show-current
git log -1 --format="%H%n%h%n%an <%ae>%n%ad%n%s" --date=iso-strict
git status --porcelain=v1 --branch
git remote -v
git rev-list --left-right --count HEAD...origin/main
```

输出（2026-11-13 20:40:24 起，20:41:39 复核一致）：

```
git version 2.34.1

main

b66ce097a2b3157e41d1eb8f993c34c4145b2b54
b66ce09
IamTinyman <174840802+IamTinyman@users.noreply.github.com>
2026-11-13T19:57:21+08:00
Initialize AI-SCI Divvy and NOAA project

## main...origin/main
 M AGENTS.md
 M HANDBOOK.md
?? docs/
?? plans/

origin  https://github.com/IamTinyman/ai-sci-lesson-vibecoding.git (fetch)
origin  https://github.com/IamTinyman/ai-sci-lesson-vibecoding.git (push)

0	0
```

| 检查项 | 结果 | 查询时间（Asia/Shanghai） |
| --- | --- | --- |
| 分支 | `main` | 2026-11-13 20:41:39 |
| HEAD | `b66ce097a2b3157e41d1eb8f993c34c4145b2b54`（短 `b66ce09`） | 2026-11-13 20:41:39 |
| 最新提交 | 2026-11-13T19:57:21+08:00，IamTinyman，"Initialize AI-SCI Divvy and NOAA project" | 2026-11-13 20:41:39 |
| 远端 | `origin` = 手册指定的 GitHub 仓库 | 2026-11-13 20:40:24 |
| 与 origin/main 差异 | ahead 0 / behind 0（基于本地 `origin/main` 引用，未联网 fetch） | 2026-11-13 20:41:39 |
| 工作区变更 | 修改：`AGENTS.md`、`HANDBOOK.md`；未跟踪：`docs/`、`plans/`（共 4 行） | 2026-11-13 20:41:39 |

变更说明：4 行变更均为本阶段由 Codex 建立的协作文档（AGENTS.md 与 HANDBOOK.md 的三方协作补充、docs/COLLABORATION.md、plans/0000-collaboration-bootstrap.md），属方案已授权内容。本报告为新增文件，写入后项目内未再改动其他文件。

## 4. 数据盘容量

命令：

```
df -hT /root/autodl-tmp
df -i /root/autodl-tmp
df -h /root /root/autodl-tmp
du -sh /root/autodl-tmp/ai-sci
du -sh /root/autodl-tmp/ai-sci/data
du -sh .git .cache data reports plans docs scripts .tmp
```

输出（2026-11-13 20:41:39 复核）：

```
/dev/md0       xfs   374G  252G  123G  68% /root/autodl-tmp
/dev/md0   1500266688 24281812 1475984876    2% /root/autodl-tmp
overlay        30G   21G  9.9G  68% /
```

| 检查项 | 结果 | 查询时间（Asia/Shanghai） |
| --- | --- | --- |
| 数据盘挂载点 | `/root/autodl-tmp`，设备 `/dev/md0`（xfs） | 2026-11-13 20:41:39 |
| 总容量 / 已用 / 可用 | 374G / 252G / 123G（使用率 68%） | 2026-11-13 20:41:39 |
| inode 使用 | 使用率 2%（剩余约 14.76 亿） | 2026-11-13 20:41:39 |
| 项目总占用 | 55M（其中 `.cache` 55M、`.git` 172K、`data` 16K） | 2026-11-13 20:41:39 |
| 系统盘（仅记录） | overlay 30G，可用 9.9G，使用率 68% | 2026-11-13 20:41:39 |

数据盘可用 123G，尚未用于本项目数据。系统盘余量偏低，后续下载与运行须保持输出落在 `/root/autodl-tmp/ai-sci`。

## 5. GPU 与进程状态

命令：

```
nvidia-smi
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

输出（`nvidia-smi` 头部时间 2026-11-13 20:40:45，20:41:39 查询复核一致）：

```
NVIDIA-SMI 595.71.05    Driver Version: 595.71.05    CUDA Version: 13.2

0  NVIDIA RTX 6000D   On   00000000:B8:00.0   Off
N/A   31C   P8   29W / 600W   0MiB / 85651MiB   0%   Default

Processes: No running processes found
```

| 检查项 | 结果 | 查询时间（Asia/Shanghai） |
| --- | --- | --- |
| GPU 数量 | 1（index 0） | 2026-11-13 20:41:39 |
| 型号 | NVIDIA RTX 6000D | 2026-11-13 20:41:39 |
| 显存 | 总计 85651 MiB，已用 0 MiB | 2026-11-13 20:41:39 |
| 利用率 / 温度 / 功耗 | 0% / 31C / 29W（上限 600W），P8 | 2026-11-13 20:41:39 |
| 驱动 / CUDA | 595.71.05 / 13.2 | 2026-11-13 20:40:45 |
| 显存计算进程 | 0 个（No running processes found） | 2026-11-13 20:41:39 |
| MIG / Persistence | Disabled / On | 2026-11-13 20:40:45 |

结论：GPU 当前完全空闲，无其他任务占用显存。本轮未启动任何 GPU 任务，也未干预任何进程。

## 6. data/ 实际文件与大小

命令：

```
find data -printf "%y %10s %TY-%Tm-%Td %TH:%TM %p\n" | sort -k5
du -ah data | sort -k2
cat data/manifest.csv
```

输出（2026-11-13 20:40:5x，20:41:39 复核为 4 个文件、合计 1327 字节）：

```
d         91 2026-11-13 19:56 data
f       1221 2026-11-13 19:56 data/README.md
f        104 2026-11-13 19:56 data/manifest.csv
d         30 2026-11-13 19:52 data/processed
f          1 2026-11-13 19:52 data/processed/.gitkeep
d         30 2026-11-13 19:52 data/raw
f          1 2026-11-13 19:52 data/raw/.gitkeep
```

| 路径 | 类型 | 大小 | 修改时间（服务器本地，CST） |
| --- | --- | --- | --- |
| `data/` | 目录 | 91 B（目录项） | 2026-11-13 19:56 |
| `data/README.md` | 文件 | 1221 B | 2026-11-13 19:56 |
| `data/manifest.csv` | 文件 | 104 B | 2026-11-13 19:56 |
| `data/processed/` | 目录 | 30 B（目录项） | 2026-11-13 19:52 |
| `data/processed/.gitkeep` | 文件 | 1 B | 2026-11-13 19:52 |
| `data/raw/` | 目录 | 30 B（目录项） | 2026-11-13 19:52 |
| `data/raw/.gitkeep` | 文件 | 1 B | 2026-11-13 19:52 |

`data/manifest.csv` 当前仅含表头：

```
source,dataset,station,period_start,period_end,retrieved_at_utc,url,local_path,sha256,bytes,units,notes
```

结论：`data/` 尚无任何实际数据文件，`data/raw/` 与 `data/processed/` 均只有占位 `.gitkeep`，与 `data/README.md` 中"当前 manifest 只有表头，尚未下载任何数据"的说明一致。

## 7. 结论

1. 本机 Harness 会话可通过 SSH 别名 `codex-gpu` 免交互登录服务器，命令均返回退出码 0。
2. 主机身份 `autodl-container-61v0gdep2p-6a3a4e72`，登录用户 `root`（uid 0），操作系统 Ubuntu 内核 5.15.0-78-generic。
3. 项目目录存在且位于数据盘 `/root/autodl-tmp/ai-sci`，工作目录正确。
4. Git 仓库位于 `main` 分支，HEAD 为 `b66ce09`，与本地记录的 `origin/main` 一致（0/0），远端为手册指定仓库。
5. 数据盘 `/dev/md0` 共 374G，可用 123G（68% 已用），inode 充足。
6. GPU 单卡 NVIDIA RTX 6000D（85651 MiB），已用 0 MiB、利用率 0%、无计算进程。
7. `data/` 只有说明文件、表头 manifest 与占位文件，无数据内容。

## 8. 偏差、限制与未核实事项

1. SSH 连接通过平台端口映射，本轮未核实本机公网出口地址。
2. ahead/behind 为 `0/0`，基于本地 `origin/main` 引用；按只读与不改动仓库的要求未执行 `git fetch`，未与 GitHub 远端实时比对。
3. 主机名 `autodl-container-61v0gdep2p-6a3a4e72` 为容器名，若 Codex 独立核对使用实例 ID 或公网地址，需按平台信息额外比对。
4. `.cache/`（55M，含 `tools/` 等）为既有缓存且被 Git 忽略，本轮未读取细节用途，也未改动。
5. 数据盘根目录下存在其他目录，仅通过目录列表观察，未进入、未读写、未改动。
6. GPU 型号与显存是否与项目预期一致，属资源分配判断，未在本轮作出，留待人类与 Codex 确认。
7. `data/` 无数据属当前阶段的预期状态；实际数据获取需后续方案授权。

## 9. AI 使用记录

- 本报告由 DeepSeek Harness 下游会话生成，所列命令与输出均为实际执行结果，数值未人工改写。
- Codex 独立核对关键状态，并删去不必要的认证路径和其他项目目录名称，未更改测量结果。
- 本轮未涉及研究判断；未使用 GPU 计算，未产生数据或分析产物。
- 全部服务器操作限定在 `/root/autodl-tmp/ai-sci` 内，且仅使用只读命令与本报告的写入。

## 附录：实际执行命令清单（按时间顺序）

```
ssh -o BatchMode=yes -o ConnectTimeout=20 codex-gpu 'hostname; whoami; echo "---"; ls -la /root/autodl-tmp/ai-sci'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && cat HANDBOOK.md AGENTS.md docs/COLLABORATION.md'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && ls -la plans/ && cat plans/0000-collaboration-bootstrap.md'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && TZ=Asia/Shanghai date; date -u; hostname; whoami; id; pwd; realpath .; uname -a'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && find reports -maxdepth 3 -printf ... && ls -la data/'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && git --version; git branch --show-current; git log -1 ...; git status --porcelain=v1 --branch; git remote -v'
ssh -o BatchMode=yes codex-gpu 'df -hT /root/autodl-tmp; df -i /root/autodl-tmp; df -h /root; du -sh /root/autodl-tmp/ai-sci /root/autodl-tmp/ai-sci/data'
ssh -o BatchMode=yes codex-gpu 'nvidia-smi'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && find data -printf ...; du -ah data'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && echo "$SSH_CONNECTION"; date; cat /etc/timezone; cat .gitignore; cat data/README.md; cat data/manifest.csv'
ssh -o BatchMode=yes codex-gpu 'cd /root/autodl-tmp/ai-sci && git rev-list --left-right --count HEAD...origin/main; du -sh .cache/*; ls -la /root/autodl-tmp'
ssh -o BatchMode=yes codex-gpu '<带时间戳的只读复核：identity/git/disk/du/gpu/data-files>'
```
