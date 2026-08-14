FROM docker.io/library/r-base@sha256:a5845a19dbe67a49284a328ad2505cf8688aecaf22e4bbbac581044bbbd11c94

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz statmod-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "744ed24f9a1c4ef6d77bd173511285cca04c58e7b7be4504ed8572e86e403f3a  host-source.tar.gz" | sha256sum --check --strict \
    && echo "f1a83f45a5bb68873385e0e415a15131ad1f65c78fa6fd53911c812bf41e76ff  donor-source.tar.gz" | sha256sum --check --strict \
    && echo "37bf14b86a068336e28970c5ce5282b2573a7ce4bdf4b8d8f6d3d5a492c7fe55  statmod-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference/limma /opt/reference/statmod; \
    extract_locked() { \
      archive="$1"; destination="$2"; expected="$3"; \
      tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$destination" 2>/tmp/tar-warnings || true; \
      actual="$(find "$destination" \( -type f -o -type l \) | wc -l)"; \
      test "$actual" = "$expected"; \
    }; \
    extract_locked host-source.tar.gz /opt/pristine-host 252; \
    extract_locked donor-source.tar.gz /opt/reference/limma 291; \
    extract_locked statmod-source.tar.gz /opt/reference/statmod 63; \
    rm -f /tmp/tar-warnings

RUN mkdir -p /opt/candidate-runner /opt/reference-runner /tests \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0700 /opt/reference-runner /tests

COPY candidate_runner.R /opt/candidate-runner/candidate_runner.R
COPY reference_runner.R /opt/reference-runner/reference_runner.R
COPY cases.R grader.R test.sh source-lock.json /tests/
RUN chmod 0444 /opt/candidate-runner/candidate_runner.R \
    && chmod 0700 /opt/reference-runner/reference_runner.R /tests/*

ENV R_ENVIRON_USER=/dev/null
ENV R_PROFILE_USER=/dev/null
WORKDIR /testbed
