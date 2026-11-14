create table notes (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  created_at timestamptz not null default now(),
  body text not null check (char_length(body) between 1 and 2000)
);

alter table notes enable row level security;

create policy "Owners read their notes" on notes
  for select to authenticated using (user_id = auth.uid());
create policy "Owners add notes" on notes
  for insert to authenticated with check (user_id = auth.uid());
create policy "Owners change their notes" on notes
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "Owners delete their notes" on notes
  for delete to authenticated using (user_id = auth.uid());

revoke all on notes from anon;
grant select, insert, update, delete on notes to authenticated;
