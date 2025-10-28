const selectedTeacherIds = new Set();
let teacherToDeleteId = null;

function closeDropdownMenus() {
    document.querySelectorAll('.dropdown-menu.active').forEach(menu => {
        menu.classList.remove('active');
    });
}

function initDropdown(triggerId, menuId, onToggle) {
    const trigger = document.getElementById(triggerId);
    const menu = document.getElementById(menuId);
    if (!trigger || !menu) {
        return;
    }

    trigger.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        const willOpen = !menu.classList.contains('active');
        closeDropdownMenus();
        if (willOpen) {
            menu.classList.add('active');
            if (typeof onToggle === 'function') {
                onToggle();
            }
        }
    });

    menu.addEventListener('click', event => {
        event.stopPropagation();
    });
}

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

function updateSelectionState() {
    const selectedInfo = document.getElementById('selectedInfo');
    const bulkActions = document.getElementById('bulkActions');
    const exportSelectedHeader = document.getElementById('exportSelectedHeader');
    const exportSelectedExcel = document.getElementById('exportSelectedExcel');

    const count = selectedTeacherIds.size;

    if (selectedInfo) {
        selectedInfo.textContent = `Выбрано: ${count}`;
    }
    if (bulkActions) {
        bulkActions.style.display = count > 0 ? 'flex' : 'none';
    }
    if (exportSelectedHeader) {
        exportSelectedHeader.style.display = count > 0 ? 'block' : 'none';
    }
    if (exportSelectedExcel) {
        exportSelectedExcel.style.display = count > 0 ? 'block' : 'none';
    }
}

function attachSelectionHandlers() {
    const selectAll = document.getElementById('selectAllTeachers');
    const checkboxes = document.querySelectorAll('.teacher-checkbox');

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checkboxes.forEach(cb => {
                cb.checked = selectAll.checked;
                const id = parseInt(cb.value);
                if (selectAll.checked) {
                    selectedTeacherIds.add(id);
                } else {
                    selectedTeacherIds.delete(id);
                }
            });
            updateSelectionState();
        });
    }

    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            const id = parseInt(cb.value);
            if (cb.checked) {
                selectedTeacherIds.add(id);
            } else {
                selectedTeacherIds.delete(id);
            }
            updateSelectionState();
        });
    });
}

async function performTeacherAction(url, options = {}, successMessage = '') {
    const defaultOptions = {
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
    };

    const response = await fetch(url, {
        ...defaultOptions,
        ...options,
    });

    if (!response.ok) {
        let message = 'Произошла ошибка';
        try {
            const data = await response.json();
            message = data.message || data.error || message;
        } catch (err) {
            // ignore
        }
        throw new Error(message);
    }

    if (successMessage) {
        console.log(successMessage);
    }

    return response.json().catch(() => ({}));
}

function requireSelection() {
    if (selectedTeacherIds.size === 0) {
        alert('Выберите хотя бы одного преподавателя');
        return false;
    }
    return true;
}

window.openAddTeacher = function openAddTeacher() {
    if (!window.TEACHER_CREATE_URL) return;
    window.location.href = window.TEACHER_CREATE_URL;
};

window.openTeacherImport = function openTeacherImport() {
    if (!window.TEACHER_IMPORT_URL) return;
    window.location.href = window.TEACHER_IMPORT_URL;
};

window.viewTeacher = function viewTeacher(id) {
    if (!window.TEACHER_VIEW_URL) return;
    window.location.href = window.TEACHER_VIEW_URL.replace('{id}', id);
};

window.editTeacher = function editTeacher(id) {
    if (!window.TEACHER_EDIT_URL) return;
    window.location.href = window.TEACHER_EDIT_URL.replace('{id}', id);
};

