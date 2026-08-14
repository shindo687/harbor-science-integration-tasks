FROM docker.io/library/gcc@sha256:1dc2dc4d3fe9e181b0472342a7af1885f3d0f757fb241f815b617f470770f660

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "ece7507b819fcf69d46caf31e430565066804e805e8446a0cd37fe83dd7b4c38  host-source.tar.gz" | sha256sum --check --strict \
    && echo "0578bc1c58380ad9ad7d8d47bef7616bbd6c5146ad14ad1af836a4122ac0988b  donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-sources/boltztrap2 \
    && tar --no-same-owner --no-same-permissions -xzf host-source.tar.gz -C /testbed \
    && tar --no-same-owner --no-same-permissions -xzf donor-source.tar.gz \
       -C /opt/donor-sources/boltztrap2 --strip-components=1 \
    && test "$(find /testbed \( -type f -o -type l \) | wc -l)" = 7221 \
    && test "$(find /opt/donor-sources/boltztrap2 \( -type f -o -type l \) | wc -l)" = 2646 \
    && test -r /testbed/PP/src/dos.f90 \
    && test -r /opt/donor-sources/boltztrap2/BoltzTraP2/bandlib.py \
    && chown -R root:root /opt/donor-sources /opt/source-archives \
    && chmod -R go-w /opt/donor-sources /opt/source-archives

COPY public-examples/ /public-cases/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /opt/task-tools/run-public-examples /opt/task-tools/public_check.py \
      /opt/task-tools/candidate_runner.py \
    && chmod 0444 /opt/task-tools/transport_driver.f90 /public-cases/* \
    && chown -R root:root /public-cases /opt/task-tools \
    && chmod -R go-w /public-cases /opt/task-tools

ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /testbed
