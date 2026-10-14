module.exports = {
  apps: [
    {
      name: "bakary",
      cwd: __dirname,
      script: ".venv/bin/gunicorn",
      args: "--config gunicorn.conf.py wsgi:app",
      interpreter: "none",
      exec_mode: "fork",
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 3000,
      time: true,
      env: {
        FLASK_CONFIG: "production",
        PORT: "4043",
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
