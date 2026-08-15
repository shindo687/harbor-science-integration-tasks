FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY source-parts/ /opt/source-parts/
RUN echo "4bcd479fbd41447a4bd3dbc5ae1904d6b139461b7e5e029232581a5b9c5e9b88  /opt/source-parts/host-source.tar.gz.part-00" | sha256sum --check --strict \
    && echo "83eaf9d02f756c012e91d7549a3df8c682f1843b15ca1afb6b782e0e52fbdaec  /opt/source-parts/host-source.tar.gz.part-01" | sha256sum --check --strict \
    && echo "1d0081baebab0ae87e3568289fa8b8301bc6e9fb7632ca1cdf76d05830909b90  /opt/source-parts/donor-source.tar.gz.part-00" | sha256sum --check --strict \
    && mkdir -p /opt/source-archives /testbed /opt/donor-source \
    && cat /opt/source-parts/host-source.tar.gz.part-00 /opt/source-parts/host-source.tar.gz.part-01 > /opt/source-archives/host-source.tar.gz \
    && cat /opt/source-parts/donor-source.tar.gz.part-00 > /opt/source-archives/donor-source.tar.gz \
    && echo "a73a74ab6a5c266c13da160ccb7affa809e8d3daa109c597c655a0d4ba88084a  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "1d0081baebab0ae87e3568289fa8b8301bc6e9fb7632ca1cdf76d05830909b90  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed --strip-components=1 \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && test "$(find /testbed -type f -o -type l | wc -l)" -eq 9677 \
    && test "$(find /opt/donor-source/mlip-3 -type f -o -type l | wc -l)" -eq 296 \
    && make -C /testbed/src serial -j8 \
    && find /testbed/src -maxdepth 1 -type f \( -name '*.tmp' -o -name 'tmp_lmpinstalledpkgs.h_name.*' \) -delete

COPY --chmod=0644 assets/ /opt/candidate-assets/
RUN chmod 0755 /opt/candidate-assets
COPY --chmod=0755 task-tools/ /opt/task-tools/
COPY --chmod=0644 public-examples/ /examples/
COPY --chmod=0644 source-lock.json /opt/task-source-lock.json

WORKDIR /testbed
