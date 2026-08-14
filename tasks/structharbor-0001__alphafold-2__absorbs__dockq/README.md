# AlphaFold 2 absorbs DockQ

这是一个 Harbor 0.20 单步算法迁移题：Agent 阅读锁定的 AlphaFold 2 与 DockQ
源码，在 AlphaFold 内独立重实现二链 DockQ，并接入 `predict_structure`。

## 隔离模型

```text
Agent image                             Separate H200 verifier image
───────────                             ───────────────────────────
/testbed  AlphaFold 2 ──修改──┐         pristine AF2 + 锁定权重
/opt/dockq  donor 源码        │ artifact        │ 真实推理
/examples  5 个公开样例       └───────────────> 原 DockQ 算参考值
                                                   │ 删除所有 reference
                                                   │ UID 10001 真实运行 /testbed
                                                   └─ 比较 15 个隐藏用例
```

- Agent 和 verifier 运行时均为 `no-network`。
- 只有 `/testbed` 会从 Agent 容器传给独立 verifier；donor 不会随提交传递。
- Agent 保持 0 GPU/8 GB，且没有权重；独立 verifier 使用一张 H200、32 GB 主存和
  `model_1_multimer_v3` 权重。
- verifier 先用 pristine AF2 真实推理并动态运行锁定 DockQ，再删除 pristine AF2 与
  donor，随后以 UID 10001 在干净环境中真实运行候选；候选不能读取 `/tests` 或
  `/logs/verifier`。
- 编译/依赖/宿主回归是 0 分硬门禁；其余得分是 15 个隐藏用例通过率。

## 计分结构

| 用例 | 内容 | 是否真实 AF2 推理 |
|---|---|---|
| 1～9 | DockQ 科学数值、刚体变换、链映射 | 否 |
| 10 | 独立 JSON CLI | 否 |
| 11 | AF2 flags、函数签名和 main 传参 | 否 |
| 12 | H200 + 官方 Multimer DataPipeline + RunModel | 是 |
| 13 | pristine 与修改版预测等效 | 是 |
| 14 | 集成 DockQ 与原始 DockQ 差分 | 是 |
| 15 | 原始 AF2 产物及新增 PKL/JSON 集成 | 是 |

用例 12～15 共享同一次候选推理，且不使用 `FakeRunner` 或 `FakeDataPipeline`。真实
输入使用 query-only 预计算 MSA 和防泄漏的微型模板库，目的是在数分钟内验证完整
预测链路，而不是衡量生产级结构预测质量。

## 版本锁

- AlphaFold 2: `c77e5d2a8961d1a353632c462914ff0a32a950f6`
- DockQ: `75db7ab4f6b824c70d120c5f620582e164ed5479`（MIT）
- AlphaFold multimer 参数：`model_1_multimer_v3`，SHA256
  `611da8fc7478928f68de12e8b226260ef1f4ce62bcc29b008572e52f4f212959`（CC BY 4.0）

## 题目文件

```text
structharbor-0001__alphafold-2__absorbs__dockq/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   ├── host-source/
│   ├── donor-source/
│   └── public-examples/
├── solution/                 # Oracle，仅供题目验收
│   └── solve.sh
└── tests/
    ├── Dockerfile            # 独立评分镜像
    ├── docker-compose.yaml   # 标准 NVIDIA GPU 资源申请（不绑定本机路径）
    ├── test.sh
    ├── grader.py
    ├── real_e2e_runner.py    # 无 Fake 的真实 AF2 runner
    ├── e2e-data/             # verifier 私有权重/小型固定数据
    └── reference/            # verifier 私有 pristine AF2 与锁定 donor
```

建议门禁：`nop = 0`、`oracle = 1`、错误常数/仅独立模块/仅流程 JSON 等
near-miss 均不能满分。

## 从 Git 仓库运行

本题将 verifier 私有模型参数和离线 Python wheelhouse 纳入 Git LFS。克隆时需要先
安装 Git LFS，并确保大文件已下载完整：

