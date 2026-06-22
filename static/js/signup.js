/**
 * Checks if the desired username is available via the SnorkelMap API
 * and adds a feedback span with the result.
 * @param {string} username - Desired username to check, not case sensitive
 */
function validateUsername(username) {
    const emailCheckPattern = /^[^@]+@[^@]+\.[^@]+$/;

    if (emailCheckPattern.test(username)) {
        return 'Username cannot be an email address.';
    }
    if (username.length < 5 || username.length > 20) {
        return 'Username must be between 5 and 20 characters.';
    }
    if (!/^[A-Za-z0-9]+$/.test(username)) {
        return 'Username can only contain letters and numbers.';
    }
    return null;
}


document.addEventListener('DOMContentLoaded', () => {
    const formButton = document.querySelector('#sm-signup-btn');
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
                feedback.textContent = 'Username available!';
            } else {
                feedback.classList.add('sm-signup__username-feedback--taken');
                feedback.textContent = 'Username already taken';
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

        checkErrorExists(usernameInput);

        const error = validateUsername(username);
        if (error) {
            createError(error, usernameInput);
            return;
        }

        checkUsername(username);
    });
});

function createError(message, field) {
    const item = document.createElement('span');
    item.className = 'errorlist';
    item.textContent = message;
    field.insertAdjacentElement('afterend', item);
}

function checkErrorExists(field) {
    const next = field.nextElementSibling;
    if(next && next.classList.contains('errorlist')) {
        next.remove();
    }
}