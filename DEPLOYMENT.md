# AWS Deployment Guide for AstroRemedis

This guide covers deploying the AstroRemedis backend to AWS using various services.

## Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI installed and configured
3. Docker installed (for containerized deployments)
4. Environment variables configured (see `.env.example`)

## Deployment Options

### Option 1: AWS Elastic Beanstalk (Recommended for Simplicity)

Elastic Beanstalk automatically handles capacity provisioning, load balancing, auto-scaling, and application health monitoring.

#### Steps:

1. **Install EB CLI** (if not already installed):
   ```bash
   pip install awsebcli
   ```

2. **Initialize Elastic Beanstalk**:
   ```bash
   cd /path/to/astro-main
   eb init -p python-3.11 astroremedis-backend --region us-east-1
   ```

3. **Create Environment**:
   ```bash
   eb create astroremedis-prod --instance-type t3.small --min-size 1 --max-size 3
   ```

4. **Set Environment Variables**:
   ```bash
   eb setenv OPENAI_API_KEY=your_key \
            OPENAI_ASSISTANT_ID=your_id \
            PROKERALA_CLIENT_ID=your_id \
            PROKERALA_CLIENT_SECRET=your_secret \
            ALLOWED_ORIGINS=https://yourdomain.com \
            FLASK_ENV=production \
            DEBUG=False
   ```

5. **Deploy**:
   ```bash
   eb deploy
   ```

6. **Check Status**:
   ```bash
   eb status
   eb health
   ```

#### Configuration Files:
- `.ebextensions/01_python.config` - Python/WSGI configuration
- `.ebextensions/02_nginx.config` - Nginx proxy settings
- `.ebextensions/03_security.config` - Security headers

---

### Option 2: AWS App Runner (Containerized)

App Runner is ideal for containerized applications with automatic scaling.

#### Steps:

1. **Build and Push Docker Image to ECR**:
   ```bash
   # Create ECR repository
   aws ecr create-repository --repository-name astroremedis-backend --region us-east-1
   
   # Get login token
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   
   # Build image
   docker build -t astroremedis-backend .
   
   # Tag and push
   docker tag astroremedis-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/astroremedis-backend:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/astroremedis-backend:latest
   ```

2. **Create App Runner Service**:
   - Go to AWS Console → App Runner
   - Create service from container image
   - Select your ECR image
   - Configure:
     - Port: 8000
     - Health check: `/api/health`
     - Environment variables (from `.env.example`)

3. **Deploy Updates**:
   ```bash
   # Rebuild and push
   docker build -t astroremedis-backend .
   docker tag astroremedis-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/astroremedis-backend:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/astroremedis-backend:latest
   ```
   App Runner will automatically detect and deploy the new image.

---

### Option 3: AWS ECS (Elastic Container Service)

For more control over infrastructure and scaling.

#### Steps:

1. **Create ECR Repository** (same as App Runner)

2. **Create Task Definition**:
   ```json
   {
     "family": "astroremedis-backend",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [{
       "name": "astroremedis-backend",
       "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/astroremedis-backend:latest",
       "portMappings": [{
         "containerPort": 8000,
         "protocol": "tcp"
       }],
       "environment": [
         {"name": "OPENAI_API_KEY", "value": "your_key"},
         {"name": "FLASK_ENV", "value": "production"}
       ],
       "logConfiguration": {
         "logDriver": "awslogs",
         "options": {
           "awslogs-group": "/ecs/astroremedis-backend",
           "awslogs-region": "us-east-1",
           "awslogs-stream-prefix": "ecs"
         }
       },
       "healthCheck": {
         "command": ["CMD-SHELL", "python -c \"import requests; requests.get('http://localhost:8000/api/health')\""],
         "interval": 30,
         "timeout": 5,
         "retries": 3
       }
     }]
   }
   ```

3. **Create ECS Service** with Application Load Balancer

4. **Configure Auto Scaling** based on CPU/Memory metrics

---

## Environment Variables

Set these in your AWS environment (Elastic Beanstalk, App Runner, or ECS):

### Required:
- `OPENAI_API_KEY` - Your OpenAI API key
- `OPENAI_ASSISTANT_ID` - Default Assistant ID
- `OPENAI_ASSISTANT_ID_HORARY` - Horary Assistant ID
- `PROKERALA_CLIENT_ID` - ProKerala API client ID
- `PROKERALA_CLIENT_SECRET` - ProKerala API secret

