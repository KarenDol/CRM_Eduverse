function togglePasswordVisibility() {
    var passwordInput = document.getElementById('password');
    var togglePasswordButton = document.querySelector('.toggle-password');
  
    if (passwordInput.type === "password") {
      passwordInput.type = "text";
      togglePasswordButton.classList.remove('fa-eye-slash');
      togglePasswordButton.classList.add('fa-eye');
    } else {
      passwordInput.type = "password";
      togglePasswordButton.classList.remove('fa-eye');
      togglePasswordButton.classList.add('fa-eye-slash');
    }
  }