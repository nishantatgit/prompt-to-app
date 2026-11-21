"""The snapshot and restore SQL, run against a real Postgres shaped like a
Supabase app. Set VYSKAR_TEST_DATABASE_URL to a Postgres you may create
databases in (as a superuser), for example
  VYSKAR_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/postgres
Without it these tests are skipped."""

import os
import uuid

import psycopg
import pytest

from tools import test_data

ADMIN_URL = os.getenv("VYSKAR_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="VYSKAR_TEST_DATABASE_URL is not set")

# A small Supabase-like app: logins, a table with an identity and a
# generated column, a child table with foreign keys, and a trigger that
# keeps a counter, like the movie rating app.
APP_SQL = """
create schema auth;
create table auth.users (id uuid primary key, email text);
create table auth.identities (
  id serial primary key, user_id uuid references auth.users on delete cascade
);
create table public.movies (
  id bigint generated always as identity primary key,
  title text not null,
  ratings_count int not null default 0,
  title_upper text generated always as (upper(title)) stored
);
create table public.ratings (
  id bigserial primary key,
  movie_id bigint not null references public.movies on delete cascade,
  user_id uuid references auth.users,
  score int not null
);
create function public.count_rating() returns trigger language plpgsql as $$
begin
  update public.movies set ratings_count = ratings_count + 1 where id = new.movie_id;
  return new;
end $$;
create trigger count_rating after insert on public.ratings
  for each row execute function public.count_rating();

insert into auth.users values ('00000000-0000-0000-0000-000000000001', 'real@example.com');
insert into auth.identities (user_id) values ('00000000-0000-0000-0000-000000000001');
insert into public.movies (title) values ('Brass Band Brigade'), ('Cold Storage');
insert into public.ratings (movie_id, user_id, score)
  values (1, '00000000-0000-0000-0000-000000000001', 9);
"""

# What Vyskar's tests do: sign up a user, add a film, rate films.
TESTS_SQL = """
insert into auth.users values ('00000000-0000-0000-0000-0000000000aa', 'vyskar.test+1@gmail.com');
insert into auth.identities (user_id) values ('00000000-0000-0000-0000-0000000000aa');
insert into public.movies (title) values ('Film 1795178728479434992');
insert into public.ratings (movie_id, user_id, score)
  values (3, '00000000-0000-0000-0000-0000000000aa', 7),
         (1, '00000000-0000-0000-0000-0000000000aa', 2);
delete from public.movies where title = 'Cold Storage';
"""


def url_for(base: str, dbname: str, user: str | None = None) -> str:
    conninfo = psycopg.conninfo.conninfo_to_dict(base)
    conninfo["dbname"] = dbname
    if user:
        conninfo["user"] = user
    return psycopg.conninfo.make_conninfo(**conninfo)


@pytest.fixture
def app_db():
    name = "vyskar_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"create database {name}")
    url = url_for(ADMIN_URL, name)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(APP_SQL)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"drop database {name} with (force)")


def state(url: str) -> dict:
    with psycopg.connect(url) as conn:
        return {
            "movies": conn.execute(
                "select id, title, ratings_count, title_upper from public.movies order by id"
            ).fetchall(),
            "ratings": conn.execute(
                "select id, movie_id, score from public.ratings order by id"
            ).fetchall(),
            "users": conn.execute("select email from auth.users order by email").fetchall(),
            "identities": conn.execute("select count(*) from auth.identities").fetchone()[0],
            "snapshot": conn.execute(
                "select count(*) from pg_namespace where nspname = %s", (test_data.SCHEMA,)
            ).fetchone()[0],
        }


def test_the_tests_leave_the_database_as_they_found_it(app_db):
    before = state(app_db)
    test_data.snapshot(app_db)
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute(TESTS_SQL)
    assert len(state(app_db)["movies"]) == 2  # one added, one deleted

    test_data.restore(app_db)

    after = state(app_db)
    assert after == before
    # The counter kept by the trigger was not counted again on restore.
    assert after["movies"][0][:3] == (1, "Brass Band Brigade", 1)
    assert after["users"] == [("real@example.com",)]
    assert after["identities"] == 1  # the test user's identity went with it
    assert after["snapshot"] == 0


def test_new_rows_after_the_restore_get_fresh_ids(app_db):
    test_data.snapshot(app_db)
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute(TESTS_SQL)
    test_data.restore(app_db)
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute("insert into public.movies (title) values ('Neon Harvest')")
    titles = [m[1] for m in state(app_db)["movies"]]
    assert titles == ["Brass Band Brigade", "Cold Storage", "Neon Harvest"]


def test_without_permission_to_turn_off_triggers_rows_go_back_in_order(app_db):
    """A role that may not set session_replication_role still restores, by
    putting parents back before children."""
    role = "app_" + uuid.uuid4().hex[:8]
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute(f"create role {role} login")
        conn.execute(f"alter schema public owner to {role}")
        conn.execute(f"grant create on database {conn.info.dbname} to {role}")
        for table in ("movies", "ratings"):
            conn.execute(f"alter table public.{table} owner to {role}")
        conn.execute(f"alter sequence public.ratings_id_seq owner to {role}")
        conn.execute(f"grant usage on schema auth to {role}")
        conn.execute(f"grant select, delete, references on auth.users to {role}")
    owner_url = url_for(app_db, psycopg.conninfo.conninfo_to_dict(app_db)["dbname"], role)
    before = state(app_db)

    test_data.snapshot(owner_url)
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute(TESTS_SQL)
    test_data.restore(owner_url)

    after = state(app_db)
    assert after["movies"] == before["movies"] and after["ratings"] == before["ratings"]
    assert after["users"] == before["users"]
    with psycopg.connect(app_db, autocommit=True) as conn:
        # The triggers are on again: a new rating is counted.
        conn.execute("insert into public.ratings (movie_id, score) values (2, 5)")
        count = conn.execute("select ratings_count from public.movies where id = 2").fetchone()[0]
        assert count == before["movies"][1][2] + 1
        conn.execute(f"reassign owned by {role} to postgres")
        conn.execute(f"drop owned by {role}")
        conn.execute(f"drop role {role}")


def test_a_failed_restore_changes_nothing(app_db):
    test_data.snapshot(app_db)
    with psycopg.connect(app_db, autocommit=True) as conn:
        conn.execute(TESTS_SQL)
        # Something the restore can't satisfy: a NOT NULL column added after
        # the snapshot, so old rows can't go back.
        conn.execute("alter table public.ratings add column note text not null default 'x'")
        conn.execute("alter table public.ratings alter column note drop default")
    during = state(app_db)
    with pytest.raises(psycopg.Error):
        test_data.restore(app_db)
    assert state(app_db) == during  # all or nothing; the snapshot is still there


def test_restore_without_a_snapshot_fails_loudly(app_db):
    with pytest.raises(psycopg.Error, match="no snapshot"):
        test_data.restore(app_db)