### Production (Required):
- `ALLOWED_ORIGINS` - **Set to your Netlify frontend URL** (e.g., `https://astroremedis.netlify.app`)
  - **Important**: Change from default `*` to restrict CORS to production frontend only
- `FLASK_ENV` - Set to `production`
- `DEBUG` - Set to `False`

### Optional:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc. - For Google Sheets integration

**Production URLs:**
- Backend: `https://api.astroremedis.com`
- Frontend: `https://astroremedis.netlify.app` (or your custom domain)

---

## Health Checks

The application provides a health check endpoint:

```
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "features": {
    "assistant_api_enabled": true,
    "openai_enabled": true,
    "prokerala_enabled": true
  }
}
```

Configure your load balancer/health check to use this endpoint.

---

## Monitoring and Logging

### CloudWatch Logs

Logs are automatically sent to CloudWatch. View them in:
- Elastic Beanstalk: Environment → Logs
- App Runner: Service → Logs
- ECS: CloudWatch Logs → `/ecs/astroremedis-backend`

### Application Logs

The application uses Python's `logging` module. Log levels can be controlled via `LOG_LEVEL` environment variable.

---

## Security Best Practices

1. **Never commit `.env` files** - Use AWS Systems Manager Parameter Store or Secrets Manager
2. **Restrict CORS origins** - Set `ALLOWED_ORIGINS` to your frontend domain(s)
3. **Use HTTPS** - Configure SSL/TLS certificates in your load balancer
4. **Enable WAF** - Consider AWS WAF for additional protection
5. **Rotate credentials** - Regularly rotate API keys and secrets
6. **Monitor access** - Enable CloudTrail for API access logging

---

## Scaling Configuration

### Elastic Beanstalk:
- Configure auto-scaling in Environment → Configuration → Capacity
- Recommended: Min 1, Max 3 instances for cost optimization

### App Runner:
- Auto-scales based on traffic (configure min/max concurrency)

### ECS:
- Configure auto-scaling policies based on CPU/Memory metrics
- Recommended: Target 70% CPU utilization

---

## Troubleshooting

### Application won't start:
1. Check CloudWatch logs for errors
2. Verify all environment variables are set
3. Check health endpoint: `curl https://your-domain/api/health`

### CORS errors:
1. Verify `ALLOWED_ORIGINS` includes your frontend domain
2. Check browser console for specific CORS error

### API timeouts:
1. Increase timeout in Gunicorn configuration (Procfile)
2. Check ProKerala/OpenAI API status
3. Review CloudWatch metrics for bottlenecks

---

## Frontend Deployment (Netlify)

The frontend is deployed on Netlify and automatically uses the production AWS backend.

### Production URLs:
- **Frontend**: `https://astroremedis.netlify.app` (or your custom domain)
- **Backend**: `https://api.astroremedis.com` (AWS)

### Netlify Configuration:

1. **Automatic Deployment** (via `netlify.toml`):
   - Build command: `cd frontend && npm install && npm run build`
   - Publish directory: `frontend/build`
   - Node version: 18

2. **Environment Variables** (Set in Netlify Dashboard):
   ```bash
   REACT_APP_API_URL=https://api.astroremedis.com
   NODE_ENV=production
   GENERATE_SOURCEMAP=false
   ```

3. **API Configuration**:
   - Frontend is already configured to use `https://api.astroremedis.com` in production
   - No code changes needed - the API URL is set in `frontend/src/services/api.js`

### Manual Build (if needed):
```bash
cd frontend
npm install
npm run build
# Deploy frontend/build/ to Netlify
```

### CORS Configuration:
Make sure your backend `ALLOWED_ORIGINS` includes your Netlify URL:
```bash
ALLOWED_ORIGINS=https://astroremedis.netlify.app
```

---

## Cost Optimization

- Use t3.small or t3.medium instances (sufficient for most workloads)
- Enable auto-scaling to scale down during low traffic
- Use CloudFront for static assets
- Consider Reserved Instances for predictable workloads

---

## Support

For issues or questions:
1. Check CloudWatch logs
2. Review application logs
3. Test health endpoint
4. Verify environment variables

---

**Last Updated**: 2024

