FROM apache/airflow:2.9.1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install extra Python dependencies required by DAGs
COPY requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt

# Install dbt with Trino adapter
RUN pip install --no-cache-dir \
    dbt-core==1.8.0 \
    dbt-trino==1.8.0
