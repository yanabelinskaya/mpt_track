// ====================================
// ОБЩИЙ JAVASCRIPT ДЛЯ ТАБЛИЦ
// ====================================

document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeFilters();
    initializeExport();
    initializeBulkActions();
    initializeAnimations();
});

// Поиск
function initializeSearch() {
    const searchField = document.querySelector('.search-field');
    let searchTimeout;
    
    if (searchField) {
        searchField.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // Можно добавить автоматический поиск
            }, 500);
        });
    }
}

function clearSearch() {
    const searchField = document.querySelector('.search-field');
    const searchForm = document.querySelector('.search-form');
    if (searchField && searchForm) {
        searchField.value = '';
        searchForm.submit();
    }
}

// Фильтры - ИСПРАВЛЕННАЯ ВЕРСИЯ
function initializeFilters() {
    const filterTrigger = document.getElementById('filterTrigger');
    const filterMenu = document.getElementById('filterMenu');
    
    console.log('Инициализация фильтров:', filterTrigger, filterMenu); // Для отладки
    
    if (filterTrigger && filterMenu) {
        // Обработчик клика по кнопке фильтров
        filterTrigger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Клик по фильтрам'); // Для отладки
            
            // Переключаем видимость меню
            const isActive = filterMenu.classList.contains('active');
            
            // Закрываем все другие меню
            document.querySelectorAll('.filter-menu.active, .dropdown-menu.active').forEach(menu => {
                if (menu !== filterMenu) {
                    menu.classList.remove('active');
                }
            });
            
            // Переключаем текущее меню
            if (isActive) {
                filterMenu.classList.remove('active');
            } else {
                filterMenu.classList.add('active');
            }
        });
        
        // Закрытие при клике вне меню
        document.addEventListener('click', function(e) {
            if (!filterTrigger.contains(e.target) && !filterMenu.contains(e.target)) {
                filterMenu.classList.remove('active');
            }
        });
        
        // Предотвращаем закрытие при клике внутри меню
        filterMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    } else {
        console.error('Элементы фильтров не найдены!');
    }
}

// Экспорт - ИСПРАВЛЕННАЯ ВЕРСИЯ
function initializeExport() {
    const exportTrigger = document.getElementById('exportTrigger');
    const exportMenu = document.getElementById('exportMenu');
    
    console.log('Инициализация экспорта:', exportTrigger, exportMenu); // Для отладки
    
    if (exportTrigger && exportMenu) {
        // Обработчик клика по кнопке экспорта
        exportTrigger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Клик по экспорту'); // Для отладки
            
            // Переключаем видимость меню
            const isActive = exportMenu.classList.contains('active');
            
            // Закрываем все другие меню
            document.querySelectorAll('.filter-menu.active, .dropdown-menu.active').forEach(menu => {
                if (menu !== exportMenu) {
                    menu.classList.remove('active');
                }
            });
            
            // Переключаем текущее меню
            if (isActive) {
                exportMenu.classList.remove('active');
            } else {
                exportMenu.classList.add('active');
            }
        });
        
        // Закрытие при клике вне меню
        document.addEventListener('click', function(e) {
            if (!exportTrigger.contains(e.target) && !exportMenu.contains(e.target)) {
                exportMenu.classList.remove('active');
            }
        });
        
        // Предотвращаем закрытие при клике внутри меню
        exportMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
}

// Массовые действия
function initializeBulkActions() {
    const selectAll = document.querySelector('[id^="selectAll"]');
    const itemCheckboxes = document.querySelectorAll('.select-checkbox:not([id^="selectAll"])');
    const bulkActions = document.getElementById('bulkActions');
    const selectedInfo = document.getElementById('selectedInfo');
    
    if (selectAll && itemCheckboxes.length > 0) {
        selectAll.addEventListener('change', function() {
            itemCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateBulkActions();
        });
        
        itemCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateBulkActions);
        });
    }
    
    function updateBulkActions() {
        if (!bulkActions || !selectedInfo) return;
        
        const selected = document.querySelectorAll('.select-checkbox:not([id^="selectAll"]):checked');
        const count = selected.length;
        
        if (count > 0) {
            bulkActions.style.display = 'flex';
            selectedInfo.textContent = `Выбрано: ${count}`;
        } else {
            bulkActions.style.display = 'none';
        }
        
        if (selectAll) {
            selectAll.checked = count === itemCheckboxes.length;
            selectAll.indeterminate = count > 0 && count < itemCheckboxes.length;
        }
    }
}

// Анимации
function initializeAnimations() {
    // Плавные анимации при наведении на строки
    document.querySelectorAll('.data-row').forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Анимации для view-switcher
    document.querySelectorAll('.view-option').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.view-option').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

// Функции экспорта (общие)
function exportToExcel() {
    console.log('Экспорт в Excel');
    const exportMenu = document.getElementById('exportMenu');
    if (exportMenu) {
        exportMenu.classList.remove('active');
    }
}

function exportToPDF() {
    console.log('Экспорт в PDF');
    const exportMenu = document.getElementById('exportMenu');
    if (exportMenu) {
        exportMenu.classList.remove('active');
    }
}

function printList() {
    console.log('Печать списка');
    const exportMenu = document.getElementById('exportMenu');
    if (exportMenu) {
        exportMenu.classList.remove('active');
    }
    window.print();
}

// Вспомогательные функции для отладки
function toggleFilterMenu() {
    const filterMenu = document.getElementById('filterMenu');
    if (filterMenu) {
        filterMenu.classList.toggle('active');
        console.log('Filter menu toggled:', filterMenu.classList.contains('active'));
    }
}

function toggleExportMenu() {
    const exportMenu = document.getElementById('exportMenu');
    if (exportMenu) {
        exportMenu.classList.toggle('active');
        console.log('Export menu toggled:', exportMenu.classList.contains('active'));
    }
}
