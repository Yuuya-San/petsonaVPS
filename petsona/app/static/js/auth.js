// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  initFlashMessages();
  initFormValidation();
  initPasswordToggles();
  initPasswordStrength();
  initButtonLoading();
});

// Flash message initialization and handling
function initFlashMessages() {
  const flashMessages = document.querySelectorAll(".flash");
  
  if (flashMessages.length > 0) {
    console.log("Flash messages found:", flashMessages.length);
  }
  
  flashMessages.forEach((flash) => {
    // Make sure the flash message is visible
    flash.style.opacity = "1";
    flash.style.visibility = "visible";
    flash.style.pointerEvents = "auto";
    
    // Close button handler
    const closeBtn = flash.querySelector(".close-flash");
    if (closeBtn) {
      closeBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeFlash(flash);
      });
    }

    // Auto-dismiss after 5 seconds
    const dismissTimeout = setTimeout(() => {
      closeFlash(flash);
    }, 5000);
    
    // Store timeout ID for cleanup if manually closed
    flash.dismissTimeout = dismissTimeout;
  });
}

// Close flash message with animation
function closeFlash(flashElement) {
  if (!flashElement) return;
  
  // Clear auto-dismiss timeout if it exists
  if (flashElement.dismissTimeout) {
    clearTimeout(flashElement.dismissTimeout);
  }
  
  flashElement.style.opacity = "0";
  flashElement.style.transform = "translateY(-10px)";
  setTimeout(() => {
    flashElement.remove();
  }, 300);
}

// Form validation and button state management
function initFormValidation() {
  const emailField = document.getElementById("email");
  const passwordField = document.getElementById("password");
  const password2Field = document.getElementById("password2");
  const submitBtn = document.querySelector(".loading-btn");
  const emailStatus = document.getElementById("email-status");
  const passwordStatus = document.getElementById("password-status");
  const password2Status = document.getElementById("password2-status");

  if (!submitBtn) return;

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function validateEmail() {
    if (!emailField) return true;
    
    const email = emailField.value.trim();
    const isValid = email.length > 0 && emailRegex.test(email);
    
    if (isValid) {
      emailField.classList.add("valid");
      emailField.classList.remove("invalid");
      if (emailStatus) {
        emailStatus.innerHTML = "";
        emailStatus.classList.add("valid");
        emailStatus.classList.remove("invalid");
      }
    } else if (email.length > 0) {
      emailField.classList.add("invalid");
      emailField.classList.remove("valid");
      if (emailStatus) {
        emailStatus.innerHTML = "";
        emailStatus.classList.add("invalid");
        emailStatus.classList.remove("valid");
      }
    } else {
      emailField.classList.remove("valid", "invalid");
      if (emailStatus) {
        emailStatus.innerHTML = "";
        emailStatus.classList.remove("valid", "invalid");
      }
    }
    
    updateButtonState();
    return isValid || !emailField;
  }

  function validatePassword() {
    if (!passwordField) return true;
    
    const password = passwordField.value;
    const isValid = password.length > 0;
    
    if (isValid) {
      passwordField.classList.add("valid");
      passwordField.classList.remove("invalid");
      if (passwordStatus) {
        passwordStatus.innerHTML = "";
        passwordStatus.classList.add("valid");
        passwordStatus.classList.remove("invalid");
      }
    } else if (password.length > 0) {
      passwordField.classList.add("invalid");
      passwordField.classList.remove("valid");
      if (passwordStatus) {
        passwordStatus.innerHTML = "";
        passwordStatus.classList.add("invalid");
        passwordStatus.classList.remove("valid");
      }
    } else {
      passwordField.classList.remove("valid", "invalid");
      if (passwordStatus) {
        passwordStatus.innerHTML = "";
        passwordStatus.classList.remove("valid", "invalid");
      }
    }
    
    updateButtonState();
    return isValid || !passwordField;
  }

  function validatePassword2() {
    if (!password2Field) return true;
    
    const password = passwordField ? passwordField.value : "";
    const password2 = password2Field.value;
    const isValid = password2.length > 0 && password === password2;
    
    if (isValid) {
      password2Field.classList.add("valid");
      password2Field.classList.remove("invalid");
      if (password2Status) {
        password2Status.innerHTML = "";
        password2Status.classList.add("valid");
        password2Status.classList.remove("invalid");
      }
    } else if (password2.length > 0) {
      password2Field.classList.add("invalid");
      password2Field.classList.remove("valid");
      if (password2Status) {
        password2Status.innerHTML = "";
        password2Status.classList.add("invalid");
        password2Status.classList.remove("valid");
      }
    } else {
      password2Field.classList.remove("valid", "invalid");
      if (password2Status) {
        password2Status.innerHTML = "";
        password2Status.classList.remove("valid", "invalid");
      }
    }
    
    updateButtonState();
    return isValid || !password2Field;
  }

  function updateButtonState() {
    let isValid = true;
    
    if (emailField) {
      isValid = isValid && emailField.classList.contains("valid");
    }
    
    if (passwordField) {
      isValid = isValid && passwordField.classList.contains("valid");
    }
    
    if (password2Field) {
      isValid = isValid && password2Field.classList.contains("valid");
    }
    
    if (isValid) {
      submitBtn.disabled = false;
    } else {
      submitBtn.disabled = true;
    }
  }

  // Add event listeners
  if (emailField) {
    emailField.addEventListener("input", validateEmail);
    emailField.addEventListener("blur", validateEmail);
  }
  
  if (passwordField) {
    passwordField.addEventListener("input", validatePassword);
    passwordField.addEventListener("blur", validatePassword);
  }
  
  if (password2Field) {
    password2Field.addEventListener("input", validatePassword2);
    password2Field.addEventListener("blur", validatePassword2);
  }

  // Initial validation
  validateEmail();
  validatePassword();
  validatePassword2();
}

