# Vercel Deployment Guide

This guide explains how to deploy the Hawaii Car Rental API to Vercel.

## Prerequisites

1. A Vercel account (sign up at https://vercel.com)
2. Vercel CLI installed (optional, for CLI deployment):
   ```bash
   npm i -g vercel
   ```

## Environment Variables

Set the following environment variables in your Vercel project settings:

### Required:
- `MONGODB_URI` - Your MongoDB connection string
  - Example: `mongodb+srv://user:password@cluster.mongodb.net/?appName=Cluster0`

### Optional:
- `MONGODB_DB` - Database name (default: `hawaii_rental`)
- `MONGODB_RESERVATIONS_COLLECTION` - Collection name (default: `reservations`)
- `AUTH_TOKEN` - API authentication token (if not set, uses default from config)
- `LOG_LEVEL` - Logging level (default: `INFO`)

## Deployment Methods

### Method 1: Deploy via Vercel Dashboard (Recommended)

1. **Push your code to GitHub/GitLab/Bitbucket**

2. **Import your repository:**
   - Go to https://vercel.com/new
   - Import your Git repository
   - Vercel will auto-detect Python/FastAPI

3. **Configure project:**
   - Framework Preset: **Other**
   - Root Directory: `.` (or leave default)
   - Build Command: Leave empty (Vercel handles it)
   - Output Directory: Leave empty
   - Install Command: `pip install -r requirements.txt`

4. **Add Environment Variables:**
   - Go to Project Settings → Environment Variables
   - Add all required variables listed above

5. **Deploy:**
   - Click "Deploy"
   - Wait for build to complete

### Method 2: Deploy via Vercel CLI

1. **Install Vercel CLI:**
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```

3. **Deploy:**
   ```bash
   vercel
   ```

4. **Set Environment Variables:**
   ```bash
   vercel env add MONGODB_URI
   vercel env add MONGODB_DB
   # ... add other variables
   ```

5. **Deploy to production:**
   ```bash
   vercel --prod
   ```

## Important Notes for Vercel

### Serverless Environment
- Vercel uses serverless functions, so the filesystem is **read-only** except `/tmp`
- The sync buffer file (`sync_buffer.jsonl`) is automatically stored in `/tmp` directory
- Each function execution has a maximum duration (set to 300 seconds in `vercel.json`)

### Function Timeout
- Default timeout: 10 seconds (Hobby plan)
- Pro plan: Up to 60 seconds
- Enterprise: Up to 300 seconds (configured in `vercel.json`)
- For long-running sync operations, consider:
  - Using Vercel Pro/Enterprise plan
  - Breaking sync into smaller chunks
  - Using background jobs (Vercel Cron Jobs)

### Cold Starts
- First request after inactivity may be slower (cold start)
- Consider using Vercel Pro plan for better performance
- Or use an external service to ping your API periodically

## API Endpoints

After deployment, your API will be available at:
- `https://your-project.vercel.app/`
- `https://your-project.vercel.app/docs` - API documentation
- `https://your-project.vercel.app/reservations` - Get reservations
- `https://your-project.vercel.app/sync` - Sync reservations
- `https://your-project.vercel.app/powerbi` - Power BI data endpoint

## Troubleshooting

### Build Errors
- Ensure `requirements.txt` includes all dependencies
- Check Python version compatibility (Vercel uses Python 3.11 by default)

### Runtime Errors
- Check environment variables are set correctly
- Review function logs in Vercel dashboard
- Ensure MongoDB connection string is valid

### Timeout Issues
- Upgrade to Vercel Pro/Enterprise for longer timeouts
- Optimize sync operations to complete faster
- Consider breaking large syncs into smaller batches

## Differences from Render

1. **Filesystem**: Vercel uses read-only filesystem (except `/tmp`)
2. **Function Timeout**: Limited execution time (vs. always-on on Render)
3. **Cold Starts**: Functions may have cold start delays
4. **Scaling**: Automatic scaling per request (vs. single instance on Render free)

## Keep-Alive (Prevent Cold Starts)

To prevent cold starts, you can:
1. Use Vercel Cron Jobs to ping your API periodically
2. Set up external monitoring service (UptimeRobot, etc.)
3. Upgrade to Vercel Pro for better performance