```bash
git lfs install
git clone <repository-url>
cd structharbor-0001__alphafold-2__absorbs__dockq
git lfs pull
git lfs ls-files
```

如果只得到 LFS pointer 而没有实际的权重和 wheel，verifier 镜像将无法构建。

### 新机器运行依赖

运行完整 Harbor Task（包括用例 12～15 的真实 AF2 推理）需要：

- Linux x86_64；
- Harbor 0.20；
- Git 和 Git LFS；
- Docker Engine 与 Docker Compose v2；
- 一张 NVIDIA CUDA GPU（H200 已验证，其他型号尚未验证）；
- 支持 CUDA 12.2 的 NVIDIA 驱动；
- NVIDIA Container Toolkit，建议 1.18 或更新版本，以正式安装方式启用 CDI。

Verifier 的资源配置为 8 CPU、32 GB 主存和 64 GB 存储。首次克隆、拉取 LFS 文件、
拉取 CUDA 基础镜像及安装 Ubuntu 系统包需要网络；Agent 和 verifier 的任务运行阶段
仍然是 `no-network`。

宿主机不需要另行安装 CUDA Toolkit、cuDNN、JAX、TensorFlow、OpenMM 或 AlphaFold
模型参数：CUDA 用户态和 Python 依赖由 `tests/Dockerfile` 封装，锁定的
`model_1_multimer_v3` 权重与离线 wheelhouse 由 Git LFS 提供。

`tests/docker-compose.yaml` 通过 CDI 申请 GPU，不挂载 `/dev/nvidia*` 或任何宿主机
驱动库路径；Toolkit 负责注入所选设备及与宿主驱动匹配的库。NVIDIA Container
Toolkit 请按[官方安装指南](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
持久安装。安装后先验证：

```bash
nvidia-smi
docker version
docker compose version
nvidia-ctk cdi list
docker run --rm --device nvidia.com/gpu=0 \
  nvidia/cuda:12.2.2-base-ubuntu22.04 nvidia-smi
```

默认使用 CDI 设备 `nvidia.com/gpu=0`；共享机器可在运行 Harbor 前设置
`AF2_VERIFIER_GPU_CDI=nvidia.com/gpu=<index-or-uuid>` 选择其他卡，而不修改仓库。
由于 Harbor 0.20 的本地 Docker provider 会在读取 Compose 前拒绝通用 GPU 字段，
`task.toml` 中 verifier 的 `gpus` 兼容值保持为 `0`；实际 GPU 要求以上述 CDI 配置为准。

本题最初在当前 H200 上为了避免重启已有 Docker 工作负载，曾从 `/tmp` 临时引导 CDI；
该做法只是一次本机验证，不是 Git 仓库依赖，也不适用于新机器。新机器应使用上面的
正式 Toolkit 安装，使 CDI 配置在重启和临时目录清理后仍然有效。

没有 NVIDIA GPU 的机器可以阅读题目、构建 Agent 环境和查看已有轨迹，但不能运行
用例 12～15 的真实 AF2 推理；这部分应交给 GPU runner 执行。

2026-08-13 最终 Harbor/H200 封版结果：Oracle 1 trial、0 exception、15/15、
Reward 1.0；NOP 1 trial、0 exception、0/15、Reward 0.0。Oracle 内两次真实推理及
完整评分约 158 秒，Harbor 全 trial（含环境/产物）约 3 分 29 秒。Verifier Python
依赖由 `tests/wheels` 离线安装，冷构建不再依赖 PyPI 或 Google Storage。

## Agent 轨迹

仓库包含 2026-08-13 使用 Kimi K2.7 Code 与 mini-swe-agent 2.4.6 运行的 3 条
独立 Harbor 轨迹，隐藏验收分别为 0/15、11/15 和 14/15。每条均包含原始轨迹、
ATIF v1.7 转换、运行配置、token 统计和完整 grader 证据：

- [Kimi + mini-swe-agent 三条轨迹](trajectories/kimi-k2.7-code-mini-swe-agent-2.4.6-20260813/README.md)
