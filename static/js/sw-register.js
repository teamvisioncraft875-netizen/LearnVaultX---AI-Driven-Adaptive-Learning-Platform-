// Service Worker Registration
// Only register service worker if it exists and browser supports it

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .catch(err => {
                console.warn('ServiceWorker registration failed:', err);
            });
    });
}
