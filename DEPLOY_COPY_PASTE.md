# 🚀 Render Deployment - Copy & Paste Guide

**Just copy the answers below exactly as shown!**

---

## 📝 FORM ANSWERS (Copy These Exactly)

### STEP 1: Go to Website
```
https://render.com
```
Click "Sign in with GitHub"

---

### STEP 2: Service Configuration

**When you see the form, copy-paste these answers:**

#### Name
```
learnvaultx
```

#### Region
```
Oregon (US West)
```
*(Select from dropdown)*

#### Branch
```
main
```

#### Root Directory
```
(leave blank - don't type anything)
```

#### Runtime
```
Python 3
```
*(Select from dropdown)*

---

### STEP 3: Build Command

**Copy this EXACTLY:**
```
pip install -r requirements.txt
```

---

### STEP 4: Start Command

**Copy this EXACTLY:**
```
gunicorn --worker-class eventlet -w 1 app:app
```

---

### STEP 5: Instance Type

Select: **Free**

---

### STEP 6: Environment Variable

**First, get your API key:**

Open your `.env` file and look for this line:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxx
```

**Then add to Render:**

**Key:**
```
GROQ_API_KEY
```

**Value:**
```
(paste your actual key from .env file - starts with gsk_)
```

**Example:**
```
Key: GROQ_API_KEY
Value: gsk_Z4FGH2sT9pXmKqR7vYnL3wBcD8jN1hM6fE5aS0
```
*(Use YOUR key from .env, not this example!)*

---

### STEP 7: Auto-Deploy

Click "Advanced" → Set Auto-Deploy to **Yes**

---

### STEP 8: Create Service

Click the big button: **Create Web Service**

---

## 🗄️ DATABASE SEEDING COMMANDS

**After deployment finishes, open Render Shell and run these 3 commands:**

### Command 1: Initialize Database
```python
python -c "from app import init_db; init_db()"
```
*Press Enter, wait for it to complete*

### Command 2: Seed Demo Data
```python
python seed_data.py
```
*Press Enter, wait for it to complete*

### Command 3: Seed CS Courses
```python
python seed_cs_courses.py
```
*Press Enter, wait for it to complete*

---

## 🧪 TEST LOGIN CREDENTIALS

**Once seeded, test with these:**

### Student Login
```
Email: student1@edu.com
Password: password123
```

### Teacher Login
```
Email: teacher1@edu.com
Password: password123
```

---

## 📋 COMPLETE CHECKLIST WITH ANSWERS

Print this and check off as you go:

```
□ 1. Go to: https://render.com
□ 2. Click "Sign in with GitHub"
□ 3. Authorize Render
□ 4. Click "New +" → "Web Service"
□ 5. Find "LearnVaultX" → Click "Connect"

CONFIGURATION FORM:
□ 6. Name: learnvaultx
□ 7. Region: Oregon (US West)
□ 8. Branch: main
□ 9. Root Directory: (blank)
□ 10. Runtime: Python 3
□ 11. Build Command: pip install -r requirements.txt
□ 12. Start Command: gunicorn --worker-class eventlet -w 1 app:app
□ 13. Instance Type: Free

ENVIRONMENT VARIABLES:
□ 14. Key: GROQ_API_KEY
□ 15. Value: (paste from .env file)

ADVANCED:
□ 16. Auto-Deploy: Yes

DEPLOY:
□ 17. Click "Create Web Service"
□ 18. Wait 5-10 minutes for "Live" status

SEED DATABASE (in Render Shell):
□ 19. python -c "from app import init_db; init_db()"
□ 20. python seed_data.py
□ 21. python seed_cs_courses.py

TEST:
□ 22. Visit your URL
□ 23. Login: student1@edu.com / password123
□ 24. See 5 CS courses
□ 25. DONE! ✅
```

---

## 🎯 QUICK COPY-PASTE REFERENCE

### All Settings in One Place:

```yaml
Name: learnvaultx
Region: Oregon (US West)
Branch: main
Root Directory: (blank)
Runtime: Python 3

Build Command:
pip install -r requirements.txt

Start Command:
gunicorn --worker-class eventlet -w 1 app:app

Instance Type: Free

Environment Variables:
- Key: GROQ_API_KEY
  Value: (from your .env file)

Auto-Deploy: Yes
```

### Shell Commands (After Deploy):
```bash
# Command 1
python -c "from app import init_db; init_db()"

# Command 2  
python seed_data.py

# Command 3
python seed_cs_courses.py
```

### Test Logins:
```
Student: student1@edu.com / password123
Teacher: teacher1@edu.com / password123
```

---

## 📸 WHAT YOUR .env FILE LOOKS LIKE

Open `.env` in your project folder. It should look like this:

```env
# AI/ML API Keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Email Configuration
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Database
DATABASE_URL=sqlite:///education.db
```

**You need to copy the value after `GROQ_API_KEY=`**

---

## 🔍 HOW TO GET YOUR GROQ_API_KEY

### Option 1: From .env File (Easiest)

1. In VS Code, open `.env` file
2. Find line: `GROQ_API_KEY=gsk_...`
3. Copy everything AFTER the `=` sign
4. That's your key!

### Option 2: From Terminal

Run this command:
```bash
cat .env | grep GROQ_API_KEY
```

You'll see:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx
```

Copy the part after `=`

### Option 3: From Notepad

1. Open File Explorer
2. Go to: `C:\Users\ASUS\Downloads\Project`
3. Open `.env` with Notepad
4. Find `GROQ_API_KEY=` line
5. Copy the value after `=`

