FROM docker.io/library/gcc@sha256:1dc2dc4d3fe9e181b0472342a7af1885f3d0f757fb241f815b617f470770f660

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "bf67074beb05da75a8b13ecf6f66d7a349a7c779ca25a9adfe834f04dfad0d0d  host-source.tar.gz" | sha256sum --check --strict \
    && echo "3c718b2a700ca0df87f7467ef7ae24ab030ae7e64ee50896f0dd5d0f1f85bd2d  donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-sources/z2pack \
    && tar --no-same-owner --no-same-permissions -xzf host-source.tar.gz -C /testbed \
    && tar --no-same-owner --no-same-permissions -xzf donor-source.tar.gz \
       -C /opt/donor-sources/z2pack --strip-components=1 \
    && test "$(find /testbed \( -type f -o -type l \) | wc -l)" = 102 \
    && test "$(find /opt/donor-sources/z2pack \( -type f -o -type l \) | wc -l)" = 76 \
    && test -r /testbed/src/hamiltonian.F90 \
    && test -r /opt/donor-sources/z2pack/z2pack/invariant.py \
    && chown -R root:root /opt/donor-sources /opt/source-archives \
    && chmod -R a+rX,go-w /opt/donor-sources /opt/source-archives

COPY public-examples/ /public-cases/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /opt/task-tools/run-public-examples /opt/task-tools/public_check.py \
      /opt/task-tools/candidate_runner.py \
    && chmod 0444 /opt/task-tools/z2_wilson_driver.f90 /public-cases/* \
    && chown -R root:root /public-cases /opt/task-tools \
    && chmod -R go-w /public-cases /opt/task-tools

ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV Z2_CANDIDATE_DRIVER=/opt/task-tools/z2_wilson_driver.f90
WORKDIR /testbed
