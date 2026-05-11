function generatePassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  let pwd = "";
  for (let i = 0; i < 10; i++) {
    pwd += chars[Math.floor(Math.random() * chars.length)];
  }
  const input = document.getElementById("temp-password");
  input.value = pwd;
  input.type = "text";
}

function togglePassword(btn) {
  const input = btn.parentElement.querySelector("input");
  input.type = input.type === "password" ? "text" : "password";
}
