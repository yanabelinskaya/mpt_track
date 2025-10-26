// group_edit.js - Скрипты для редактирования группы

let currentStudentId = null;
let currentGroupId = null;
let facultiesData = {};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initCustomSelects();
    initFacultyProfessionLogic();
});

// Инициализация кастомных селектов
function initCustomSelects() {
    const selects = document.querySelectorAll('.custom-select');
    
    selects.forEach(selectContainer => {
        const trigger = selectContainer.querySelector('.select-trigger');
        const dropdown = selectContainer.querySelector('.select-dropdown');
        const options = selectContainer.querySelectorAll('.select-option');
        const hiddenSelect = selectContainer.querySelector('select');
        const selectText = selectContainer.querySelector('.select-text');
        
        if (!trigger || !dropdown || !hiddenSelect || !selectText) return;
        
        // Клик по триггеру
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (trigger.classList.contains('disabled')) return;
            
            // Закрыть другие селекты
            document.querySelectorAll('.custom-select').forEach(otherSelect => {
                if (otherSelect !== selectContainer) {
                    const otherTrigger = otherSelect.querySelector('.select-trigger');
                    const otherDropdown = otherSelect.querySelector('.select-dropdown');
                    if (otherTrigger && otherDropdown) {
                        otherTrigger.classList.remove('active');
                        otherDropdown.classList.remove('show');
                    }
                }
            });
            
            // Переключить текущий
            trigger.classList.toggle('active');
            dropdown.classList.toggle('show');
        });
        
        // Клик по опции
        options.forEach(option => {
            option.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                if (option.classList.contains('disabled')) return;
                
                const value = option.getAttribute('data-value');
                const text = option.querySelector('.select-option-text').textContent;
                
                // Обновить UI
                selectText.textContent = text;
                trigger.classList.remove('placeholder');
                
                // Обновить hidden select
                hiddenSelect.value = value;
                
                // Обновить selected класс
                options.forEach(opt => opt.classList.remove('selected'));
                option.classList.add('selected');
                
                // Закрыть dropdown
                trigger.classList.remove('active');
                dropdown.classList.remove('show');
                
                // Trigger change event
                const changeEvent = new Event('change', { bubbles: true });
                hiddenSelect.dispatchEvent(changeEvent);
            });
        });
    });
    
    // Закрытие при клике вне селекта
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.custom-select')) {
            document.querySelectorAll('.custom-select').forEach(select => {
                const trigger = select.querySelector('.select-trigger');
                const dropdown = select.querySelector('.select-dropdown');
                if (trigger && dropdown) {
                    trigger.classList.remove('active');
                    dropdown.classList.remove('show');
                }
            });
        }
    });
}

// Инициализация логики специальность -> профессия
function initFacultyProfessionLogic() {
    const facultySelect = document.querySelector('#facultySelect select');
    const professionContainer = document.querySelector('#professionSelect');
    
    if (!facultySelect || !professionContainer) return;
    
    facultySelect.addEventListener('change', function() {
        updateProfessionOptions(this.value);
    });
    
    // Инициализация при загрузке (если специальность уже выбрана)
    if (facultySelect.value) {
        updateProfessionOptions(facultySelect.value);
    }
}

// Обновление опций профессий
function updateProfessionOptions(facultyId) {
    const professionContainer = document.querySelector('#professionSelect');
    const professionTrigger = professionContainer.querySelector('.select-trigger');
    const professionText = professionContainer.querySelector('.select-text');
    const professionDropdown = professionContainer.querySelector('.select-dropdown');
    const professionSelect = professionContainer.querySelector('select');
    
    if (!facultyId || !facultiesData[facultyId]) {
        // Деактивация селекта профессий
        professionTrigger.classList.add('disabled', 'placeholder');
        professionText.textContent = 'Сначала выберите специальность';
        professionDropdown.innerHTML = '<div class="select-option disabled"><div class="select-option-text">Сначала выберите специальность</div></div>';
        professionSelect.innerHTML = '<option value="">Сначала выберите специальность</option>';
        return;
    }
    
    // Активация селекта профессий
    professionTrigger.classList.remove('disabled');
    
    const faculty = facultiesData[facultyId];
    const professions = faculty.professions || [];
    
    // Очистить и заполнить select
    professionSelect.innerHTML = '<option value="">Выберите профессию</option>';
    professionDropdown.innerHTML = '';
    
    professions.forEach(profession => {
        // Добавить в hidden select
        const option = document.createElement('option');
        option.value = profession;
        option.textContent = profession;
        professionSelect.appendChild(option);
        
        // Добавить в dropdown
        const dropdownOption = document.createElement('div');
        dropdownOption.className = 'select-option';
        dropdownOption.setAttribute('data-value', profession);
        dropdownOption.innerHTML = `
            <div class="select-option-icon">
                <i class="bi bi-briefcase"></i>
            </div>
            <div class="select-option-text">${profession}</div>
        `;
        professionDropdown.appendChild(dropdownOption);
    });
    
    // Сброс выбранной профессии
    professionTrigger.classList.add('placeholder');
    professionText.textContent = 'Выберите профессию';
    
    // Переинициализация событий для новых опций
    setTimeout(() => {
        initCustomSelects();
    }, 50);
}

