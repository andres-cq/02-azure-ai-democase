# Unified Bootstrap

Shared infrastructure for all workshops in the azure-casestudies repository.

## What It Creates

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-ccworkshop-shared` | Shared infrastructure |
| Storage Account | `ccccworkshoptfstate` | Terraform state (naming: `cc${project_name}tfstate`) |
| Managed Identity | `id-ccworkshop-github` | GitHub Actions OIDC |

## Quick Start

```bash
cd bootstrap

# Configure subscription
# Edit terraform.tfvars: subscription_id = "your-subscription-id"

az login
terraform init
terraform plan
terraform apply
```

## GitHub Configuration

After bootstrap, configure GitHub secrets using the output:

```bash
terraform output github_actions_configuration
```

### Repository Secrets

| Secret | Value |
|--------|-------|
| `AZURE_TENANT_ID` | From output |
| `AZURE_SUBSCRIPTION_ID` | From output |

### Environment Secrets

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | Client ID for dev |

## Cleanup

### Destroy Everything (Recommended)

Use the GitHub Actions workflow to destroy all workshops and bootstrap in the correct order:

1. Go to **Actions** → **Terraform Destroy All**
2. Click **Run workflow**
3. Type `DESTROY-ALL` to confirm
4. Approve each environment gate (dev → staging → prod)

This workflow destroys in order: dev → staging → prod → bootstrap

### Manual Bootstrap Destroy

**Warning:** Only use after all workshops are destroyed. Destroying bootstrap removes state storage.

```bash
terraform destroy
```
