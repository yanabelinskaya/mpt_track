window.studentJournalUI = window.studentJournalUI || {};

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

    window.studentJournalUI.toggleTheme = function(forceTheme) {
        const currentTheme = htmlElement.getAttribute('data-bs-theme');
        const nextTheme = forceTheme || (currentTheme === 'dark' ? 'light' : 'dark');
        setTheme(nextTheme);
    };

    window.studentJournalUI.getTheme = function() {
        return htmlElement.getAttribute('data-bs-theme');
    };
    
    // Обработчик переключателя
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            window.studentJournalUI.toggleTheme();
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

    window.studentJournalUI.toggleSidebar = toggleSidebar;
    
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
    initHotkeys();

    const hotkeyGuideButton = document.getElementById('hotkeyGuideButton');
    if (hotkeyGuideButton) {
        hotkeyGuideButton.addEventListener('click', () => {
            if (window.studentJournalUI.showHotkeySheet) {
                window.studentJournalUI.showHotkeySheet();
            }
        });
    }

    function initHotkeys() {
        if (!document.body.dataset.hotkeys) {
            return;
        }

        const hotkeyRegistry = [];
        const hotkeyToast = createHotkeyToast();
        const cheatSheet = createCheatSheet();
        const cheatSheetList = cheatSheet.querySelector('[data-hotkey-list]');
        let cheatSheetVisible = false;
        let toastTimer;
        let focusTimer;
        let currentlyHighlighted;

        const bootstrapModal = window.bootstrap ? window.bootstrap.Modal : null;

        document.addEventListener('keydown', function(event) {
            const target = event.target;
            const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable);

            for (const entry of hotkeyRegistry) {
                if (!entry.allowInInputs && isInput) {
                    continue;
                }
                if (!matchesCombo(event, entry.parsed)) {
                    continue;
                }
                const handled = entry.handler(event);
                if (handled !== false) {
                    event.preventDefault();
                    break;
                }
            }
        }, true);

        const coreHotkeys = [
            {
                combo: 'Ctrl+Slash',
                description: 'Открыть/закрыть список горячих клавиш',
                handler: () => toggleCheatSheet(),
                allowInInputs: true
            },
            {
                combo: 'Escape',
                description: 'Закрыть всплывающие окна или подсказки',
                handler: () => closePanels(),
                allowInInputs: true
            },
            {
                combo: 'Ctrl+KeyB',
                description: 'Свернуть или раскрыть боковую панель',
                handler: () => {
                    toggleSidebar();
                    showToast('Боковая панель переключена');
                    return true;
                }
            },
            {
                combo: 'Ctrl+KeyT',
                description: 'Переключить тему оформления',
                handler: () => {
                    window.studentJournalUI.toggleTheme();
                    const theme = window.studentJournalUI.getTheme();
                    showToast(theme === 'dark' ? 'Включена тёмная тема' : 'Включена светлая тема');
                },
                allowInInputs: true
            },
            {
                combo: 'Ctrl+Shift+KeyF',
                description: 'Поставить фокус в поисковой строке',
                handler: () => focusSearchField(),
                allowInInputs: true
            },
            {
                combo: 'Ctrl+Enter',
                description: 'Отправить активную форму/модальное окно',
                handler: () => submitCurrentForm(),
                allowInInputs: true
            },
            {
                combo: 'Ctrl+Shift+KeyH',
                description: 'Перейти на панель управления',
                handler: () => jumpToDashboard()
            },
            {
                combo: 'Ctrl+Alt+KeyQ',
                description: 'Быстрый выход из аккаунта',
                handler: () => triggerLogout(),
                allowInInputs: true
            }
        ];

        coreHotkeys.forEach(registerHotkey);
        bindDeclarativeHotkeys();
        observeHotkeyMutations();
        renderCheatSheet();

        function registerHotkey(config) {
            if (!config || !config.combo || typeof config.handler !== 'function') {
                return;
            }
            const parsed = parseCombo(config.combo);
            if (!parsed) {
                return;
            }
            const entry = {
                combo: config.combo,
                description: config.description || 'Без описания',
                handler: config.handler,
                allowInInputs: Boolean(config.allowInInputs),
                showInSheet: config.showInSheet !== false,
                parsed,
                displayParts: parsed.displayParts
            };
            hotkeyRegistry.push(entry);
        }

        function bindDeclarativeHotkeys(root = document) {
            const targets = [];
            if (root !== document && root.nodeType === 1 && root.hasAttribute('data-hotkey')) {
                targets.push(root);
            }
            const scopedElements = typeof root.querySelectorAll === 'function'
                ? root.querySelectorAll('[data-hotkey]')
                : [];
            scopedElements.forEach(node => targets.push(node));

            let registeredAny = false;
            targets.forEach(element => {
                if (element.dataset.hotkeyBound === 'true') {
                    return;
                }
                const combo = element.dataset.hotkey;
                if (!combo) {
                    return;
                }
                const description = element.dataset.hotkeyDescription || element.getAttribute('title') || (element.textContent || '').trim() || 'Действие';
                registerHotkey({
                    combo,
                    description,
                    handler: () => {
                        if (typeof element.click === 'function') {
                            element.click();
                        } else {
                            element.focus();
                        }
                        return true;
                    }
                });
                element.dataset.hotkeyBound = 'true';
                registeredAny = true;
            });

            if (registeredAny) {
                renderCheatSheet();
            }
        }

        function observeHotkeyMutations() {
            const observer = new MutationObserver(mutations => {
                let shouldRebind = false;
                outer: for (const mutation of mutations) {
                    if (!mutation.addedNodes || !mutation.addedNodes.length) {
                        continue;
                    }
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType !== 1) {
                            continue;
                        }
                        const element = node;
                        if (typeof element.hasAttribute === 'function' && element.hasAttribute('data-hotkey')) {
                            shouldRebind = true;
                            break outer;
                        }
                        if (typeof element.querySelector === 'function' && element.querySelector('[data-hotkey]')) {
                            shouldRebind = true;
                            break outer;
                        }
                    }
                }
                if (shouldRebind) {
                    bindDeclarativeHotkeys();
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }

        function focusSearchField() {
            const selectors = [
                '.search-field input',
                'input.search-field',
                'input[type="search"]',
                '[data-hotkey-focus="search"]'
            ];
            let field = null;
            for (const selector of selectors) {
                const candidate = document.querySelector(selector);
                if (candidate) {
                    field = candidate;
                    break;
                }
            }
            if (!field) {
                showToast('Поле поиска не найдено');
                return false;
            }
            field.focus();
            if (typeof field.select === 'function') {
                field.select();
            }
            highlightElement(field);
            showToast('Фокус в поиске');
            return true;
        }

        function submitCurrentForm() {
            const activeElement = document.activeElement;
            if (!activeElement) {
                showToast('Нет активной формы');
                return false;
            }
            const form = activeElement.form || activeElement.closest('form');
            if (!form) {
                showToast('Нет формы для отправки');
                return false;
            }
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
            showToast('Форма отправлена');
            return true;
        }

        function jumpToDashboard() {
            const dashboardLink = document.querySelector('[data-hotkey="Alt+Digit1"]');
            if (!dashboardLink) {
                showToast('Ссылка на панель не найдена');
                return false;
            }
            dashboardLink.click();
            showToast('Открываем панель управления');
            return true;
        }

        function triggerLogout() {
            const logoutForm = document.getElementById('logoutForm');
            if (!logoutForm) {
                showToast('Форма выхода не найдена');
                return false;
            }
            if (typeof logoutForm.requestSubmit === 'function') {
                logoutForm.requestSubmit();
            } else {
                logoutForm.submit();
            }
            showToast('Выходим из аккаунта...');
            return true;
        }

        function closePanels() {
            let closed = false;
            if (cheatSheetVisible) {
                toggleCheatSheet(false);
                closed = true;
            }
            if (closeActiveModal()) {
                closed = true;
            }
            return closed;
        }

        function closeActiveModal() {
            const openedModal = document.querySelector('.modal.show');
            if (!openedModal || !bootstrapModal) {
                return false;
            }
            const instance = bootstrapModal.getInstance(openedModal) || new bootstrapModal(openedModal);
            instance.hide();
            return true;
        }

        function toggleCheatSheet(forceState) {
            const shouldShow = typeof forceState === 'boolean' ? forceState : !cheatSheetVisible;
            cheatSheetVisible = shouldShow;
            cheatSheet.classList.toggle('show', shouldShow);
            if (shouldShow) {
                renderCheatSheet();
            }
            return true;
        }

        function renderCheatSheet() {
            if (!cheatSheetList) {
                return;
            }
            cheatSheetList.innerHTML = '';
            hotkeyRegistry.filter(entry => entry.showInSheet !== false).forEach(entry => {
                const row = document.createElement('div');
                row.className = 'hotkey-overlay__row';

                const label = document.createElement('div');
                label.className = 'hotkey-overlay__label';
                label.textContent = entry.description;

                const badges = document.createElement('div');
                badges.className = 'hotkey-badges';
                entry.displayParts.forEach(part => {
                    const badge = document.createElement('span');
                    badge.className = 'hotkey-badge';
                    badge.textContent = part;
                    badges.appendChild(badge);
                });

                row.appendChild(label);
                row.appendChild(badges);
                cheatSheetList.appendChild(row);
            });
        }

        function showToast(message) {
            if (!hotkeyToast) {
                return;
            }
            hotkeyToast.textContent = message;
            hotkeyToast.classList.add('show');
            clearTimeout(toastTimer);
            toastTimer = setTimeout(() => {
                hotkeyToast.classList.remove('show');
            }, 1600);
        }

        function highlightElement(element) {
            if (!element) {
                return;
            }
            if (currentlyHighlighted && currentlyHighlighted !== element) {
                currentlyHighlighted.classList.remove('hotkey-focus-ring');
            }
            currentlyHighlighted = element;
            element.classList.add('hotkey-focus-ring');
            clearTimeout(focusTimer);
            focusTimer = setTimeout(() => {
                element.classList.remove('hotkey-focus-ring');
                currentlyHighlighted = null;
            }, 1500);
        }

        function createHotkeyToast() {
            const toast = document.createElement('div');
            toast.className = 'hotkey-toast';
            toast.setAttribute('role', 'status');
            toast.setAttribute('aria-live', 'polite');
            document.body.appendChild(toast);
            return toast;
        }

        function createCheatSheet() {
            const overlay = document.createElement('div');
            overlay.className = 'hotkey-overlay';
            overlay.innerHTML = `
                <div class="hotkey-overlay__card" role="dialog" aria-modal="true" aria-label="Горячие клавиши">
                    <div class="hotkey-overlay__header">
                        <p class="hotkey-overlay__title">Горячие клавиши</p>
                        <button type="button" class="btn-close" data-close-hotkey-sheet aria-label="Закрыть"></button>
                    </div>
                    <div class="hotkey-overlay__body">
                        <div class="hotkey-overlay__list" data-hotkey-list></div>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', event => {
                if (event.target === overlay || event.target.hasAttribute('data-close-hotkey-sheet')) {
                    toggleCheatSheet(false);
                }
            });
            return overlay;
        }

        window.studentJournalUI.showHotkeySheet = () => toggleCheatSheet(true);
        window.studentJournalUI.hideHotkeySheet = () => toggleCheatSheet(false);

        function parseCombo(combo) {
            const parts = combo.split('+').map(part => part.trim()).filter(Boolean);
            if (!parts.length) {
                return null;
            }
            const descriptor = {
                ctrl: false,
                alt: false,
                shift: false,
                meta: false,
                key: null,
                code: null,
                parts,
                displayParts: parts.map(formatComboPart)
            };
            parts.forEach(part => {
                const lower = part.toLowerCase();
                if (lower === 'ctrl' || lower === 'control') {
                    descriptor.ctrl = true;
                } else if (lower === 'alt' || lower === 'option') {
                    descriptor.alt = true;
                } else if (lower === 'shift') {
                    descriptor.shift = true;
                } else if (lower === 'cmd' || lower === 'meta' || lower === 'win') {
                    descriptor.meta = true;
                } else if (/^(key|digit|numpad|arrow|f\d+)/i.test(part) || isSpecialCode(part)) {
                    descriptor.code = part.toLowerCase();
                } else {
                    descriptor.key = lower.length === 1 ? lower : lower;
                }
            });
            if (!descriptor.key && !descriptor.code) {
                descriptor.key = parts[parts.length - 1].toLowerCase();
            }
            return descriptor;
        }

        function isSpecialCode(part) {
            const specials = ['slash', 'backslash', 'space', 'enter', 'escape', 'minus', 'equal'];
            return specials.includes(part.toLowerCase());
        }

        function matchesCombo(event, descriptor) {
            if (!descriptor) {
                return false;
            }
            if (!!descriptor.ctrl !== event.ctrlKey) {
                return false;
            }
            if (!!descriptor.alt !== event.altKey) {
                return false;
            }
            if (!!descriptor.shift !== event.shiftKey) {
                return false;
            }
            if (!!descriptor.meta !== event.metaKey) {
                return false;
            }
            if (descriptor.code) {
                return event.code.toLowerCase() === descriptor.code;
            }
            if (descriptor.key) {
                const key = (event.key || '').toLowerCase();
                return key === descriptor.key;
            }
            return false;
        }

        function formatComboPart(part) {
            const lower = part.toLowerCase();
            if (lower === 'ctrl' || lower === 'control') {
                return 'Ctrl';
            }
            if (lower === 'alt' || lower === 'option') {
                return 'Alt';
            }
            if (lower === 'shift') {
                return 'Shift';
            }
            if (lower === 'meta' || lower === 'cmd' || lower === 'win') {
                return 'Cmd';
            }
            if (/^key[a-z]$/i.test(part)) {
                return part.slice(3).toUpperCase();
            }
            if (/^digit\d$/i.test(part)) {
                return part.slice(5);
            }
            if (/^numpad\d$/i.test(part)) {
                return 'Num ' + part.slice(6);
            }
            if (/^f\d+$/i.test(part)) {
                return part.toUpperCase();
            }
            if (lower === 'slash') {
                return '/';
            }
            if (lower === 'enter') {
                return 'Enter';
            }
            if (lower === 'space') {
                return 'Space';
            }
            if (lower === 'escape') {
                return 'Esc';
            }
            return part.toUpperCase();
        }
    }
});
