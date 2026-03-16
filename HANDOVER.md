# Handover Tracker

Resources and accounts created during development that need to be transferred
or cleaned up when handing this project over to Pooja.

---

## Accounts to transfer / recreate

| Service | Account used | Action on handover |
|---|---|---|
| GitHub | mishra69 (Abhishek) | Transfer repo to Pooja's account |
| OpenRouter | Abhishek's account | Create new account under Pooja, update `OPENROUTER_API_KEY` in `.env` |
| GCP | Abhishek's account | Create new project under Pooja's Google account, re-run deploy script |
| Cloudflare | (domain owner) | Add Pooja as zone admin or transfer domain |

---

## Resources created

| Resource | Location | Notes |
|---|---|---|
| GCP VM | us-central1, project: TBD | e2-micro, free tier |
| GCP Static IP | us-central1 | Reserved, attach to VM |
| GCP Firewall rule | `jyotish-allow-http` | Allows port 80 inbound |
| Subdomain | `jyotish-agent.poojamishra.com` | A record → GCP VM IP |
| OpenRouter API key | OpenRouter dashboard | Revoke after Pooja creates her own |

---

## Config files on the VM

| File | Path | Contains |
|---|---|---|
| App env | `/etc/jyotish/.env` | `OPENROUTER_API_KEY` (only key needed — no GCP key required) |
| Systemd service | `/etc/systemd/system/jyotish.service` | App startup, runs as `www-data` |
| Caddyfile | `/etc/caddy/Caddyfile` | Reverse proxy :80 → localhost:8501 |
| App code | `/opt/jyotish/` | Git clone of this repo, owned by `www-data` |

## Fresh deployment steps

All config (OpenRouter key + GCP settings) lives in `.env`. Fill in `.env` first.

```bash
# 1. Fill in .env with GCP_PROJECT_ID, GCP_ZONE, GCP_VM_NAME, GCLOUD path, etc.
#    (copy the GCP section from .env.example or HANDOVER.md if starting fresh)

# 2. Provision VM
bash deploy/setup_gcp.local.sh

# 3. Copy .env to VM  (only OPENROUTER_API_KEY is used on the server)
source .env
$GCLOUD compute scp .env jyotish-agent:/tmp/.env --zone=$GCP_ZONE

# 4. Copy and run server setup on VM
$GCLOUD compute scp deploy/setup_server.sh jyotish-agent:/tmp/ --zone=$GCP_ZONE
$GCLOUD compute ssh jyotish-agent --zone=$GCP_ZONE -- "bash /tmp/setup_server.sh"
```

## Known issues and fixes already baked in

**File permissions after `git pull`:**
The service runs as `www-data` but `git pull` runs as root, leaving new files
owned by root. This breaks DB writes. Fixed in `deploy/update.sh` by running
`chown -R www-data:www-data /opt/jyotish` after every pull.
`setup_server.sh` also runs this chown at the end of initial setup.

---

## Backlog items before full handover

- [ ] Basic auth (username/password on the app)
- [ ] Pooja reviews yoga list — confirm which yogas she uses most
- [ ] Topic templates reviewed by Pooja
- [ ] PDF export of final brief
- [ ] Client history / past consultations

---

## To clean up from Abhishek's accounts after handover

- [ ] Delete GCP project (or transfer)
- [ ] Revoke OpenRouter API key
- [ ] Remove GitHub repo from personal account (after transfer)
- [ ] Delete Cloudflare DNS A record for `jyotish-agent.poojamishra.com` (if domain stays with Abhishek)
