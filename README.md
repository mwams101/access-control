# Building Access Control System

Django monolith implementing the requirements & design document: a building access
control system for **Admin**, **Security**, and **Visitor** roles, with pre-registered
visits, QR access passes, walk-in registration, blacklist checks, occupancy tracking,
an append-only audit log, and a REST API.

## Quick start (development)

```bash
# 1. Create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements/dev.txt

# 3. Create the database and an admin account
python manage.py migrate
python manage.py createsuperuser   # then set role=ADMIN in /django-admin/ or shell

# 4. Run
python manage.py runserver
```

Dev settings use SQLite and the console email backend — approval/denial/host-arrival
emails print to the runserver terminal so you can see FR-19/20/21 working without SMTP.

### Create the three roles quickly

```bash
python manage.py shell -c "
from apps.accounts.models import User
User.objects.create_superuser('admin', password='admin12345', role='ADMIN', email='admin@example.com')
User.objects.create_user('guard', password='guard12345', role='SECURITY', first_name='Gate', last_name='Officer')
"
```

Visitors self-register at `/accounts/signup/`.

## Walking through the main flows

1. **Visitor** signs up, then submits a request at `/visits/new/` (host, purpose, time window; optional entity/group with party members and vehicle reg).
2. **Security/Admin** reviews it at `/visits/gate/pending/` → approve (with optional zones, single-entry toggle) or deny with a reason.
3. On approval a **Pass** is created with a signed token; the visitor's detail page shows the **QR code** (requires the `qrcode` package; falls back to the raw token text).
4. At the gate, Security opens `/visits/gate/verify/`, scans the QR (a USB scanner types the token) or enters the `VR-XXXXXX` reference. The system checks: signature, revocation, time window, single-entry reuse, and **blacklist** — denied attempts are recorded as `CheckInEvent(kind=DENIED)` and blacklist hits email all admins.
5. Check-in marks the visit `CHECKED_IN`, notifies the host, and the visitor appears on the **Currently inside** list (`/visits/gate/occupancy/`), with overdue flagging.
6. **Walk-ins**: `/visits/gate/walkin/` does blacklist check → auto-approve → pass → check-in in one screen.
7. **Admin** has a dashboard (`/reports/dashboard/`), filterable visits report with CSV export (`/reports/visits/`), zone and blacklist management, and the append-only audit log (`/reports/audit/`).

## REST API (`/api/v1/`)

Session-authenticated; DRF browsable API works out of the box.

| Endpoint | Role | Purpose |
|---|---|---|
| `GET/POST /visits/` | Visitor (own) / Staff (all, `?status=`) | List & create requests |
| `POST /visits/{id}/approve/` | Security/Admin | Approve → returns pass |
| `POST /visits/{id}/deny/` | Security/Admin | Deny with `{"reason": ...}` |
| `POST /passes/verify/` | Security/Admin | `{"token", "gate"}` → allow/deny (v2 hardware contract) |
| `POST /passes/{id}/checkin/` `/checkout/` | Security/Admin | Record movement |
| `GET /occupancy/` | Security/Admin | Currently-inside list |

## Housekeeping

Mark stale approved/pending visits as expired (run via cron or Celery beat):

```bash
python manage.py expire_visits
```

## Tests

```bash
python manage.py test apps.visits
```

Covers: pass issuance, tampered tokens, expired windows, single-entry reuse,
blacklist denial with DENIED event + alert, the full check-in/out lifecycle,
and blocked walk-ins.

## Production

- `DJANGO_SETTINGS_MODULE=config.settings.prod` — PostgreSQL, Redis-backed cache/sessions, SMTP email, full HTTPS hardening (HSTS, secure cookies, SSL redirect). Configure via the env vars in `.env.example`.
- `pip install -r requirements/prod.txt`, then `python manage.py collectstatic` and run with `gunicorn config.wsgi`.
- Replace the Tailwind CDN `<script>` in `templates/base.html` with a compiled stylesheet for production.

## Project structure

```
access_control/
├── config/                  # settings (base/dev/prod), urls, api_urls, wsgi/asgi
├── apps/
│   ├── accounts/            # custom User + roles, auth views, RBAC mixins, DRF permissions
│   ├── visits/              # VisitRequest, Pass, CheckInEvent, services (all workflows), API
│   ├── access/              # Zone, Blacklist + admin management screens
│   ├── notifications/       # email notifications (Celery-ready plain functions)
│   └── reports/             # AuditLog (append-only), dashboard, CSV exports
├── templates/               # Tailwind-based UI for all three roles
└── requirements/            # base / dev / prod
```

## Design notes

- **All state changes flow through `apps/visits/services.py`** so audit logging and notifications are applied consistently, and the web views and the API share identical behavior.
- **QR passes contain no PII** — only a signed (`django.core.signing`) pass reference; tampering fails verification.
- **Audit log is append-only**: no update/delete views exist, and the Django admin registration forbids add/change/delete.
- **ID numbers are masked** (`****1234`) in list views; full values appear only on staff detail/verify screens.
- **v2 integration points**: `POST /api/v1/passes/verify/` is the contract for turnstile/RFID hardware; `notifications/services.py` is the seam for SMS (e.g. Africa's Talking) and Celery.
