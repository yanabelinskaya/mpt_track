// groups.js - ИСПРАВЛЕННАЯ ВЕРСИЯ без перехвата кликов

console.log('🚀 Загрузка groups.js...');

function initializeExpansionState() {
    document.querySelectorAll('.specialty-content').forEach(content => {
        content.dataset.manualExpanded = content.classList.contains('show') ? 'true' : 'false';
        content.dataset.openedBySearch = 'false';
    });
    
    document.querySelectorAll('.groups-list').forEach(list => {
        list.dataset.manualExpanded = list.classList.contains('show') ? 'true' : 'false';
        list.dataset.openedBySearch = 'false';
    });
}

function getCurrentCourseValue() {
    if (window.currentFilters?.course) {
        return String(window.currentFilters.course);
    }
    const hiddenInput = document.getElementById('courseFilterInput');
    if (hiddenInput?.value) {
        return String(hiddenInput.value);
    }
    const activeTab = document.querySelector('.course-tab.active');
    return activeTab?.dataset.course || '1';
}

function findMatchingCoursesForQuery(searchValue) {
    const query = (searchValue || '').trim().toLowerCase();
    if (!query || !Array.isArray(window.groupsIndex)) {
        return [];
    }

    const specialtyFilter = window.currentFilters?.specialty
        ? String(window.currentFilters.specialty)
        : '';
    const professionFilter = (window.currentFilters?.profession || '').trim().toLowerCase();
    const statusFilter = (window.currentFilters?.status || '').trim().toLowerCase();

    const matchedCourses = new Set();

    window.groupsIndex.forEach(item => {
        if (!item) {
            return;
        }

        const itemCourse = item.course != null ? String(item.course) : '';
        if (!itemCourse) {
            return;
        }

        if (specialtyFilter && String(item.faculty_id) !== specialtyFilter) {
            return;
        }

        if (professionFilter && (item.profession || '').toLowerCase() !== professionFilter) {
            return;
        }

        if (statusFilter && statusFilter !== 'all' && (item.status || '').toLowerCase() !== statusFilter) {
            return;
        }

        const haystack = [
            item.code,
            item.name,
            item.profession,
            item.faculty_name,
            itemCourse
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();

        if (haystack.includes(query)) {
            matchedCourses.add(itemCourse);
        }
    });

    return Array.from(matchedCourses);
}

function autoSwitchCourseForSearch(searchValue) {
    const matchingCourses = findMatchingCoursesForQuery(searchValue);
    if (!matchingCourses.length) {
        return false;
    }

    const currentCourse = getCurrentCourseValue();
    if (matchingCourses.some(course => course === currentCourse)) {
        return false;
    }

    matchingCourses.sort((a, b) => Number(a) - Number(b));
    const targetCourse = matchingCourses[0];
    if (!targetCourse) {
        return false;
    }

    if (window.currentFilters) {
        window.currentFilters.course = targetCourse;
    }
    const hiddenCourse = document.getElementById('courseFilterInput');
    if (hiddenCourse) {
        hiddenCourse.value = targetCourse;
    }

    const url = new URL(window.location.href);
    url.searchParams.set('course', targetCourse);
    const trimmedSearch = (searchValue || '').trim();
    if (trimmedSearch) {
        url.searchParams.set('search', trimmedSearch);
    } else {
        url.searchParams.delete('search');
    }

    window.location.href = url.toString();
    return true;
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DOM загружен, инициализация...');
    
    initializeExpansionState();
    initializeFilters();
    initializeSearchAndFilter();
    initializeSearchField();
    updateCourseCounters();
    
    const searchInput = document.querySelector('input[name="search"]');
    const initialSearch = searchInput ? searchInput.value : '';
    applySearchFilter(initialSearch, { autoDetectCourse: Boolean(initialSearch) });
    
    console.log('✅ Инициализация завершена');
});

// Функция переключения курсов - только для вкладок курсов
function switchCourse(courseNumber, event) {
    console.log('🎓 Переключение курса:', courseNumber);
    
    event.preventDefault();
    event.stopPropagation();
    
    // Обновляем активную вкладку
    const allTabs = document.querySelectorAll('.course-tab');
    allTabs.forEach(tab => {
        tab.classList.remove('active');
    });
    
    event.currentTarget.classList.add('active');
    
    // Обновляем скрытое поле
    const courseInput = document.getElementById('courseFilterInput');
    if (courseInput) {
        courseInput.value = courseNumber;
    }
    
    // Обновляем глобальные фильтры
    if (window.currentFilters) {
        window.currentFilters.course = courseNumber;
    }
    
    // Отправляем форму
    const form = document.getElementById('mainSearchForm');
    if (form) {
        form.submit();
    }
    
    return false;
}

