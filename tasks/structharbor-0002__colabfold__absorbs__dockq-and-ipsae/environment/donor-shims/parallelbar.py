"""Minimal deterministic compatibility shim for locked DockQ."""


def progress_map(function, iterable, **_kwargs):
    return [function(item) for item in iterable]

