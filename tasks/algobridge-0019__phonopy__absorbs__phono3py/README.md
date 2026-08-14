# ALGOBRIDGE-0019：phonopy 原生 FC3 拟合

状态：`accepted`。这是一道 CPU-only、离线、single-step Harbor 算法迁移题：
要求 Agent 修改锁定的 phonopy 源码，使其原生完成 phono3py 的有限位移
FC2/FC3 联合重建，不得在候选执行时调用或依赖 phono3py、symfc 或其他 FC3
实现。

## 差分任务

```text
锁定 phonopy 数据 → 锁定 phono3py produce_fc3(symfc) → 参考结果
                                                   │
Agent 修改后的 phonopy → fit_fc3                  ├─ 差分比较
                                                   │
                    物理不变量与隔离门禁 ──────────┘
```

Agent 只需新增 `phonopy/harmonic/third_order.py`。API、force convention、
最小二乘截断、对称性和返回字段的完整约定见 `instruction.md`。

源码被精确固定为：

- phonopy `4bac506220d426784020ea24812c93e2a016be18`；
- phono3py `2dc8200a65dc3a4dd3824d248af50545f03f8ea2`；
- reference backend：symfc `1.7.3`；
- Python 基础镜像：`python:3.12.11-slim-bookworm`，使用 digest 固定。

归档、wheel、tree 与依赖 manifest 的 SHA256 位于 `source-lock.json`。两者均为
BSD-3-Clause；第三方边界见 `THIRD_PARTY.md`。

## 隔离与评分

`task.toml` 设置 `environment_mode = "separate"` 和 `network_mode =
"no-network"`。Harbor 先运行 Agent 并收集 `/testbed`，关闭 Agent 容器后，
再启动由 `tests/Dockerfile` 构建的独立 verifier。

Verifier 的执行顺序是：

1. 使用真实锁定 phono3py 逐例计算参考结果；
2. 只允许候选新增指定模块，并检查禁止依赖、执行原语及 donor token 片段；
3. 把 `/testbed` 设为只读，并物理删除 reference runtime、donor source、
   reference runner、wheel 与 pristine host；
4. 以无 home 写权限的 UID 10001、无网络环境执行候选；
5. 检查非法输入、旋转/原子重排硬门禁，再对 15 个隐藏用例逐例计分。

任一硬门禁失败得 0。其余 Reward 为通过隐藏用例数除以 15。比较 FC2、FC3、
预测 force、残差、rank、奇异值、条件数和空间群操作数，并独立检查导数索引
置换、三轴 acoustic sum rule、预测/残差一致性、零净力及空间群等变性。

## 验收结果

| 实现 | 结果 | Reward |
|---|---:|---:|
| clean-room Oracle | 15/15 | 1.0 |
| pristine phonopy（NOP） | source gate | 0.0 |
| 忽略空间群的 near miss | 10/15 | 0.6666666667 |
| 直接 import phono3py | dependency gate | 0.0 |
| 公开样例 | 5/5 | — |

正式 Harbor 0.20 Oracle 与 NOP 各完成 1 个 trial，均为 0 exception、0 retry，
Rewards 分别为 `1.0` 和 `0.0`，两次 `/testbed` artifact collection 均为
`ok`。机器可读 job、trial、lock、artifact 和 verifier 报告保存在
`validation/evidence/`。

5 个公开 fixture 只由锁定 reference 生成。在 Agent 环境实现 API 后可运行：

```bash
/opt/task-tools/run-public-examples
```

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0019-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0019-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储；不需要
GPU 或 H200。基础镜像首次获取可能联网，但镜像构建中的依赖安装、Agent 和
verifier 执行均使用仓库内锁定材料且不访问网络。
