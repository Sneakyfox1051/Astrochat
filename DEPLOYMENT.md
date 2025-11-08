# Deployment Guide - AstroRemedis

This guide provides instructions for deploying the AstroRemedis application to GitHub and production platforms.

## 🌐 Deployment URLs

### Production URLs
- **Backend API**: `https://astroremedis.onrender.com`
- **Frontend**: (Add your frontend deployment URL here - e.g., Vercel, Netlify, GitHub Pages)

### Local Development URLs (Commented Out)
- **Backend API**: `http://127.0.0.1:5000` (commented in `frontend/src/services/api.js`)
- **Frontend**: `http://localhost:3000`

## 📋 Pre-Deployment Checklist

- [x] Backend API URL updated to production URL
- [x] Local development URLs commented out
- [x] Environment variables configured on deployment platform
- [x] `.gitignore` properly configured to exclude sensitive files
- [ ] Frontend deployed and URL added to documentation
- [ ] CORS configured to allow frontend domain

## 🚀 GitHub Deployment

### Step 1: Initialize Git Repository (if not already done)

```bash
# Navigate to project root
cd astro-main

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: AstroRemedis deployment ready"
```

### Step 2: Create GitHub Repository

1. Go to [GitHub](https://github.com) and create a new repository
2. Name it `astroremedis` (or your preferred name)
3. **DO NOT** initialize with README, .gitignore, or license (we already have these)

### Step 3: Push to GitHub

```bash
# Add remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/astroremedis.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

## 🔧 Backend Deployment (Render.com)

### Prerequisites
- Render.com account
- GitHub repository connected

### Deployment Steps

1. **Create New Web Service on Render**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository and branch

2. **Configure Build Settings**
   - **Name**: `astroremedis-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2`
   - **Root Directory**: Leave empty (or set to `backend` if deploying only backend)

3. **Environment Variables**
   Add the following environment variables in Render dashboard:
   ```
   PROKERALA_CLIENT_ID=your_client_id
   PROKERALA_CLIENT_SECRET=your_client_secret
   OPENAI_API_KEY=your_openai_key
   OPENAI_ASSISTANT_ID=your_assistant_id
   GOOGLE_CLIENT_ID=your_google_client_id (optional)
   GOOGLE_CLIENT_SECRET=your_google_client_secret (optional)
   GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
   GOOGLE_REFRESH_TOKEN=your_refresh_token (optional)
   GOOGLE_SHEETS_SPREADSHEET_NAME=AstroRemedis Data
   GOOGLE_SHEETS_WORKSHEET_NAME=Sheet1
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy
   - Your backend will be available at: `https://astroremedis.onrender.com`

## 🎨 Frontend Deployment

### Option 1: Vercel (Recommended)

1. **Install Vercel CLI** (optional)
   ```bash
   npm i -g vercel
   ```

2. **Deploy via Vercel Dashboard**
   - Go to [Vercel](https://vercel.com)
   - Import your GitHub repository
   - Configure:
     - **Framework Preset**: Create React App
     - **Root Directory**: `frontend`
     - **Build Command**: `npm run build`
     - **Output Directory**: `build`
     - **Install Command**: `npm install`

3. **Environment Variables**
   - `REACT_APP_API_URL`: `https://astroremedis.onrender.com` (optional, already set in code)

4. **Deploy**
   - Click "Deploy"
   - Your frontend will be available at: `https://your-app.vercel.app`

### Option 2: Netlify

1. **Deploy via Netlify Dashboard**
   - Go to [Netlify](https://netlify.com)
   - Click "Add new site" → "Import an existing project"
   - Connect GitHub repository

2. **Configure Build Settings**
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/build`

3. **Environment Variables**
   - Add `REACT_APP_API_URL` if needed

4. **Deploy**
   - Click "Deploy site"
   - Your frontend will be available at: `https://your-app.netlify.app`

### Option 3: GitHub Pages

1. **Install gh-pages**
   ```bash
   cd frontend
   npm install --save-dev gh-pages
   ```

2. **Update package.json**
   Add to `scripts`:
   ```json
   "predeploy": "npm run build",
   "deploy": "gh-pages -d build"
   ```

3. **Add homepage**
   Update `package.json`:
   ```json
   "homepage": "https://YOUR_USERNAME.github.io/astroremedis"
   ```

4. **Deploy**
   ```bash
   npm run deploy
   ```

## 🔐 Environment Variables

### Backend (.env file - DO NOT COMMIT)
Create `backend/.env` with:
```env
PROKERALA_CLIENT_ID=your_client_id
PROKERALA_CLIENT_SECRET=your_client_secret
OPENAI_API_KEY=your_openai_key
OPENAI_ASSISTANT_ID=your_assistant_id
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_REFRESH_TOKEN=your_refresh_token
GOOGLE_SHEETS_SPREADSHEET_NAME=AstroRemedis Data
GOOGLE_SHEETS_WORKSHEET_NAME=Sheet1
```

### Frontend (.env file - Optional)
Create `frontend/.env` with:
```env
REACT_APP_API_URL=https://astroremedis.onrender.com
```

## 🔄 Updating Deployment

### Backend Updates
1. Make changes to code
2. Commit and push to GitHub
3. Render will automatically redeploy

### Frontend Updates
1. Make changes to code
2. Commit and push to GitHub
3. Vercel/Netlify will automatically redeploy

## 🧪 Testing Deployment

### Backend Health Check
```bash
curl https://astroremedis.onrender.com/api/health
```

### Frontend Connection Test
1. Open browser console
2. Check for API connection logs
3. Verify API calls are going to production URL

## 📝 Code Changes for Deployment

### Frontend (`frontend/src/services/api.js`)
- ✅ Deployed URL: `https://astroremedis.onrender.com` (active)
- ✅ Local URL: `http://127.0.0.1:5000` (commented out)

### Backend (`backend/app.py`)
- ✅ Local development server: Commented out
- ✅ Production: Uses Gunicorn via Procfile

## 🐛 Troubleshooting

### CORS Issues
- Ensure backend CORS allows frontend domain
- Check `CORS(app)` in `backend/app.py`

### Environment Variables
- Verify all variables are set in deployment platform
- Check variable names match exactly (case-sensitive)

### Build Failures
- Check build logs in deployment platform
- Verify all dependencies are in `requirements.txt` and `package.json`
- Ensure Node.js and Python versions are compatible

### API Connection Issues
- Verify backend URL is correct in frontend
- Check backend is running and accessible
- Test backend health endpoint

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Vercel Documentation](https://vercel.com/docs)
- [Netlify Documentation](https://docs.netlify.com)
- [GitHub Pages Documentation](https://pages.github.com)

## ✅ Post-Deployment Checklist

- [ ] Backend health endpoint responding
- [ ] Frontend loads correctly
- [ ] API calls working from frontend
- [ ] CORS configured properly
- [ ] Environment variables set correctly
- [ ] SSL certificates active (HTTPS)
- [ ] Error logging configured
- [ ] Monitoring set up (optional)

---

**Last Updated**: 2024
**Maintained by**: AstroRemedis Development Team