// Password toggle functionality for multiple fields
function initPasswordToggles() {
  const toggleButtons = document.querySelectorAll(".toggle-password");

  toggleButtons.forEach((toggleBtn, index) => {
    const passwordFieldId = index === 0 ? "password" : "password2";
    const passwordField = document.getElementById(passwordFieldId);

    if (!toggleBtn || !passwordField) return;

    // Show/hide toggle based on input value
    passwordField.addEventListener("input", () => {
      if (passwordField.value.length > 0) {
        toggleBtn.classList.add("show");
      } else {
        toggleBtn.classList.remove("show");
      }
    });

    toggleBtn.addEventListener("click", (e) => {
      e.preventDefault();

      const icon = toggleBtn.querySelector("i");

      if (passwordField.type === "password") {
        passwordField.type = "text";
        icon.classList.remove("fa-eye");
        icon.classList.add("fa-eye-slash");
        toggleBtn.setAttribute("aria-label", "Hide password");
      } else {
        passwordField.type = "password";
        icon.classList.remove("fa-eye-slash");
        icon.classList.add("fa-eye");
        toggleBtn.setAttribute("aria-label", "Show password");
      }
    });
  });
}

// Button loading animation handler
function initButtonLoading() {
  const btn = document.querySelector(".loading-btn");
  const form = document.querySelector(".auth-form");

  if (!btn || !form) return;

  // Prevent multiple submissions
  let isSubmitting = false;

  form.addEventListener("submit", (e) => {
    if (isSubmitting || btn.disabled) {
      e.preventDefault();
      return;
    }

    isSubmitting = true;
    
    // Show pet loading overlay
    showPetLoading();
    
    const text = btn.querySelector(".btn-text");
    const loader = btn.querySelector(".loader");

    if (text && loader) {
      btn.disabled = true;
      text.style.display = "none";
      loader.classList.add("show");
    }

    // Optional: Reset after 30 seconds if page doesn't reload
    setTimeout(() => {
      if (isSubmitting && btn.disabled) {
        isSubmitting = false;
        btn.disabled = false;
        hidePetLoading();
        if (text && loader) {
          text.style.display = "inline";
          loader.classList.remove("show");
        }
      }
    }, 30000);
  });

  // Reset if form validation fails
  form.addEventListener("invalid", () => {
    isSubmitting = false;
    btn.disabled = false;
    hidePetLoading();
    const text = btn.querySelector(".btn-text");
    const loader = btn.querySelector(".loader");
    if (text && loader) {
      text.style.display = "inline";
      loader.classList.remove("show");
    }
  }, true);
  
  // Reset if there's a network error
  form.addEventListener("error", () => {
    isSubmitting = false;
    btn.disabled = false;
    hidePetLoading();
    const text = btn.querySelector(".btn-text");
    const loader = btn.querySelector(".loader");
    if (text && loader) {
      text.style.display = "inline";
      loader.classList.remove("show");
    }
  });
}

