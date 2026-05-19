/*
  generate_schema_name
  --------------------
  Override dbt's default schema-name generation behaviour.

  By default dbt concatenates the target schema with the custom schema
  (e.g. "cdm_staging"), which creates ugly schema names in multi-schema
  projects.

  This override ensures that:
    - When no custom_schema_name is set, the target.schema (e.g. "cdm") is used.
    - When a custom_schema_name IS set, that value is used verbatim (trimmed),
      so staging → "staging", cdm → "cdm", marts → "marts".

  This keeps schema names clean across all environments.
*/

{% macro generate_schema_name(custom_schema_name, node) -%}

  {%- set default_schema = target.schema -%}

  {%- if custom_schema_name is none -%}
    {{ default_schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}

{%- endmacro %}
