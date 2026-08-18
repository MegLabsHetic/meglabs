/**
 * Le logo : un icosaèdre en fil de fer qui tourne lentement.
 *
 * Écrit à la main — les douze sommets d'un icosaèdre se déduisent du nombre d'or,
 * la rotation est un produit de deux matrices, et la projection perspective tient en
 * une division. Une bibliothèque 3D coûterait plusieurs centaines de kilo-octets
 * pour ça, sur un projet dont la frugalité est un argument de soutenance.
 *
 * Le rendu s'arrête hors écran et ne démarre pas si la personne a demandé moins de
 * mouvement — la forme reste alors dessinée, simplement immobile.
 */
"use client";

import { useEffect, useRef } from "react";

type Sommet = [number, number, number];

const OR = (1 + Math.sqrt(5)) / 2;

// Les douze sommets d'un icosaèdre : trois rectangles d'or orthogonaux.
const SOMMETS: Sommet[] = [
  [-1, OR, 0], [1, OR, 0], [-1, -OR, 0], [1, -OR, 0],
  [0, -1, OR], [0, 1, OR], [0, -1, -OR], [0, 1, -OR],
  [OR, 0, -1], [OR, 0, 1], [-OR, 0, -1], [-OR, 0, 1],
];

const ARETES: [number, number][] = [
  [0, 1], [0, 5], [0, 7], [0, 10], [0, 11],
  [1, 5], [1, 7], [1, 8], [1, 9],
  [2, 3], [2, 4], [2, 6], [2, 10], [2, 11],
  [3, 4], [3, 6], [3, 8], [3, 9],
  [4, 5], [4, 9], [4, 11],
  [5, 9], [5, 11],
  [6, 7], [6, 8], [6, 10],
  [7, 8], [7, 10],
  [8, 9], [10, 11],
];

export function Logo3D({ taille = 120 }: { taille?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const surface = canvas.current;
    const contexte = surface?.getContext("2d");
    if (!surface || !contexte) return;

    const moinsDeMouvement = window.matchMedia("(prefers-reduced-motion: reduce)");
    const densite = Math.min(window.devicePixelRatio || 1, 2);
    surface.width = taille * densite;
    surface.height = taille * densite;
    contexte.scale(densite, densite);

    const rayon = taille * 0.3;
    const centre = taille / 2;
    let animation = 0;
    let angle = 0.6;

    const tourner = ([x, y, z]: Sommet, a: number): Sommet => {
      // Rotation autour de Y, puis inclinaison fixe autour de X : la forme garde
      // une assise, au lieu de rouler dans tous les sens.
      const xy = x * Math.cos(a) - z * Math.sin(a);
      const zy = x * Math.sin(a) + z * Math.cos(a);
      const inclinaison = 0.42;
      return [
        xy,
        y * Math.cos(inclinaison) - zy * Math.sin(inclinaison),
        y * Math.sin(inclinaison) + zy * Math.cos(inclinaison),
      ];
    };

    const dessiner = () => {
      contexte.clearRect(0, 0, taille, taille);
      const projetes = SOMMETS.map((sommet) => {
        const [x, y, z] = tourner(sommet, angle);
        const echelle = 2.6 / (2.6 + z / 2);
        return { x: centre + x * rayon * echelle, y: centre + y * rayon * echelle, z };
      });

      for (const [depart, arrivee] of ARETES) {
        const a = projetes[depart];
        const b = projetes[arrivee];
        // Les arêtes du fond s'estompent : c'est ce qui donne le volume.
        const profondeur = (a.z + b.z) / 2;
        const opacite = 0.22 + 0.6 * (1 - (profondeur + 2) / 4);
        contexte.strokeStyle = `rgba(63, 191, 174, ${Math.max(0.12, Math.min(0.92, opacite))})`;
        contexte.lineWidth = profondeur < 0 ? 1.6 : 1;
        contexte.beginPath();
        contexte.moveTo(a.x, a.y);
        contexte.lineTo(b.x, b.y);
        contexte.stroke();
      }

      for (const point of projetes) {
        if (point.z > 0.4) continue;
        contexte.fillStyle = "rgba(95, 214, 198, 0.95)";
        contexte.beginPath();
        contexte.arc(point.x, point.y, 1.9, 0, Math.PI * 2);
        contexte.fill();
      }
    };

    const animer = () => {
      angle += 0.0055;
      dessiner();
      animation = requestAnimationFrame(animer);
    };

    dessiner();
    if (!moinsDeMouvement.matches) animation = requestAnimationFrame(animer);

    const arreter = () => {
      cancelAnimationFrame(animation);
      animation = 0;
    };
    const reprendre = () => {
      if (!animation && !document.hidden && !moinsDeMouvement.matches) {
        animation = requestAnimationFrame(animer);
      }
    };
    const surVisibilite = () => (document.hidden ? arreter() : reprendre());
    document.addEventListener("visibilitychange", surVisibilite);

    return () => {
      arreter();
      document.removeEventListener("visibilitychange", surVisibilite);
    };
  }, [taille]);

  return (
    <canvas
      ref={canvas}
      aria-hidden
      style={{ width: taille, height: taille }}
      className="shrink-0"
    />
  );
}
