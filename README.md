# Harbor Science Integration Tasks

这是已通过验收的科学软件功能集成 Harbor Tasks 总仓库。每道题仍保留独立
GitHub 仓库；本仓库在 `tasks/` 下保存各独立仓库指定 commit 的完整、逐字节
一致快照，便于统一浏览、检索、克隆和运行。

## 当前收录

- 29 个已验收 Task
- AlgoBridge：25 个
- StructHarbor：4 个
- 独立仓库不会被本仓库替代或删除

完整目录见 [TASKS.md](TASKS.md)。每个快照的来源 URL、commit、Git tree、
文件数、Git blob/LFS/展开字节数记录在 `tasks.lock.json`；
`scripts/verify_snapshots.py` 会校验聚合后的子目录 Git tree 与独立仓库锁定
commit 完全一致。

## 克隆

仓库包含上游/下游锁定源码和离线运行资产，完整克隆体积较大。只使用单题时
建议 sparse clone：

```bash
git clone --filter=blob:none --sparse \
  https://github.com/shindo687/harbor-science-integration-tasks.git
cd harbor-science-integration-tasks
git sparse-checkout set \
  tasks/algobridge-0004__seurat__absorbs__clusterprofiler \
  scripts README.md TASKS.md task-sources.json tasks.lock.json
```

`structharbor-0001__alphafold-2__absorbs__dockq` 的模型参数和离线 wheels
使用 74 个 Git LFS 对象（约 946 MB）。这些对象已经上传到本总仓库，不依赖
H200 本地目录；克隆全部题目或该题前需安装 Git LFS：

```bash
git lfs install
git clone https://github.com/shindo687/harbor-science-integration-tasks.git
```

## 使用 Harbor

每个 `tasks/<task-name>/` 都是独立 Harbor Task 根目录：

```bash
cd tasks/structharbor-0001__alphafold-2__absorbs__dockq
harbor run --path . --agent oracle --job-name smoke
```

具体硬件、Docker/NVIDIA 和运行参数以各题自己的 README 为准。

## 完整性验证

```bash
python3 scripts/verify_snapshots.py
```

验证器要求 29 个目录全部存在，并检查：来源记录、锁定 commit、子目录 Git
tree、文件数量、Git/LFS/展开字节数，以及 GitHub 100 MB 普通 Git 单文件限制。

## 更新快照

本仓库不修改题目内容。题目先在独立仓库完成并验收，再从指定 commit 同步：

```bash
python3 scripts/sync_tasks.py \
  --source-root /path/to/local/repos \
  --task <task-name>
python3 scripts/generate_index.py
git add tasks/<task-name> tasks.lock.json TASKS.md
```

同步脚本只读取 `task-sources.json` 中固定的来源与 commit；若本地没有独立仓库，
可增加 `--fetch-missing`，脚本会克隆到被 Git 忽略的 `.sync-cache/`。
若只需重新计算来源树和 LFS 统计、不替换任务目录，可增加 `--metadata-only`。

## 许可证

本仓库是多个项目和 Task 的集合，不声明覆盖全部内容的统一许可证。每道题的
Task 代码以及内嵌上游/下游源码分别遵循其目录中的 LICENSE、COPYING、NOTICE
和来源锁定记录。详见 [LICENSES.md](LICENSES.md)。
