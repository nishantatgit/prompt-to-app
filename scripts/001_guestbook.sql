create table guestbook_entries (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  name text not null check (char_length(name) between 1 and 80),
  message text not null check (char_length(message) between 1 and 500)
);

alter table guestbook_entries enable row level security;

create policy "Anyone can read entries" on guestbook_entries
  for select to anon, authenticated using (true);

create policy "Anyone can add an entry" on guestbook_entries
  for insert to anon, authenticated with check (true);

-- No update or delete policy, so nobody can change or remove entries.
grant select, insert on guestbook_entries to anon, authenticated;
