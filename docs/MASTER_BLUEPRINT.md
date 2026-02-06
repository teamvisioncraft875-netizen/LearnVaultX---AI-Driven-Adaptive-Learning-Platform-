# LearnVaultX: The Master Blueprint

> [!IMPORTANT]
> This document contains the **Universal Truth** of the LearnVaultX application. It details every pixel, every database column, and every line of logic required to rebuild the system from scratch.

---

## 1. Frontend Architecture & Design System

### 1.1 The "Holy Trinity" Theme System
The application is built on a CSS Variable system that supports three distinct themes. The "Futuristic" theme is the default and signature look.

#### **Theme 1: Futuristic (Signature)**
*   **Concept**: Deep space, neon bioluminescence, glassmorphism.
*   **Background**: Deep Navy Void (`#0B1220`) with radial gradients.
    *   `background-image`: `radial-gradient(circle at 20% 50%, rgba(56, 189, 248, 0.08) 0%, transparent 50%)`, `radial-gradient(circle at 80% 30%, rgba(167, 139, 250, 0.08) 0%, transparent 50%)`.
*   **Primary Brand Color**: Neon Cyan (`#38BDF8`).
*   **Secondary Accent**: Electric Purple (`#A78BFA`).
*   **Surface Texture**: "Glass" - Semi-transparent dark blue with blur (`backdrop-filter: blur(12px)`).
    *   RGBA: `rgba(30, 41, 59, 0.7)`
*   **Interactive Glows**: All primary actions and cards have a box-shadow glow: `0 0 20px rgba(56, 189, 248, 0.15)`.

#### **Theme 2: Dark (Professional)**
*   **Concept**: High contrast, matte finish, productivity focused.
*   **Background**: Slate Gray (`#0F172A`).
*   **Primary**: Corporate Blue (`#3B82F6`).
*   **Surface**: Solid Dark Gray (`#1E293B`).
*   **No Glows**: Uses standard clean borders (`#374151`).

#### **Theme 3: Light (Minimal)**
*   **Concept**: Paper-like, clean, traditional.
*   **Background**: Off-White (`#F3F4F6`).
*   **Primary**: Deep Blue (`#2563EB`).
*   **Surface**: Pure White (`#FFFFFF`) with Drop Shadows.

### 1.2 Layout Specs (The 3-Zone Dashboard)
The core interface (`student_dashboard.html`) uses a strict 3-zone grid layout usually hidden/revealed on mobile.

| Zone | Width | Function | Key Components |
| :--- | :--- | :--- | :--- |
| **Zone 1: Sidebar** | 250px | Navigation & Profile | Logo, Nav Menu (Dashboard, Classes, Progress), User Profile (Bottom) |
| **Zone 2: Center** | Flex-Grow | Main Content | "Hero" Welcome header, Quick Actions Grid, Class Cards, Analytics Grid |
| **Zone 3: AI Panel** | 350px | KyKnoX Intelligence | Mode Switcher (Socratic/Expert/Coach), Chat Interface, Voice Controls |

#### **Mobile Responsiveness Strategy**
*   **< 1024px**:
    *   Sidebar: Becomes an off-canvas drawer (Drawer Left).
    *   AI Panel: Becomes an off-canvas drawer (Drawer Right).
    *   Overlay: A black semi-transparent overlay appears when either drawer is open.

### 1.3 Typography System
*   **Headings**: `Inter` (Google Fonts). Weights: 600, 700.
    *   `h1`: 2.5rem (Desktop), 2rem (Mobile).
*   **Body**: `Inter`. Weight: 400. Line-height: 1.5.
*   **Monospace/Code**: `JetBrains Mono`.
*   **Scale**:
    *   `xs`: 0.75rem
    *   `sm`: 0.875rem
    *   `base`: 1rem
    *   `lg`: 1.125rem
    *   `xl`: 1.25rem
    *   `2xl`: 1.5rem
    *   `3xl`: 1.875rem

---

## 2. Backend Architecture (Flask)

### 2.1 Technology Stack
*   **Server**: Flask (Python 3.10+)
*   **Async**: Flask-SocketIO (for real-time classroom features)
*   **Database**: SQLite (via standard `sqlite3` library, wrapped in a `DatabaseManager` class)
*   **AI Engine**: `requests` library calling Groq API (`mixtral-8x7b-32768` model)

### 2.2 Database Schema (The Data Truth)
The system requires these exact tables to function.

