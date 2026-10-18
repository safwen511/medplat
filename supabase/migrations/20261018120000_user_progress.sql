-- MedPlat user data: profile, answers, lesson follow-up (fiche de suivi), highlights, error reports.
-- Course content is static (built from the pipeline); only per-student data lives here.
-- Every table has row-level security: a student reads and writes only their own rows.

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  faculty text not null default 'sfax',
  year text check (year in ('dcem1', 'dcem2')),
  exam_date date,
  onboarded_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.attempts (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  question_id text not null,
  lesson_id text not null,
  faculty text not null,
  year text not null,
  mode text not null check (mode in ('lesson', 'quiz', 'game', 'exam')),
  correct boolean not null,
  response jsonb,
  time_ms integer not null check (time_ms >= 0),
  hints_used smallint not null default 0 check (hints_used between 0 and 3),
  created_at timestamptz not null default now()
);
create index attempts_user_time on public.attempts (user_id, created_at desc);
create index attempts_user_lesson on public.attempts (user_id, lesson_id);

create table public.lesson_progress (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lesson_id text not null,
  faculty text not null,
  year text not null,
  status text not null default 'lu' check (status in ('lu', 'revise_1', 'revise_2', 'maitrise')),
  revisions smallint not null default 0,
  first_read_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, lesson_id)
);

create table public.highlights (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lesson_id text not null,
  quote text not null check (char_length(quote) between 1 and 2000),
  note text check (char_length(note) <= 2000),
  created_at timestamptz not null default now()
);
create index highlights_user_lesson on public.highlights (user_id, lesson_id);

create table public.error_reports (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lesson_id text not null,
  question_id text,
  message text not null check (char_length(message) between 1 and 2000),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.attempts enable row level security;
alter table public.lesson_progress enable row level security;
alter table public.highlights enable row level security;
alter table public.error_reports enable row level security;

create policy "own profile: read" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "own profile: update" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create policy "own attempts: read" on public.attempts
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own attempts: insert" on public.attempts
  for insert to authenticated with check ((select auth.uid()) = user_id);

create policy "own progress: read" on public.lesson_progress
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own progress: insert" on public.lesson_progress
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own progress: update" on public.lesson_progress
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "own highlights: read" on public.highlights
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own highlights: insert" on public.highlights
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own highlights: delete" on public.highlights
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Error reports are write-once for students; reviewers read them with the dashboard.
create policy "own reports: insert" on public.error_reports
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own reports: read" on public.error_reports
  for select to authenticated using ((select auth.uid()) = user_id);

-- A profile row is created at the first sign-in (Google), with the provider's display name.
create function public.handle_new_user() returns trigger
  language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create function public.touch_updated_at() returns trigger
  language plpgsql set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger lesson_progress_touch before update on public.lesson_progress
  for each row execute function public.touch_updated_at();
