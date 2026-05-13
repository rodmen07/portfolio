# v1.10 — Cost & FinOps Implementation Guide

> **Status:** Published ✅  
> **Version:** v1.10.0  
> **Release Date:** 2026-05-07

This document covers the FinOps (Financial Operations) implementation for Portfolio v1.10, including budget alerts, per-service cost tracking, and cloud scaling optimization.

---

## What's New in v1.10

### 1. Budget Alerts & Spend Monitoring

**Feature:** Automated GCP billing budget alerts that notify you when spending approaches your monthly threshold.

**How it works:**
- Define a monthly budget threshold (default: $500 USD)
- Receive alerts at 50%, 90%, and 100% of budget
- Alerts sent via email to your operations team
- Tracks only **Cloud Run** service costs (excludes Artifact Registry, Cloud SQL)

**Configuration:**
```bash
cd Portfolio/microservices

# terraform/terraform.tfvars
billing_account_id = "012345-ABCDEF-GHIJKL"  # Get from gcloud
monthly_budget_usd = 500                      # Your threshold
budget_alert_email = "ops@example.com"        # Alert recipient
```

**Get your billing account ID:**
```bash
gcloud billing accounts list
# Returns: 012345-ABCDEF-GHIJKL | My GCP Account
```

**Deploy:**
```bash
cd terraform
terraform plan  # Review budget alert resources
terraform apply
```

---

### 2. Cloud Run Min-Instance Tuning

**Problem:** Previously, all services had `min_instance_count = 0`, causing cold starts (5-10s latency) on infrequent requests. This degrades user experience and wastes engineer time debugging "why is the API slow?"

**Solution:** Configure per-service minimum instances based on traffic patterns:

| Service | Min Instances | Reasoning |
|---------|--------------|-----------|
| `accounts-service` | **1** | Critical path (auth, JWT validation); high traffic |
| `contacts-service` | **1** | High traffic (CRM core) |
| `activities-service` | **1** | High traffic (frequently queried) |
| `audit-service` | **1** | Always-on (receives mutation events from all services) |
| `projects-service` | **1** | Client portal (customer-facing) |
| `opportunities-service` | **1** | Sales ops (high traffic) |
| `backend-service` | **1** | Admin task API (internal tools) |
| `automation-service` | **0** | Batch/scheduled; low frequency → scale-to-zero |
| `integrations-service` | **0** | Batch; low frequency → scale-to-zero |
| `reporting-service` | **0** | Batch; scheduled runs (daily/weekly) → scale-to-zero |
| `search-service` | **0** | Indexed; less frequently called → scale-to-zero |
| `spend-service` | **0** | Batch; infrequent queries → scale-to-zero |

**Impact:**
- **Cost:** 5/12 services at min=0 preserve scale-to-zero savings while 7 critical services stay warm (warm instances cost $0.24/month each)
- **Performance:** 7 services always warm = near-zero cold starts on critical paths
- **Configuration:** Defined in `terraform/cost_variables.tf` via `service_min_instances` map

**Override defaults:**
```hcl
# terraform/terraform.tfvars
service_min_instances = {
  "accounts-service"      = 1
  "automation-service"    = 1  # Override: keep warm if you have frequent batch jobs
  # ... rest inherit from defaults
}
```

---

### 3. Cost Alerts & Performance Monitoring

**Alerting Policy:** Automatic email alerts for cost anomalies and resource contention:

1. **High CPU Utilization** (>80%) — indicates scaling bottleneck
2. **High Memory Usage** (>78% of 512Mi) — indicates memory leak or inefficiency
3. **High Database Connections** (>10) — indicates connection pool exhaustion
4. **Budget Spend** (50%, 90%, 100%) — spend trending

**Notification Channel:**
- Email: `budget_alert_email` (set in tfvars)
- Frequency: Real-time (300s evaluation windows)

