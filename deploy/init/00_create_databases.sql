-- Phase 0 数据库初始化（在 192.168.168.100 上以超级用户执行，psql 专用语法）
--
--   psql -h 127.0.0.1 -U postgres -f 00_create_databases.sql
--
-- 如果已有 customer_service 角色，本脚本不会修改其密码。

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'customer_service') THEN
        CREATE ROLE customer_service LOGIN PASSWORD 'customer_service';
    END IF;
END
$$;

SELECT 'CREATE DATABASE edu_customer_service OWNER customer_service'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'edu_customer_service')\gexec

SELECT 'CREATE DATABASE edu_ai_service OWNER customer_service'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'edu_ai_service')\gexec

\connect edu_customer_service
GRANT ALL ON SCHEMA public TO customer_service;

\connect edu_ai_service
GRANT ALL ON SCHEMA public TO customer_service;