function initializeSearchAndFilter() {
    console.log('🔧 Инициализация поиска и фильтров...');
    
    const filterTrigger = document.getElementById('filterTrigger');
    const filterMenu = document.getElementById('filterMenu');
    
    if (filterTrigger && filterMenu) {
        filterTrigger.addEventListener('click', function(e) {
            e.stopPropagation();
            filterMenu.classList.toggle('show');
        });
        
        document.addEventListener('click', function() {
            filterMenu.classList.remove('show');
        });
        
        filterMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    const statusRadios = document.querySelectorAll('input[name="status"]');
    statusRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelector('.search-form').submit();
        });
    });
}

function initializeFilters() {
    console.log('🔧 Инициализация фильтров специальностей...');
    
    const specialtyFilter = document.querySelector('select[name="specialty"]');
    const professionFilter = document.querySelector('select[name="profession"]');
    
    if (specialtyFilter && professionFilter) {
        specialtyFilter.addEventListener('change', function() {
            updateProfessionOptions();
        });

        // Первичная загрузка списка профессий на основании текущих фильтров
        updateProfessionOptions(true);
    }
}

function updateProfessionOptions(preserveSelection = false) {
    console.log('🔄 Обновление списка профессий...');
    
    const specialtyFilter = document.querySelector('select[name="specialty"]');
    const professionFilter = document.getElementById('professionFilterSelect');
    
    if (!specialtyFilter || !professionFilter) {
        return;
    }
    
    const selectedSpecialty = specialtyFilter.value;
    const currentFilters = window.currentFilters || {};
    const currentProfession = currentFilters.profession || '';
    const previousSelection = preserveSelection ? currentProfession : professionFilter.value;
    
    professionFilter.innerHTML = '<option value="">Все профессии</option>';
    let professionsSet = new Set();

    if (selectedSpecialty && window.groupsData?.specialties?.[selectedSpecialty]) {
        window.groupsData.specialties[selectedSpecialty].professions.forEach(profession => {
            if (profession) {
                professionsSet.add(profession);
            }
        });
    } else if (window.groupsData?.specialties) {
        Object.values(window.groupsData.specialties).forEach(specialty => {
            (specialty.professions || []).forEach(profession => {
                if (profession) {
                    professionsSet.add(profession);
                }
            });
        });
    }

    const sortedProfessions = Array.from(professionsSet).sort((a, b) => a.localeCompare(b, 'ru'));

    sortedProfessions.forEach(profession => {
        const option = document.createElement('option');
        option.value = profession;
        option.textContent = profession;
        if (profession === previousSelection) {
            option.selected = true;
        }
        professionFilter.appendChild(option);
    });
}

function updateProfessionFilterAndSubmit() {
    console.log('🔄 Обновление профессий и отправка формы...');
    updateProfessionOptions();
    document.getElementById('mainSearchForm').submit();
}

function clearSearch() {
    console.log('🧹 Очистка поиска...');
    const searchInput = document.querySelector('input[name="search"]');
    if (searchInput) {
        searchInput.value = '';
        updateSearchParam('');
        applySearchFilter('', { autoDetectCourse: false });
        searchInput.focus();
    }
}

function initializeSearchField() {
    const searchInput = document.querySelector('input[name="search"]');
    if (!searchInput) {
        return;
    }

    let debounceTimer = null;

    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const value = searchInput.value;
            updateSearchParam(value);
            applySearchFilter(value, { autoDetectCourse: Boolean(value.trim()) });
        }, 400);
    });

    searchInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            const value = searchInput.value;
            updateSearchParam(value);
            applySearchFilter(value, { autoDetectCourse: true });
        }
    });

    const submitButton = document.getElementById('searchSubmitButton');
    if (submitButton) {
        submitButton.addEventListener('click', function(event) {
            event.preventDefault();
            const value = searchInput.value;
            updateSearchParam(value);
            applySearchFilter(value, { autoDetectCourse: true });
        });
    }
}

function updateCourseCounters() {
    console.log('📊 Обновление счетчиков курсов...');
    
    try {
        const course1Count = document.querySelectorAll('[data-group-course="1"]:not(.hidden-by-search)').length;
        const course2Count = document.querySelectorAll('[data-group-course="2"]:not(.hidden-by-search)').length;
        const course3Count = document.querySelectorAll('[data-group-course="3"]:not(.hidden-by-search)').length;
        const course4Count = document.querySelectorAll('[data-group-course="4"]:not(.hidden-by-search)').length;
        
        console.log('📈 Подсчитано групп по курсам:', {1: course1Count, 2: course2Count, 3: course3Count, 4: course4Count});
        
    } catch (error) {
        console.error('💥 Ошибка при обновлении счетчиков:', error);
    }
}

