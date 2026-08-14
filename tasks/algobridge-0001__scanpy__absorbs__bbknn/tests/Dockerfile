FROM python:3.12.11-slim-bookworm

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      scanpy==1.14.0.dev21+gfabadb941 pytest==8.4.1 pooch==1.8.2

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY reference/host-source/ /opt/pristine-host/
COPY reference/donor-source/ /opt/reference-donor/
COPY reference_runner.py protocol.py source-hashes.sha256 source-links.txt /opt/reference-runner/
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py protocol.py /opt/candidate-runner/
COPY cases.py grader.py test.sh /tests/
COPY public-examples/ /examples/
COPY regression-tests/ /opt/regression-tests/
COPY installed-scanpy/ /opt/installed-scanpy/

RUN chmod 0755 /tests/test.sh /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-tools /opt/candidate-runner \
      /opt/regression-tests /opt/installed-scanpy /examples \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-tools /opt/candidate-runner \
      /opt/regression-tests /opt/installed-scanpy /examples \
    && chmod 0700 /tests /opt/reference-runner /opt/candidate-tools \
    && chmod 0755 /opt/candidate-runner /opt/regression-tests \
      /opt/installed-scanpy /examples \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/protocol.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

