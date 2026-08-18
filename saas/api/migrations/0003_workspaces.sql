-- Organisation a deux niveaux : un utilisateur a des espaces de travail,
-- chaque espace contient des projets.

create table if not exists workspaces (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    name        text not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists idx_workspaces_user on workspaces(user_id);

alter table projects add column if not exists workspace_id uuid
    references workspaces(id) on delete cascade;

-- Reprise de l'existant : un espace par utilisateur ayant deja des projets.
insert into workspaces (user_id, name)
select distinct user_id, 'Espace principal'
from projects
where workspace_id is null;

update projects p
set workspace_id = w.id
from workspaces w
where p.workspace_id is null
  and w.user_id = p.user_id
  and w.name = 'Espace principal';

alter table projects alter column workspace_id set not null;
create index if not exists idx_projects_workspace on projects(workspace_id);
