FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

COPY host-source.tar.gz /tmp/host-source.tar.gz
RUN mkdir -p /opt/reference-lammps && \
    tar -xzf /tmp/host-source.tar.gz -C /opt/reference-lammps --strip-components=1 && \
    make -C /opt/reference-lammps/src serial -j8 && \
    rm /tmp/host-source.tar.gz

COPY wheels /opt/wheels
RUN cd /opt/wheels && sha256sum -c SHA256SUMS && \
    python -m pip install --no-index --no-deps ./*.whl

COPY donor-source.tar.gz /tmp/donor-source.tar.gz
RUN mkdir -p /opt/reference-phonopy-source && \
    tar -xzf /tmp/donor-source.tar.gz -C /opt/reference-phonopy-source --strip-components=1 && \
    rm /tmp/donor-source.tar.gz

COPY . /tests
RUN chmod 755 /tests/test.sh /tests/grader.py /tests/reference_runner.py && \
    mkdir -p /logs/verifier /testbed

WORKDIR /testbed
