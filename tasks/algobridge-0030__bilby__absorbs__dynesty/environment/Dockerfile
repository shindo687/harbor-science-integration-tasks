FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps /opt/wheels/*.whl

COPY host-source/ /testbed/
COPY donor-source/ /opt/dynesty-source/
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
COPY source-lock.json host-snapshot.sha256 donor-snapshot.sha256 /opt/task-locks/

RUN python /opt/task-tools/prepare_host.py \
    && python -m pip install --no-index --no-deps --no-build-isolation -e /testbed \
    && SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DYNESTY=3.0.0+locked.d8affbc \
      python -m pip install --no-index --no-deps --no-build-isolation \
      -e /opt/dynesty-source \
    && chmod 0755 /examples/verify_examples.py \
    && chmod -R go-w /opt/dynesty-source /opt/task-tools /opt/task-locks /examples

# The donor is runnable study material for the Agent only. It is outside
# /testbed and cannot cross the separate-verifier artifact boundary.
ENV PYTHONPATH=/opt/dynesty-source/py
ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV MPLBACKEND=Agg
WORKDIR /testbed
