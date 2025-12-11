# Production Configuration Guide

## Overview

This document outlines the production URLs and configuration for AstroRemedis.

## Production URLs

### Backend (AWS)
- **Production URL**: `https://api.astroremedis.com`
- **Deployment**: AWS (Elastic Beanstalk / App Runner / ECS)
- **Health Check**: `https://api.astroremedis.com/api/health`

### Frontend (Netlify)
- **Production URL**: `https://astroremedis.netlify.app` (or your custom domain)
- **Deployment**: Netlify
- **Build Command**: `cd frontend && npm install && npm run build`
- **Publish Directory**: `frontend/build`

## Configuration

### Backend Environment Variables

Set these in your AWS environment (Elastic Beanstalk, App Runner, or ECS):

```bash
# Required API Keys
OPENAI_API_KEY=your_openai_key
OPENAI_ASSISTANT_ID=your_assistant_id
OPENAI_ASSISTANT_ID_HORARY=your_horary_assistant_id
PROKERALA_CLIENT_ID=your_prokerala_id
PROKERALA_CLIENT_SECRET=your_prokerala_secret

# CORS Configuration - Set to your Netlify frontend URL
ALLOWED_ORIGINS=https://astroremedis.netlify.app

# Production Settings
FLASK_ENV=production
DEBUG=False
```

### Frontend Environment Variables

For Netlify deployment, set these in Netlify Dashboard → Site Settings → Environment Variables:

```bash
# Backend API URL (AWS Production)
REACT_APP_API_URL=https://api.astroremedis.com

# Build Settings
NODE_ENV=production
GENERATE_SOURCEMAP=false
```

Or create `frontend/.env.production` file (already configured):

```bash
REACT_APP_API_URL=https://api.astroremedis.com
NODE_ENV=production
GENERATE_SOURCEMAP=false
```

## CORS Configuration

The backend is configured to accept requests from the Netlify frontend. Make sure:

1. **Backend CORS** (`backend/app.py`):
   - Set `ALLOWED_ORIGINS` environment variable to your Netlify URL
   - Example: `ALLOWED_ORIGINS=https://astroremedis.netlify.app`

2. **Frontend API Calls** (`frontend/src/services/api.js`):
   - Already configured to use `https://api.astroremedis.com` in production
   - Falls back to localhost only in development

## Verification Steps

### 1. Verify Backend
```bash
curl https://api.astroremedis.com/api/health
```

Expected response:
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

### 2. Verify Frontend
1. Open your Netlify site: `https://astroremedis.netlify.app`
2. Open browser DevTools → Network tab
3. Try to generate a Kundli
4. Verify API calls go to `https://api.astroremedis.com`

### 3. Verify CORS
1. Open Netlify site in browser
2. Open DevTools → Console
3. Check for CORS errors
4. If errors appear, verify `ALLOWED_ORIGINS` in backend includes your Netlify URL

## Deployment Checklist

### Backend (AWS)
- [ ] Environment variables set in AWS
- [ ] `ALLOWED_ORIGINS` includes Netlify URL
- [ ] Health check endpoint accessible
- [ ] SSL certificate configured (HTTPS)
- [ ] Logs accessible in CloudWatch

### Frontend (Netlify)
- [ ] Build command: `cd frontend && npm install && npm run build`
- [ ] Publish directory: `frontend/build`
- [ ] Environment variables set in Netlify
- [ ] `REACT_APP_API_URL` points to AWS backend
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificate active

## Troubleshooting

### CORS Errors
**Problem**: Browser shows CORS errors when calling API

**Solution**:
1. Check `ALLOWED_ORIGINS` in backend includes your Netlify URL
2. Verify URL matches exactly (including https:// and no trailing slash)
3. Restart backend after changing CORS settings

### API Connection Failed
**Problem**: Frontend can't connect to backend

**Solution**:
1. Verify backend is running: `curl https://api.astroremedis.com/api/health`
2. Check `REACT_APP_API_URL` in Netlify environment variables
3. Verify Netlify build logs for any errors
4. Check browser console for specific error messages

### Build Failures
**Problem**: Netlify build fails

**Solution**:
1. Check Netlify build logs
2. Verify Node version (should be 18+)
3. Ensure `package.json` has all dependencies
4. Check for environment variable issues

## URL Updates

If you need to change production URLs:

1. **Backend URL Change**:
   - Update `frontend/src/services/api.js`: `API_BASE_URL_DEPLOYED`
   - Update `frontend/.env.production`: `REACT_APP_API_URL`
   - Update Netlify environment variable: `REACT_APP_API_URL`
   - Rebuild and redeploy frontend

2. **Frontend URL Change**:
   - Update backend `ALLOWED_ORIGINS` environment variable
   - Restart backend
   - Update any hardcoded references

## Security Notes

- ✅ Backend uses HTTPS (required for production)
- ✅ Frontend uses HTTPS (Netlify default)
- ✅ CORS restricted to production frontend URL
- ✅ Security headers enabled
- ✅ Input sanitization active
- ✅ Environment variables for sensitive data

---

**Last Updated**: 2024

