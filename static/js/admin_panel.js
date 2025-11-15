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
    
    const sidebar = document.getElementById('sidebar');
    const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
    const SIDEBAR_COLLAPSED_KEY = 'sidebarCollapsed';
    const rootElement = document.documentElement;
    
    function applyStoredSidebarState() {
        if (!sidebar) {
            return;
        }
        if (window.innerWidth < 992) {
            document.body.classList.remove('sidebar-collapsed');
            rootElement.classList.remove('sidebar-prefers-collapsed');
            return;
        }
        const shouldCollapse = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
        document.body.classList.toggle('sidebar-collapsed', shouldCollapse);
        rootElement.classList.toggle('sidebar-prefers-collapsed', shouldCollapse);
    }
    
    applyStoredSidebarState();
    
    function toggleSidebar() {
        if (!sidebar) {
            return;
        }
        if (window.innerWidth < 992) {
            sidebar.classList.toggle('show');
        } else {
            const willCollapse = !document.body.classList.contains('sidebar-collapsed');
            document.body.classList.toggle('sidebar-collapsed', willCollapse);
            rootElement.classList.toggle('sidebar-prefers-collapsed', willCollapse);
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, willCollapse ? 'true' : 'false');
        }
    }
    
    sidebarToggleButtons.forEach(button => {
        button.addEventListener('click', toggleSidebar);
    });
    
    window.addEventListener('resize', function() {
        if (!sidebar) {
            return;
        }
        if (window.innerWidth < 992) {
            document.body.classList.remove('sidebar-collapsed');
            rootElement.classList.remove('sidebar-prefers-collapsed');
        } else {
            sidebar.classList.remove('show');
            applyStoredSidebarState();
        }
    });
});
