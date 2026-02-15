/**
 * Модуль аутентификации
 * Управляет входом в систему, проверкой токена и отображением модального окна
 */

(function () {
  'use strict';

  const AUTH_API = {
    LOGIN: '/api/auth/login',
    VERIFY: '/api/auth/verify',
    LOGOUT: '/api/auth/logout'
  };

  let isAuthenticated = false;

  /**
   * Проверяет наличие и валидность токена аутентификации
   */
  async function checkAuthentication() {
    try {
      const response = await fetch(AUTH_API.VERIFY, {
        method: 'POST',
        credentials: 'same-origin'
      });

      if (response.ok) {
        const data = await response.json();
        isAuthenticated = data.authenticated === true;
      } else {
        isAuthenticated = false;
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      isAuthenticated = false;
    }

    return isAuthenticated;
  }

  /**
   * Показывает модальное окно аутентификации
   */
  function showAuthModal() {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.classList.remove('hidden');
      // Фокус на поле логина
      setTimeout(() => {
        const usernameField = document.getElementById('auth-username');
        if (usernameField) {
          usernameField.focus();
        }
      }, 100);
    }
  }

  /**
   * Скрывает модальное окно аутентификации
   */
  function hideAuthModal() {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.classList.add('hidden');
    }
  }

  /**
   * Показывает сообщение об ошибке в форме
   */
  function showAuthError(message) {
    const errorEl = document.getElementById('auth-error');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.classList.add('visible');
    }
  }

  /**
   * Скрывает сообщение об ошибке
   */
  function hideAuthError() {
    const errorEl = document.getElementById('auth-error');
    if (errorEl) {
      errorEl.classList.remove('visible');
    }
  }

  /**
   * Обработка отправки формы логина
   */
  async function handleLogin(event) {
    event.preventDefault();

    const usernameField = document.getElementById('auth-username');
    const passwordField = document.getElementById('auth-password');
    const submitBtn = document.getElementById('auth-submit');

    const username = usernameField?.value.trim();
    const password = passwordField?.value.trim();

    if (!username || !password) {
      showAuthError('Заполните все поля');
      return;
    }

    hideAuthError();

    // Блокируем кнопку на время запроса
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Вход...';
    }

    try {
      const response = await fetch(AUTH_API.LOGIN, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          isAuthenticated = true;
          hideAuthModal();

          // Очищаем форму
          if (usernameField) usernameField.value = '';
          if (passwordField) passwordField.value = '';

          // Перезагружаем страницу для инициализации приложения
          window.location.reload();
        } else {
          showAuthError('Ошибка входа');
        }
      } else {
        const data = await response.json().catch(() => ({}));
        showAuthError(data.error || 'Неверный логин или пароль');
      }
    } catch (error) {
      console.error('Login error:', error);
      showAuthError('Ошибка подключения к серверу');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Войти';
      }
    }
  }

  /**
   * Выход из системы
   */
  async function logout() {
    try {
      await fetch(AUTH_API.LOGOUT, {
        method: 'POST',
        credentials: 'same-origin'
      });

      isAuthenticated = false;
      window.location.reload();
    } catch (error) {
      console.error('Logout error:', error);
    }
  }

  /**
   * Инициализация модуля аутентификации
   */
  async function initAuth() {
    // Проверяем авторизацию
    const authenticated = await checkAuthentication();

    if (!authenticated) {
      // Показываем модальное окно
      showAuthModal();
    }

    // Обработчик формы логина
    const loginForm = document.getElementById('auth-form');
    if (loginForm) {
      loginForm.addEventListener('submit', handleLogin);
    }

    // Enter в поле пароля = отправка формы
    const passwordField = document.getElementById('auth-password');
    if (passwordField) {
      passwordField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          handleLogin(e);
        }
      });
    }

    // Запрещаем закрытие модалки кликом вне её
    const overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          // Не закрываем - пользователь должен войти
          e.stopPropagation();
        }
      });
    }
  }

  // Экспортируем API для использования в других модулях
  window.Auth = {
    check: checkAuthentication,
    logout: logout,
    isAuthenticated: () => isAuthenticated
  };

  // Запускаем проверку авторизации при загрузке страницы
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
  } else {
    initAuth();
  }
})();
