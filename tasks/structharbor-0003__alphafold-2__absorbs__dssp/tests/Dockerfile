FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels numpy==2.3.3

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz dssp-runtime.tar.gz \
     dssp-4.4.11-h629725b_0.conda /opt/source-archives/
RUN echo "7b6900aa9cafb0bc14e0e6bf25b74faa67fa3133f3e3474f511279f6cf3fab59  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "cc632a1a67545061a44a5cc0caca995b625b34190623844ba72548eddb67c461  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "174a3c2259313b2d9472b8b33df02d94c9611f0e61ed28b5d9b5ef03e1a95e28  /opt/source-archives/dssp-runtime.tar.gz" | sha256sum --check --strict \
    && echo "5580f0cce0c4a1cee944f25272ba5f729eff4dc88721ebf2196c646891e2190c  /opt/source-archives/dssp-4.4.11-h629725b_0.conda" | sha256sum --check --strict \
    && mv /opt/source-archives/dssp-4.4.11-h629725b_0.conda /opt/source-archives/dssp.conda \
    && mkdir -p /opt/pristine-host /opt/reference-dssp-source /opt/dssp \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-dssp-source \
    && tar -xzf /opt/source-archives/dssp-runtime.tar.gz -C /opt/dssp \
    && /opt/dssp/bin/mkdssp --version | grep -F "4.4.11"

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/
COPY fixtures/ /tests/fixtures/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/dssp /opt/reference-dssp-source \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/source-archives \
    && chmod -R go-w /tests /opt/dssp /opt/reference-dssp-source \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/source-archives \
    && chmod 0700 /tests /opt/dssp /opt/reference-dssp-source \
      /opt/pristine-host /opt/reference-runner /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

