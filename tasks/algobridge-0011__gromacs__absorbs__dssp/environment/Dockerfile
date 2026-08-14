FROM python@sha256:69719dbce933473eb3632ee1c3b25788e71752d615ddee02536475be4d9e310b

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python3 -m pip install --no-index --no-deps --find-links=/opt/wheels \
       cmake==3.31.6 ninja==1.11.1.3

COPY host-source.tar.gz donor-source.tar.gz source-lock.json /opt/source-archives/
RUN echo "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "cc632a1a67545061a44a5cc0caca995b625b34190623844ba72548eddb67c461  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && test "$(find /testbed -type f -o -type l | wc -l)" -eq 8124 \
    && test "$(find /opt/donor-source -type f -o -type l | wc -l)" -eq 32

COPY public-examples/ /opt/public-examples/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /opt/task-tools/run-public-examples /opt/public-examples/verify_examples.py \
    && ln -s /opt/task-tools/run-public-examples /usr/local/bin/run-public-examples

WORKDIR /testbed
