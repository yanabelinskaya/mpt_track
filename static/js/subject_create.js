// subject_create.js — логика страницы создания предмета

console.log('🚀 subject_create.js загружен');

document.addEventListener('DOMContentLoaded', () => {
    initializeCustomSelects();
    initializeProfessionSelect();
    initializeSubjectSelectSearch();
    initializeTeacherSelection();
    initializeTeacherSearch();
    handleSubjectSelection('');
    updateTeacherCount();
    filterTeachers('');
    console.log('✅ Инициализация формы добавления предмета завершена');
});

function initializeCustomSelects() {
    document.querySelectorAll('.custom-select').forEach(wrapper => {
        if (wrapper.dataset.customInitialized === 'true') {
            return;
        }

        wrapper.dataset.customInitialized = 'true';

        const trigger = wrapper.querySelector('.select-trigger');
        const dropdown = wrapper.querySelector('.select-dropdown');
        const hiddenSelect = wrapper.querySelector('select');
        const displayText = trigger?.querySelector('.select-text');

        if (!trigger || !dropdown || !hiddenSelect) {
            return;
        }

        if (displayText && !displayText.dataset.placeholder) {
            displayText.dataset.placeholder = displayText.textContent;
        }

        trigger.addEventListener('click', event => {
            if (wrapper.classList.contains('is-disabled')) {
                return;
            }

            event.stopPropagation();

            document.querySelectorAll('.custom-select .select-dropdown.show').forEach(openDropdown => {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.remove('show');
                    openDropdown.closest('.custom-select')?.querySelector('.select-trigger')?.classList.remove('active');
                }
            });

            dropdown.classList.toggle('show');
            trigger.classList.toggle('active');

            if (dropdown.classList.contains('show') && (wrapper.id === 'professionSelect' || wrapper.id === 'subjectSelect')) {
                const searchInput = dropdown.querySelector('.select-search input');
                if (searchInput) {
                    setTimeout(() => searchInput.focus(), 0);
                }
            }
        });

        dropdown.addEventListener('click', event => {
            const option = event.target.closest('.select-option');
            if (
                !option ||
                option.classList.contains('disabled') ||
                option.dataset.value === undefined
            ) {
                return;
            }

            if (wrapper.classList.contains('is-disabled')) {
                return;
            }

            event.stopPropagation();

            const value = option.dataset.value ?? '';
            const label = option.dataset.label ?? option.querySelector('.select-option-text')?.textContent ?? '';

            hiddenSelect.value = value;

            dropdown.querySelectorAll('.select-option[data-value]').forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');

            if (displayText) {
                displayText.textContent = label;
            }

            trigger.classList.toggle('placeholder', value === '');

            dropdown.classList.remove('show');
            trigger.classList.remove('active');

            if (wrapper.id === 'professionSelect') {
                let professions = wrapper.professionsList || JSON.parse(wrapper.dataset.professions || '[]');
                if (!professions.includes(value) && value) {
                    professions = [...professions, value];
                    wrapper.professionsList = professions;
                    wrapper.dataset.professions = JSON.stringify(professions);
                    if (!Array.from(hiddenSelect.options).some(opt => opt.value === value)) {
                        hiddenSelect.appendChild(new Option(label || value, value));
                    }
                }

                const searchInput = dropdown.querySelector('.select-search input');
                if (searchInput) {
                    searchInput.value = '';
                    renderProfessionOptions(wrapper, '');
                }
            } else if (wrapper.id === 'subjectSelect') {
                const searchInput = dropdown.querySelector('.select-search input');
                if (searchInput) {
                    searchInput.value = '';
                }
                if (typeof wrapper.subjectFilter === 'function') {
                    wrapper.subjectFilter('');
                }
            }

            handleSelectSideEffects(wrapper.id, value, option.dataset.professions || '');
        });

        syncTriggerWithSelect(wrapper, hiddenSelect.value);
    });

    document.addEventListener('click', event => {
        if (!event.target.closest('.custom-select')) {
            document.querySelectorAll('.custom-select .select-dropdown.show').forEach(openDropdown => {
                openDropdown.classList.remove('show');
                openDropdown.closest('.custom-select')?.querySelector('.select-trigger')?.classList.remove('active');
            });
        }
    });
}

