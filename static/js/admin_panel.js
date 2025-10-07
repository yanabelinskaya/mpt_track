// Theme Toggle Logic
(function() {
    const htmlElement = document.documentElement;
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    
    function getStoredTheme() {
        return localStorage.getItem('theme');
    }
    
    function getPreferredTheme() {
        const storedTheme = getStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
    function setTheme(theme) {
        htmlElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
        
        if (theme === 'dark') {
            themeIcon.className = 'bi bi-moon-stars';
        } else {
            themeIcon.className = 'bi bi-sun';
        }
    }
    
    // Устанавливаем начальную тему
    setTheme(getPreferredTheme());
    
    // Обработчик переключателя
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = htmlElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });
    }
})();

// Sidebar toggle for mobile
document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
});


document.addEventListener('DOMContentLoaded', function() {
    const sidebarNav = document.querySelector('.sidebar-nav');
    let scrollTimeout;
    
    if (sidebarNav) {
        // Функция обновления теней
        function updateScrollShadows() {
            const scrollTop = sidebarNav.scrollTop;
            const scrollHeight = sidebarNav.scrollHeight;
            const clientHeight = sidebarNav.clientHeight;
            const scrollBottom = scrollHeight - scrollTop - clientHeight;
            
            // Показываем верхнюю тень если прокрутили вниз
            if (scrollTop > 10) {
                sidebarNav.classList.add('can-scroll-up');
            } else {
                sidebarNav.classList.remove('can-scroll-up');
            }
            
            // Показываем нижнюю тень если можно прокрутить еще вниз
            if (scrollBottom > 10) {
                sidebarNav.classList.add('can-scroll-down');
            } else {
                sidebarNav.classList.remove('can-scroll-down');
            }
        }
        
        // Обработчик скролла
        sidebarNav.addEventListener('scroll', function() {
            // Добавляем класс при скролле для эффектов
            this.classList.add('fast-scroll');
            
            // Обновляем тени
            updateScrollShadows();
            
            // Убираем класс через 150мс после окончания скролла
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.classList.remove('fast-scroll');
            }, 150);
        });
        
        // Инициализация теней при загрузке
        setTimeout(() => {
            updateScrollShadows();
        }, 100);
        
        // Плавная прокрутка к активному элементу при загрузке
        const activeLink = sidebarNav.querySelector('.nav-link.active');
        if (activeLink) {
            setTimeout(() => {
                activeLink.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'center' 
                });
            }, 300);
        }
    }
    
    // Остальной код остается прежним...
    document.getElementById('sidebarToggle')?.addEventListener('click', function() {
        document.getElementById('sidebar').classList.toggle('show');
    });
    
    document.addEventListener('click', function(e) {
        const sidebar = document.getElementById('sidebar');
        const toggle = document.getElementById('sidebarToggle');
        
        if (window.innerWidth < 992 && !sidebar.contains(e.target) && !toggle.contains(e.target)) {
            sidebar.classList.remove('show');
        }
    });
});
