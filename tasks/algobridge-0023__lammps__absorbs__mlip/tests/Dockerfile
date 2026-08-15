FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate \
    && install -d -m 0700 /tests /opt/reference-mlip /opt/reference-mlip/bin \
       /opt/reference-mlip/lib /opt/donor-source /opt/pristine-host \
       /opt/source-archives /opt/source-archives/parts /opt/reference-runner \
    && install -d -m 0755 /opt/candidate-assets

COPY --chmod=0400 source-parts/ /opt/source-archives/parts/
RUN cat /opt/source-archives/parts/host-source.tar.gz.part-00 /opt/source-archives/parts/host-source.tar.gz.part-01 > /opt/source-archives/host-source.tar.gz \
    && cat /opt/source-archives/parts/donor-source.tar.gz.part-00 > /opt/source-archives/donor-source.tar.gz \
    && echo "a73a74ab6a5c266c13da160ccb7affa809e8d3daa109c597c655a0d4ba88084a  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "1d0081baebab0ae87e3568289fa8b8301bc6e9fb7632ca1cdf76d05830909b90  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && test "$(find /opt/pristine-host/lammps -type f -o -type l | wc -l)" -eq 9677 \
    && test "$(find /opt/donor-source/mlip-3 -type f -o -type l | wc -l)" -eq 296 \
    && chmod 0400 /opt/source-archives/host-source.tar.gz /opt/source-archives/donor-source.tar.gz

COPY --chmod=0700 reference-bin/mlp /opt/reference-mlip/bin/mlp
COPY --chmod=0600 reference-bin/lib/ /opt/reference-mlip/lib/
COPY --chmod=0400 assets/mtp9-bounded.mtp /opt/reference-mlip/mtp9-bounded.mtp
COPY --chmod=0444 assets/ /opt/candidate-assets/
RUN chmod 0755 /opt/candidate-assets \
    && LD_LIBRARY_PATH=/opt/reference-mlip/lib /opt/reference-mlip/bin/mlp help | grep 'mlp serial version'

COPY --chmod=0700 reference_runner.py /opt/reference-runner/reference_runner.py
COPY --chmod=0700 cases.py candidate_runner.py grader.py reference_runner.py test.sh source-lock.json /tests/

WORKDIR /testbed
