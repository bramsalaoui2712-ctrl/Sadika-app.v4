module.exports = {
  webpack: {
    configure: (config) => {
      if (config.optimization) {
        config.optimization.minimize = false;     // coupe la minification
        config.optimization.minimizer = [];       // enlève Terser/CSS Minimizer
      }
      return config;
    },
  },
};