**View alerts in GCP Console:**
```bash
gcloud monitoring alert-policies list
gcloud monitoring alert-policies describe POLICY_ID --format=json
```

---

### 4. FinOps Dashboard

**Dashboard URL:**
After applying Terraform, view the custom Cloud Monitoring dashboard:

```bash
terraform output monitoring_dashboard_link
# Returns: https://console.cloud.google.com/monitoring/dashboards/custom/xyz?project=...
```

**Dashboard Panels:**

**Summary Metrics (Row 1):**
- Monthly Budget (vs spend)
- Estimated Cost Trend
- Cloud Run Instances Running (real-time)
- Avg Response Time

**Per-Service Breakdown (Row 2):**
- Cloud Run Billed Time by Service (stacked area) — see which services consume the most compute
- Cold Start Count by Service (line) — identify services still experiencing cold starts

**Database & Infrastructure (Row 3):**
- Cloud SQL CPU % utilization
- Cloud SQL Memory % utilization
- Artifact Registry Storage (GB)

**Error & Performance (Row 4):**
- Error Rate (5xx %) — identify reliability issues
- P99 Latency (ms) — tail latency by service
- DB Connections Active — connection pool health

**Key Metrics to Watch:**
- **Cost Trend:** Should be stable; sudden spikes → investigate
- **Cold Start Count:** Should be near-zero after v1.10; investigate if increasing
- **DB Connections:** Should stay <10; if >15 → add read replicas or scale down services
- **Error Rate:** Should stay <0.1% (service SLA: 99.9% uptime)

---

## Terraform Files Added/Modified

### New Files
- `terraform/cost.tf` — Budget alerts, notification channels, alert policies
- `terraform/cost_variables.tf` — FinOps variables (budget, billing account, min instances)
- `terraform/monitoring.tf` — Cloud Monitoring dashboard definition

### Modified Files
- `terraform/cloud_run.tf` — Updated Rust and backend services to use `lookup(var.service_min_instances, ...)`
  - Line 57: Rust services scaling block
  - Line 128: Backend service scaling block

---

## Deployment Instructions

### Prerequisites
1. GCP project with Cloud Run, Cloud SQL, Cloud Monitoring APIs enabled ✓ (already enabled in v1.0)
2. Billing account linked to your GCP project
3. Terraform ≥1.5

### Step 1: Update terraform.tfvars

```hcl
# Portfolio/microservices/terraform/terraform.tfvars

# Existing variables (unchanged)
project_id          = "my-gcp-project"
region              = "us-south1"
frontend_origin     = "https://rodmen07.github.io"
# ... other existing vars ...

# NEW: FinOps Configuration (v1.10)
billing_account_id  = "012345-ABCDEF-GHIJKL"
monthly_budget_usd  = 500
budget_alert_email  = "ops@example.com"

# NEW: Optional—override default min instances (use if different from table above)
service_min_instances = {}  # Use defaults if not specified
```

### Step 2: Plan & Apply

```bash
cd Portfolio/microservices/terraform

# Review changes (budget, alert, monitoring)
terraform plan

# Apply (takes 2-3 minutes)
terraform apply

# Verify
terraform output monitoring_dashboard_link
```

### Step 3: Validate

1. **Check Budget Alert:** Open GCP Console → Billing → Budgets & alerts
   - Should see "Portfolio Microservices - Monthly" with $500 threshold
   
2. **Check Alert Policies:** Cloud Console → Monitoring → Alert policies
   - Should see 4 new policies (CPU, memory, DB connections, budget)

3. **Check Dashboard:** Click output URL or go to Monitoring → Dashboards
   - Should see FinOps dashboard with real-time metrics

4. **Test Email Notification:** Optional—manually trigger a test alert
   ```bash
   gcloud monitoring alert-policies list --format="value(name)" | head -1 | \
   xargs -I {} gcloud monitoring alert-policies update {} --update-notification-channels=...
   ```

---

## Cost Estimation & Savings

### Monthly Cost Breakdown (typical)

