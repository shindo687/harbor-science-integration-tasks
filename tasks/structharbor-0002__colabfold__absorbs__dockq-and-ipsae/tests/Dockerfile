FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps /opt/wheels/*.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY test.sh grader.py candidate_runner.py host-files.sha256 host-snapshot.sha256 \
  reference-files.sha256 reference-provenance.json batch-structure-lock.json /tests/
COPY reference/ /tests/reference/
RUN chmod 0755 /tests/test.sh \
    && chown -R root:root /tests \
    && chmod -R go-w /tests

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