function syncTriggerWithSelect(wrapper, value) {
    const trigger = wrapper.querySelector('.select-trigger');
    const dropdown = wrapper.querySelector('.select-dropdown');
    const hiddenSelect = wrapper.querySelector('select');
    const displayText = trigger?.querySelector('.select-text');

    if (!trigger || !dropdown || !displayText || !hiddenSelect) {
        return;
    }

    const options = Array.from(dropdown.querySelectorAll('.select-option[data-value]'));
    options.forEach(option => option.classList.remove('selected'));

    const matchingOption = options.find(option => (option.dataset.value ?? '') === value);

    if (matchingOption) {
        matchingOption.classList.add('selected');
        const label = matchingOption.dataset.label ?? matchingOption.querySelector('.select-option-text')?.textContent ?? displayText.textContent;
        displayText.textContent = label;
        trigger.classList.toggle('placeholder', value === '');
    } else if (value) {
        const hiddenOption = Array.from(hiddenSelect.options).find(opt => opt.value === value);
        if (hiddenOption) {
            displayText.textContent = hiddenOption.text || hiddenOption.value;
            trigger.classList.remove('placeholder');
            return;
        }
        trigger.classList.remove('placeholder');
        displayText.textContent = value;
    } else {
        displayText.textContent = displayText.dataset.placeholder || displayText.textContent;
        trigger.classList.add('placeholder');
    }
}

function handleSelectSideEffects(selectId, value, professionsRaw) {
    switch (selectId) {
        case 'facultySelect':
            updateProfessionOptions(value || '', professionsRaw);
            break;
        case 'subjectSelect':
            handleSubjectSelection(value || '');
            break;
        default:
            break;
    }
}

function initializeProfessionSelect() {
    updateProfessionOptions('', '');
}

function initializeSubjectSelectSearch() {
    const wrapper = document.getElementById('subjectSelect');
    if (!wrapper || wrapper.dataset.subjectSearchInitialized === 'true') {
        return;
    }

    const dropdown = wrapper.querySelector('.select-dropdown');
    const optionsList = dropdown?.querySelector('.select-options-list');
    const searchInput = dropdown?.querySelector('.select-search input');
    const emptyMessage = dropdown?.querySelector('.subject-search-message');

    if (!dropdown || !optionsList || !searchInput) {
        return;
    }

    wrapper.dataset.subjectSearchInitialized = 'true';

    const options = Array.from(optionsList.querySelectorAll('.select-option[data-value]')) || [];

    const applyFilter = rawTerm => {
        const term = (rawTerm || '').trim().toLowerCase();
        let visibleCount = 0;

        options.forEach(option => {
            const value = option.dataset.value;
            if (value === undefined) {
                return;
            }

            if (value === '') {
                option.style.display = '';
                return;
            }

            const optionText = option.querySelector('.select-option-text')?.textContent.toLowerCase() || '';
            const matches = !term || optionText.includes(term);
            option.style.display = matches ? '' : 'none';
            if (matches) {
                visibleCount += 1;
            }
        });

        if (emptyMessage) {
            const shouldShow = Boolean(term) && visibleCount === 0;
            emptyMessage.style.display = shouldShow ? 'block' : 'none';
        }
    };

    wrapper.subjectFilter = applyFilter;

    searchInput.addEventListener('input', () => applyFilter(searchInput.value));
    searchInput.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            applyFilter(searchInput.value);
        }
    });

    applyFilter('');
}

