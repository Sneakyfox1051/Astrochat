# Quick Start: AWS Deployment

## Prerequisites

1. AWS Account
2. AWS CLI configured (`aws configure`)
3. Environment variables set (see `.env.example`)

## Quick Deploy Options

### Option 1: Elastic Beanstalk (Easiest)

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 astroremedis-backend

# Create and deploy
eb create astroremedis-prod
eb deploy
```

### Option 2: App Runner (Containerized)

```bash
# On Linux/Mac
./deploy.sh apprunner

# On Windows
.\deploy.ps1 -DeploymentType apprunner
```

Then create service in AWS Console → App Runner.

### Option 3: ECS (Full Control)

```bash
# On Linux/Mac
./deploy.sh ecs

# On Windows
.\deploy.ps1 -DeploymentType ecs
```

Then create cluster, task definition, and service in AWS Console → ECS.

## Environment Variables

Set these in your AWS environment:

**Required:**
- `OPENAI_API_KEY`
- `OPENAI_ASSISTANT_ID`
- `OPENAI_ASSISTANT_ID_HORARY`
- `PROKERALA_CLIENT_ID`
- `PROKERALA_CLIENT_SECRET`

**Recommended:**
- `ALLOWED_ORIGINS` - Your frontend domain(s)
- `FLASK_ENV=production`
- `DEBUG=False`

## Health Check

Test your deployment:
```bash
curl https://your-backend-url/api/health
```

## Full Documentation

See `DEPLOYMENT.md` for detailed instructions.

