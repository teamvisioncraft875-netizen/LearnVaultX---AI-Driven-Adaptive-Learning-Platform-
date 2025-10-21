# 🚀 Deploy LearnVaultX to Render - Step by Step

## 📋 Prerequisites

✅ GitHub repository ready: https://github.com/visioncraft157-sketch/LearnVaultX  
✅ All code pushed  
✅ Deployment files present (Procfile, render.yaml, requirements.txt)  

---

## 🎯 Step-by-Step Deployment

### **Step 1: Go to Render**

1. Open browser
2. Go to: **https://render.com**
3. Click **"Get Started for Free"** or **"Sign In"**

---

### **Step 2: Sign In with GitHub**

1. Click **"Sign in with GitHub"**
2. Authorize Render to access your GitHub
3. You'll be redirected to your Render dashboard

---

### **Step 3: Create New Web Service**

1. On Render dashboard, click **"New +"** button (top right)
2. Select **"Web Service"**
3. You'll see "Connect a repository" page

---

### **Step 4: Connect Your Repository**

1. Find **"LearnVaultX"** in the list
   - If you don't see it, click **"Configure account"**
   - Grant Render access to the repository

2. Click **"Connect"** next to LearnVaultX

---

### **Step 5: Configure Web Service**

Fill in these details:

#### **Basic Settings:**
```
Name: learnvaultx
(or any unique name you prefer)

Region: Oregon (US West)
(or closest to you)

Branch: main

Root Directory: (leave blank)
```

#### **Build & Deploy:**
```
Runtime: Python 3

Build Command: pip install -r requirements.txt

Start Command: gunicorn --worker-class eventlet -w 1 app:app
```

---

### **Step 6: Select Plan**

1. Scroll down to **"Instance Type"**
2. Select **"Free"** plan
   - ✅ Free tier available
   - ✅ Perfect for demos and testing
   - ℹ️ May spin down after inactivity

---

### **Step 7: Add Environment Variables**

Scroll to **"Environment Variables"** section:

Click **"Add Environment Variable"** and add these:

```
Key: GROQ_API_KEY
Value: (paste your Groq API key from .env file)
```

**Optional (for best AI):**
```
Key: ANTHROPIC_API_KEY
Value: (your Claude API key if you have one)
```

**Optional (email features):**
```
Key: EMAIL_USER
Value: your-email@gmail.com

Key: EMAIL_PASSWORD
Value: your-app-password
```

---

### **Step 8: Advanced Settings (Optional)**

Click **"Advanced"** to expand:

```
Auto-Deploy: Yes
(automatically deploy when you push to GitHub)

Health Check Path: /
(Render will ping this to check if app is running)
```

---

### **Step 9: Create Web Service**

1. Review all settings
2. Click **"Create Web Service"** button (bottom)
3. **Wait for deployment** (5-10 minutes)

You'll see:
- Build logs in real-time
- Status: "Building..." → "Live"

---

### **Step 10: Deployment Progress**

Watch the logs:

```
==> Cloning from https://github.com/visioncraft157-sketch/LearnVaultX...
==> Downloading cache...
==> Running build command 'pip install -r requirements.txt'...
==> Installing dependencies...
==> Build successful!
==> Deploying...
==> Your service is live 🎉
```

---

### **Step 11: Get Your Live URL**

Once deployed, you'll see:

```
✅ Your service is live at:
https://learnvaultx.onrender.com

(or whatever name you chose)
```

**Copy this URL!**

---

### **Step 12: Test Your Live App**

1. Click the URL or visit it in browser
2. You should see your login page!
3. Test login:
   - Student: `student1@edu.com` / `password123`
   - Teacher: `teacher1@edu.com` / `password123`

---

## ⚠️ Important Notes

### **Database Warning:**

Your current setup uses SQLite, which is **not persistent** on Render free tier!

**What this means:**
- Database resets when service restarts
- You'll lose quiz submissions, user data
- **For demo only** - works fine!

**For production:**
- Upgrade to PostgreSQL (see below)
- Or use external database

---

### **Cold Starts:**

Free tier spins down after 15 minutes of inactivity:

**When someone visits:**
- First load: 30-60 seconds (waking up)
- Subsequent loads: Fast!

**For demo:**
- Visit your URL 5 minutes before demo
- It will be warmed up and fast

---

## 🔄 Updating Your Deployment

### **Automatic Updates:**

Since Auto-Deploy is enabled:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push

