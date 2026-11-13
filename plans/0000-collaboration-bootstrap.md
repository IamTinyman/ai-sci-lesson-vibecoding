# 0000 协作入口与远程连通性检查

## 目标

建立三方协作入口，确认下游 agent 能在本机 Harness 会话中通过 SSH 访问服务器项目，并回报真实执行结果。

## 输入

- 本机调度目录 /Users/tinyman/BUPT/PHD/2026_2027_1/ai-sci。
- SSH 别名 codex-gpu。
- 服务器仓库 /root/autodl-tmp/ai-sci。
- 项目准则 HANDBOOK.md 和 docs/COLLABORATION.md。

## 执行

下游先通过 SSH 阅读服务器的项目准则，再检查 hostname、当前用户、项目绝对路径、Git 分支与最新提交、数据盘容量、GPU 状态和 data/ 实际文件。

所有检查均使用只读命令。将检查结果和关键命令写入服务器 reports/agent_runs/0000-connectivity.md，并在会话中给出摘要和遇到的问题。该报告是本轮执行产物。

## 验收

- Harness 会话绑定指定的本机入口目录，并使用人类指定的模型。
- 会话实际调用工具执行 SSH，记录服务器路径和命令结果。
- 主机身份、用户、项目路径、分支与提交等静态项与 Codex 的独立核对一致。GPU、磁盘余量、Git 状态和 data/ 文件等动态项均记录查询时间，并在相近时间核对。
- 报告文件位于服务器项目的数据盘目录。
- Git 变更仅包含本轮协作文档和检查报告等已授权内容。
