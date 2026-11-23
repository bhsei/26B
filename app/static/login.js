const form = document.getElementById('login-form');
const message = document.getElementById('login-status');
const button = document.getElementById('login-btn');
form.addEventListener('submit', async event => {
  event.preventDefault();
  button.disabled = true;
  message.textContent = 'Signing in…';
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-Requested-With': 'OutliersAAC'},
      body: JSON.stringify({
        email: document.getElementById('email').value,
        password: document.getElementById('password').value
      })
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(' ') : data.detail;
      throw new Error(detail || 'Sign-in failed.');
    }
    document.getElementById('password').value = '';
    window.location.assign('/app');
  } catch (error) {
    message.textContent = error.message || 'Could not reach the server. Try again.';
    document.getElementById('password').value = '';
    button.disabled = false;
  }
});