1.  **`users`**: `id, name, email (unique), password_hash, role (student/teacher)`
2.  **`classes`**: `id, title, description, teacher_id (FK)`
3.  **`enrollments`**: `id, student_id (FK), class_id (FK)` - *Unique constraint on student+class*.
4.  **`lectures`**: `id, class_id, filename, filepath` - *Stores paths to `static/uploads`*.
5.  **`quizzes`**: `id, class_id, title`
6.  **`quiz_questions`**: `id, quiz_id, question_text, options (JSON), correct_option_index`
7.  **`quiz_submissions`**: `id, quiz_id, student_id, score, answers (JSON)`
8.  **`ai_queries`**: `id, user_id, prompt, response` - *Logs all AI interactions*.
9.  **`student_metrics`**: `user_id, class_id, score_avg` - *Calculated analytics*.

### 2.3 Feature Logic Details

#### **A. KyKnoX AI System**
*   **Location**: `modules/kyknox_ai_new.py`
*   **Logic**:
    1.  Receives `prompt` and `mode` (Expert/Socratic/Coach) from frontend.
    2.  Builds a **System Prompt**:
        *   *Socratic*: "Ask guiding questions instead of direct answers."
        *   *Coach*: "Be supportive and motivational."
        *   *Expert*: "Provide factual, detailed answers."
    3.  Injects **Context**: Fetches user's "Weak Topics" from `adaptive_learning` module and appends to prompt: `Context: {weak_topics: ['Calculus', 'Arrays']}`.
    4.  Calls Groq API.
    5.  Returns Markdown response -> Parsed to HTML on server -> Sent to frontend.

#### **B. Adaptive Learning Engine**
*   **Location**: `modules/adaptive_learning_new.py` (and `app.py` integration)
*   **Logic**:
    1.  **Trigger**: Triggers on `submit_quiz` endpoint.
    2.  **Analysis**:
        *   Calculates Score.
        *   If Score < 50% on a specific Topic ID (mapped in `question_topics`), marks topic as "Weak".
    3.  **Recommendations**:
        *   If "Weak Topic" exists, query `lectures` table for filenames matching that topic.
        *   Create entry in `recommendations` table.
    4.  **Display**: Student Dashboard fetches `/api/student/recommendations` to show cards.

#### **C. Class Management**
*   **Teacher**: Can upload files. File paths are saved in DB, actual files in `static/uploads`.
    *   *Constraint*: Allowed extensions: `pdf, ppt, pptx, doc, docx, mp4`.
*   **Student**: Can "Join" classes via `/api/join_class`.
    *   *Logic*: Checks `enrollments` table for duplicates before inserting.

---

## 3. UI Implementation Details (The Secret Sauce)

### 3.1 The Glass Card Effect
To replicate the exact "Future" feel on cards:
```css
.glass-card {
    background: rgba(15, 23, 42, 0.6); /* Semi-transparent navy */
    border: 1px solid rgba(56, 189, 248, 0.2); /* Cyan border with low opacity */
    backdrop-filter: blur(12px); /* The "Frosted" glass look */
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
```

### 3.2 The Neon Button
To replicate the glowing primary button:
```css
.btn-primary {
    background: linear-gradient(135deg, #38BDF8 0%, #22D3EE 100%); /* Cyan Gradient */
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.3); /* The Glow */
    border: 1px solid rgba(255,255,255,0.1);
}
.btn-primary:hover {
    box-shadow: 0 0 30px rgba(56, 189, 248, 0.5); /* Stronger Glow */
}
```

### 3.3 The Animations
Core screens use a "Fade In Up" entry animation:
```css
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
.animate-entry {
    animation: fadeInUp 0.5s ease-out forwards;
}
```

---

## 4. Rebuild Instructions (Step-by-Step)

If you lose the source code, follow this algorithm to revive it:

1.  **Scaffold**: Create folder structure `static/css`, `static/js`, `templates`, `modules`.
2.  **Database**: Run the SQL schema provided in Section 2.2 to create the `learnvault.db`.
3.  **Backend**: Write `app.py` with Flask routes matching the endpoints in Section 2.3.
4.  **AI**: Get a Groq API Key. Implement the `KyKnoX` class to wrap the HTTP request.
5.  **Frontend**:
    *   Create `variables.css` with the colors from Section 1.1.
    *   Create `layout.css` implementing the 3-zone grid from Section 1.2.
    *   Create `student_dashboard.html` using the exact card styles from Section 3.1.
6.  **Verify**: Log in as a student -> Check if the dashboard loads with the dark navy background -> Ask AI a question.

---
**End of Master Blueprint**
