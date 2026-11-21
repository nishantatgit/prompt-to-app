"""Leave an app's database as the tests found it.

Vyskar's tests run against the app's real Supabase database: they add rows,
rate things and sign up users. Before the tests, every table in the public
schema is copied into a snapshot schema, with the ids of the existing users.
After them, the tables get their rows back from the snapshot, users the
tests signed up are deleted, and the snapshot is dropped, so people who open
the app never see "Film 1795178728479434992".

The restore runs in one transaction: either the database is back as it was,
or nothing changed and the build is stopped before deploy.
"""

import psycopg

from tools.supabase import wait_for_connection

SCHEMA = "vyskar_snapshot"
USERS = "_vyskar_users"

SNAPSHOT_SQL = f"""
drop schema if exists {SCHEMA} cascade;
create schema {SCHEMA};
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('create table {SCHEMA}.%I as table public.%I', t.tablename, t.tablename);
  end loop;
  if to_regclass('auth.users') is not null then
    execute 'create table {SCHEMA}.{USERS} as select id from auth.users';
  end if;
end $$;
"""

RESTORE_SQL = f"""
do $$
declare
  tn text;
  tables text[];
  pending text[];
  still text[];
  cols text;
  replica boolean := false;
begin
  if to_regnamespace('{SCHEMA}') is null then
    raise exception 'no snapshot to restore';
  end if;

  select coalesce(array_agg(s.tablename order by s.tablename), '{{}}') into tables
  from pg_tables s
  join pg_tables p on p.schemaname = 'public' and p.tablename = s.tablename
  where s.schemaname = '{SCHEMA}';

  -- Triggers and foreign key checks off while rows go back, so counters
  -- kept by triggers aren't counted twice. Supabase's postgres role may set
  -- this. Where it can't, the tables' own triggers are switched off, which
  -- their owner may do, and rows go back in foreign key order instead.
  begin
    set local session_replication_role = replica;
    replica := true;
  exception when insufficient_privilege then
    foreach tn in array tables loop
      execute format('alter table public.%I disable trigger user', tn);
    end loop;
  end;

  if array_length(tables, 1) > 0 then
    execute (
      select 'truncate ' || string_agg(format('public.%I', x), ', ')
      from unnest(tables) x
    );
  end if;

  pending := tables;
  loop
    exit when coalesce(array_length(pending, 1), 0) = 0;
    still := '{{}}';
    foreach tn in array pending loop
      -- Generated columns are computed again, so they are left out.
      select string_agg(format('%I', a.attname), ', ' order by a.attnum) into cols
      from pg_attribute a
      where a.attrelid = format('public.%I', tn)::regclass
        and a.attnum > 0 and not a.attisdropped and a.attgenerated = '';
      begin
        execute format(
          'insert into public.%I (%s) overriding system value select %s from {SCHEMA}.%I',
          tn, cols, cols, tn
        );
      exception when foreign_key_violation then
        still := still || tn;
      end;
    end loop;
    if array_length(still, 1) = array_length(pending, 1) then
      raise exception 'could not put back rows of: %', array_to_string(still, ', ');
    end if;
    pending := still;
  end loop;

  if replica then
    set local session_replication_role = origin;
  else
    foreach tn in array tables loop
      execute format('alter table public.%I enable trigger user', tn);
    end loop;
  end if;
  if to_regclass('{SCHEMA}.{USERS}') is not null and to_regclass('auth.users') is not null then
    -- With triggers on again, so a user's sessions and identities go too.
    delete from auth.users where id not in (select id from {SCHEMA}.{USERS});
  end if;
end $$;
drop schema {SCHEMA} cascade;
"""


def _run(database_url: str, sql: str, connect) -> None:
    with wait_for_connection(database_url, connect) as conn:
        conn.execute(sql)


def snapshot(database_url: str, connect=psycopg.connect) -> None:
    """Copy every public table, and the ids of existing users."""
    _run(database_url, SNAPSHOT_SQL, connect)


def restore(database_url: str, connect=psycopg.connect) -> None:
    """Put the tables back as the snapshot has them, delete users signed up
    since, and drop the snapshot. All or nothing."""
    _run(database_url, RESTORE_SQL, connect)
