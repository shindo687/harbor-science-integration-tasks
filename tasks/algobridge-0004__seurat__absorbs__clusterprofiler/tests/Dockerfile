FROM docker.io/library/r-base@sha256:a5845a19dbe67a49284a328ad2505cf8688aecaf22e4bbbac581044bbbd11c94

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz clusterprofiler-source.tar.gz dose-source.tar.gz qvalue-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "afa95adc7012df50fe7c63bc744eb44dd72e241929b9180a1bc6b53d050601ae  host-source.tar.gz" | sha256sum --check --strict \
    && echo "814bdb801534badf75c6efe8ff623cc7d2279e478055736aef4efbc6b593e324  clusterprofiler-source.tar.gz" | sha256sum --check --strict \
    && echo "94f09d7247b7c9c4f34475e984b87350d778eb1983e8240b7d575c6fedbb1f0b  dose-source.tar.gz" | sha256sum --check --strict \
    && echo "569faa5c3757931d54159073764765cea532dd1a6faef9f832377b9a30d3b2c5  qvalue-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference/clusterProfiler /opt/reference/DOSE /opt/reference/qvalue; \
    extract_locked() { \
      archive="$1"; destination="$2"; expected="$3"; \
      tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$destination" 2>/tmp/tar-warnings || true; \
      actual="$(find "$destination" \( -type f -o -type l \) | wc -l)"; \
      test "$actual" = "$expected"; \
    }; \
    extract_locked host-source.tar.gz /opt/pristine-host 430; \
    extract_locked clusterprofiler-source.tar.gz /opt/reference/clusterProfiler 133; \
    extract_locked dose-source.tar.gz /opt/reference/DOSE 83; \
    extract_locked qvalue-source.tar.gz /opt/reference/qvalue 30; \
    rm -f /tmp/tar-warnings

RUN mkdir -p /opt/candidate-runner /opt/reference-runner /tests \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0700 /opt/reference-runner /tests

COPY --chmod=0444 candidate_runner.R /opt/candidate-runner/candidate_runner.R
COPY --chmod=0700 reference_runner.R /opt/reference-runner/reference_runner.R
COPY --chmod=0700 cases.R grader.R test.sh source-lock.json /tests/

ENV R_ENVIRON_USER=/dev/null
ENV R_PROFILE_USER=/dev/null
WORKDIR /testbed
