"""Minimal import compatibility for AlphaFold's static residue constants.

The bounded task uses no JAX numerical operation.  Locked AlphaFold imports
``jax.tree.map`` once to map atom-name strings in a nested Python list, so this
module supplies exactly that standard tree traversal without shipping jaxlib.
"""


def _map(function, value, *others):
    if isinstance(value, dict):
        return type(value)(
            (key, _map(function, item, *(other[key] for other in others)))
            for key, item in value.items()
        )
    if isinstance(value, list):
        return [
            _map(function, item, *(other[index] for other in others))
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return type(value)(
            _map(function, item, *(other[index] for other in others))
            for index, item in enumerate(value)
        )
    return function(value, *others)


class _Tree:
    map = staticmethod(_map)


tree = _Tree()

