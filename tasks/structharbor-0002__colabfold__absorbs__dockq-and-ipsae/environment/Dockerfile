FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps /opt/wheels/*.whl

COPY host-source/ /testbed/
COPY donor-source/dockq/ /opt/dockq/
COPY donor-source/ipsae/ /opt/ipsae/
COPY donor-shims/ /opt/dockq/shims/
COPY examples/ /examples/

# The original donors are runnable only for Agent research. They are outside
# /testbed and therefore never cross the separate-verifier artifact boundary.
ENV PYTHONPATH=/opt/dockq/shims:/opt/dockq/src
ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
