// group_create.js - исправленная версия БЕЗ клонирования

console.log('🚀 Загрузка group_create.js...');

// Данные специальностей и профессий
window.facultiesData = window.facultiesData || {};

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DOM загружен, инициализация создания группы...');
    
    initializeCustomSelects();
    initializeStudentSelection();
    updateSelectedCount();
    
    console.log('✅ Инициализация завершена');
});

// ===== КАСТОМНЫЕ СЕЛЕКТЫ =====

function initializeCustomSelects() {
    console.log('🔧 Инициализация кастомных селектов...');
    
    const customSelects = document.querySelectorAll('.custom-select');
    console.log('📊 Найдено кастомных селектов:', customSelects.length);
    
    customSelects.forEach(selectWrapper => {
        const trigger = selectWrapper.querySelector('.select-trigger');
        const dropdown = selectWrapper.querySelector('.select-dropdown');
        const options = selectWrapper.querySelectorAll('.select-option:not(.disabled)');
        const hiddenSelect = selectWrapper.querySelector('select');
        
        console.log(`🎯 Инициализация селекта: ${selectWrapper.id}`);
        
        // Клик по триггеру
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            console.log(`📂 Клик по триггеру селекта: ${selectWrapper.id}`);
            
            // Закрываем все другие селекты
            document.querySelectorAll('.custom-select .select-dropdown.show').forEach(otherDropdown => {
                if (otherDropdown !== dropdown) {
                    otherDropdown.classList.remove('show');
                    otherDropdown.closest('.custom-select').querySelector('.select-trigger').classList.remove('active');
                }
            });
            
            // Переключаем текущий
            dropdown.classList.toggle('show');
            trigger.classList.toggle('active');
        });
        
        // Клик по опции
        options.forEach(option => {
            option.addEventListener('click', function(e) {
                e.stopPropagation();
                
                const value = this.dataset.value;
                const text = this.querySelector('.select-option-text').textContent;
                
                console.log(`✅ Выбрана опция: ${text} (${value})`);
                
                // Обновляем скрытый select
                hiddenSelect.value = value;
                
                // Обновляем отображение
                const selectText = trigger.querySelector('.select-text');
                selectText.textContent = text;
                trigger.classList.remove('placeholder');
                
                // Убираем selected со всех опций
                options.forEach(opt => opt.classList.remove('selected'));
                
                // Добавляем selected к выбранной
                this.classList.add('selected');
                
                // Закрываем dropdown
                dropdown.classList.remove('show');
                trigger.classList.remove('active');
                
                // Специальная логика для специальности
                if (selectWrapper.id === 'facultySelect') {
                    updateProfessions(value, this.dataset.professions);
                }
                
                // Специальная логика для курса
                if (selectWrapper.id === 'courseSelect') {
                    updateEnrollmentDate(value);
                }
            });
        });
    });
    
    // Закрытие при клике вне
    document.addEventListener('click', function(e) {
        // НЕ закрываем если клик по студентам или их поиску
        if (!e.target.closest('.students-selection')) {
            document.querySelectorAll('.custom-select .select-dropdown.show').forEach(dropdown => {
                dropdown.classList.remove('show');
                dropdown.closest('.custom-select').querySelector('.select-trigger').classList.remove('active');
            });
        }
    });
}

// Обновление профессий при выборе специальности
function updateProfessions(facultyId, professionsStr) {
    console.log('🔄 Обновление профессий для специальности:', facultyId);
    
    const professionSelect = document.getElementById('professionSelect');
    const trigger = professionSelect.querySelector('.select-trigger');
    const dropdown = professionSelect.querySelector('.select-dropdown');
    const hiddenSelect = professionSelect.querySelector('select');
    
    // Очищаем
    dropdown.innerHTML = '';
    hiddenSelect.innerHTML = '<option value="">Выберите профессию</option>';
    
    if (professionsStr && professionsStr.trim()) {
        const professions = professionsStr.split(',').map(p => p.trim()).filter(p => p);
        console.log('💼 Найдено профессий:', professions);
        
        professions.forEach(profession => {
            // Добавляем в скрытый select
            const option = document.createElement('option');
            option.value = profession;
            option.textContent = profession;
            hiddenSelect.appendChild(option);
            
            // Добавляем в кастомный dropdown
            const customOption = document.createElement('div');
            customOption.className = 'select-option';
            customOption.dataset.value = profession;
            customOption.innerHTML = `
                <div class="select-option-icon">
                    <i class="bi bi-briefcase"></i>
                </div>
                <div class="select-option-text">${profession}</div>
            `;
            
            customOption.addEventListener('click', function(e) {
                e.stopPropagation();
                
                hiddenSelect.value = profession;
                trigger.querySelector('.select-text').textContent = profession;
                trigger.classList.remove('placeholder');
                
                // Убираем selected со всех
                dropdown.querySelectorAll('.select-option').forEach(opt => opt.classList.remove('selected'));
                this.classList.add('selected');
                
                dropdown.classList.remove('show');
                trigger.classList.remove('active');
            });
            
            dropdown.appendChild(customOption);
        });
        
        // Обновляем placeholder
        trigger.querySelector('.select-text').textContent = 'Выберите профессию';
        trigger.classList.add('placeholder');
        
    } else {
        dropdown.innerHTML = '<div class="select-option disabled"><div class="select-option-text">Нет профессий</div></div>';
        trigger.querySelector('.select-text').textContent = 'Нет профессий';
        trigger.classList.add('placeholder');
    }
}

