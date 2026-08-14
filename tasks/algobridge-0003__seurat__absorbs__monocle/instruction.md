# Add native principal-graph pseudotime to Seurat

The checkout at `/testbed` is the complete source tree of a locked official
Seurat commit. The read-only Monocle3 source at `/opt/donor-sources/monocle3`
is supplied as algorithm documentation. Add a bounded implementation of cell
projection and root-oriented geodesic pseudotime natively to Seurat. The final
implementation must not import, execute, link, or copy Monocle3.

Create `/testbed/R/principal_graph_pseudotime.R` and export exactly this public
function:

```r
PrincipalGraphPseudotime <- function(
  embedding,
  principal_vertices,
  principal_edges,
  root_vertices = character(),
  root_cells = character()
)
```

Also add `export(PrincipalGraphPseudotime)` to `NAMESPACE` and add
`'principal_graph_pseudotime.R'` to the `Collate` field in `DESCRIPTION`.

The supported input is deliberately fixed:

- `embedding` is a numeric matrix of 3 through 96 cells by 2 or 3 dimensions;
  its unique, nonempty row names are the cell names.
- `principal_vertices` is a numeric matrix of 2 through 32 vertices in the
  same dimensions. Its row names are exactly `Y_1`, ..., `Y_n` in order.
- `principal_edges` is a 1 through 64 row, two-column character matrix defining
  a simple undirected graph. Endpoints must exist, edges must be unique, and
  principal edges must have nonzero Euclidean length.
- Coordinates must be finite with absolute value at most `1e4`, and no
  principal vertex may be isolated.
- Specify exactly one nonempty root mode: `root_vertices` or `root_cells`.
  Names must exist, roots must be unique, and every graph component must have
  a root. Root cells resolve to their nearest principal vertices.

Return a list with these fields on success:

```r
list(
  status = "ok",
  pseudotime = named_numeric_by_cell,
  closest_vertex = named_character_by_cell,
  cell_state = named_character_by_cell,
  vertex_role = named_character_by_vertex,
  root_vertices = resolved_root_vertex_names
)
```

Match the locked Monocle3 1.4.26 behavior represented by its real
`project2MST` followed by `order_cells`: first assign each cell to its nearest
principal vertex, project it to the best incident line segment, form the
cell-augmented weighted graph, and measure shortest-path distance from the
resolved roots. Ties and output ordering must be deterministic. Pseudotime is
checked to absolute tolerance `1e-8`; vertex projection, state, role, and roots
are checked exactly.

Vertex roles are `root`, `branch`, `leaf`, or `internal`; roots take precedence
over the other roles. A root or non-root degree-greater-than-two vertex has
state `node:<vertex>`. Remove those cut vertices from the principal graph and
label each remaining connected segment `segment:<first-vertex>`, where the
first vertex is the lowest original `Y_n` order; cells inherit the state of
their closest vertex.

Return `list(status = "invalid_input", error = ...)` for unsupported input.
Graph learning, expression matrices, and Seurat object mutation are outside
this bounded task.

The implementation may use `igraph`, already imported by Seurat, plus base R.
It cannot depend on Monocle3, subprocesses, network access, hidden verifier
files, precomputed case answers, dynamic code loading, or native/foreign escape
paths. Preserve every existing Seurat file except the two package integration
files named above; unrelated additions are ignored by the interface.

Five public inputs and locked real-reference outputs are in `/public-cases`.
After implementing the function, run:

```sh
/opt/task-tools/run-public-examples
```

The hidden verifier uses new line, branch, cycle, disconnected, 3D, irregular,
near-tie, and root-cell cases, malformed inputs, edge-order changes, and cell
permutations.
