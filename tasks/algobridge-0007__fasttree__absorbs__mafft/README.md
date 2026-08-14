# ALGOBRIDGE-0007: FastTree absorbs MAFFT

状态：**accepted**。

这是一道 Harbor single-step 算法迁移题：Agent 在 FastTree 2.2.0 中新增
`--align-small`，原生实现受限的 progressive multiple alignment，然后继续
进入 FastTree 原有建树链路。最终候选不能调用、链接、vendor 或依赖 MAFFT。

## 任务范围

- 输入 2–32 条未比对 DNA/蛋白 FASTA；单条最多 512 residues，总计最多
  8,192 residues。
- 全局 affine-gap pairwise DP。
- 确定性 UPGMA guide tree。
- profile/profile sum-of-pairs progressive alignment。
- DNA identity matrix、蛋白 BLOSUM62；默认 gap open/extend 为 `4.0/0.75`。
- 输出 alignment、rooted guide Newick，以及 FastTree 最终 Newick。
- 不包含 FFT 加速和迭代精修。

接口：

```bash
./FastTree [-nt] -quiet -noboot \
  --align-small \
  --alignment-out aligned.fa \
  --guide-tree-out guide.nwk \
  --align-matrix identity|blosum62 \
  --align-gap-open 4.0 \
  --align-gap-extend 0.75 \
  input.fa > tree.nwk
```

完整 Agent 要求见 `instruction.md`。

## 差分评分

Verifier 对 15 个隐藏输入运行：

```text
锁定 MAFFT core ──alignment──> 锁定 FastTree ──> reference tree
          │
          └── verifier 独立数学实现 ───────────> bounded UPGMA guide

修改后的 FastTree ──> candidate alignment + guide + final tree
```

逐题同时检查：

- alignment residue-pair column homology 和 affine sum-of-pairs score；
- bounded UPGMA guide 的 splits、branch distances、ultrametric invariant；
- 最终 FastTree tree 的 splits、RF=0、leaf-pair branch distances `1e-5`；
- 去 gap 后序列不变、各行等长、无全-gap列、leaf identifiers 完整；
- DNA/蛋白输入置换不改变规范化 homology 和最终 tree splits。

编译、源码策略、候选隔离和原 FastTree 接口回归是 hard gates。隐藏 fixtures
覆盖 2/3/6/16 条序列、internal/terminal/long indel、duplicates、tied guide
distance、DNA、protein 和输入置换。

## 隔离关系

`environment/Dockerfile` 创建 Agent 环境：

- `/testbed` 只有可编辑的精简 FastTree 源码，没有预编译上游二进制；
- `/opt/mafft-source` 提供只读 BSD core 源码和文档供 Agent 学习；
- `/examples` 提供 5 个公开样例；
- 全程 no-network。

Harbor 只收集 Agent 修改后的 `/testbed`。在
`environment_mode = "separate"` 下，Agent 容器停止后才由
`tests/Dockerfile` 创建独立 verifier。Verifier 先生成私有
`MAFFT -> FastTree` references，再删除 `/opt/reference-tools`、MAFFT source、
pristine host 和源码 archives；随后才以 UID 10001 编译、运行候选。候选阶段
没有 MAFFT executable/package/source，也不能读取 `/tests` 私有 fixtures。

源码策略还会拒绝 bundled executables/archives、进程执行或动态加载，以及
MAFFT 的 72-token exact / 128-token normalized source fragments。

## 验收结果

| Candidate | Hard gates | Hidden | Reward |
| --- | --- | ---: | ---: |
| clean-room C Oracle | 全部通过 | 15/15 | 1.0 |
| pristine FastTree / NOP | source-policy 拒绝 | 0/15 | 0.0 |
| sequential-guide near miss | 全部通过 | 5/15 | 0.333333333333 |

- 公开样例：`5/5`。
- Oracle C 实现对 15 个隐藏用例通过 AddressSanitizer/UBSan。
- Formal Harbor Oracle：1 trial、0 exception、0 retry、Reward `1.0`，60 秒。
- Formal Harbor NOP：1 trial、0 exception、0 retry、Reward `0.0`，41 秒。
- 两个 formal jobs 的输入 Task digest 相同；精确值保存在两份
  `harbor-*-trial-lock.json` 中。
- 两次 `/testbed` artifact 状态均为 `ok`。

机器可读结果位于 `validation/evidence/`。

## 本地公开样例

Agent 环境中执行：

```bash
/opt/task-tools/run-public-examples
```

仓库开发环境中也可直接运行：

```bash
python3 public-examples/verify_examples.py /path/to/modified/FastTree
```

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0007-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0007-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

依赖 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储；不需要
GPU/H200。基础镜像缓存就绪后，Agent 和 verifier 的安装、运行均不访问网络。

## 锁定来源

- FastTree 2.2.0：`a5a2723ea1e64faf3da7ea514521cfa348891add`。
- MAFFT core：`0a2319b41ec99282487c2d758029cb7ef1fbc5c2`。
- 基础镜像：`python:3.12.11-bookworm`，digest 固定在
  `source-lock.json`。

仓库只包含 FastTree 必要源码和 MAFFT 的 BSD-licensed `core/`；预编译
FastTree、MAFFT binaries、MPI、extensions 和大型测试 archives 均未打包。
许可证和 archive SHA-256 见 `THIRD_PARTY.md` 与 `source-lock.json`。
