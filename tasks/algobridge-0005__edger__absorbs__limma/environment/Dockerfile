FROM docker.io/library/r-base@sha256:a5845a19dbe67a49284a328ad2505cf8688aecaf22e4bbbac581044bbbd11c94

COPY host-source.tar.gz donor-source.tar.gz statmod-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "744ed24f9a1c4ef6d77bd173511285cca04c58e7b7be4504ed8572e86e403f3a  host-source.tar.gz" | sha256sum --check --strict \
    && echo "f1a83f45a5bb68873385e0e415a15131ad1f65c78fa6fd53911c812bf41e76ff  donor-source.tar.gz" | sha256sum --check --strict \
    && echo "37bf14b86a068336e28970c5ce5282b2573a7ce4bdf4b8d8f6d3d5a492c7fe55  statmod-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/donor-sources/limma /opt/reference-dependencies/statmod; \
    extract_locked() { \
      archive="$1"; destination="$2"; expected="$3"; \
      tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$destination" 2>/tmp/tar-warnings || true; \
      actual="$(find "$destination" \( -type f -o -type l \) | wc -l)"; \
      test "$actual" = "$expected"; \
    }; \
    extract_locked host-source.tar.gz /testbed 252; \
    extract_locked host-source.tar.gz /opt/pristine-host 252; \
    extract_locked donor-source.tar.gz /opt/donor-sources/limma 291; \
    extract_locked statmod-source.tar.gz /opt/reference-dependencies/statmod 63; \
    rm -rf /opt/source-archives /tmp/tar-warnings

COPY public-examples/ /public-cases/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /opt/task-tools/run-public-examples \
    && chmod 0444 /opt/task-tools/candidate_runner.R /public-cases/* \
    && test -r /testbed/R/calcNormFactors.R \
    && test -r /opt/donor-sources/limma/R/voom.R \
    && test -r /opt/reference-dependencies/statmod/R/digamma.R

ENV R_ENVIRON_USER=/dev/null
ENV R_PROFILE_USER=/dev/null
WORKDIR /testbed
