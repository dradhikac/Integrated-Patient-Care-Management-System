// IPCMS Main JavaScript Utilities

document.addEventListener('DOMContentLoaded', function() {
    // Quick Demo Account Filler for Viva / Testing
    const demoPills = document.querySelectorAll('.demo-pill');
    demoPills.forEach(pill => {
        pill.addEventListener('click', function() {
            const email = this.getAttribute('data-email');
            const password = this.getAttribute('data-password');
            
            const emailInput = document.getElementById('email');
            const passwordInput = document.getElementById('password');
            
            if (emailInput && passwordInput) {
                emailInput.value = email;
                passwordInput.value = password;
                
                // Add highlight effect
                emailInput.classList.add('is-valid');
                passwordInput.classList.add('is-valid');
                setTimeout(() => {
                    emailInput.classList.remove('is-valid');
                    passwordInput.classList.remove('is-valid');
                }, 1500);
            }
        });
    });

    // Toggle Password Visibility
    const togglePasswordBtn = document.getElementById('togglePassword');
    if (togglePasswordBtn) {
        togglePasswordBtn.addEventListener('click', function() {
            const passwordInput = document.getElementById('password');
            const icon = this.querySelector('i');
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.classList.replace('bi-eye', 'bi-eye-slash');
            } else {
                passwordInput.type = 'password';
                icon.classList.replace('bi-eye-slash', 'bi-eye');
            }
        });
    }

    // Auto-dismiss Alerts after 8 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 8000);
    });
});
