{# Fails for any combination of `columns` that appears more than once (a grain check). #}
{% test dbt_project_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as occurrences
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
