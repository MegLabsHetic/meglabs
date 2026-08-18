-- Entrepot analytique : le CSV n'est plus retransporte a chaque calcul.
-- Un dataset devient une TABLE dans le fichier DuckDB du projet ; Postgres
-- ne garde que la metadonnee (nom de table, correspondance des colonnes,
-- historique des ingestions).

alter table datasets add column if not exists table_name  text;
alter table datasets add column if not exists column_map  jsonb;
alter table datasets add column if not exists ingested_at timestamptz;

create unique index if not exists idx_datasets_table
    on datasets(project_id, table_name) where table_name is not null;

-- Historique des chargements d'une source (import initial et rafraichissements)
create table if not exists ingestions (
    id          uuid primary key default gen_random_uuid(),
    dataset_id  uuid not null references datasets(id) on delete cascade,
    user_id     uuid not null references users(id) on delete cascade,
    mode        text not null default 'replace',
    verdict     text,
    row_count   integer,
    detail      jsonb,
    created_at  timestamptz not null default now()
);
create index if not exists idx_ingestions_dataset on ingestions(dataset_id, created_at desc);

-- Tableaux de bord : on stocke la SPEC (le SQL), jamais le resultat.
-- Rouvrir un tableau de bord ne coute donc aucun appel IA.
create table if not exists dashboards (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    user_id     uuid not null references users(id) on delete cascade,
    name        text not null default 'Tableau de bord',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists idx_dashboards_project on dashboards(project_id);

create table if not exists widgets (
    id           uuid primary key default gen_random_uuid(),
    dashboard_id uuid not null references dashboards(id) on delete cascade,
    title        text not null,
    sql          text not null,
    viz          text not null default 'table',
    format       text not null default 'nombre',
    position     integer not null default 0,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);
create index if not exists idx_widgets_dashboard on widgets(dashboard_id, position);
