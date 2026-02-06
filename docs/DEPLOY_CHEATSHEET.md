# 🚀 Render Deploy - CHEAT SHEET

## ⚡ COPY-PASTE VALUES

### 🌐 Website
```
https://render.com
```

### 📝 Form Fields

**Name:**
```
learnvaultx
```

**Region:**
```
Oregon (US West)
```

**Branch:**
```
main
```

**Root Directory:**
```
(leave blank)
```

**Runtime:**
```
Python 3
```

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
gunicorn --worker-class eventlet -w 1 app:app
```

**Instance Type:**
```
Free
```

### 🔑 Environment Variable

**Key:**
```
GROQ_API_KEY
```

**Value:**
```
(open .env file and copy the value after GROQ_API_KEY=)
```

### ⚙️ Advanced Settings

**Auto-Deploy:**
```
Yes
```

---

## 🗄️ DATABASE COMMANDS (Run in Render Shell)

**After deployment, run these 3 commands:**

```python
python -c "from app import init_db; init_db()"
```

```python
python seed_data.py
```

```python
python seed_cs_courses.py
```

---

## 🧪 TEST LOGINS

**Student:**
```
Email: student1@edu.com
Password: password123
```

**Teacher:**
```
Email: teacher1@edu.com
Password: password123
```

---

## ✅ QUICK CHECKLIST

```
□ Go to render.com
□ Sign in with GitHub
□ New + → Web Service
□ Connect LearnVaultX
□ Name: learnvaultx
□ Region: Oregon (US West)
□ Build: pip install -r requirements.txt
□ Start: gunicorn --worker-class eventlet -w 1 app:app
□ Free plan
□ Add GROQ_API_KEY
□ Create Web Service
□ Wait 10 minutes
□ Open Shell
□ Run 3 commands above
□ Test login
□ DONE! ✅
```

---

## 📍 YOUR URL

```
https://learnvaultx.onrender.com
```

---

**That's it! Copy-paste and go!** 🚀

