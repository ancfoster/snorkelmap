/**
 * Checks if the desired username is available via the SnorkelMap API
 * and adds a feedback span with the result.
 * @param {string} username - Desired username to check, not case sensitive
 */
document.addEventListener('DOMContentLoaded', () => {
    const usernameInput = document.getElementById('id_username');
    if (!usernameInput) return;

    const feedback = document.createElement('span');
    feedback.className = 'sm-signup__username-feedback';
    usernameInput.insertAdjacentElement('afterend', feedback);

    const checkUsername = async (username) => {
        try {
            const response = await fetch(`/api/v1/users/check_username_availability/${username}`);
            const data = await response.json();
            feedback.classList.remove(
                'sm-signup__username-feedback--available',
                'sm-signup__username-feedback--taken'
            );
            if (data.available) {
                feedback.classList.add('sm-signup__username-feedback--available');
                feedback.textContent = '✓ Username available';
            } else {
                feedback.classList.add('sm-signup__username-feedback--taken');
                feedback.textContent = '✗ Username already taken';
            }
        } catch (err) {
            feedback.textContent = '';
        }
    };

    usernameInput.addEventListener('input', () => {
        if (!usernameInput.value.trim()) {
            feedback.textContent = '';
            feedback.classList.remove(
                'sm-signup__username-feedback--available',
                'sm-signup__username-feedback--taken'
            );
        }
    });

    usernameInput.addEventListener('blur', () => {
        const username = usernameInput.value.trim();
        if (username.length >= 3) checkUsername(username);
    });
});