"""Minimal dependency shim; the one-mapping verifier path never calls this."""


def progress_map(function, iterable, **_kwargs):
    return [function(item) for item in iterable]
