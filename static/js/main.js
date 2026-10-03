// Main client-side scripts for MediCloud Share
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss flash messages after 5 seconds if desired
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});
