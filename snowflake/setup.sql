-- One-time Snowflake setup for this project. Run as ACCOUNTADMIN (e.g. in a free trial account).
-- Creates a small auto-suspending warehouse, the database, and a least-privilege role for the
-- pipeline and dbt. Replace <your_user> with your Snowflake user name.

use role accountadmin;

create warehouse if not exists transforming
    warehouse_size = xsmall
    auto_suspend = 60          -- seconds idle before suspending, so the trial credits last
    auto_resume = true
    initially_suspended = true;

create database if not exists citibike;

create role if not exists transformer;
grant usage on warehouse transforming to role transformer;
grant usage, create schema on database citibike to role transformer;
grant role transformer to user <your_user>;

-- Then, from the repo root:
--   export SNOWFLAKE_ACCOUNT=<org-account>  SNOWFLAKE_USER=<your_user>  SNOWFLAKE_PASSWORD=...
--   python -m pipeline.run extract
--   python -m pipeline.run load --target snowflake
--   python -m pipeline.run transform --target snowflake
