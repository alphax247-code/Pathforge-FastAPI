# PathForge Deployment Guide

## Required Environment Variables

Your application requires the following environment variables to be set in your deployment platform (Railway, Heroku, etc.):

### Essential Variables

1. **SUPABASE_URL**
   - Your Supabase project URL
   - Format: `https://your-project.supabase.co`
   - Find it in: Supabase Dashboard > Project Settings > API

2. **SUPABASE_ANON_KEY**
   - Your Supabase anonymous/public key
   - Find it in: Supabase Dashboard > Project Settings > API > Project API keys > `anon` `public`

3. **SUPABASE_SERVICE_ROLE_KEY**
   - Your Supabase service role key (private, keep secure!)
   - Find it in: Supabase Dashboard > Project Settings > API > Project API keys > `service_role` (click "Reveal" to see it)

4. **FLASK_SECRET_KEY**
   - A random secret string for Flask session security
   - Generate one with: `python -c "import secrets; print(secrets.token_hex(32))"`

### Optional Variables

5. **SUPABASE_REDIRECT_URL**
   - OAuth callback URL for your deployment
   - Format: `https://your-app.railway.app/auth/callback`
   - Or: `https://your-custom-domain.com/auth/callback`

6. **VIDEOS_BUCKET**
   - Supabase storage bucket name for videos
   - Default: `Files`

7. **ADMIN_USERNAME**
   - Admin panel username
   - Default: `admin`

8. **ADMIN_PASSWORD**
   - Admin panel password
   - **IMPORTANT**: Change from default!

9. **OPENAI_API_KEY** (Optional)
   - Required only if using AI features
   - Get it from: https://platform.openai.com/api-keys

---

## How to Set Environment Variables

### Railway

1. Go to your Railway project dashboard
2. Click on your service
3. Go to the "Variables" tab
4. Click "New Variable" for each variable
5. Enter the variable name and value
6. Click "Add" or "Deploy" to apply changes

### Heroku

1. Go to your Heroku app dashboard
2. Click "Settings" tab
3. Click "Reveal Config Vars"
4. Add each environment variable with its value
5. Changes apply automatically

### Vercel

1. Go to your Vercel project
2. Go to Settings > Environment Variables
3. Add each variable with its value
4. Redeploy your application

---

## Getting Your Supabase Credentials

1. Go to https://supabase.com/dashboard
2. Select your project (or create a new one)
3. Click on "Project Settings" (gear icon in sidebar)
4. Click on "API" in the settings menu
5. Copy the following:
   - **Project URL** → `SUPABASE_URL`
   - **anon public key** → `SUPABASE_ANON_KEY`
   - **service_role key** → `SUPABASE_SERVICE_ROLE_KEY` (click "Reveal" first)

---

## Quick Setup Checklist

- [ ] Copy `.env.example` to `.env` (for local development)
- [ ] Fill in all values in `.env`
- [ ] Set all required variables in your deployment platform
- [ ] Set `SUPABASE_REDIRECT_URL` to match your deployed URL
- [ ] Change `ADMIN_PASSWORD` from default value
- [ ] Generate a secure `FLASK_SECRET_KEY`
- [ ] Verify deployment logs show no environment variable errors

---

## Testing Your Deployment

After setting environment variables:

1. Trigger a new deployment (or it may auto-deploy)
2. Check the deployment logs for errors
3. Visit your deployed URL
4. Try logging in with OAuth (Google/Facebook)
5. Check that all features work correctly

---

## Common Issues

### "Missing Supabase env vars" error
- Make sure all three Supabase variables are set correctly
- Check for extra spaces or missing characters
- Verify the variable names match exactly (case-sensitive)

### OAuth redirect issues
- Ensure `SUPABASE_REDIRECT_URL` matches your deployed domain
- Update OAuth redirect URLs in Supabase Dashboard > Authentication > URL Configuration
- Add your domain to "Site URL" and "Redirect URLs"

### Database connection issues
- Verify your Supabase project is active and not paused
- Check that the service role key has proper permissions
- Ensure your database schema is set up correctly

---

## Security Best Practices

1. **Never commit** `.env` file to git (it's in `.gitignore`)
2. **Rotate keys** if they're ever exposed publicly
3. **Use different keys** for development and production
4. **Enable Row Level Security** (RLS) in Supabase for all tables
5. **Restrict service role key** usage to server-side only

---

## Need Help?

- Supabase Docs: https://supabase.com/docs
- Railway Docs: https://docs.railway.app
- Flask Docs: https://flask.palletsprojects.com/
