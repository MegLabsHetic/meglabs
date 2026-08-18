create extension if not exists pgcrypto;

-- Miroir des utilisateurs (l'identite fait foi cote Supabase ; id = auth uid)
create table if not exists users (
    id          uuid primary key,
    email       text,
    tier        text not null default 'free',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table if not exists projects (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    name        text not null,
    description text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists idx_projects_user on projects(user_id);

create table if not exists datasets (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    user_id     uuid not null references users(id) on delete cascade,
    filename    text not null,
    row_count   integer,
    col_count   integer,
    size_bytes  bigint,
    status      text not null default 'pending',
    profile     jsonb,
    created_at  timestamptz not null default now()
);
create index if not exists idx_datasets_project on datasets(project_id);

-- File de jobs (traitement asynchrone par le worker Rust, verrou SKIP LOCKED)
create table if not exists jobs (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    project_id  uuid references projects(id) on delete cascade,
    dataset_id  uuid references datasets(id) on delete cascade,
    kind        text not null,
    status      text not null default 'queued',
    payload     jsonb not null default '{}'::jsonb,
    result      jsonb,
    error       text,
    created_at  timestamptz not null default now(),
    started_at  timestamptz,
    finished_at timestamptz
);
create index if not exists idx_jobs_status on jobs(status, created_at);
create index if not exists idx_jobs_user on jobs(user_id);

-- Suivi d'usage (quotas / rate limiting par palier)
create table if not exists usage_events (
    id          bigserial primary key,
    user_id     uuid not null references users(id) on delete cascade,
    action      text not null,
    metadata    jsonb,
    created_at  timestamptz not null default now()
);
create index if not exists idx_usage_user_action_date on usage_events(user_id, action, created_at);

-- Abonnements (branchement Stripe a venir ; palier applique des maintenant)
create table if not exists subscriptions (
    id                     uuid primary key default gen_random_uuid(),
    user_id                uuid not null references users(id) on delete cascade,
    tier                   text not null default 'free',
    status                 text not null default 'active',
    stripe_customer_id     text,
    stripe_subscription_id text,
    current_period_end     timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);
create index if not exists idx_subscriptions_user on subscriptions(user_id);
