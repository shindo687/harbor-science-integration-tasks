# Harbor Science Integration Tasks

这是已通过验收的科学软件功能集成 Harbor Tasks 总仓库。每道题仍保留独立
GitHub 仓库；本仓库在 `tasks/` 下保存各独立仓库指定 commit 的完整、逐字节
一致快照，便于统一浏览、检索、克隆和运行。

## 当前收录

- 20 个已验收 Task
- AlgoBridge：18 个
- StructHarbor：2 个
- 独立仓库不会被本仓库替代或删除

完整目录见 [TASKS.md](TASKS.md)。每个快照的来源 URL、commit、Git tree、
文件数和字节数记录在 `tasks.lock.json`；`scripts/verify_snapshots.py` 会校验
聚合后的子目录 Git tree 与独立仓库锁定 commit 完全一致。

## 克隆

仓库包含上游/下游锁定源码和离线运行资产，完整克隆体积较大。只使用单题时
建议 sparse clone：

```bash
git clone --filter=blob:none --sparse \
  https://github.com/shindo687/harbor-science-integration-tasks.git
cd harbor-science-integration-tasks
git sparse-checkout set \
  tasks/structharbor-0001__alphafold-2__absorbs__dockq \
  scripts README.md TASKS.md task-sources.json tasks.lock.json
```

需要全部题目时正常克隆即可：

```bash
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

验证器要求 20 个目录全部存在，并检查：来源记录、锁定 commit、子目录 Git
tree、文件数量、总字节数，以及 GitHub 100 MB 单文件限制。

## 更新快照

本仓库不修改题目内容。题目先在独立仓库完成并验收，再从指定 commit 同步：

```bash
python3 scripts/sync_tasks.py \
  --source-root /path/to/local/repos \
  --task <task-name>
git add tasks/<task-name> tasks.lock.json
python3 scripts/generate_index.py
```

同步脚本只读取 `task-sources.json` 中固定的来源与 commit；若本地没有独立仓库，
可增加 `--fetch-missing`，脚本会克隆到被 Git 忽略的 `.sync-cache/`。

## 许可证

本仓库是多个项目和 Task 的集合，不声明覆盖全部内容的统一许可证。每道题的
Task 代码以及内嵌上游/下游源码分别遵循其目录中的 LICENSE、COPYING、NOTICE
和来源锁定记录。详见 [LICENSES.md](LICENSES.md)。