---

## ✅ FILLED-IN EXAMPLE

**Here's what your Render form should look like when filled:**

```
┌─────────────────────────────────────────┐
│ Name                                     │
│ learnvaultx                             │
├─────────────────────────────────────────┤
│ Region                                   │
│ Oregon (US West) ▼                      │
├─────────────────────────────────────────┤
│ Branch                                   │
│ main                                     │
├─────────────────────────────────────────┤
│ Root Directory                           │
│                                          │
├─────────────────────────────────────────┤
│ Runtime                                  │
│ Python 3 ▼                              │
├─────────────────────────────────────────┤
│ Build Command                            │
│ pip install -r requirements.txt         │
├─────────────────────────────────────────┤
│ Start Command                            │
│ gunicorn --worker-class eventlet -w 1..│
├─────────────────────────────────────────┤
│ Instance Type                            │
│ ○ Starter ($7/mo)                       │
│ ● Free                                   │
├─────────────────────────────────────────┤
│ Environment Variables                    │
│ GROQ_API_KEY = gsk_xxxxx...            │
│ [+ Add Environment Variable]            │
├─────────────────────────────────────────┤
│ Advanced                                 │
│ Auto-Deploy: Yes ●                      │
└─────────────────────────────────────────┘

        [Create Web Service]
```

---

## 🎬 VISUAL STEP-BY-STEP

### Phase 1: Sign In (1 minute)
```
1. Open browser
2. Type: render.com
3. Click "Sign In"
4. Click "Sign in with GitHub"
5. Click "Authorize Render"
✓ You're in!
```

### Phase 2: Create Service (2 minutes)
```
6. Click "New +" button
7. Click "Web Service"
8. Find "LearnVaultX"
9. Click "Connect"
✓ Form opens!
```

### Phase 3: Fill Form (3 minutes)
```
10. Name: type "learnvaultx"
11. Region: select "Oregon (US West)"
12. Branch: leave as "main"
13. Root Directory: leave blank
14. Runtime: select "Python 3"
15. Build Command: paste "pip install -r requirements.txt"
16. Start Command: paste "gunicorn --worker-class eventlet -w 1 app:app"
17. Instance Type: click "Free"
18. Click "+ Add Environment Variable"
19. Key: type "GROQ_API_KEY"
20. Value: paste your key from .env
21. Click "Advanced"
22. Auto-Deploy: select "Yes"
✓ Form complete!
```

### Phase 4: Deploy (10 minutes)
```
23. Click "Create Web Service"
24. Watch logs scroll
25. Wait for "Live" status
26. Copy your URL
✓ App is live!
```

### Phase 5: Seed Database (2 minutes)
```
27. Click "Shell" tab
28. Type: python -c "from app import init_db; init_db()"
29. Press Enter, wait
30. Type: python seed_data.py
31. Press Enter, wait
32. Type: python seed_cs_courses.py
33. Press Enter, wait
✓ Database ready!
```

### Phase 6: Test (1 minute)
```
34. Open your URL in new tab
35. Email: student1@edu.com
36. Password: password123
37. Click Login
38. See dashboard with 5 courses
✓ SUCCESS! 🎉
```

---

## 🆘 TROUBLESHOOTING ANSWERS

### "Can't find LearnVaultX repository"
**Answer:** 
1. Click "Configure account"
2. Select "Only select repositories"
3. Click dropdown
4. Check "LearnVaultX"
5. Click "Save"

### "Build failed"
**Answer:**
Check you typed build command exactly:
```
pip install -r requirements.txt
```
(No extra spaces!)

### "App crashes on start"
**Answer:**
Check start command is exactly:
```
gunicorn --worker-class eventlet -w 1 app:app
```

### "App loads but no data"
**Answer:**
Run the 3 seed commands in Shell:
```python
python -c "from app import init_db; init_db()"
python seed_data.py
python seed_cs_courses.py
```

### "Can't login"
**Answer:**
Make sure you ran seed commands first!
Then use:
```
Email: student1@edu.com
Password: password123
```

---

## 🎯 YOUR FINAL URL

After deployment, your URL will be:

```
https://learnvaultx.onrender.com
```

(If name is taken, try: `learnvaultx-yourinitials`)

---

## 📝 SAVE THESE DETAILS

**Write this down:**

```
Project: LearnVaultX
Live URL: https://learnvaultx.onrender.com
GitHub: https://github.com/visioncraft157-sketch/LearnVaultX

Logins:
- Student: student1@edu.com / password123
- Teacher: teacher1@edu.com / password123

Render Dashboard: https://dashboard.render.com
```

---

## ⏱️ TIMELINE

```
0:00 - Start at render.com
0:01 - Sign in with GitHub
0:02 - Create Web Service
0:03 - Start filling form
0:06 - Form complete
0:07 - Click "Create Web Service"
0:17 - Deployment complete (wait time)
0:18 - Open Shell
0:20 - Run seed commands
0:21 - Test login
0:22 - SUCCESS! ✅
```

**Total time: ~20 minutes**

---

## 🎉 THAT'S IT!

**Everything you need to copy-paste is above!**

**Just:**
1. Open render.com
2. Copy-paste the settings above
3. Run the 3 shell commands
4. Test with student1@edu.com
5. Done!

**Your app will be live!** 🚀

---

## 💾 SAVE THIS FILE

Keep this file open while deploying!

You can copy-paste directly from here.

---

**Good luck!** 🎯

**You've got this!** 💪

