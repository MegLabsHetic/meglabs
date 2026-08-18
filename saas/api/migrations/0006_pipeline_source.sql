-- La pipeline retenue a l'import decrit la source, pas seulement ce chargement-la.
--
-- Sans elle, un fichier rafraichi repart brut : les montants « 1 234,56 € »
-- reviennent en texte et la colonne, typee DOUBLE a l'import, redevient du
-- VARCHAR. Toutes les sommes du tableau de bord tombent alors en silence.
-- De meme, un tableau decoupe en tables liees se retrouverait recolle en un
-- seul bloc, a cote des dimensions restees en place.
--
-- On conserve donc les corrections et le decoupage valides par l'utilisateur
-- pour les REJOUER a chaque mise a jour : la source garde sa forme.

alter table datasets add column if not exists clean_actions jsonb;
alter table datasets add column if not exists decoupage     jsonb;
