(function() {
    function getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return decodeURIComponent(value);
            }
        }
        return '';
    }

    function notify(message, type = 'info') {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        } else {
            alert(message);
        }
    }

    async function processRequest(button) {
        const requestId = button.getAttribute('data-password-request-id');
        if (!requestId || !window.PASSWORD_REQUEST_PROCESS_URL) {
            return;
        }

        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Отправка...';

        try {
            const response = await fetch(
                window.PASSWORD_REQUEST_PROCESS_URL.replace('{id}', requestId),
                {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ comment: '' }),
                }
            );

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Не удалось обработать запрос');
            }

            notify(data.message || 'Запрос выполнен', 'success');
            setTimeout(() => window.location.reload(), 800);
        } catch (error) {
            notify(error.message || 'Ошибка обработки запроса', 'danger');
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-password-request-id]').forEach(button => {
            button.addEventListener('click', () => processRequest(button));
        });
    });
})();
