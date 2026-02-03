document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('mainForm');

  const statusInput = document.getElementById("status");
  const statusButtons = document.querySelectorAll(".status-btn");
  const statusBar = document.querySelector(".status-bar");

  const participantId = document.getElementById('participant_id');
  const lastname = document.getElementById('lastname');
  const firstname = document.getElementById('firstname');
  const email = document.getElementById('email');
  const phone = document.getElementById('phone');
  const phoneLabel = document.getElementById('phone-label');

  const grade = document.getElementById('grade');
  const school = document.getElementById('school');

  const results = document.getElementById('results');
  const note = document.getElementById('note');

  const h2 = document.querySelector('h2');

  // Buttons (same ids as your template)
  const buttons_edit = document.getElementById('buttons_edit');
  const button_back = document.getElementById('button_back');
  const button_cancel = document.getElementById('button_cancel');

  const statusMap = {
    "Лид": "Лид",
    "Акт": "Акт",
    "Арх": "Арх",
  };



  //Populate a client card on the load
  block_edit();
  existsWhatsapp();

  function allow_edit() {
    lastname.disabled = false;
    firstname.disabled = false;
    email.disabled = false;
    phone.disabled = false;
    grade.disabled = false;
    school.disabled = false;
    results.disabled = false;
    note.disabled = false;

    buttons_edit.style.display = 'flex';
    button_back.style.display = 'none';

    // click handler
    statusBar.classList.add('choosable');

    statusButtons.forEach(btn => {
      btn.addEventListener("click", statusClickHandler);
    });


    button_cancel.addEventListener('click', (event) => {
      event.preventDefault();
      block_edit();
    });
  }

  function block_edit() {
    // Populate inputs with values
    participantId.innerHTML = `<p><b>Participant ID:</b> ${client.participant_id}</p>`;
    lastname.value = client.last_name ?? '';
    firstname.value = client.first_name ?? '';
    email.value = client.email ?? '';
    phone.value = client.phone ?? '';
    grade.value = client.grade ?? '';
    school.value = client.school ?? '';
    results.value = client.results ?? '';
    note.value = client.note ?? '';

    statusBar.classList.remove('choosable');

    // reset first
    statusButtons.forEach(b => b.classList.remove("active"));

    const current = client.status || "Лид";

    statusButtons.forEach(btn => {
      if (btn.dataset.status === current) {
        btn.classList.add("active");
      }
      btn.removeEventListener("click", statusClickHandler);
    });

    statusInput.value = current;



    // Disable all inputs
    lastname.disabled = true;
    firstname.disabled = true;
    email.disabled = true;
    phone.disabled = true;
    grade.disabled = true;
    school.disabled = true;
    results.disabled = true;
    note.disabled = true;
    // Reset validations
    [
      lastname,
      firstname,
      email,
      phone,
      grade,
      school,
      results,
      note,
    ].forEach(setDefault);

    buttons_edit.style.display = 'none';
    button_back.style.display = 'block';

    // Click title to edit
    h2.addEventListener('click', () => {
      h2.classList.remove('edit');
      allow_edit();
    });
  }

  function statusClickHandler(e) {
    const btn = e.currentTarget;

    statusButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    statusInput.value = btn.dataset.status;

    console.log("STATUS:", statusInput.value);
  }

  // Submit with validation
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (checkInputs()) form.submit();
  });

  // Sanitizers
  lastname.addEventListener('input', () => {
    lastname.value = lastname.value.replace(
      /[^a-zA-Zа-яА-ЯёЁәіңғүұқөһӘІҢҒҮҰҚӨҺ-]/g,
      ''
    );
  });

  firstname.addEventListener('input', () => {
    firstname.value = firstname.value.replace(
      /[^a-zA-Zа-яА-ЯёЁәіңғүұқөһӘІҢҒҮҰҚӨҺ-]/g,
      ''
    );
  });

  grade.addEventListener('input', () => {
    grade.value = grade.value.replace(/[^0-9]/g, '');
    
    if (parseInt(grade.value, 10) > 13) {
      grade.value = '13';
    }
  });

  phone.addEventListener('input', existsWhatsapp);

  // WhatsApp availability check (kept from your logic)
  function existsWhatsapp() {
    if (isPhone(phone.value)) {
      fetch(`/wa_exists_one/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({ phone: phone.value }),
      })
        .then((response) => response.json())
        .then((data) => {
          phoneLabel.innerText = data.exists
            ? 'Номер Телефона | WhatsApp доступен'
            : 'Номер Телефона | WhatsApp не доступен';
        })
        .catch((error) => {
          console.error('Error:', error);
          alert('Произошла ошибка!');
        });
    } else {
      phoneLabel.innerText = 'Номер Телефона';
    }
  }

  // Phone mask (same)
  var maskOptions = { mask: '+7 (000) 000-00-00', lazy: false };
  var mask = new IMask(phone, maskOptions);

  function checkInputs() {
    let isValid = true;

    validateField(lastname, lastname.value.trim() !== '', 'Это поле не может быть пустым');
    validateField(firstname, firstname.value.trim() !== '', 'Это поле не может быть пустым');

    // email is optional
    validateField(email, isEmailOrEmpty(email.value.trim()), 'Некорректный email');

    validateField(phone, isPhone(phone.value.trim()), 'Некорректный телефон');

    validateField(grade, isPositiveInt(grade.value), 'Укажите класс числом');
    validateField(school, school.value.trim() !== '', 'Это поле не может быть пустым');

    validateField(results, results.value.trim() !== '', 'Results не может быть пустым');

    // note optional
    validateField(note, true, '');

    document.querySelectorAll('.form-control').forEach((control) => {
      if (control.classList.contains('error')) isValid = false;
    });

    return isValid;
  }

  function validateField(input, condition, errorMessage) {
    if (condition) setSuccess(input);
    else setError(input, errorMessage);
  }

  function setError(input, message) {
    const formControl = input.parentElement;
    const icon = formControl.querySelector('.icon');
    formControl.className = 'form-control error';
    if (icon) icon.className = 'icon fas fa-times-circle';
    input.placeholder = message;
  }

  function setSuccess(input) {
    const formControl = input.parentElement;
    const icon = formControl.querySelector('.icon');
    formControl.className = 'form-control success';
    if (icon) icon.className = 'icon fas fa-check-circle';
  }

  function setDefault(input) {
    const formControl = input.parentElement;
    const icon = formControl.querySelector('.icon');
    formControl.className = 'form-control';
    if (icon) icon.className = 'icon';
  }

  function isPhone(value) {
    // Keep it permissive because mask adds symbols
    const digits = value.replace(/\D/g, '');
    return digits.length >= 11;
  }

  function isPositiveInt(value) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) && n > 0;
  }

  function isEmailOrEmpty(value) {
    if (!value) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }
});