FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 PyYAML==6.0.3 spglib==2.7.0 \
      h5py==3.16.0 typing-extensions==4.16.0 phonors==0.3.0

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "932dfdebe9dedee2f6687f86dce8029c4cf6bfd257e2e564ae07417720a6b216  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "7180cf6db46a17051d3da0a33acacf182c7a7412c7e8365fca574c99292cead3  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/reference-phono3py-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
      -C /opt/reference-phono3py-source \
    && rm -rf /opt/source-archives \
    && chown -R root:root /opt/pristine-host /opt/reference-phono3py-source \
    && chmod -R go-w /opt/pristine-host /opt/reference-phono3py-source

COPY public-examples/ /examples/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /examples/verify_examples.py /opt/task-tools/run-public-examples \
    && chown -R root:root /examples /opt/task-tools \
    && chmod -R go-w /examples /opt/task-tools

ENV PYTHONNOUSERSITE=1
ENV PYTHONPATH=/testbed
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
