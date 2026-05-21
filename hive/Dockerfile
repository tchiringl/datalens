# =============================================================================
# Apache Hive 4.2.0 Metastore — adds PostgreSQL JDBC driver
# Base: apache/hive:4.2.0 (missing postgres JDBC in classpath)
# =============================================================================
FROM apache/hive:4.2.0

USER root

# PostgreSQL JDBC driver — required for schematool to initialize metastore schema
RUN curl -fsSL "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar" \
    -o /opt/hive/lib/postgresql-42.7.3.jar

USER hive
