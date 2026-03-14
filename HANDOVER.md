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
| App env | `/etc/jyotish/.env` | `OPENROUTER_API_KEY` |
| Systemd service | `/etc/systemd/system/jyotish.service` | App startup config |
| Caddyfile | `/etc/caddy/Caddyfile` | Reverse proxy config |
| App code | `/opt/jyotish/` | Git clone of this repo |

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
