# 🚀 LearnVaultX Deployment Guide for Render.com

## 📋 Prerequisites
- GitHub repository with your LearnVaultX project
- Render.com account (free)
- AI API key (DeepSeek, Groq, or OpenAI)

## 🚀 Step-by-Step Deployment

### 1. **Prepare Your Repository**
✅ All files are ready in your GitHub repo:
- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `Procfile` - Render startup command
- `render.yaml` - Render configuration
- `start_server.py` - Production startup script

### 2. **Create Render Account**
1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Connect your GitHub account

### 3. **Deploy Your App**
1. **Click "New +"** → **"Web Service"**
2. **Connect Repository:**
   - Select your GitHub account
   - Choose `visioncraft157-sketch/EduLearn` repository
   - Click "Connect"

3. **Configure Service:**
   - **Name:** `learnvaultx` (or your preferred name)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python start_server.py`
   - **Plan:** `Free`

### 4. **Set Environment Variables**
In Render dashboard, go to **Environment** tab and add:

```
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
DEEPSEEK_API_KEY=your_deepseek_key_here
GROQ_API_KEY=your_groq_key_here
OPENAI_API_KEY=your_openai_key_here
```

**Note:** You only need ONE AI API key. Groq is recommended (free & fast).

### 5. **Deploy!**
1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies
   - Start your application
   - Provide a public URL

## 🌐 **Your App Will Be Live At:**
`https://learnvaultx.onrender.com` (or similar)

## 🔧 **Troubleshooting**

### Common Issues:
1. **Build Fails:** Check `requirements.txt` for missing dependencies
2. **App Crashes:** Check logs in Render dashboard
3. **Database Issues:** SQLite file is created automatically
4. **AI Not Working:** Verify API keys in environment variables

### Render Logs:
- Go to your service dashboard
- Click "Logs" tab to see real-time logs
- Check for any error messages

## 🎯 **Features After Deployment:**
- ✅ **Public URL:** Accessible from anywhere
- ✅ **Auto-deploy:** Updates when you push to GitHub
- ✅ **Free Hosting:** No cost for basic usage
- ✅ **SSL Certificate:** HTTPS enabled automatically
- ✅ **Database:** SQLite database persists
- ✅ **AI Chatbot:** Working with your API keys

## 📱 **Testing Your Deployed App:**
1. Visit your Render URL
2. Register a new account
3. Test the AI chatbot
4. Upload files and test features
5. Check mobile responsiveness

## 🔄 **Updating Your App:**
1. Make changes to your local code
2. Push to GitHub: `git push origin main`
3. Render automatically redeploys
4. Your app updates in 2-3 minutes

## 💡 **Pro Tips:**
- **Free Plan Limits:** 750 hours/month (enough for development)
- **Sleep Mode:** Free apps sleep after 15 minutes of inactivity
- **Wake Time:** Takes 30 seconds to wake up
- **Upgrade:** $7/month for always-on service

## 🎉 **Success!**
Your LearnVaultX AI-Based Low-Bandwidth Virtual Teaching & Animation System is now live on the internet!

**Share your deployed app with your team, mentor, and showcase it in your presentation!**
