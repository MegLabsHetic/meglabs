import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Regroupe l'application et ses seules dependances utiles dans `.next/standalone`.
  // Sans cela, l'image de production embarquerait tout `node_modules` : plusieurs
  // centaines de megaoctets qui ne servent qu'a la compilation.
  output: "standalone",
};

export default nextConfig;
