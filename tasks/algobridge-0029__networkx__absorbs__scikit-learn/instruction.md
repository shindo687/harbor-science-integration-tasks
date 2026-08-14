# 任务：在 NetworkX 中原生实现 normalized spectral clustering

在 `/testbed` 中修改锁定的 **NetworkX** 源码，实现原生 normalized spectral
clustering。scikit-learn 的锁定源码位于 `/opt/scikit-learn`，仅供理解原有工作流；
`/examples` 中有 5 个公开样例。

将 scikit-learn 的 normalized spectral clustering 能力以独立、受限实现迁移到
NetworkX。最终实现不得在运行时调用、import、链接、下载或 vendor scikit-learn，
也不得读取 `/opt/scikit-learn`、`/tests` 或 verifier 结果。不要复制 donor 实现；请依据
算法定义独立实现。

### 算法范围

仅需支持无向 `Graph`：非负有限边权、symmetric normalized Laplacian、最小特征值对应
的特征向量、节点度归一化和 deterministic k-means。必须支持 disconnected graph 和
isolates；不要求 directed/multigraph、Nyström、LOBPCG 或 AMG。

## 必须提供的宿主 API

新增以下函数，并从 `networkx.algorithms.community` 和顶层 `networkx` 导出：

```python
spectral_clustering(
    G,
    n_clusters,
    *,
    weight="weight",
    assign_labels="kmeans",
    seed=0,
    eigen_tol=1e-10,
)
```

返回一个包含下列字段的字典：

- `nodes`：用于矩阵行的确定性节点顺序；
- `partition`：`node -> int label`；
- `eigenvalues`：normalized Laplacian 最小的 `n_clusters` 个特征值；
- `embedding`：与 `nodes` 对齐、shape 为 `(n, n_clusters)` 的 degree-normalized、
  row-normalized spectral embedding；
- `normalized_cut`：各 cluster `cut(S, V-S) / volume(S)` 之和；零 volume 项记为 0。

节点排序必须不依赖插入顺序。题目 fixtures 使用整数或字符串节点；可使用类型信息和
`repr(node)` 构造稳定顺序。`assign_labels` 本题只接受 `"kmeans"`。k-means 应作用于
row-normalized embedding。无效参数、负权、
有向图和 multigraph 应给出清晰异常。

## 数学约定

令加权邻接矩阵为 `A`、degree 为 `d`，symmetric normalized Laplacian 为
`L_sym = I - D^(-1/2) A D^(-1/2)`；isolate 对应的行列按 SciPy normalized
Laplacian 约定为 0。选择最小的 `n_clusters` 个 eigenpairs，确定性消除单个特征向量
的符号歧义，再进行 seeded k-means（10 次初始化，选择最小 inertia）。

特征向量在重根时允许正交旋转，因此 verifier 比较 embedding 的列空间 projector，
不会逐元素比较 eigenvector。cluster label 也允许整体重命名。

## 差分 Oracle

- Reference A+B：NetworkX adjacency 交给锁定的 sklearn `SpectralClustering`。
- Candidate：只运行修改后的 NetworkX。
- 比较：partition 用 label-permutation invariant ARI=1；eigenspace projector 1e-6；Ncut 1e-8。

除数值差分外，Verifier 必须检查以下科学/数学不变量：

- cluster label 重命名不影响 partition
- node insertion order 不影响规范结果
- 完全断开的 components 在 k 足够时不被拆混

## 公开验证

```bash
python /examples/verify_examples.py /testbed
python -m pytest -q networkx/algorithms/community/tests
```

隐藏 fixtures 与公开类别相同但数值和规模不同。不要针对公开数据硬编码。

## Fixtures 类别

two moons graph、SBM、disconnected components、isolates、weighted ties、degenerate eigenvalues。

## 非胶水判定

核心是 Laplacian 谱分解和聚类优化，而非图格式适配。

论文共现证据：`NetworkX -> scikit-learn`，出现在 5 篇论文中。题目实现必须保持宿主现有公共 API/回归测试，不做无关重构。
