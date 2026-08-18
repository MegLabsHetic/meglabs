-- Apparence d'un indicateur, separee de son calcul.
--
-- « mets cette courbe en orange », « entoure le pic » : ces demandes ne
-- changent ni la requete ni le chiffre, seulement la lecture. Les garder a
-- part du SQL permet de rejouer l'indicateur sur des donnees fraiches sans
-- perdre la mise en forme choisie.
--
-- Le contenu est valide cote engine (liste fermee de couleurs et de mises en
-- evidence) : rien de ce qu'un modele propose n'arrive ici tel quel.

alter table widgets add column if not exists style jsonb;
