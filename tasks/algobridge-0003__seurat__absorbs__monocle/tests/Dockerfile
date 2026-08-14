FROM quay.io/biocontainers/r-monocle3@sha256:513fa87e98bebc2bc81442d779788866acfe9c29d42ec345db65d9818405050a

USER root

RUN addgroup --gid 10001 candidate \
    && adduser --uid 10001 --ingroup candidate --no-create-home \
      --shell /usr/sbin/nologin --disabled-password --gecos "" candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "ec63d2ffc7536ae16949c6de75a03bc574a3520f9f8651bfcfd04e59255dc00b  host-source.tar.gz" | sha256sum -c \
    && echo "f14316ae6050718f5b0779a644a4b3c9958877b388151e607b36e895092d7792  donor-source.tar.gz" | sha256sum -c \
    && mkdir -p /opt/pristine-host /opt/reference/monocle3 \
    && tar -xzf host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf donor-source.tar.gz -C /opt/reference/monocle3 \
    && test "$(find /opt/pristine-host \( -type f -o -type l \) | wc -l)" = 455 \
    && test "$(find /opt/reference/monocle3 \( -type f -o -type l \) | wc -l)" = 227 \
    && test -r /opt/pristine-host/R/dimensional_reduction.R \
    && test -r /opt/reference/monocle3/R/order_cells.R \
    && test -r /opt/reference/monocle3/R/learn_graph.R \
    && Rscript -e 'stopifnot(as.character(packageVersion("monocle3")) == "1.4.26"); source_env <- new.env(parent = globalenv()); sys.source("/opt/reference/monocle3/R/learn_graph.R", source_env); sys.source("/opt/reference/monocle3/R/order_cells.R", source_env); package_env <- asNamespace("monocle3"); functions <- c("project2MST", "project_point_to_line_segment", "findNearestPointOnMST", "find_nearest_vertex", "order_cells", "extract_general_graph_ordering", "branch_nodes", "leaf_nodes", "root_nodes"); for (name in functions) stopifnot(identical(formals(source_env[[name]]), formals(package_env[[name]])), identical(body(source_env[[name]]), body(package_env[[name]])))' \
    && chown -R root:root /opt/pristine-host /opt/reference /opt/source-archives \
    && chmod 0700 /opt/pristine-host /opt/reference /opt/source-archives \
    && chmod 0700 /usr/local/lib/R/library/monocle3

RUN mkdir -p /opt/candidate-runner /tests \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0555 /opt/candidate-runner \
    && chmod 0700 /tests

COPY candidate_entry.R candidate_runner.R /opt/candidate-runner/
COPY cases.R reference_runner.R grader.R test.sh source-lock.json /tests/
COPY public-examples/ /tests/public-examples/
RUN chown -R root:root /opt/candidate-runner /tests \
    && chmod 0444 /opt/candidate-runner/candidate_entry.R /opt/candidate-runner/candidate_runner.R \
    && chmod 0700 /tests /tests/* \
    && chmod 0755 /tests/test.sh

ENV PSEUDOTIME_CANDIDATE_FILE=/testbed/R/principal_graph_pseudotime.R
ENV PSEUDOTIME_CANDIDATE_ENTRY=/opt/candidate-runner/candidate_entry.R
ENV R_ENVIRON_USER=/dev/null
ENV R_PROFILE_USER=/dev/null
WORKDIR /testbed
