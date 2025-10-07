// ====================================
// JAVASCRIPT ДЛЯ ГЛАВНОЙ СТРАНИЦЫ
// ====================================

document.addEventListener('DOMContentLoaded', function() {
    initializeChartControls();
    initializeNotifications();
    initializeAnimations();
});

// Управление графиком
function initializeChartControls() {
    const chartBtns = document.querySelectorAll('.chart-btn');
    
    chartBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            chartBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const period = this.dataset.period;
            updateChart(period);
        });
    });
}

function updateChart(period) {
    console.log('Обновление графика для периода:', period);
    // Здесь будет логика обновления графика
}

// Управление уведомлениями
function initializeNotifications() {
    const dismissBtns = document.querySelectorAll('.notification-btn.dismiss');
    
    dismissBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const notification = this.closest('.notification-item');
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            
            setTimeout(() => {
                notification.remove();
                updateNotificationBadge();
            }, 300);
        });
    });
}

function updateNotificationBadge() {
    const badge = document.querySelector('.notification-badge');
    const notifications = document.querySelectorAll('.notification-item');
    
    if (badge) {
        badge.textContent = notifications.length;
        if (notifications.length === 0) {
            badge.style.display = 'none';
        }
    }
}

// Анимации
function initializeAnimations() {
    // Анимация появления карточек
    const cards = document.querySelectorAll('.stat-card, .dashboard-card');
    
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
    
    // Hover эффекты для графика
    const chartBars = document.querySelectorAll('.chart-bar');
    chartBars.forEach(bar => {
        bar.addEventListener('mouseenter', function() {
            const value = this.querySelector('.bar-value');
            if (value) {
                value.style.transform = 'translateX(-50%) scale(1.2)';
                value.style.color = 'var(--primary)';
            }
        });
        
        bar.addEventListener('mouseleave', function() {
            const value = this.querySelector('.bar-value');
            if (value) {
                value.style.transform = 'translateX(-50%) scale(1)';
                value.style.color = 'var(--text-primary)';
            }
        });
    });
}

// Функции действий
function openAddStudent() {
    console.log('Открытие формы добавления студента');
    // Здесь будет логика открытия модального окна
}

function openAddTeacher() {
    console.log('Открытие формы добавления преподавателя');
    // Здесь будет логика открытия модального окна
}

function openAddGroup() {
    console.log('Открытие формы создания группы');
}

function openSchedule() {
    console.log('Переход к расписанию');
}

function openGrades() {
    console.log('Переход к журналу оценок');
}

function openReports() {
    console.log('Переход к отчетам');
}

function openSubjects() {
    console.log('Переход к дисциплинам');
}

function openAddSubject() {
    console.log('Добавление новой дисциплины');
}

function openAllActivity() {
    console.log('Показать всю активность');
}

// Обновление данных в реальном времени (можно добавить позже)
function refreshDashboard() {
    console.log('Обновление данных дашборда');
    // Здесь будет AJAX запрос для обновления данных
}

// Автообновление каждые 5 минут
setInterval(refreshDashboard, 300000);
