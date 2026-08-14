FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      scanpy==1.14.0.dev21+gfabadb941 pytest==8.4.1 pooch==1.8.2 \
    && python -m venv --system-site-packages /opt/reference-venv \
    && /opt/reference-venv/bin/pip install --no-index --no-deps \
      /opt/wheels/scvelo-0.3.3+locked.f63c0e7-py3-none-any.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY reference/host-source/ /opt/reference-host/
COPY reference/donor-source/ /opt/reference-donor/
COPY reference/host-source/ /opt/pristine-host/
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py protocol.py /opt/candidate-runner/
COPY reference_runner.py protocol.py /opt/reference-runner/
COPY cases.py grader.py test.sh source-lock.json \
  reference-host-files.sha256 reference-donor-files.sha256 /tests/

RUN python - <<'PY'
from importlib.util import find_spec
from pathlib import Path
import shutil, scanpy
target = Path('/opt/installed-scanpy')
target.mkdir()
shutil.copytree(Path(scanpy.__file__).resolve().parent, target / 'scanpy')
spec = find_spec('testing')
shutil.copytree(Path(next(iter(spec.submodule_search_locations))).resolve(), target / 'testing')
PY

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/candidate-tools /opt/installed-scanpy /opt/reference-venv \
    && chmod -R go-w /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/candidate-tools /opt/installed-scanpy /opt/reference-venv \
    && chmod 0700 /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-tools \
      /opt/installed-scanpy /opt/reference-venv \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/protocol.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV MPLBACKEND=Agg
WORKDIR /testbed
