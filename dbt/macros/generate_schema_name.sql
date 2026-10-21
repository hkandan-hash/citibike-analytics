{#
  Use the configured schema name as-is (staging, core, analytics...) instead of dbt's default
  "<target_schema>_<custom>" prefixing, so DuckDB and Snowflake end up with the same layout.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
