# go-gateway multi-region HA failover verification

This runbook validates the `v1.11.1` HA rollout for `go-gateway` with:

- regional Cloud Run deployments in `us-south1` (primary) and `us-west1` (failover)
- global external HTTP load balancer fronting both regions
- multi-region backend routing on the global backend service

## Prerequisites

- `gcloud` authenticated to the target project
- `terraform` available if you need to re-apply infra state
- IAM access to Cloud Run, Compute Load Balancing, and logs

## 1) Verify both regional services are healthy

```bash
gcloud run services describe go-gateway --region us-south1 --format='value(status.url)'
gcloud run services describe go-gateway --region us-west1 --format='value(status.url)'
```

For each URL returned, verify:

```bash
curl -i "<REGIONAL_URL>/health"
```

Expected: HTTP `200`.

## 2) Verify global LB endpoint is reachable

Get the global IP from Terraform output:

```bash
cd terraform/go-gateway-ha
terraform output http_endpoint
```

Then verify health through the global entrypoint:

```bash
curl -i "http://<GLOBAL_IP>/health"
```

Expected: HTTP `200`.

## 3) Simulate primary-region impairment

Temporarily impair public access in the primary region:

```bash
# Optional controlled impairment: temporarily remove invoker permission in primary region
gcloud run services remove-iam-policy-binding go-gateway \
  --region us-south1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

Wait ~30-90 seconds, then repeat global probe:

```bash
curl -i "http://<GLOBAL_IP>/health"
```

Expected: Global endpoint remains `200` via failover backend.

## 4) Restore steady state

```bash
gcloud run services add-iam-policy-binding go-gateway \
  --region us-south1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

Re-check both regional endpoints and the global endpoint.

## 5) Evidence to capture

- Regional `/health` responses before/after impairment
- Global `/health` responses before/during/after impairment
- Cloud Logging snippets showing request continuity during failover window
- Timestamped command transcript in incident/change ticket
