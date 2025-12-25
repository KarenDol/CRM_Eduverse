document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('profile-form');
    const actionButtons = document.querySelector('.action-buttons');
    const editButtons = document.querySelectorAll('.edit-button');
    const passwordToggles = document.querySelectorAll('.password-toggle');
    const resetButton = document.querySelector('.btn-reset');
    const saveButton = document.querySelector('.btn-save');
    const avatarContainer = document.querySelector('.avatar-container');
    const avatarImage = document.getElementById('avatar-image');
    const fileInput = document.getElementById("file-Input");
    const phoneInput = document.getElementById('phone');

    let phoneMask;

    function applyPhoneMask() {
        phoneMask = IMask(phoneInput, {
            mask: '+{7} (000) 000 0000'
        });
    }

    phoneInput.disabled ? phoneMask?.destroy() : applyPhoneMask();

    let originalData = {
        username: '',
        email: '',
        phone: '',
        avatarSrc: ''
    };

    function initForm() {
        const userData = fetchUserData();
        for (const [key, value] of Object.entries(userData)) {
            const input = document.getElementById(key);
            if (input) {
                input.value = value;
                originalData[key] = value;
            }
        }
        console.log(`serve_static for ${userData.avatarSrc}`);
        avatarImage.src = '/api/serve_static/' + userData.avatarSrc;
        originalData.avatarSrc = userData.avatarSrc;
    }

    // проверка изменений в форме
    function checkFormChanged() {
        const hasChanges = Object.keys(originalData).some(key => {
            if (key === 'avatarSrc') {
                return originalData[key] !== avatarImage.src;
            }
            const input = document.getElementById(key);
            return input && input.value !== originalData[key];
        }) || document.getElementById('old-password').value || document.getElementById('new-password').value;


        // если есть изменения, сбросить и сохранить
        resetButton.disabled = !hasChanges;
        saveButton.disabled = !hasChanges;
    }

    function updateOriginalData() {
        for (const key of Object.keys(originalData)) {
            if (key === 'avatarSrc') {
                originalData[key] = avatarImage.src;
            } else {
                const input = document.getElementById(key);
                if (input) {
                    originalData[key] = input.value;
                }
            }
        }
    }

    initForm();

    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const field = this.dataset.field;
            const input = document.getElementById(field);
            input.disabled = !input.disabled;
            if (!input.disabled) {
                input.focus();
                // Re-apply the mask when enabling the input field
                if (field === 'phone') {
                    applyPhoneMask(); // Ensure phone mask is applied
                }
            } else {
                if (field === 'phone') {
                    phoneMask.destroy(); // Destroy mask when input is disabled
                }
            }
            checkFormChanged();
        });
    });

    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.closest('.password-input').querySelector('input');
            const type = input.type === 'password' ? 'text' : 'password';
            input.type = type;
            this.innerHTML = type === 'password' 
                ? '<svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>'
                : '<svg viewBox="0 0 24 24"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>';
        });
    });

    form.addEventListener('input', checkFormChanged);

    form.addEventListener('submit', function(e) {
        console.log("Форма Успешно Отправлена");
        e.preventDefault();
        const formData = new FormData();
        
        formData.append('username', document.getElementById('username').value);
        formData.append('email', document.getElementById('email').value);
        formData.append('phone', document.getElementById('phone').value);
        formData.append('oldPassword', document.getElementById('old-password').value);
        formData.append('newPassword', document.getElementById('new-password').value);

        const file = fileInput.files[0];
        if (file) {
            console.log(file.name);
            formData.append('avatar', file);
        }

        fetch('/user_settings/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value // CSRF token for security
            },
            body: formData
        })
        .then(response => {
            if (response.ok) {
                // Redirect on success
                window.location.href = '/user_settings/';
            } else {
                console.error('Error submitting form:', response.statusText);
                alert('An error occurred while updating settings. Please try again.');
            }
        })
        // после успешной отправки обновляем ориг данные
    });

    resetButton.addEventListener('click', function() {
        for (const [key, value] of Object.entries(originalData)) {
            if (key === 'avatarSrc') {
                console.log(`serve_static for ${value}`);
                avatarImage.src = '/api/serve_static/' + value;
            } else {
                const input = document.getElementById(key);
                if (input) {
                    input.value = value;
                    input.disabled = true;
                }
            }
        }
        document.getElementById('old-password').value = '';
        document.getElementById('new-password').value = '';
        actionButtons.style.display = 'none';
    });

    avatarContainer.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                avatarImage.src = e.target.result;
                checkFormChanged(); // чекаем изменения после загрузки нового аватара
            }
            reader.readAsDataURL(file);
        }
    });
});