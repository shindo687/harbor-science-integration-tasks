## 任务

在 `/testbed` 中的 **Scanpy** 仓库实现：**Scanpy 原生 LISI 批次混合与标签保持评分**。
锁定的 scIB 源码位于 `/opt/scib-source`，仅供理解原工作流；`/examples`
中有 5 个公开样例。

将 **scIB** 的 `scIB local inverse Simpson index (iLISI/cLISI)` 能力以独立、受限实现迁移到 Scanpy。实现不得在运行时调用、import、链接、下载或 vendor scIB；不得复制许可证不兼容的 donor 代码。

### 算法范围

在给定 kNN distance graph 上，先取加权最短路邻域，再以固定 perplexity
二分求局部概率并计算 batch/cell-type LISI；不含 embedding 或邻居重建。

### 输入与输出

- 输入：对称 CSR 正边距离、batch label、cell-type label、`n_neighbors`、perplexity。
- 输出：逐 cell iLISI/cLISI、有效邻居数与全局 median。
- 宿主接口：Scanpy 新增 lisi_graph_score，不得调用 scIB。

### 差分 oracle

- Reference A+B：Scanpy embedding/graph 交给锁定 scIB LISI 实现。
- Candidate：只运行修改后的 Scanpy。
- 比较：逐 cell 分数 1e-6，median 1e-7；label 编码和 CSR 顺序规范化。

除数值差分外，Verifier 必须检查以下科学/数学不变量：

- LISI 在 1 与可见类别数之间
- 单一类别的 LISI 恒为 1
- 类别名称置换不改变分数

图中某个 cell 可达的其他 cell 少于 `n_neighbors` 时，其 LISI 按锁定 scIB
行为记为 1；`effective_neighbors` 返回实际可达数与 `n_neighbors` 的较小者。
孤立 cell 因此得到 LISI 1 和有效邻居数 0。

### Fixtures

完全混合/完全分离、孤立 cell、不平衡类别、重复距离、不同 perplexity。

### 非胶水判定

需要求解局部 entropy/perplexity 并计算概率多样性，是数值评分算法。

论文共现证据：`Scanpy -> scIB`，出现在 3 篇论文中。题目实现必须保持宿主现有公共 API/回归测试，不做无关重构。

### 公开验证

```bash
/opt/task-tools/run-public-examples
python -m pytest -q tests/test_metrics.py -k confusion_matrix
```

隐藏 fixtures 与公开类别相同但数值和规模不同；不要针对公开数据硬编码。