// Функции для модальных окон
function showTransferModal(studentId, studentName) {
    currentStudentId = studentId;
    document.getElementById('transferStudentName').textContent = studentName;
    const modal = new bootstrap.Modal(document.getElementById('transferModal'));
    modal.show();
    
    // Переинициализация селектов в модальном окне
    setTimeout(() => {
        initCustomSelects();
    }, 100);
}

function showRemoveModal(studentId, studentName) {
    currentStudentId = studentId;
    document.getElementById('removeStudentName').textContent = studentName;
    const modal = new bootstrap.Modal(document.getElementById('removeModal'));
    modal.show();
    
    // Переинициализация селектов в модальном окне
    setTimeout(() => {
        initCustomSelects();
    }, 100);
}

function showAddStudentModal() {
    const modal = new bootstrap.Modal(document.getElementById('addStudentModal'));
    modal.show();
    
    // Переинициализация селектов в модальном окне
    setTimeout(() => {
        initCustomSelects();
    }, 100);
}

function confirmTransfer() {
    const targetGroup = document.getElementById('targetGroup').value;
    const reason = document.getElementById('transferReason').value;
    
    if (!targetGroup) {
        alert('Выберите группу для перевода');
        return;
    }
    
    // AJAX запрос для перевода студента
    fetch(`/groups/transfer-student/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            student_id: currentStudentId,
            target_group_id: targetGroup === 'null' ? null : targetGroup,
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при переводе студента');
    });
}

function confirmRemove() {
    const reason = document.getElementById('removeReason').value;
    const comment = document.getElementById('removeComment').value;
    
    if (!reason) {
        alert('Выберите причину исключения');
        return;
    }
    
    // AJAX запрос для исключения студента
    fetch(`/groups/remove-student/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            student_id: currentStudentId,
            reason: reason,
            comment: comment
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при исключении студента');
    });
}

function confirmAddStudent() {
    const selectedStudents = Array.from(document.querySelectorAll('#addStudentModal input[name="students"]:checked'))
        .map(input => input.value);
    
    if (selectedStudents.length === 0) {
        alert('Выберите хотя бы одного студента');
        return;
    }
    
    // AJAX запрос для добавления студентов
    fetch(`/groups/${currentGroupId}/add-students/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            student_ids: selectedStudents
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при добавлении студентов');
    });
}

function addStudentToGroup(studentId, studentName) {
    if (confirm(`Добавить студента ${studentName} в группу?`)) {
        fetch(`/groups/${currentGroupId}/add-student/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                student_id: studentId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Произошла ошибка при добавлении студента');
        });
    }
}

// Поиск студентов в модальном окне
function filterStudentsInModal(searchTerm) {
    const studentItems = document.querySelectorAll('#addStudentModal .student-item');
    const searchLower = searchTerm.toLowerCase();
    
    studentItems.forEach(item => {
        const studentName = item.getAttribute('data-student-name') || '';
        const visible = studentName.includes(searchLower);
        item.style.display = visible ? 'flex' : 'none';
    });
}

// Выбор/снятие всех студентов
function selectAllStudentsInModal() {
    const checkboxes = document.querySelectorAll('#addStudentModal input[name="students"]');
    checkboxes.forEach(checkbox => {
        if (!checkbox.disabled) {
            checkbox.checked = true;
            checkbox.closest('.student-item').classList.add('selected');
        }
    });
    updateSelectedCount();
}

function unselectAllStudentsInModal() {
    const checkboxes = document.querySelectorAll('#addStudentModal input[name="students"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        checkbox.closest('.student-item').classList.remove('selected');
    });
    updateSelectedCount();
}

// Обновление счетчика выбранных студентов
function updateSelectedCount() {
    const selectedCount = document.querySelectorAll('#addStudentModal input[name="students"]:checked').length;
    const counter = document.getElementById('selectedCountModal');
    if (counter) {
        counter.textContent = selectedCount;
    }
}

// Получение CSRF токена
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return decodeURIComponent(value);
        }
    }
    return '';
}

// Глобальная переменная для ID группы

