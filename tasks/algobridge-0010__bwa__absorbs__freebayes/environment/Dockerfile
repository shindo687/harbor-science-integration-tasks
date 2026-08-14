FROM ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential ca-certificates python3 zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY host-source.tar.gz donor-source.tar.gz source-lock.json /opt/task-inputs/
COPY public_cases /public-cases/
RUN echo "0e30b97c3dc7182dbaa489b5599e9c14679b3c68b81006aa994ef00a0573e45a  /opt/task-inputs/host-source.tar.gz" | sha256sum --check --strict \
    && echo "0e12819c649c6b0ba83052182b16ae4588a009c9c4389148e95aaeecce740221  /opt/task-inputs/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/freebayes-source \
    && tar -xzf /opt/task-inputs/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/task-inputs/donor-source.tar.gz -C /opt/freebayes-source \
    && sed -i 's/-O2$/-O2 -fcommon/' /testbed/Makefile \
    && echo "3fb40f4cfeec6f87a5b298b046a9026e93b258bd85914ab1e5830423763fb434  /testbed/Makefile" | sha256sum --check --strict \
    && make -C /testbed -j"$(nproc)" \
    && /testbed/bwa 2>&1 | grep -F "Version: 0.7.17-r1188" \
    && make -C /testbed clean \
    && chown -R root:root /opt/freebayes-source /opt/task-inputs \
      /public-cases \
    && chmod -R go-w /opt/freebayes-source /opt/task-inputs /public-cases

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
WORKDIR /testbed
