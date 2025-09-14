module.exports = {
  webpack: {
    configure: (config) => {
      if (config.optimization) {
        config.optimization.minimize = false;
        config.optimization.minimizer = [];
      }
      return config;
    },
  },
};