function updateProfessionOptions(facultyId, professionsRaw) {
    const wrapper = document.getElementById('professionSelect');
    if (!wrapper) {
        return;
    }

    const trigger = wrapper.querySelector('.select-trigger');
    const dropdown = wrapper.querySelector('.select-dropdown');
    const hiddenSelect = wrapper.querySelector('select');
    const displayText = trigger?.querySelector('.select-text');

    if (!trigger || !dropdown || !hiddenSelect || !displayText) {
        return;
    }

    const basePlaceholder = 'Сначала выберите специальность';
    const readyPlaceholder = 'Выберите профессию';
    const startMessageDefault = 'Выберите профессию или начните ввод';
    const emptyMessageDefault = 'Профессии не найдены. Введите новую профессию';

    hiddenSelect.innerHTML = '';
    hiddenSelect.value = '';
    hiddenSelect.disabled = true;
    dropdown.innerHTML = '';
    wrapper.classList.add('is-disabled');
    wrapper.professionsList = [];
    wrapper.dataset.professions = JSON.stringify([]);
    wrapper.dataset.professionStartMessage = startMessageDefault;
    wrapper.dataset.professionEmptyMessage = emptyMessageDefault;

    if (!facultyId) {
        hiddenSelect.appendChild(new Option(basePlaceholder, ''));
        dropdown.innerHTML = `
            <div class="select-option disabled">
                <div class="select-option-text">${basePlaceholder}</div>
            </div>
        `;

        displayText.textContent = basePlaceholder;
        displayText.dataset.placeholder = basePlaceholder;
        trigger.classList.add('placeholder');
        return;
    }

    const professionsFromDataset = (professionsRaw || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    const professionsFromMap = (window.facultiesData || {})[facultyId] || [];
    let professions = Array.from(new Set([
        ...professionsFromDataset,
        ...professionsFromMap
    ]));

    professions.sort((a, b) => a.localeCompare(b, 'ru'));

    hiddenSelect.disabled = false;
    wrapper.classList.remove('is-disabled');

    hiddenSelect.appendChild(new Option(readyPlaceholder, ''));
    professions.forEach(name => {
        hiddenSelect.appendChild(new Option(name, name));
    });

    wrapper.professionsList = professions;
    wrapper.dataset.professions = JSON.stringify(professions);
    wrapper.dataset.professionStartMessage = startMessageDefault;
    wrapper.dataset.professionEmptyMessage = professions.length
        ? 'Ничего не найдено. Создайте новую профессию'
        : emptyMessageDefault;

    const searchWrapper = document.createElement('div');
    searchWrapper.className = 'select-search';
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Поиск профессий...';
    searchWrapper.appendChild(searchInput);
    dropdown.appendChild(searchWrapper);

    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'select-options-list';
    dropdown.appendChild(optionsContainer);

    const messageOption = document.createElement('div');
    messageOption.className = 'select-option disabled profession-message';
    const messageText = document.createElement('div');
    messageText.className = 'select-option-text';
    messageText.textContent = wrapper.dataset.professionStartMessage;
    messageOption.appendChild(messageText);
    dropdown.appendChild(messageOption);

    searchInput.addEventListener('input', () => {
        renderProfessionOptions(wrapper, searchInput.value);
    });

    displayText.textContent = readyPlaceholder;
    displayText.dataset.placeholder = readyPlaceholder;
    trigger.classList.add('placeholder');

    renderProfessionOptions(wrapper, '');
    syncTriggerWithSelect(wrapper, hiddenSelect.value);
}

function renderProfessionOptions(wrapper, query) {
    if (!wrapper) {
        return;
    }

    const dropdown = wrapper.querySelector('.select-dropdown');
    const hiddenSelect = wrapper.querySelector('select');

    if (!dropdown || !hiddenSelect) {
        return;
    }

    const optionsContainer = dropdown.querySelector('.select-options-list');
    const messageOption = dropdown.querySelector('.profession-message');

    if (!optionsContainer || !messageOption) {
        return;
    }

    const professions = wrapper.professionsList || JSON.parse(wrapper.dataset.professions || '[]');
    const normalizedQuery = (query || '').trim().toLowerCase();
    const trimmedValue = (query || '').trim();
    const startMessage = wrapper.dataset.professionStartMessage || 'Выберите профессию или начните ввод';
    const emptyMessage = wrapper.dataset.professionEmptyMessage || 'Профессии не найдены. Введите новую профессию';

    optionsContainer.innerHTML = '';

    const matchedProfessions = normalizedQuery
        ? professions.filter(name => name.toLowerCase().includes(normalizedQuery))
        : professions;
    const hasExactMatch = matchedProfessions.some(name => name.toLowerCase() === normalizedQuery);

    if (matchedProfessions.length) {
        messageOption.classList.add('hidden');

        matchedProfessions.forEach(name => {
            const option = document.createElement('div');
            option.className = 'select-option';
            option.dataset.value = name;
            option.dataset.label = name;

            const icon = document.createElement('div');
            icon.className = 'select-option-icon';
            icon.innerHTML = '<i class="bi bi-briefcase"></i>';

            const text = document.createElement('div');
            text.className = 'select-option-text';
            text.textContent = name;

            option.appendChild(icon);
            option.appendChild(text);

            if (hiddenSelect.value === name) {
                option.classList.add('selected');
            }

            optionsContainer.appendChild(option);
        });
    } else {
        messageOption.classList.remove('hidden');
        const textElement = messageOption.querySelector('.select-option-text');
        if (textElement) {
            textElement.textContent = emptyMessage;
        }
    }

    if (!hasExactMatch && trimmedValue) {
        const createOption = document.createElement('div');
        createOption.className = 'select-option';
        createOption.dataset.value = trimmedValue;
        createOption.dataset.label = trimmedValue;
        createOption.dataset.custom = 'true';

        const icon = document.createElement('div');
        icon.className = 'select-option-icon';
        icon.innerHTML = '<i class="bi bi-plus-circle"></i>';

        const text = document.createElement('div');
        text.className = 'select-option-text';
        text.textContent = `Создать "${trimmedValue}"`;

        createOption.appendChild(icon);
        createOption.appendChild(text);

        optionsContainer.appendChild(createOption);
    }

    if (!normalizedQuery && professions.length) {
        messageOption.classList.add('hidden');
        const textElement = messageOption.querySelector('.select-option-text');
        if (textElement) {
            textElement.textContent = startMessage;
        }
    }
}

function initializeTeacherSelection() {
    const teacherItems = document.querySelectorAll('.teacher-item');

    teacherItems.forEach(item => {
        const checkbox = item.querySelector('.teacher-checkbox');
        if (!checkbox) {
            return;
        }

        item.addEventListener('click', event => {
            if (event.target === checkbox) {
                updateTeacherItemState(item, checkbox.checked);
                updateTeacherCount();
                return;
            }

            checkbox.checked = !checkbox.checked;
            updateTeacherItemState(item, checkbox.checked);
            updateTeacherCount();
        });

        checkbox.addEventListener('change', () => {
            updateTeacherItemState(item, checkbox.checked);
            updateTeacherCount();
        });

        updateTeacherItemState(item, checkbox.checked);
    });
}

function initializeTeacherSearch() {
    const searchInput = document.querySelector('.teachers-selection .search-input');
    if (!searchInput) {
        return;
    }

    const runFilter = () => {
        filterTeachers(searchInput.value);
    };

    searchInput.addEventListener('input', runFilter);
    searchInput.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            runFilter();
        }
    });
}