window.deleteTeacher = async function deleteTeacher(id) {
    if (!window.TEACHER_DELETE_URL) return;
    if (!confirm('Удалить преподавателя? Действие необратимо.')) return;

    try {
        await performTeacherAction(
            window.TEACHER_DELETE_URL.replace('{id}', id),
            { method: 'POST' },
            'Преподаватель удалён'
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.bulkActivateTeachers = async function bulkActivateTeachers() {
    if (!window.TEACHER_BULK_ACTIVATE_URL || !requireSelection()) return;
    try {
        await performTeacherAction(
            window.TEACHER_BULK_ACTIVATE_URL,
            {
                method: 'POST',
                body: JSON.stringify({
                    mode: 'selected',
                    teacher_ids: Array.from(selectedTeacherIds),
                }),
            },
            'Аккаунты активированы'
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.bulkDeactivateTeachers = async function bulkDeactivateTeachers() {
    if (!window.TEACHER_BULK_DEACTIVATE_URL || !requireSelection()) return;
    try {
        await performTeacherAction(
            window.TEACHER_BULK_DEACTIVATE_URL,
            {
                method: 'POST',
                body: JSON.stringify({
                    mode: 'selected',
                    teacher_ids: Array.from(selectedTeacherIds),
                }),
            },
            'Аккаунты деактивированы'
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.bulkDeleteTeachers = async function bulkDeleteTeachers() {
    if (!window.TEACHER_BULK_DELETE_URL || !requireSelection()) return;
    if (!confirm('Удалить выбранных преподавателей?')) return;
    try {
        await performTeacherAction(
            window.TEACHER_BULK_DELETE_URL,
            {
                method: 'POST',
                body: JSON.stringify({
                    mode: 'selected',
                    teacher_ids: Array.from(selectedTeacherIds),
                }),
            },
            'Преподаватели удалены'
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.bulkCreateAccessTeachers = async function bulkCreateAccessTeachers() {
    if (!window.TEACHER_BULK_CREATE_ACCESS_URL || !requireSelection()) return;
    try {
        await performTeacherAction(
            window.TEACHER_BULK_CREATE_ACCESS_URL,
            {
                method: 'POST',
                body: JSON.stringify({
                    mode: 'selected',
                    teacher_ids: Array.from(selectedTeacherIds),
                }),
            },
            'Учётные записи созданы'
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.exportAllToExcel = function exportAllToExcel() {
    if (!window.TEACHER_EXPORT_URL) return;
    const params = new URLSearchParams(window.location.search);
    window.location.href = `${window.TEACHER_EXPORT_URL}?${params.toString()}`;
};

window.exportSelectedToExcel = function exportSelectedToExcel() {
    if (!window.TEACHER_EXPORT_URL || !requireSelection()) return;
    const params = new URLSearchParams();
    Array.from(selectedTeacherIds).forEach(id => params.append('ids', id));
    window.location.href = `${window.TEACHER_EXPORT_URL}?${params.toString()}`;
};

window.clearSearch = function clearSearch() {
    const searchField = document.querySelector('.search-field');
    if (searchField) {
        searchField.value = '';
        searchField.form.submit();
    }
};

window.toggleTeacherStatus = async function toggleTeacherStatus(id) {
    if (!window.TEACHER_TOGGLE_STATUS_URL) return;
    try {
        await performTeacherAction(
            window.TEACHER_TOGGLE_STATUS_URL.replace('{id}', id),
            { method: 'POST' }
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.resetTeacherPassword = async function resetTeacherPassword(id) {
    if (!window.TEACHER_RESET_PASSWORD_URL) return;
    try {
        await performTeacherAction(
            window.TEACHER_RESET_PASSWORD_URL.replace('{id}', id),
            {
                method: 'POST',
                body: JSON.stringify({ send_email: true }),
            }
        );
        alert('Пароль отправлен преподавателю на email');
    } catch (error) {
        alert(error.message);
    }
};

window.createTeacherAccess = async function createTeacherAccess(id) {
    if (!window.TEACHER_CREATE_ACCESS_URL) return;
    try {
        await performTeacherAction(
            window.TEACHER_CREATE_ACCESS_URL.replace('{id}', id),
            {
                method: 'POST',
                body: JSON.stringify({ send_email: true }),
            }
        );
        window.location.reload();
    } catch (error) {
        alert(error.message);
    }
};

window.addEventListener('DOMContentLoaded', () => {
    attachSelectionHandlers();
    updateSelectionState();
    initDropdown('addTeacherTrigger', 'addTeacherMenu');
    initDropdown('exportTrigger', 'exportMenu', updateSelectionState);
    document.addEventListener('click', closeDropdownMenus);
});

console.log('✅ teachers.js инициализирован');