// Обновление даты поступления при выборе курса
function updateEnrollmentDate(course) {
    console.log('📅 Обновление даты поступления для курса:', course);
    
    if (course) {
        const currentYear = new Date().getFullYear();
        const currentMonth = new Date().getMonth();
        
        let enrollmentYear;
        if (currentMonth >= 8) {
            enrollmentYear = currentYear - parseInt(course) + 1;
        } else {
            enrollmentYear = currentYear - parseInt(course);
        }
        
        const enrollmentDate = `${enrollmentYear}-09-01`;
        document.getElementById('id_enrollment_date').value = enrollmentDate;
        
        console.log('✅ Установлена дата поступления:', enrollmentDate);
    }
}

// Фильтрация опций в селекте
function filterSelectOptions(input, selectId) {
    const selectWrapper = document.getElementById(selectId);
    const options = selectWrapper.querySelectorAll('.select-option:not(.disabled)');
    const query = input.value.toLowerCase();
    
    console.log(`🔍 Фильтрация в селекте ${selectId} по запросу: "${query}"`);
    
    options.forEach(option => {
        const text = option.querySelector('.select-option-text').textContent.toLowerCase();
        if (text.includes(query)) {
            option.style.display = 'flex';
        } else {
            option.style.display = 'none';
        }
    });
}

// ===== ВЫБОР СТУДЕНТОВ =====

function initializeStudentSelection() {
    console.log('👥 Инициализация выбора студентов...');
    
    const studentItems = document.querySelectorAll('.student-item');
    console.log('📊 Найдено студентов:', studentItems.length);
    
    studentItems.forEach((item, index) => {
        const checkbox = item.querySelector('.student-checkbox');
        
        if (checkbox) {
            console.log(`🎯 Инициализация студента ${index + 1}: ${item.dataset.studentName || 'Неизвестно'}`);
            
            // ИСПРАВЛЕНО: НЕ клонируем, просто добавляем обработчики
            initializeSingleStudent(item);
        }
    });
}

function initializeSingleStudent(item) {
    const checkbox = item.querySelector('.student-checkbox');
    
    if (!checkbox) return;
    
    // Проверяем, не был ли уже инициализирован
    if (item.dataset.initialized === 'true') {
        console.log('⚠️ Студент уже инициализирован, пропускаем');
        return;
    }
    
    item.dataset.initialized = 'true';
    
    // Клик по элементу студента (НЕ по чекбоксу)
    item.addEventListener('click', function(e) {
        // Если клик именно по чекбоксу, не дублируем действие
        if (e.target === checkbox) {
            console.log('📋 Прямой клик по чекбоксу');
            updateStudentItemState(item, checkbox.checked);
            updateSelectedCount();
            return;
        }
        
        console.log('👤 Клик по студенту:', item.dataset.studentName);
        
        // Переключаем чекбокс
        checkbox.checked = !checkbox.checked;
        
        // Обновляем визуальное состояние
        updateStudentItemState(item, checkbox.checked);
        
        // Обновляем счетчик
        updateSelectedCount();
    });
    
    // Клик по чекбоксу (дополнительная обработка)
    checkbox.addEventListener('change', function(e) {
        console.log('☑️ Изменение чекбокса студента:', item.dataset.studentName, 'выбран:', this.checked);
        
        // Обновляем визуальное состояние
        updateStudentItemState(item, this.checked);
        
        // Обновляем счетчик
        updateSelectedCount();
    });
    
    // Инициализируем состояние
    updateStudentItemState(item, checkbox.checked);
}

function updateStudentItemState(item, isChecked) {
    if (isChecked) {
        item.classList.add('selected');
    } else {
        item.classList.remove('selected');
    }
}

