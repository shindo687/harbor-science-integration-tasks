FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY host-source.tar.gz /tmp/host-source.tar.gz
RUN mkdir -p /testbed && \
    tar -xzf /tmp/host-source.tar.gz -C /testbed --strip-components=1 && \
    make -C /testbed/src serial -j8 && \
    find /testbed/src -maxdepth 1 -type f \
      \( -name '*.tmp' -o -name 'tmp_lmpinstalledpkgs.h_name.*' \) -delete && \
    rm /tmp/host-source.tar.gz

COPY donor-source.tar.gz /tmp/donor-source.tar.gz
RUN mkdir -p /opt/reference-phonopy-source && \
    tar -xzf /tmp/donor-source.tar.gz -C /opt/reference-phonopy-source --strip-components=1 && \
    rm /tmp/donor-source.tar.gz

COPY public-examples /public-examples
COPY public_check.py /usr/local/bin/check-fc2-public
RUN chmod 755 /usr/local/bin/check-fc2-public

WORKDIR /testbed
CMD ["sleep", "infinity"]