function updateTeacherItemState(item, isChecked) {
    if (isChecked) {
        item.classList.add('selected');
    } else {
        item.classList.remove('selected');
    }
}

function selectAllTeachers() {
    document.querySelectorAll('.teacher-checkbox').forEach(checkbox => {
        checkbox.checked = true;
        const item = checkbox.closest('.teacher-item');
        if (item) {
            updateTeacherItemState(item, true);
        }
    });
    updateTeacherCount();
}

function unselectAllTeachers() {
    document.querySelectorAll('.teacher-checkbox').forEach(checkbox => {
        checkbox.checked = false;
        const item = checkbox.closest('.teacher-item');
        if (item) {
            updateTeacherItemState(item, false);
        }
    });
    updateTeacherCount();
}

function filterTeachers(query) {
    const lowerQuery = (query || '').toLowerCase();
    document.querySelectorAll('.teacher-item').forEach(item => {
        const name = item.dataset.teacherName || '';
        const email = item.dataset.teacherEmail || '';
        const details = item.querySelector('.student-details')?.textContent.toLowerCase() || '';

        if (!lowerQuery || name.includes(lowerQuery) || email.includes(lowerQuery) || details.includes(lowerQuery)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function updateTeacherCount() {
    const countElement = document.getElementById('teachersSelectedCount');
    if (!countElement) {
        return;
    }

    const total = document.querySelectorAll('.teacher-checkbox:checked').length;
    countElement.textContent = total;
}

function handleSubjectSelection(subjectId) {
    const nameInput = document.getElementById('id_subject_name');
    const shortInput = document.getElementById('id_subject_short_name');
    const descriptionInput = document.getElementById('id_subject_description');

    if (!nameInput || !shortInput || !descriptionInput) {
        return;
    }

    if (!subjectId) {
        nameInput.disabled = false;
        shortInput.disabled = false;
        descriptionInput.disabled = false;

        nameInput.placeholder = 'Например, Математика';
        shortInput.placeholder = 'Например, Мат.';
        descriptionInput.placeholder = 'Краткое описание предмета';

        nameInput.value = '';
        shortInput.value = '';
        descriptionInput.value = '';
        return;
    }

    const selectedSubject = (window.subjectsData || []).find(
        subject => String(subject.id) === String(subjectId)
    );

    nameInput.value = '';
    nameInput.disabled = true;
    nameInput.placeholder = 'Чтобы создать новый предмет, очистите выбор выше';

    if (selectedSubject) {
        shortInput.value = selectedSubject.short_name || '';
        descriptionInput.value = selectedSubject.description || '';
    } else {
        shortInput.value = '';
        descriptionInput.value = '';
    }

    shortInput.disabled = true;
    shortInput.placeholder = 'Используется существующее значение';

    descriptionInput.disabled = true;
    descriptionInput.placeholder = 'Используется существующее описание';
}

function resetSubjectForm() {
    const form = document.getElementById('subjectCreateForm');
    if (!form) {
        return;
    }

    form.reset();

    document.querySelectorAll('.custom-select').forEach(wrapper => {
        const trigger = wrapper.querySelector('.select-trigger');
        const dropdown = wrapper.querySelector('.select-dropdown');
        const hiddenSelect = wrapper.querySelector('select');
        const displayText = trigger?.querySelector('.select-text');

        if (!trigger || !dropdown || !hiddenSelect || !displayText) {
            return;
        }

        hiddenSelect.value = '';
        trigger.classList.add('placeholder');
        dropdown.querySelectorAll('.select-option').forEach(option => option.classList.remove('selected'));

        if (wrapper.id === 'facultySelect') {
            displayText.textContent = 'Выберите специальность';
        } else if (wrapper.id === 'professionSelect') {
            displayText.textContent = 'Сначала выберите специальность';
        } else if (wrapper.id === 'courseSelect') {
            displayText.textContent = 'Выберите курс';
        } else if (wrapper.id === 'subjectSelect') {
            displayText.textContent = 'Выберите предмет';
        }
    });

    updateProfessionOptions('', '');

    document.querySelectorAll('.teacher-checkbox').forEach(checkbox => {
        checkbox.checked = false;
        const item = checkbox.closest('.teacher-item');
        if (item) {
            updateTeacherItemState(item, false);
            item.style.display = 'flex';
        }
    });

    const teacherSearch = document.querySelector('.teachers-selection .search-input');
    if (teacherSearch) {
        teacherSearch.value = '';
    }

    updateTeacherCount();
    handleSubjectSelection('');
}

window.selectAllTeachers = selectAllTeachers;
window.unselectAllTeachers = unselectAllTeachers;
window.filterTeachers = filterTeachers;
window.resetSubjectForm = resetSubjectForm;