# Render automatically deploys! ✨
```

### **Manual Deploy:**

1. Go to Render dashboard
2. Click on your service
3. Click **"Manual Deploy"**
4. Select **"Deploy latest commit"**

---

## 📊 Monitor Your App

### **On Render Dashboard:**

1. **Logs**: See real-time application logs
2. **Metrics**: CPU, memory usage
3. **Events**: Deployment history
4. **Settings**: Change environment variables

### **Useful Logs Commands:**

In Render dashboard, click **"Logs"** to see:
- Application startup
- Incoming requests
- Errors (if any)
- Database operations

---

## 🐛 Troubleshooting

### **App Won't Start?**

Check logs for:
```
Error: ...
```

**Common fixes:**
1. Check environment variables are set
2. Verify `requirements.txt` is complete
3. Check `Procfile` or start command is correct

### **Database Issues?**

**Expected behavior:**
- SQLite works but resets on restart
- Data is temporary on free tier

**Solution for persistence:**
1. Upgrade to PostgreSQL database
2. Update app to use PostgreSQL
3. See `RENDER_DEPLOYMENT_GUIDE.md` for details

### **Slow Loading?**

**First visit after inactivity:**
- Wait 30-60 seconds (service waking up)
- Refresh page
- Should be fast afterwards

**For demo:**
- Visit URL 5 minutes before
- Service will be warm and responsive

---

## ✨ Upgrade Options

### **Free → Starter ($7/month):**
- No cold starts
- Always on
- 512 MB RAM
- Better for production

### **Add PostgreSQL:**
```
1. In Render dashboard: New > PostgreSQL
2. Create database
3. Copy connection string
4. Update app to use PostgreSQL
5. Update DATABASE_URL environment variable
```

---

## 🎯 Quick Reference

### **Your URLs:**
```
GitHub: https://github.com/visioncraft157-sketch/LearnVaultX
Render: https://learnvaultx.onrender.com
(or your custom name)
```

### **Default Logins:**
```
Teacher: teacher1@edu.com / password123
Student: student1@edu.com / password123
```

### **Important Files:**
```
Procfile - Start command
render.yaml - Render configuration
requirements.txt - Python dependencies
wsgi.py - WSGI application
```

---

## 🎬 For Tomorrow's Demo

### **Option 1: Use Local (Recommended)**
```
✅ Instant loading
✅ No cold starts
✅ Full control
✅ No internet dependency

URL: http://localhost:5000
```

### **Option 2: Use Render URL**
```
✅ Shows deployment capability
✅ Accessible from anywhere
✅ Professional URL

⚠️ Visit 5 minutes before demo
⚠️ First load may be slow
⚠️ Database resets on restart

URL: https://learnvaultx.onrender.com
```

### **Best Approach:**

1. **Demo on local** for speed and reliability
2. **Mention Render** deployment as additional capability
3. **Show Render URL** at the end if time permits

---

## 📋 Deployment Checklist

Before deploying:
- [x] All code pushed to GitHub ✓
- [x] `requirements.txt` has all dependencies ✓
- [x] `Procfile` exists ✓
- [x] `render.yaml` configured ✓
- [ ] Render account created
- [ ] Repository connected to Render
- [ ] Environment variables set
- [ ] Service deployed
- [ ] Live URL tested
- [ ] Database seeded (run seed scripts)

---

## 🚀 Ready to Deploy!

### **Quick Summary:**

1. **Go to:** https://render.com
2. **Sign in** with GitHub
3. **New Web Service**
4. **Connect** LearnVaultX repository
5. **Configure:**
   - Runtime: Python 3
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn --worker-class eventlet -w 1 app:app`
6. **Add** environment variables (GROQ_API_KEY)
7. **Deploy!**
8. **Wait** 5-10 minutes
9. **Test** your live URL
10. **Success!** 🎉

---

## 💡 Pro Tips

1. **Warm up before demo:**
   ```
   Visit your Render URL 5 minutes before presenting
   ```

2. **Monitor logs:**
   ```
   Keep Render logs open during demo
   Can troubleshoot in real-time if needed
   ```

3. **Have backup:**
   ```
   Always have local version running
   localhost:5000 as fallback
   ```

4. **Database persistence:**
   ```
   For real use, upgrade to PostgreSQL
   Free SQLite resets on restart
   ```

---

## 🎉 You're Ready to Deploy!

**Follow the steps above and your app will be live in 10 minutes!**

**Your live URL will be:**
```
https://learnvaultx.onrender.com
(or your chosen name)
```

**Good luck with deployment and tomorrow's demo!** 🚀

