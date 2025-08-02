# HTPI Tenant Service

Multi-tenant management service for the HTPI healthcare system.

## Features

- Tenant CRUD operations
- Multi-tenant access control
- User-tenant mapping
- ClaimMD account management per tenant
- Feature toggles per tenant

## Architecture

This service manages:
- Tenant organizations (hospitals, clinics)
- User access to tenants
- Tenant-specific settings and features
- ClaimMD API account associations

## NATS Subscriptions

- `htpi.tenant.create` - Create new tenant
- `htpi.tenant.update` - Update tenant settings
- `htpi.tenant.list` - List all tenants (admin)
- `htpi.tenant.get` - Get single tenant
- `htpi.tenant.list.for.user` - List user's accessible tenants
- `htpi.tenant.verify.access` - Verify user-tenant access

## Response Channels

- `admin.tenant.response.*` - Admin portal responses
- `customer.tenants.response.*` - Customer portal tenant lists

## Environment Variables

```bash
NATS_URL=nats://localhost:4222
```

## Running Locally

```bash
pip install -r requirements.txt
python app.py
```

## Docker Deployment

```bash
docker build -t htpi-tenant-service .
docker run -e NATS_URL=nats://host.docker.internal:4222 htpi-tenant-service
```