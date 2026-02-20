/* Arena Quiz Engine JS */
(function () {
    // Define startQuiz globally first so button doesn't crash on click if data is missing
    window.startQuiz = function () {
        if (!window.QUIZ_DATA || !QUIZ_DATA.totalQuestions) {
            console.error("Quiz data missing or empty");
            alert("Unable to start quiz: No questions loaded. Please refresh.");
            return;
        }
        const overlay = document.getElementById('startOverlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.style.display = 'none', 300);
        }
        startTimer();
    };

    if (!window.QUIZ_DATA || !QUIZ_DATA.totalQuestions) return;

    let currentIndex = 0;
    let answers = new Array(QUIZ_DATA.totalQuestions).fill(null);
    let questionStartTimes = new Array(QUIZ_DATA.totalQuestions).fill(0);
    let questionTimes = new Array(QUIZ_DATA.totalQuestions).fill(0);
    let timeLeft = QUIZ_DATA.timeLimit;
    let timerInterval = null;
    let quizStartTime = Date.now();

    // Timer logic
    function startTimer() {
        quizStartTime = Date.now();
        questionStartTimes[currentIndex] = Date.now();

        timerInterval = setInterval(() => {
            timeLeft--;
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                submitQuiz();
                return;
            }
            const m = Math.floor(timeLeft / 60);
            const s = timeLeft % 60;
            const display = document.getElementById('timerDisplay');
            if (display) display.textContent = `${m}:${s.toString().padStart(2, '0')}`;

            const timer = document.getElementById('quizTimer');
            if (timer) {
                if (timeLeft <= 30) timer.className = 'quiz-timer danger';
                else if (timeLeft <= 120) timer.className = 'quiz-timer warning';
            }
        }, 1000);
    }

    // startQuiz defined at top

    // Initialize first question view but don't start timer yet
    // questionStartTimes[0] will be set in startTimer
    // We need to show the functionality is ready (if needed)
    // But since HTML defaults (display:none except first) are fine, we just wait.

    // Make functions global
    window.selectOption = function (btn, qIndex) {
        const q = document.querySelector(`.quiz-question[data-index="${qIndex}"]`);
        q.querySelectorAll('.quiz-option').forEach(o => o.classList.remove('selected'));
        btn.classList.add('selected');
        answers[qIndex] = btn.getAttribute('data-option');
        // Update dot
        const dots = document.querySelectorAll('.quiz-dot');
        if (dots[qIndex]) dots[qIndex].classList.add('answered');
    };

    function showQuestion(index) {
        // Save time for current question
        if (questionStartTimes[currentIndex]) {
            questionTimes[currentIndex] += (Date.now() - questionStartTimes[currentIndex]) / 1000;
        }
        currentIndex = index;
        questionStartTimes[currentIndex] = Date.now();

        document.querySelectorAll('.quiz-question').forEach(q => q.style.display = 'none');
        document.querySelector(`.quiz-question[data-index="${index}"]`).style.display = 'block';

        document.getElementById('questionCounter').textContent = `${index + 1}/${QUIZ_DATA.totalQuestions}`;
        document.getElementById('prevBtn').disabled = (index === 0);

        const isLast = (index === QUIZ_DATA.totalQuestions - 1);
        document.getElementById('nextBtn').style.display = isLast ? 'none' : '';
        document.getElementById('submitBtn').style.display = isLast ? '' : 'none';

        document.querySelectorAll('.quiz-dot').forEach((d, i) => {
            d.classList.toggle('active', i === index);
        });

        // Update Gamified Progress Bar
        const progress = document.getElementById('progressBar');
        if (progress) {
            const pct = ((index + 1) / QUIZ_DATA.totalQuestions) * 100;
            progress.style.width = `${pct}%`;
        }
    }

    window.nextQuestion = function () {
        if (currentIndex < QUIZ_DATA.totalQuestions - 1) showQuestion(currentIndex + 1);
    };
    window.prevQuestion = function () {
        if (currentIndex > 0) showQuestion(currentIndex - 1);
    };
    window.goToQuestion = function (i) { showQuestion(i); };

    window.submitQuiz = function () {
        clearInterval(timerInterval);
        // Save final question time
        if (questionStartTimes[currentIndex]) {
            questionTimes[currentIndex] += (Date.now() - questionStartTimes[currentIndex]) / 1000;
        }

        const totalTime = Math.round((Date.now() - quizStartTime) / 1000);
        const payload = {
            quiz_type: QUIZ_DATA.quizType,
            exam: QUIZ_DATA.exam,
            subject: QUIZ_DATA.subject,
            total_time: totalTime,
            answers: QUIZ_DATA.questions.map((q, i) => ({
                question_id: q.id,
                selected_option: answers[i] || '',
                time_taken: Math.round(questionTimes[i] || 0)
            }))
        };

        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Submitting...';
        }

        fetch('/arena/submit_attempt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(r => r.json())
            .then(res => {
                if (res.success && res.redirect) {
                    window.location.href = res.redirect;
                } else {
                    alert('Submission failed: ' + (res.error || 'Unknown error'));
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🚀 Submit'; }
                }
            })
            .catch(err => {
                console.error('Submit error:', err);
                alert('Network error. Please try again.');
                if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🚀 Submit'; }
            });
    };
})();
