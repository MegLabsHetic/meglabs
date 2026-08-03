import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Le bind mount Docker casse la detection de changement native sous Windows :
  // le polling est le seul moyen fiable d'avoir le hot reload en conteneur.
  webpack: (config) => {
    config.watchOptions = { poll: 1000, aggregateTimeout: 300 };
    return config;
  },
};

export default nextConfig;