// Выбрать всех студентов
function selectAllStudents() {
    console.log('👥 Выбрать всех студентов');
    
    const studentItems = document.querySelectorAll('.student-item');
    let count = 0;
    
    studentItems.forEach(item => {
        const checkbox = item.querySelector('.student-checkbox');
        if (checkbox && !checkbox.disabled) {
            checkbox.checked = true;
            updateStudentItemState(item, true);
            count++;
        }
    });
    
    console.log(`✅ Выбрано студентов: ${count}`);
    updateSelectedCount();
}

// Снять выбор со всех студентов
function unselectAllStudents() {
    console.log('👥 Снять выбор со всех студентов');
    
    const studentItems = document.querySelectorAll('.student-item');
    let count = 0;
    
    studentItems.forEach(item => {
        const checkbox = item.querySelector('.student-checkbox');
        if (checkbox) {
            checkbox.checked = false;
            updateStudentItemState(item, false);
            count++;
        }
    });
    
    console.log(`✅ Снят выбор с ${count} студентов`);
    updateSelectedCount();
}

// Обновление счетчика выбранных
function updateSelectedCount() {
    const checked = document.querySelectorAll('.student-checkbox:checked').length;
    const countElement = document.getElementById('selectedCount');
    
    if (countElement) {
        countElement.textContent = checked;
        console.log('📊 Обновлен счетчик выбранных студентов:', checked);
    }
}

// ИСПРАВЛЕННАЯ функция фильтрации студентов
function filterStudents(query) {
    console.log('🔍 Фильтрация студентов по запросу:', query);
    
    const items = document.querySelectorAll('.student-item');
    const lowerQuery = query.toLowerCase();
    let visibleCount = 0;
    
    items.forEach(item => {
        const checkbox = item.querySelector('.student-checkbox');
        
        // Пропускаем элементы без чекбокса (например, "Студенты не найдены")
        if (!checkbox) {
            return;
        }
        
        const studentName = item.dataset.studentName || '';
        const studentNameElement = item.querySelector('.student-name');
        const studentEmail = item.querySelector('.student-details');
        
        // Ищем в имени и email
        let searchText = studentName;
        if (studentNameElement) {
            searchText += ' ' + studentNameElement.textContent.toLowerCase();
        }
        if (studentEmail) {
            searchText += ' ' + studentEmail.textContent.toLowerCase();
        }
        
        if (searchText.includes(lowerQuery)) {
            item.style.display = 'flex';
            visibleCount++;
        } else {
            item.style.display = 'none';
        }
    });
    
    console.log(`👀 Показано студентов: ${visibleCount}`);
}

// Устаревшая функция для совместимости
function toggleStudent(studentId) {
    console.log('⚠️ Использована устаревшая функция toggleStudent для ID:', studentId);
    
    const checkbox = document.getElementById(`student_${studentId}`);
    const item = checkbox ? checkbox.closest('.student-item') : null;
    
    if (checkbox && item) {
        checkbox.checked = !checkbox.checked;
        updateStudentItemState(item, checkbox.checked);
        updateSelectedCount();
    }
}

// ===== СБРОС ФОРМЫ =====

function resetForm() {
    console.log('🔄 Сброс формы');
    
    // Сбрасываем HTML форму
    document.getElementById('groupCreateForm').reset();
    
    // Сбрасываем выбор студентов
    unselectAllStudents();
    
    // Сбрасываем кастомные селекты
    document.querySelectorAll('.custom-select').forEach(selectWrapper => {
        const trigger = selectWrapper.querySelector('.select-trigger');
        const options = selectWrapper.querySelectorAll('.select-option');
        const selectText = trigger.querySelector('.select-text');
        
        trigger.classList.add('placeholder');
        options.forEach(opt => opt.classList.remove('selected'));
        
        // Восстанавливаем оригинальные placeholder'ы
        if (selectWrapper.id === 'facultySelect') {
            selectText.textContent = 'Выберите специальность';
        } else if (selectWrapper.id === 'professionSelect') {
            selectText.textContent = 'Сначала выберите специальность';
        } else if (selectWrapper.id === 'courseSelect') {
            selectText.textContent = 'Выберите курс';
        }
    });
    
    // Сбрасываем профессии
    updateProfessions('', '');
    
    // Очищаем поле поиска студентов
    const searchInput = document.querySelector('.students-search input');
    if (searchInput) {
        searchInput.value = '';
        filterStudents(''); // Показываем всех студентов
    }
    
    console.log('✅ Форма сброшена');
}

console.log('✅ group_create.js полностью загружен');
