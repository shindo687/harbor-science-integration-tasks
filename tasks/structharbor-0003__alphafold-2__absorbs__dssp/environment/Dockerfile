FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels numpy==2.3.3

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "7b6900aa9cafb0bc14e0e6bf25b74faa67fa3133f3e3474f511279f6cf3fab59  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "cc632a1a67545061a44a5cc0caca995b625b34190623844ba72548eddb67c461  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && chown -R root:root /opt/donor-source /opt/source-archives \
    && chmod -R go-w /opt/donor-source /opt/source-archives

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
COPY source-lock.json /opt/task-source-lock.json
RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/task-tools /examples /opt/task-source-lock.json \
    && chmod -R go-w /opt/task-tools /examples /opt/task-source-lock.json

ENV PYTHONNOUSERSITE=1
ENV PYTHONPATH=/testbed
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

