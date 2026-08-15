#!/usr/bin/env python3
"""Deterministic molecular fixtures for ALGOBRIDGE-0014."""

from __future__ import annotations


def case(name, smiles, seed, num_confs=3, prune_rms=0.15):
    return {
        "name": name,
        "smiles": smiles,
        "seed": seed,
        "num_confs": num_confs,
        "prune_rms": prune_rms,
    }


def public_cases():
    return [
        case("public_butane", "CCCC", 1101, 3, 0.12),
        case("public_cyclohexane", "C1CCCCC1", 1102, 2, 0.10),
        case("public_lactic_acid", "C[C@H](O)C(=O)O", 1103, 3, 0.12),
        case("public_dichloroethane", "ClCCCl", 1104, 3, 0.12),
        case("public_tartaric_acid", "O=C(O)[C@@H](O)[C@H](O)C(=O)O", 1105, 3, 0.12),
    ]


def hidden_cases():
    return [
        case("hidden_ethanol", "CCO", 1201, 3, 0.10),
        case("hidden_pentane", "CCCCC", 1202, 4, 0.14),
        case("hidden_hexane", "CCCCCC", 1203, 4, 0.14),
        case("hidden_isobutane", "CC(C)C", 1204, 2, 0.10),
        case("hidden_diethyl_ether", "CCOCC", 1205, 3, 0.12),
        case("hidden_propylbenzene", "CCCc1ccccc1", 1206, 3, 0.12),
        case("hidden_ethyl_acetate", "CCOC(=O)C", 1207, 3, 0.12),
        case("hidden_alanine", "N[C@@H](C)C(=O)O", 1208, 3, 0.12),
        case("hidden_two_butanol", "CC[C@H](O)C", 1209, 3, 0.12),
        case("hidden_phenylethanol", "C[C@@H](O)c1ccccc1", 1210, 3, 0.12),
        case("hidden_threonine", "N[C@@H]([C@H](O)C)C(=O)O", 1211, 3, 0.12),
        case("hidden_ibuprofen", "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O", 1212, 4, 0.14),
        case("hidden_cyclopentane", "C1CCCC1", 1213, 2, 0.10),
        case("hidden_methylcyclohexane", "CC1CCCCC1", 1214, 3, 0.10),
        case("hidden_benzene", "c1ccccc1", 1215, 1, 0.10),
    ]