// Password strength checker
function initPasswordStrength() {
  // Only run on register and reset password pages (where strength meter exists)
  const strengthMeter = document.querySelector(".password-strength-meter");
  if (!strengthMeter) return;

  const passwordField = document.getElementById("password");
  const password2Field = document.getElementById("password2");
  const strengthBar = document.querySelector(".strength-bar");
  const strengthText = document.querySelector(".strength-text");
  const submitBtn = document.querySelector(".loading-btn");
  const requirementsContainer = document.querySelector(".password-requirements");

  if (!passwordField || !strengthBar || !strengthText || !submitBtn) return;

  function calculateStrength(password) {
    let score = 0;
    let requirements = {
      length: password.length >= 8,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /\d/.test(password),
      special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
    };
    
    // Count met requirements
    let metRequirements = Object.values(requirements).filter(Boolean).length;
    
    // Base points per requirement met
    score = metRequirements * 20; // 0-100
    
    // Bonus points for length beyond minimum
    if (password.length >= 12) score += 10;
    if (password.length >= 16) score += 10;
    
    return Math.min(score, 100);
  }

  function getStrengthLevel(strength) {
    if (strength < 60) return { level: "WEAK", width: "25%", color: "#f39c12" };
    if (strength < 80) return { level: "FAIR", width: "50%", color: "#f1c40f" };
    if (strength < 100) return { level: "GOOD", width: "75%", color: "#3498db" };
    return { level: "STRONG", width: "100%", color: "#1b7b36" };
  }

  function updateRequirements(password) {
    if (!requirementsContainer) return;
    
    const requirements = {
      length: password.length >= 8,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /\d/.test(password),
      special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
    };

    const reqIds = {
      length: "req-length",
      uppercase: "req-uppercase",
      lowercase: "req-lowercase",
      number: "req-number",
      special: "req-special"
    };

    // Update requirement checklist
    Object.entries(requirements).forEach(([key, met]) => {
      const elem = document.getElementById(reqIds[key]);
      if (elem) {
        if (met) {
          elem.classList.add("met");
          const icon = elem.querySelector("i");
          if (icon) {
            icon.className = "fas fa-check-circle";
          }
        } else {
          elem.classList.remove("met");
          const icon = elem.querySelector("i");
          if (icon) {
            icon.className = "fas fa-times-circle";
          }
        }
      }
    });
  }

  function updateStrengthMeter() {
    const password = passwordField.value;
    
    if (password.length === 0) {
      strengthMeter.classList.remove("show");
      if (requirementsContainer) requirementsContainer.classList.remove("show");
      return;
    }
    
    strengthMeter.classList.add("show");
    if (requirementsContainer) requirementsContainer.classList.add("show");
    
    // Update requirements checklist
    updateRequirements(password);
    
    const strength = calculateStrength(password);
    const { level, width, color } = getStrengthLevel(strength);
    
    // Update bar width and color
    strengthBar.style.width = width;
    strengthBar.className = "strength-bar";
    
    if (level === "WEAK") strengthBar.classList.add("weak");
    else if (level === "FAIR") strengthBar.classList.add("fair");
    else if (level === "GOOD") strengthBar.classList.add("good");
    else if (level === "STRONG") strengthBar.classList.add("strong");
    
    // Update text
    strengthText.textContent = level;
    strengthText.className = "strength-text";
    if (level === "WEAK") strengthText.classList.add("weak");
    else if (level === "FAIR") strengthText.classList.add("fair");
    else if (level === "GOOD") strengthText.classList.add("good");
    else if (level === "STRONG") strengthText.classList.add("strong");
    
    // Update button state if password2 field exists
    if (password2Field) {
      updateButtonState();
    }
  }

  function updateButtonState() {
    const password = passwordField.value;
    const password2 = password2Field.value;
    const strength = calculateStrength(password);
    
    // Require STRONG password (100 = all 5 requirements met: 8+ chars, uppercase, lowercase, number, special)
    const isPasswordValid = strength === 100;
    const isPassword2Valid = password2.length > 0 && password === password2;
    
    // Also check email if it exists
    const emailField = document.getElementById("email");
    let isEmailValid = true;
    if (emailField) {
      isEmailValid = emailField.classList.contains("valid");
    }
    
    if (isEmailValid && isPasswordValid && isPassword2Valid) {
      submitBtn.disabled = false;
    } else {
      submitBtn.disabled = true;
    }
  }

  passwordField.addEventListener("input", updateStrengthMeter);
}