function updateSearchParam(value) {
    const url = new URL(window.location.href);
    const trimmed = (value || '').trim();
    
    if (trimmed) {
        url.searchParams.set('search', trimmed);
    } else {
        url.searchParams.delete('search');
    }
    
    window.history.replaceState({}, '', url);
    
    if (window.currentFilters) {
        window.currentFilters.search = trimmed;
    }
}

function setExpanded(element, toggle, expand) {
    if (!element) {
        return;
    }
    
    if (expand) {
        element.classList.add('show');
        if (toggle) {
            toggle.classList.add('rotated');
        }
    } else {
        element.classList.remove('show');
        if (toggle) {
            toggle.classList.remove('rotated');
        }
    }
}

function resetSearchState() {
    document.querySelectorAll('.group-row').forEach(row => {
        row.classList.remove('hidden-by-search');
        row.style.display = '';
    });
    
    document.querySelectorAll('.empty-search-state').forEach(node => node.remove());
    
    document.querySelectorAll('.groups-list').forEach(groupsList => {
        const toggle = groupsList.parentElement.querySelector('.profession-toggle');
        const shouldShow = groupsList.dataset.manualExpanded === 'true';
        setExpanded(groupsList, toggle, shouldShow);
        groupsList.dataset.openedBySearch = 'false';
        
        const defaultEmptyState = groupsList.querySelector('.empty-state');
        if (defaultEmptyState) {
            defaultEmptyState.style.display = '';
        }
    });
    
    document.querySelectorAll('.specialty-section').forEach(section => {
        section.style.display = '';
        const specialtyContent = section.querySelector('.specialty-content');
        const toggle = section.querySelector('.specialty-toggle');
        if (specialtyContent) {
            const shouldShow = specialtyContent.dataset.manualExpanded === 'true';
            setExpanded(specialtyContent, toggle, shouldShow);
            specialtyContent.dataset.openedBySearch = 'false';
        }
    });
    
    const resultsEmpty = document.getElementById('searchResultsEmpty');
    if (resultsEmpty) {
        resultsEmpty.style.display = 'none';
    }
    
    updateCourseCounters();
}

function applySearchFilter(value, options = {}) {
    const searchValue = (value || '').trim().toLowerCase();
    const autoDetectCourse = Boolean(options.autoDetectCourse);
    
    if (!searchValue) {
        resetSearchState();
        return;
    }

    if (autoDetectCourse) {
        const switched = autoSwitchCourseForSearch(value);
        if (switched) {
            return;
        }
    }
    
    let totalVisibleGroups = 0;
    let totalVisibleSpecialties = 0;
    
    document.querySelectorAll('.specialty-section').forEach(section => {
        const specialtyContent = section.querySelector('.specialty-content');
        const specialtyToggle = section.querySelector('.specialty-toggle');
        const specialtyName = (section.dataset.specialtyName || '').toLowerCase();
        
        let specialtyMatches = false;
        
        section.querySelectorAll('.profession-section').forEach(profSection => {
            const groupsList = profSection.querySelector('.groups-list');
            const professionToggle = profSection.querySelector('.profession-toggle');
            const professionName = (profSection.dataset.professionName || '').toLowerCase();
            const groupRows = profSection.querySelectorAll('.group-row');
            
            let visibleInProfession = 0;
            
            groupRows.forEach(row => {
                const groupName = (row.dataset.groupName || '').toLowerCase();
                const meta = (row.querySelector('.group-meta')?.textContent || '').toLowerCase();
                const combined = `${groupName} ${meta} ${professionName} ${specialtyName}`;
                
                if (combined.includes(searchValue)) {
                    row.classList.remove('hidden-by-search');
                    row.style.display = '';
                    visibleInProfession += 1;
                } else {
                    row.classList.add('hidden-by-search');
                    row.style.display = 'none';
                }
            });
            
            const defaultEmptyState = groupsList.querySelector('.empty-state');
            let searchEmptyState = groupsList.querySelector('.empty-search-state');
            if (!searchEmptyState) {
                searchEmptyState = document.createElement('div');
                searchEmptyState.className = 'empty-state empty-search-state';
                searchEmptyState.innerHTML = '<h4>Нет групп</h4><p>По вашему запросу ничего не найдено</p>';
                searchEmptyState.style.display = 'none';
                groupsList.appendChild(searchEmptyState);
            }
            
            if (groupRows.length === 0) {
                const matchesByName = professionName.includes(searchValue) || specialtyName.includes(searchValue);
                if (matchesByName) {
                    groupsList.dataset.openedBySearch = 'true';
                    if (groupsList.dataset.manualExpanded !== 'true') {
                        setExpanded(groupsList, professionToggle, true);
                    }
                    if (defaultEmptyState) {
                        defaultEmptyState.style.display = '';
                    }
                    searchEmptyState.style.display = 'none';
                    specialtyMatches = true;
                } else {
                    groupsList.dataset.openedBySearch = 'false';
                    if (groupsList.dataset.manualExpanded !== 'true') {
                        setExpanded(groupsList, professionToggle, false);
                    }
                    if (defaultEmptyState) {
                        defaultEmptyState.style.display = '';
                    }
                    searchEmptyState.style.display = 'none';
                }
                return;
            }
            
            if (visibleInProfession > 0) {
                groupsList.dataset.openedBySearch = 'true';
                if (groupsList.dataset.manualExpanded !== 'true') {
                    setExpanded(groupsList, professionToggle, true);
                }
                if (defaultEmptyState) {
                    defaultEmptyState.style.display = 'none';
                }
                searchEmptyState.style.display = 'none';
                
                specialtyMatches = true;
                totalVisibleGroups += visibleInProfession;
            } else {
                groupsList.dataset.openedBySearch = 'false';
                if (groupsList.dataset.manualExpanded !== 'true') {
                    setExpanded(groupsList, professionToggle, false);
                }
                if (defaultEmptyState) {
                    defaultEmptyState.style.display = 'none';
                }
                searchEmptyState.style.display = 'block';
            }
        });
        
        if (specialtyMatches) {
            section.style.display = '';
            if (specialtyContent) {
                specialtyContent.dataset.openedBySearch = 'true';
                if (specialtyContent.dataset.manualExpanded !== 'true') {
                    setExpanded(specialtyContent, specialtyToggle, true);
                }
            }
            totalVisibleSpecialties += 1;
        } else {
            section.style.display = 'none';
            if (specialtyContent) {
                specialtyContent.dataset.openedBySearch = 'false';
                if (specialtyContent.dataset.manualExpanded !== 'true') {
                    setExpanded(specialtyContent, specialtyToggle, false);
                }
            }
        }
    });
    
    const resultsEmpty = document.getElementById('searchResultsEmpty');
    if (resultsEmpty) {
        resultsEmpty.style.display = totalVisibleGroups === 0 ? 'block' : 'none';
    }
    
    updateCourseCounters();
}

