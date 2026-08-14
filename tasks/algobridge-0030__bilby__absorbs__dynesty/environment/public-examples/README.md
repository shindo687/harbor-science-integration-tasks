# Public examples

Run after implementing `bilby.core.sampler.internal_nested`:

```bash
python3 /examples/verify_examples.py
```

The examples expose broad analytic tolerances for evidence and posterior means.
Hidden tests use different parameters and also compare to the locked dynesty
pipeline, exercise the real Bilby sampler registry, and enforce isolation.

