FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 numexpr==2.14.1 openmm==8.5.2

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/reference-host /opt/pristine-host /opt/reference-donor \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/reference-host \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-donor
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/

RUN python - <<'PY'
from pathlib import Path
import openmm
import shutil
source = Path(openmm.__file__).resolve().parent
shutil.copytree(source, Path('/opt/installed-openmm/openmm'))
shutil.copytree(Path('/usr/local/lib/python3.12/site-packages/OpenMM.libs'),
                Path('/opt/installed-openmm/OpenMM.libs'))
PY

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/candidate-tools /opt/installed-openmm /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/candidate-tools /opt/installed-openmm /opt/source-archives \
    && chmod 0700 /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/candidate-tools \
      /opt/installed-openmm \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV PYMBAR_DISABLE_JAX=1
WORKDIR /testbed
