# Third-party source notices

The task images contain immutable source snapshots for reproducible offline
builds.  They are not candidate solutions.

| Component | Locked revision | License | Purpose |
| --- | --- | --- | --- |
| FastTree 2.2.0 | `a5a2723ea1e64faf3da7ea514521cfa348891add` | GPL-2.0-or-later | Editable host and pristine tree builder |
| MAFFT core | `0a2319b41ec99282487c2d758029cb7ef1fbc5c2` | BSD-3-Clause | Read-only study source and private reference workflow |

Only MAFFT's BSD-licensed `core/` subtree, top-level README, and core license
are archived.  The separately licensed `extensions/` subtree is excluded.
The authoritative upstream URLs and Git tree identities are in
`source-lock.json`; full license texts remain inside their source archives.

FastTree's source header grants GPL version 2 or any later version.  The
repository's bundled `LICENSE` file contains the GPL version 3 text, which is
one permitted later-version license under that source grant.
