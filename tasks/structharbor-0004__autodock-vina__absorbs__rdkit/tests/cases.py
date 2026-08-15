#!/usr/bin/env python3
"""Deterministic molecule descriptions for STRUCTHARBOR-0004."""

from __future__ import annotations


def case(name, smiles, seed, perturb=0.12, dielectric_model=1,
         dielectric_constant=1.0):
    return {
        "name": name,
        "smiles": smiles,
        "seed": seed,
        "perturb": perturb,
        "dielectric_model": dielectric_model,
        "dielectric_constant": dielectric_constant,
    }


def public_cases():
    return [
        case("public_ethanol", "CCO", 101, 0.10),
        case("public_acetamide", "CC(=O)N", 202, 0.16),
        case("public_benzene", "c1ccccc1", 303, 0.08),
        case("public_butane", "CCCC", 404, 0.22, 2, 2.0),
        case("public_glycine_zwitterion", "[NH3+]CC(=O)[O-]", 505, 0.14),
    ]


def hidden_cases():
    return [
        case("hidden_aspirin", "CC(=O)Oc1ccccc1C(=O)O", 611, 0.18),
        case("hidden_caffeine", "Cn1c(=O)c2c(ncn2C)n(C)c1=O", 622, 0.12),
        case("hidden_phenol", "Oc1ccccc1", 633, 0.15, 2, 3.0),
        case("hidden_cyclohexane", "C1CCCCC1", 644, 0.20),
        case("hidden_acetone", "CC(=O)C", 655, 0.17),
        case("hidden_ethyl_acetate", "CCOC(=O)C", 666, 0.13),
        case("hidden_pyridine", "n1ccccc1", 677, 0.11),
        case("hidden_morpholine", "C1COCCN1", 688, 0.19, 2, 4.0),
        case("hidden_dimethyl_sulfoxide", "CS(=O)C", 699, 0.14),
        case("hidden_alanine_zwitterion", "[NH3+][C@@H](C)C(=O)[O-]", 710, 0.16),
        case("hidden_isobutane", "CC(C)C", 721, 0.21),
        case("hidden_formamide", "NC=O", 732, 0.12),
        case("hidden_acetonitrile", "CC#N", 743, 0.10),
        case("hidden_styrene", "C=Cc1ccccc1", 754, 0.17, 2, 2.5),
        case("hidden_naphthalene", "c1ccc2ccccc2c1", 765, 0.09),
    ]
