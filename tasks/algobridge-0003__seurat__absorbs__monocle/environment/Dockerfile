FROM quay.io/biocontainers/r-monocle3@sha256:513fa87e98bebc2bc81442d779788866acfe9c29d42ec345db65d9818405050a

USER root

RUN addgroup --gid 10001 candidate \
    && adduser --uid 10001 --ingroup candidate --no-create-home \
      --shell /usr/sbin/nologin --disabled-password --gecos "" candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "ec63d2ffc7536ae16949c6de75a03bc574a3520f9f8651bfcfd04e59255dc00b  host-source.tar.gz" | sha256sum -c \
    && echo "f14316ae6050718f5b0779a644a4b3c9958877b388151e607b36e895092d7792  donor-source.tar.gz" | sha256sum -c \
    && mkdir -p /testbed /opt/donor-sources/monocle3 \
    && tar -xzf host-source.tar.gz -C /testbed \
    && tar -xzf donor-source.tar.gz -C /opt/donor-sources/monocle3 \
    && test "$(find /testbed \( -type f -o -type l \) | wc -l)" = 455 \
    && test "$(find /opt/donor-sources/monocle3 \( -type f -o -type l \) | wc -l)" = 227 \
    && test -r /testbed/R/dimensional_reduction.R \
    && test -r /opt/donor-sources/monocle3/R/order_cells.R \
    && test -r /opt/donor-sources/monocle3/R/learn_graph.R \
    && chown -R root:root /opt/source-archives /opt/donor-sources \
    && chmod -R a+rX,go-w /opt/source-archives /opt/donor-sources \
    && chmod 0700 /usr/local/lib/R/library/monocle3

COPY public-examples/ /public-cases/
COPY task-tools/ /opt/task-tools/
RUN chown -R root:root /public-cases /opt/task-tools \
    && chmod -R a+rX,go-w /public-cases /opt/task-tools \
    && chmod 0755 /opt/task-tools/run-public-examples

ENV PSEUDOTIME_CANDIDATE_FILE=/testbed/R/principal_graph_pseudotime.R
ENV PSEUDOTIME_CANDIDATE_ENTRY=/opt/task-tools/candidate_entry.R
ENV R_ENVIRON_USER=/dev/null
ENV R_PROFILE_USER=/dev/null
WORKDIR /testbed
