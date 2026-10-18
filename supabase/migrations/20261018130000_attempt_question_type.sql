-- Question type of each answer (qcm, qrm, vrai_faux, ...), for accuracy by type.
alter table public.attempts add column question_type text;
