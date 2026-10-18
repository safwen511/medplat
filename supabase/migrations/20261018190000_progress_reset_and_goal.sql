-- Students may reset a lesson to "Non lu" (delete their own follow-up row) and set a daily goal.
create policy "own progress: delete" on public.lesson_progress
  for delete to authenticated using ((select auth.uid()) = user_id);

alter table public.profiles add column daily_goal smallint not null default 20
  check (daily_goal between 5 and 200);
