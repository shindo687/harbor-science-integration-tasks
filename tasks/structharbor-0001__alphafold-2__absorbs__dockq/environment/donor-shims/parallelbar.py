"""Serial compatibility shim for DockQ's optional parallelbar dependency."""


def progress_map(function, items, **_kwargs):
    return [function(item) for item in items]
