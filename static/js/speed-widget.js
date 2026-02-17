/**
 * Draggable Speed Widget
 * Features: Drag & Drop, Persist Position, Speed Test, Glassmorphism
 */

(function () {
    // 1. Inject CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/speed-widget.css?v=' + new Date().getTime();
    document.head.appendChild(link);

    // 2. Create Widget HTML
    const widget = document.createElement('div');
    widget.id = 'speed-widget';
    widget.innerHTML = `
        <span class="speed-icon">📡</span>
        <span class="speed-text">
            <span class="speed-value">...</span>
            <span class="speed-unit">kbps</span>
        </span>
    `;
    document.body.appendChild(widget);

    // 3. Variables
    let isDragging = false;
    let startX, startY, initialLeft, initialTop;
    const padding = 20; // Edge padding

    // 4. Load Saved Position
    const savedPos = localStorage.getItem('speedWidgetPos');
    if (savedPos) {
        try {
            const { top, left } = JSON.parse(savedPos);
            // Ensure within bounds
            const maxLeft = window.innerWidth - widget.offsetWidth - padding;
            const maxTop = window.innerHeight - widget.offsetHeight - padding;

            const safeLeft = Math.min(Math.max(padding, left), maxLeft);
            const safeTop = Math.min(Math.max(padding, top), maxTop);

            widget.style.left = safeLeft + 'px';
            widget.style.top = safeTop + 'px';
            widget.style.bottom = 'auto'; // Override default bottom/right
            widget.style.right = 'auto';
        } catch (e) {
            console.error('Error restoring widget pos:', e);
        }
    }

    // 5. Drag Logic
    widget.addEventListener('mousedown', startDrag);
    widget.addEventListener('touchstart', startDrag, { passive: false });

    function startDrag(e) {
        isDragging = true;

        // Get mouse/touch pos
        const clientX = e.clientX || e.touches[0].clientX;
        const clientY = e.clientY || e.touches[0].clientY;

        // Get initial widget pos
        const rect = widget.getBoundingClientRect();
        startX = clientX;
        startY = clientY;
        initialLeft = rect.left;
        initialTop = rect.top;

        // Prevent text selection
        e.preventDefault();

        document.addEventListener('mousemove', onDrag);
        document.addEventListener('mouseup', stopDrag);
        document.addEventListener('touchmove', onDrag, { passive: false });
        document.addEventListener('touchend', stopDrag);
    }

    function onDrag(e) {
        if (!isDragging) return;

        const clientX = e.clientX || (e.touches ? e.touches[0].clientX : 0);
        const clientY = e.clientY || (e.touches ? e.touches[0].clientY : 0);

        const dx = clientX - startX;
        const dy = clientY - startY;

        let newLeft = initialLeft + dx;
        let newTop = initialTop + dy;

        // Boundary checks
        const maxLeft = window.innerWidth - widget.offsetWidth - padding;
        const maxTop = window.innerHeight - widget.offsetHeight - padding;

        newLeft = Math.min(Math.max(padding, newLeft), maxLeft);
        newTop = Math.min(Math.max(padding, newTop), maxTop);

        widget.style.left = newLeft + 'px';
        widget.style.top = newTop + 'px';
        widget.style.bottom = 'auto';
        widget.style.right = 'auto';

        e.preventDefault(); // Prevent scrolling on touch
    }

    function stopDrag() {
        if (!isDragging) return;
        isDragging = false;

        // Save position
        const rect = widget.getBoundingClientRect();
        localStorage.setItem('speedWidgetPos', JSON.stringify({
            top: rect.top,
            left: rect.left
        }));

        document.removeEventListener('mousemove', onDrag);
        document.removeEventListener('mouseup', stopDrag);
        document.removeEventListener('touchmove', onDrag);
        document.removeEventListener('touchend', stopDrag);
    }

    // 6. Window Resize Handler
    window.addEventListener('resize', () => {
        const rect = widget.getBoundingClientRect();
        const maxLeft = window.innerWidth - widget.offsetWidth - padding;
        const maxTop = window.innerHeight - widget.offsetHeight - padding;

        if (rect.left > maxLeft || rect.top > maxTop) {
            widget.style.left = Math.min(rect.left, maxLeft) + 'px';
            widget.style.top = Math.min(rect.top, maxTop) + 'px';
        }
    });

    // 7. Speed Test Logic
    const speedValueEl = widget.querySelector('.speed-value');
    const speedUnitEl = widget.querySelector('.speed-unit');

    async function checkSpeed() {
        if (!navigator.onLine) {
            updateUI(0, 'Offline', 'offline');
            return;
        }

        try {
            const startTime = performance.now();
            const fileSize = 50000; // 50KB to fetch

            // Random query param to prevent caching (though header is also set)
            const response = await fetch(`/api/speed-test?size=${fileSize}&t=${startTime}`);
            if (!response.ok) throw new Error('Network error');

            const blob = await response.blob();
            const endTime = performance.now();
            const duration = (endTime - startTime) / 1000; // Seconds

            // Calculate bps: size (bytes) * 8 / time (s)
            const bitsLoaded = fileSize * 8;
            const bps = bitsLoaded / duration;

            // Convert to kbps or mbps
            const kbps = bps / 1024;
            const mbps = kbps / 1024;

            if (mbps >= 1) {
                updateUI(mbps.toFixed(1), 'Mbps', 'fast');
            } else {
                updateUI(kbps.toFixed(0), 'Kbps', 'slow');
            }

        } catch (e) {
            console.error('Speed Widget Error:', e);
            // Try to show more specific error if possible
            if (e.message.includes('Network')) {
                updateUI(0, 'Net Err', 'offline');
            } else {
                updateUI(0, 'JS Err', 'slow');
            }
        }
    }

    function updateUI(value, unit, status) {
        speedValueEl.textContent = value;
        speedUnitEl.textContent = unit;

        widget.classList.remove('offline', 'slow', 'fast');
        if (unit === 'Offline') {
            widget.classList.add('offline');
        } else {
            widget.classList.add(status);
        }
    }

    // 8. Init & Interval
    checkSpeed();
    setInterval(checkSpeed, 5000); // Check every 5s

    // 9. Online/Offline Listeners
    window.addEventListener('online', checkSpeed);
    window.addEventListener('offline', () => updateUI(0, 'Offline', 'offline'));

})();