function toggleSpecialty(facultyId) {
    console.log('🏢 Переключение специальности:', facultyId);
    const content = document.getElementById(`content-${facultyId}`);
    const toggle = document.getElementById(`toggle-${facultyId}`);
    
    if (content && toggle) {
        if (content.classList.contains('show')) {
            content.classList.remove('show');
            toggle.classList.remove('rotated');
        } else {
            content.classList.add('show');
            toggle.classList.add('rotated');
        }
    }
}

function toggleProfession(facultyId, professionIndex) {
    console.log('💼 Переключение профессии:', facultyId, professionIndex);
    const content = document.getElementById(`prof-content-${facultyId}-${professionIndex}`);
    const toggle = document.getElementById(`prof-toggle-${facultyId}-${professionIndex}`);
    
    if (content && toggle) {
        if (content.classList.contains('show')) {
            content.classList.remove('show');
            toggle.classList.remove('rotated');
        } else {
            content.classList.add('show');
            toggle.classList.add('rotated');
        }
    }
}

let allExpanded = false;
function toggleAllSpecialties() {
    console.log('🔄 Переключение всех специальностей');
    const button = event.target.closest('button');
    
    const specialtyContents = document.querySelectorAll('.specialty-content');
    const specialtyToggles = document.querySelectorAll('.specialty-toggle');
    const professionContents = document.querySelectorAll('.groups-list');
    const professionToggles = document.querySelectorAll('.profession-toggle');
    
    if (!allExpanded) {
        specialtyContents.forEach(content => content.classList.add('show'));
        specialtyToggles.forEach(toggle => toggle.classList.add('rotated'));
        professionContents.forEach(content => content.classList.add('show'));
        professionToggles.forEach(toggle => toggle.classList.add('rotated'));
        
        button.innerHTML = '<i class="bi bi-arrows-collapse"></i> Свернуть все';
        allExpanded = true;
        
    } else {
        professionContents.forEach(content => content.classList.remove('show'));
        professionToggles.forEach(toggle => toggle.classList.remove('rotated'));
        specialtyContents.forEach(content => content.classList.remove('show'));
        specialtyToggles.forEach(toggle => toggle.classList.remove('rotated'));
        
        button.innerHTML = '<i class="bi bi-arrows-expand"></i> Развернуть все';
        allExpanded = false;
    }
}

console.log('✅ groups.js полностью загружен');
