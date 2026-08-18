-- Authentification native : comptes e-mail + mot de passe geres par l'API,
-- sans dependance a un fournisseur externe.
--
-- Le mot de passe n'est JAMAIS stocke : seule une empreinte Argon2id l'est,
-- avec son sel integre.

alter table users add column if not exists password_hash text;
alter table users add column if not exists name          text;
alter table users add column if not exists last_login_at timestamptz;

-- Unicite de l'e-mail, insensible a la casse, uniquement pour les comptes
-- locaux : les identites externes (Supabase) n'ont pas de mot de passe ici
-- et ne doivent pas entrer en collision.
create unique index if not exists idx_users_email_local
    on users (lower(email))
    where password_hash is not null;
