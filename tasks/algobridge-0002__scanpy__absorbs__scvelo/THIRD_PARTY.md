# Third-party source provenance

本仓库包含用于构建 Agent 学习环境和独立差分 verifier 的 commit-locked 源码快照。

| 角色 | 项目 | Commit | Tree | License |
| --- | --- | --- | --- | --- |
| Host | Scanpy | `fabadb9412c0d1cd9df9d9c2e95ac266d564ee18` | `c68e70c22539158ed52fd8169761d818ac8510a2` | BSD-3-Clause |
| Donor/reference | scVelo | `f63c0e70596ced2f1bee8cf07e8ab66037cf86b2` | `50237cef428c6bf42611522d8721983847af4584` | BSD-3-Clause |

上游许可证原文保留在 `environment/host-source/LICENSE` 和
`environment/donor-source/LICENSE`。Oracle 是独立编写的 clean-room 实现；候选评分
阶段不存在 donor 源码或可导入的 scVelo runtime。
