# AI BatchPic Deployment

This directory contains deployment helpers for the web version.

## Server deployment

```bash
export REPO_URL=https://github.com/resign13/img.git
export APP_DIR=/opt/ai-batchpic
export DOMAIN_NAME=your-domain.example.com
bash deploy/server_deploy.sh
```

Runtime secrets should be placed in `/opt/ai-batchpic/.env` on the server, for example:

```env
MANJU_GEMINI_IMAGE_KEY=...
HANCAT_IMAGE_KEY=...
MINGYU_NANO_BANANA_KEY=...
CATKING_ROUTE3_KEY=...
```

## GitHub Actions auto deploy

Add these repository secrets:

- `SERVER_HOST`
- `SERVER_USER`
- `SERVER_PASSWORD`
- `SERVER_PORT` (optional, defaults to 22)
- `APP_DIR` (optional, defaults to `/opt/ai-batchpic`)
- `REPO_URL` (optional, defaults to `https://github.com/resign13/img.git`)
- `DOMAIN_NAME` (optional, used for nginx server_name)

Each push to `main` runs `.github/workflows/deploy.yml`.
