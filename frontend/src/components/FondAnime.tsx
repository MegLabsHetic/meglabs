/**
 * Fond animé : une grille en perspective qui fuit vers l'horizon, et des points
 * qui dérivent en profondeur.
 *
 * Écrit à la main sur un canvas 2D plutôt qu'avec une bibliothèque 3D : la
 * projection perspective tient en une ligne, et ajouter 600 ko de dépendance pour
 * un décor serait un mauvais échange — surtout sur un projet qui met la frugalité
 * en avant.
 *
 * Le rendu s'arrête quand l'onglet passe en arrière-plan, et ne démarre pas du tout
 * si la personne a demandé moins de mouvement.
 */
"use client";

import { useEffect, useRef } from "react";

interface Point {
  x: number;
  y: number;
  z: number;
}

const NB_POINTS = 90;
const PROFONDEUR = 900;
const FOCALE = 320;

export function FondAnime() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const surface = canvas.current;
    if (!surface) return;

    const moinsDeMouvement = window.matchMedia("(prefers-reduced-motion: reduce)");
    const contexte = surface.getContext("2d");
    if (!contexte) return;

    let largeur = 0;
    let hauteur = 0;
    let animation = 0;
    let derniere = performance.now();

    const points: Point[] = Array.from({ length: NB_POINTS }, () => ({
      x: (Math.random() - 0.5) * 2200,
      y: (Math.random() - 0.5) * 1200,
      z: Math.random() * PROFONDEUR,
    }));

    const redimensionner = () => {
      const densite = Math.min(window.devicePixelRatio || 1, 2);
      largeur = surface.clientWidth;
      hauteur = surface.clientHeight;
      surface.width = largeur * densite;
      surface.height = hauteur * densite;
      contexte.setTransform(densite, 0, 0, densite, 0, 0);
    };

    // Projection perspective : plus un point est loin, plus il se rapproche du
    // point de fuite et plus il pâlit.
    const projeter = (point: Point) => {
      const echelle = FOCALE / (FOCALE + point.z);
      return {
        x: largeur / 2 + point.x * echelle,
        y: hauteur * 0.55 + point.y * echelle,
        echelle,
      };
    };

    const dessinerGrille = (decalage: number) => {
      contexte.lineWidth = 1;
      for (let rang = 0; rang < 22; rang += 1) {
        const z = ((rang * 60 + decalage) % PROFONDEUR) + 40;
        const echelle = FOCALE / (FOCALE + z);
        const y = hauteur * 0.55 + 260 * echelle;
        contexte.strokeStyle = `rgba(94, 179, 246, ${0.16 * echelle})`;
        contexte.beginPath();
        contexte.moveTo(0, y);
        contexte.lineTo(largeur, y);
        contexte.stroke();
      }

      for (let colonne = -11; colonne <= 11; colonne += 1) {
        const bas = projeter({ x: colonne * 190, y: 260, z: 40 });
        const loin = projeter({ x: colonne * 190, y: 260, z: PROFONDEUR });
        contexte.strokeStyle = "rgba(94, 179, 246, 0.07)";
        contexte.beginPath();
        contexte.moveTo(bas.x, bas.y);
        contexte.lineTo(loin.x, loin.y);
        contexte.stroke();
      }
    };

    const dessinerPoints = () => {
      for (const point of points) {
        const { x, y, echelle } = projeter(point);
        if (x < -50 || x > largeur + 50 || y < -50 || y > hauteur + 50) continue;
        contexte.fillStyle = `rgba(167, 139, 250, ${0.5 * echelle})`;
        contexte.beginPath();
        contexte.arc(x, y, Math.max(0.4, 2.2 * echelle), 0, Math.PI * 2);
        contexte.fill();
      }
    };

    const rendre = (maintenant: number) => {
      const ecoule = Math.min(maintenant - derniere, 64);
      derniere = maintenant;

      contexte.clearRect(0, 0, largeur, hauteur);
      dessinerGrille((maintenant / 26) % PROFONDEUR);

      for (const point of points) {
        point.z -= ecoule * 0.035;
        if (point.z <= 1) point.z = PROFONDEUR;
      }
      dessinerPoints();

      animation = requestAnimationFrame(rendre);
    };

    const demarrer = () => {
      if (animation || moinsDeMouvement.matches) return;
      derniere = performance.now();
      animation = requestAnimationFrame(rendre);
    };

    const arreter = () => {
      cancelAnimationFrame(animation);
      animation = 0;
    };

    // Une image fixe reste dessinée même sans animation : le décor existe, il ne
    // bouge simplement pas.
    const dessinerUneFois = () => {
      contexte.clearRect(0, 0, largeur, hauteur);
      dessinerGrille(0);
      dessinerPoints();
    };

    const surVisibilite = () => (document.hidden ? arreter() : demarrer());

    redimensionner();
    dessinerUneFois();
    demarrer();

    window.addEventListener("resize", redimensionner);
    document.addEventListener("visibilitychange", surVisibilite);

    return () => {
      arreter();
      window.removeEventListener("resize", redimensionner);
      document.removeEventListener("visibilitychange", surVisibilite);
    };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <canvas ref={canvas} className="h-full w-full opacity-70" />
      {/* Halos colorés : ils donnent la profondeur que le canvas seul n'a pas. */}
      <div
        className="absolute -top-40 left-1/4 h-[520px] w-[520px] rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(34,211,238,0.10), transparent 65%)" }}
      />
      <div
        className="absolute -bottom-52 right-1/5 h-[560px] w-[560px] rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(167,139,250,0.10), transparent 65%)" }}
      />
      {/* Voile du bas : les contenus longs ne doivent pas se noyer dans la grille. */}
      <div
        className="absolute inset-x-0 bottom-0 h-1/3"
        style={{ background: "linear-gradient(180deg, transparent, var(--fond))" }}
      />
    </div>
  );
}
