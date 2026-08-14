# Third-party source material

## Bilby

- Repository: https://github.com/bilby-dev/bilby
- Commit: `a139afa5e0bb1879f18aed28344adec8ca6cab9b`
- Tree: `758065ac767be42b55d281eb37719e08dffb0b6b`
- License: MIT (`environment/host-source/LICENSE.md`)
- Role: host source available to the Agent and restored into the verifier.

The curated host snapshot includes the complete `bilby` Python package,
packaging metadata, licenses, and Python regression tests. Large unrelated
binary test data and documentation images are intentionally excluded.

## dynesty

- Repository: https://github.com/joshspeagle/dynesty
- Commit: `d8affbcd18d1cb894e0c7102ba31c65794461b55`
- Tree: `dbcfbfd8b9bd24bcc11dd3375b01832478030641`
- License: MIT (`environment/donor-source/LICENSE`)
- Role: study material in the Agent image and executable scientific reference
  in the private verifier; it is never a task artifact.

The curated donor snapshot contains the complete `py/dynesty` package,
upstream tests, packaging metadata, citation, and license. Notebooks, generated
figures, and the paper PDF are excluded because they are not required to run
the locked reference algorithm.

