FROM python@sha256:ee0c7d26e2dba416773cb51c042496e9cffacc872459f57726935dd6833f2d96

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.2.6 scipy==1.15.3 openmm==8.5.2 \
    && python -m pip install --no-index --find-links=/opt/wheels \
      --target=/opt/reference-runtime pyemma==2.5.12+6.g3327f28b \
    && PYTHONPATH=/opt/reference-runtime python -c \
      'import pyemma; assert pyemma.__version__ == "2.5.12+6.g3327f28b"'

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "acc2045d9be27621069cdb549aa4a6f6531a063eb9027c583c13786cd276677a  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-pyemma-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
       -C /opt/reference-pyemma-source --strip-components=1

COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/

RUN python - <<'PY'
from pathlib import Path
import openmm
import shutil
source = Path(openmm.__file__).resolve().parent
target = Path('/opt/installed-openmm')
shutil.copytree(source, target / 'openmm')
libs = next(source.parent.glob('OpenMM.libs'))
shutil.copytree(libs, target / 'OpenMM.libs')
PY

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/reference-runtime \
      /opt/reference-pyemma-source /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/candidate-tools /opt/installed-openmm \
      /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-runtime \
      /opt/reference-pyemma-source /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/candidate-tools /opt/installed-openmm \
      /opt/source-archives \
    && chmod 0700 /tests /opt/reference-runtime \
      /opt/reference-pyemma-source /opt/pristine-host /opt/reference-runner \
      /opt/candidate-tools /opt/installed-openmm /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
