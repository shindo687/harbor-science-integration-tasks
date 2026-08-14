"""Private deterministic fixtures for ALGOBRIDGE-0007.

The records deliberately avoid biologically ambiguous repeat placements: a
clean-room bounded progressive implementation can reproduce the locked MAFFT
column homology without hard-coding MAFFT internals.
"""

DEFAULT_GAP_OPEN = 4.0
DEFAULT_GAP_EXTEND = 0.75


def _sixteen_dna():
    return [
        (
            f"d16{i:02d}",
            "ATGCCGTAGCTAA" + ("GGG" if i >= 8 else "")
            + "CGTTGACCTGATCGTACGA",
        )
        for i in range(16)
    ]


CASES = [
    {
        "id": "dna_pair_internal",
        "alphabet": "dna",
        "records": [
            ("dpa", "GCTACGTTAGCACCTG"),
            ("dpb", "GCTACGTTGGGAGCACCTG"),
        ],
    },
    {
        "id": "dna_three_internal",
        "alphabet": "dna",
        "records": [
            ("dta", "ATGCCGTAGCTAACGTTGAC"),
            ("dtb", "ATGCCGTAGGGTCTAACGTTGAC"),
            ("dtc", "ATGCCGTAGCTAACGTCGAC"),
        ],
    },
    {
        "id": "dna_terminal",
        "alphabet": "dna",
        "records": [
            ("dea", "GGGACCTTAGCATC"),
            ("deb", "ACCTTAGCATC"),
            ("dec", "GGGACCTCAGCATC"),
            ("ded", "GGGACCTTAGCATCTT"),
        ],
    },
    {
        "id": "dna_long_insert",
        "alphabet": "dna",
        "records": [
            ("dla", "AACCTGATCGTACGGA"),
            ("dlb", "AACCTGATTTTTTCGTACGGA"),
            ("dlc", "AACCTGATTTTTCGTACGGA"),
            ("dld", "AACCTGATCGTACAGA"),
        ],
    },
    {
        "id": "dna_duplicates",
        "alphabet": "dna",
        "records": [
            ("dda", "TTGACCGTACCTGA"),
            ("ddb", "TTGACCGTACCTGA"),
            ("ddc", "TTGACCGTTTACCTGA"),
            ("ddd", "TTGACCGTACCA"),
        ],
    },
    {
        "id": "dna_tied_guide",
        "alphabet": "dna",
        "records": [
            ("dga", "ATGCCGTAGCTA"),
            ("dgb", "ATGCCGTAGCTT"),
            ("dgc", "ATGCCGTAGCTC"),
            ("dgd", "ATGCCGTAGCTG"),
        ],
    },
    {
        "id": "dna_six_clusters",
        "alphabet": "dna",
        "permutation_group": "dna-six",
        "records": [
            ("d6a", "ATGCGTACGTTAC"),
            ("d6b", "ATGCGTACGCTAC"),
            ("d6c", "ATGCGTGGGACGTTAC"),
            ("d6d", "ATGCGTGGGACGCTAC"),
            ("d6e", "ATGCGTACGTTAT"),
            ("d6f", "ATGCGTACGCTAT"),
        ],
    },
    {
        "id": "dna_sixteen_indel",
        "alphabet": "dna",
        "records": _sixteen_dna(),
    },
    {
        "id": "dna_six_permuted",
        "alphabet": "dna",
        "permutation_group": "dna-six",
        "records": [
            ("d6f", "ATGCGTACGCTAT"),
            ("d6c", "ATGCGTGGGACGTTAC"),
            ("d6a", "ATGCGTACGTTAC"),
            ("d6e", "ATGCGTACGTTAT"),
            ("d6b", "ATGCGTACGCTAC"),
            ("d6d", "ATGCGTGGGACGCTAC"),
        ],
    },
    {
        "id": "protein_pair",
        "alphabet": "protein",
        "records": [
            ("ppa", "MNNIRRVLIVDDASK"),
            ("ppb", "MNNIRRAGGVLIVDDASK"),
        ],
    },
    {
        "id": "protein_motif",
        "alphabet": "protein",
        "records": [
            ("pma", "MNNIRRVLIVDDASK"),
            ("pmb", "MNNIRRVLIVDEASK"),
            ("pmc", "MNNIRRAGGVLIVDDASK"),
            ("pmd", "MNNIRRAGGVLIVDEASK"),
        ],
    },
    {
        "id": "protein_long_insert",
        "alphabet": "protein",
        "records": [
            ("pla", "MKTWQHDPDLVIKR"),
            ("plb", "MKTWQHDGGGGPDLVIKR"),
            ("plc", "MKTWQHDGGGPDLVIKR"),
            ("pld", "MKTWQHDPDLVIRR"),
        ],
    },
    {
        "id": "protein_duplicates",
        "alphabet": "protein",
        "records": [
            ("pda", "ACDEFGHIKLMNPQ"),
            ("pdb", "ACDEFGHIKLMNPQ"),
            ("pdc", "ACDEFGGGHIKLMNPQ"),
            ("pdd", "ACDEFGHIKLMNAQ"),
        ],
    },
    {
        "id": "protein_six_clusters",
        "alphabet": "protein",
        "permutation_group": "protein-six",
        "records": [
            ("p6a", "MKWVTFISLLFLFSSAYSR"),
            ("p6b", "MKWVTFISLLFLFSTAYSR"),
            ("p6c", "MKWVTFISGGGLLFLFSSAYSR"),
            ("p6d", "MKWVTFISGGGLLFLFSTAYSR"),
            ("p6e", "MKWVTFISLLFLFSSAFSR"),
            ("p6f", "MKWVTFISLLFLFSTAFSR"),
        ],
    },
    {
        "id": "protein_six_permuted",
        "alphabet": "protein",
        "permutation_group": "protein-six",
        "records": [
            ("p6f", "MKWVTFISLLFLFSTAFSR"),
            ("p6c", "MKWVTFISGGGLLFLFSSAYSR"),
            ("p6a", "MKWVTFISLLFLFSSAYSR"),
            ("p6e", "MKWVTFISLLFLFSSAFSR"),
            ("p6b", "MKWVTFISLLFLFSTAYSR"),
            ("p6d", "MKWVTFISGGGLLFLFSTAYSR"),
        ],
    },
]


assert len(CASES) == 15


LEGACY_ALIGNMENT = [
    ("legacy_a", "ATGCCGTA---GCTAACGTTGAC"),
    ("legacy_b", "ATGCCGTAGGGGCTAACGTTGAC"),
    ("legacy_c", "ATGCCGTA---GCTAACGTCGAC"),
    ("legacy_d", "ATGCCGTAGGGGCTAACGTCGAC"),
    ("legacy_e", "ATGCCGTA---GCTAACGTTGAT"),
]

