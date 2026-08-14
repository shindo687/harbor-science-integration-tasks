FROM debian:bookworm-slim

RUN sed -i \
      -e 's|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' \
      -e 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
      ca-certificates git patch \
      python3 python3-absl python3-biopython python3-networkx python3-numpy \
    && rm -rf /var/lib/apt/lists/*

COPY host-source/ /testbed/
COPY donor-source/ /opt/dockq/
COPY donor-shims/ /opt/dockq/shims/
COPY public-examples/ /examples/

# Locked DockQ remains runnable for research in the Agent phase.  Neither this
# directory nor PYTHONPATH is transferred to the separate verifier container.
ENV PYTHONPATH=/opt/dockq/shims:/opt/dockq/src:/opt/dockq/src/DockQ
WORKDIR /testbed
