{# Station IDs are prefixed JC (Jersey City) or HB (Hoboken); anything else is a New York City dock. #}
{% macro station_area(station_id) -%}
    case
        when {{ station_id }} is null then null
        when {{ station_id }} like 'JC%' then 'Jersey City'
        when {{ station_id }} like 'HB%' then 'Hoboken'
        else 'New York City'
    end
{%- endmacro %}
