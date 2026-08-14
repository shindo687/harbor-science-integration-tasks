FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python3 -m pip install --no-index --no-deps --find-links=/opt/wheels \
       cmake==3.31.6 ninja==1.11.1.3 \
    && rm -rf /opt/wheels

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/pymbar-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/pymbar-source \
    && rm -rf /opt/source-archives

COPY public-examples/ /examples/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /examples/verify_examples.py /opt/task-tools/run-public-examples \
    && chown -R root:root /opt/pristine-host /opt/pymbar-source /examples /opt/task-tools \
    && chmod -R go-w /opt/pristine-host /opt/pymbar-source /examples /opt/task-tools

ENV PYTHONNOUSERSITE=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
