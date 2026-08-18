-- Contenu brut du dataset, pour les operations post-profilage (nettoyage, KPIs).
-- Etape provisoire : a migrer vers de l'object storage (S3/MinIO) pour les gros fichiers.
alter table datasets add column if not exists content text;