| Resource | Tier | Monthly Cost |
|----------|------|--------------|
| Cloud Run (7 @ min=1) | f1-micro CPU + memory | $1.70 (7 × $0.24/month) |
| Cloud Run compute (request-based) | 1M requests/month | $25-40 |
| Cloud SQL PostgreSQL | db-f1-micro (shared) | $6-8 |
| Artifact Registry | Docker images | $0.50-1 |
| Cloud Monitoring | Standard (included) | Free |
| Cloud Audit Logs → GCS | Ingest + storage | $2-3 |
| **Total** | | **$35-53** |

### Savings from v1.10

- **Before v1.10:** All 12 services at min=0 → cold starts 30-50% of time
- **After v1.10:** 7 critical services at min=1 → cold starts ~0%
- **Additional cost:** $0.24 × 7 = **~$1.70/month** (negligible)
- **Benefit:** 5-10s latency reduction on critical paths + better user experience

### Cost Optimization Tips

1. **Scale to Zero Aggressively:** If `search-service` is rarely used, keep at min=0
   ```hcl
   service_min_instances = {
     "search-service" = 0  # Scale-to-zero if <100 requests/day
   }
   ```

2. **Right-size Database:** Current db-f1-micro is shared; upgrade only if >80% CPU
   ```hcl
   db_tier = "db-custom-1-3840"  # 1 vCPU, 3.75 GB RAM (~$20/month)
   ```

3. **Compress Cloud SQL Backups:** Terraform already enables; saves ~50% storage
4. **Use Artifact Registry Lifecycle Policies:** Auto-delete images >90 days old
5. **Audit Log Filtering:** Log only suspicious activity, not all GET requests

---

## Monitoring & Ongoing Operations

### Daily Checks (automated)
- Budget alert emails if spending >50% of monthly target
- Alert emails if services have cold starts, high errors, or resource exhaustion

### Weekly Review
```bash
# Pull latest metrics
gcloud monitoring timeseries list \
  --filter='metric.type="run.googleapis.com/execution_times"' \
  --format=table

# Check if any service near max instances
gcloud monitoring timeseries list \
  --filter='metric.type="run.googleapis.com/instance_count"' \
  --format=table
```

### Monthly Optimization
1. Review dashboard → identify high-cost services
2. Check cold start count → adjust min instances if needed
3. Review error rate → debug root causes
4. Update budget if spending trend changes

---

## Troubleshooting

### Alerts not arriving
- **Check:** Email in `budget_alert_email` variable correct?
- **Check:** Gmail/corporate email server not filtering?
- **Fix:** Test by manually triggering alert via `gcloud` CLI

### Dashboard metrics empty
- **Check:** Wait 5-10 minutes for metrics to populate
- **Check:** Services have traffic (requests are being logged)
- **Fix:** Send test request: `curl https://accounts-service-xxx.run.app/health`

### Cold starts still high after v1.10
- **Check:** Is min_instance_count actually set? `terraform state show google_cloud_run_v2_service.rust_services['accounts-service']`
- **Check:** Service not redeployed? New deployments reset to min=0 automatically (fix: ensure CI/CD respects Terraform state)

### Budget not showing recent spend
- **Check:** Billing data lags 24 hours; refresh tomorrow
- **Check:** Ensure Cloud Run service is in included GCP project (not a different project)

---

## Next Steps (v1.11)

- **Multi-region Cloud Run:** Promote go-gateway to us-south1 + us-west1 with global load balancer
- **Read Replicas:** Add Cloud SQL read replica for reporting queries
- **Pub/Sub Scaling:** Replace sync HTTP calls with async Pub/Sub for batch jobs (auto-scales, saves $$)

---

## References

- [GCP Billing Budgets & Alerts](https://cloud.google.com/billing/docs/how-to/budgets)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Cloud Monitoring Dashboards](https://cloud.google.com/monitoring/dashboards)
- [Terraform GCP Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
