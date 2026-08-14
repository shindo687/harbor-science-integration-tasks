FROM python:3.12.11-slim-bookworm

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 pytest==8.4.1

COPY host-source/ /testbed/
COPY donor-source/ /opt/scikit-learn/
COPY public-examples/ /examples/

ENV PYTHONPATH=/testbed
WORKDIR /testbed
