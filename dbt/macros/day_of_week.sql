{# Day of week with Sunday = 0 ... Saturday = 6 on every adapter. #}
{% macro day_of_week(ts) -%}
    {{ return(adapter.dispatch('day_of_week')(ts)) }}
{%- endmacro %}

{% macro default__day_of_week(ts) -%}
    extract(dow from {{ ts }})
{%- endmacro %}

{# Snowflake's DAYOFWEEK depends on the session's WEEK_START; DAYNAME does not. #}
{% macro snowflake__day_of_week(ts) -%}
    decode(dayname({{ ts }}), 'Sun', 0, 'Mon', 1, 'Tue', 2, 'Wed', 3, 'Thu', 4, 'Fri', 5, 'Sat', 6)
{%- endmacro %}
