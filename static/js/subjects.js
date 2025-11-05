console.log('📘 subjects.js loaded');

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

function initializeSubjectExpansionState() {
    document.querySelectorAll('.specialty-content').forEach(content => {
        content.dataset.manualExpanded = content.classList.contains('show') ? 'true' : 'false';
        content.dataset.openedByFilter = 'false';
    });

    document.querySelectorAll('.subjects-list').forEach(list => {
        list.dataset.manualExpanded = list.classList.contains('show') ? 'true' : 'false';
        list.dataset.openedByFilter = 'false';
    });
}

function initSubjectFilterSelect() {
    const selectContainer = document.getElementById('subjectSpecialtySelect');
    if (!selectContainer) {
        return;
    }

    const trigger = selectContainer.querySelector('.select-trigger');
    const dropdown = selectContainer.querySelector('.select-dropdown');
    const options = selectContainer.querySelectorAll('.select-option');
    const hiddenSelect = selectContainer.querySelector('select');
    const selectText = selectContainer.querySelector('.select-text');

    if (!trigger || !dropdown || !hiddenSelect || !selectText) {
        return;
    }

    trigger.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        trigger.classList.toggle('active');
        dropdown.classList.toggle('show');
    });

    options.forEach(option => {
        option.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();

            if (option.classList.contains('disabled')) {
                return;
            }

            const value = option.dataset.value || '';
            const text = option.querySelector('.select-option-text').textContent.trim();

            hiddenSelect.value = value;
            selectText.textContent = text;

            if (value) {
                trigger.classList.remove('placeholder');
            } else {
                trigger.classList.add('placeholder');
            }

            options.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');

            trigger.classList.remove('active');
            dropdown.classList.remove('show');

            if (!window.currentFilters) {
                window.currentFilters = {};
            }
            window.currentFilters.specialty = value;

            updateFilterBadge();
            updateSubjectUrl();
            applySubjectFilters({ forceAutoExpand: Boolean(value) });
            closeSubjectFilterMenu();
        });
    });

    document.addEventListener('click', event => {
        if (!event.target.closest('#subjectSpecialtySelect')) {
            trigger.classList.remove('active');
            dropdown.classList.remove('show');
        }
    });
}

function setActiveCourseTab(courseNumber) {
    document.querySelectorAll('.course-tab').forEach(tab => {
        const tabCourse = tab.dataset.course;
        tab.classList.toggle('active', tabCourse === courseNumber);
    });
}

function updateFilterBadge() {
    const badge = document.getElementById('subjectFilterBadge');
    if (!badge) {
        return;
    }
    if (window.currentFilters?.specialty) {
        badge.style.display = 'inline-flex';
    } else {
        badge.style.display = 'none';
    }
}

function updateCourseTitle(courseNumber) {
    const suffix = document.getElementById('courseTitleSuffix');
    const valueNode = document.getElementById('courseTitleValue');

    if (!suffix || !valueNode) {
        return;
    }

    if (courseNumber) {
        valueNode.textContent = courseNumber;
        suffix.style.display = '';
    } else {
        valueNode.textContent = '';
        suffix.style.display = 'none';
    }
}

function updateSubjectUrl() {
    const url = new URL(window.location.href);
    const search = (window.currentFilters?.search || '').trim();
    const specialty = window.currentFilters?.specialty || '';
    const course = window.currentFilters?.course || '1';

    if (search) {
        url.searchParams.set('search', search);
    } else {
        url.searchParams.delete('search');
    }

    if (specialty) {
        url.searchParams.set('specialty', specialty);
    } else {
        url.searchParams.delete('specialty');
    }

    if (course) {
        url.searchParams.set('course', course);
    } else {
        url.searchParams.delete('course');
    }

    window.history.replaceState({}, '', url);
}

function applySubjectFilters(options = {}) {
    const searchTerm = (window.currentFilters?.search || '').trim().toLowerCase();
    const specialty = window.currentFilters?.specialty || '';
    const course = window.currentFilters?.course || '1';
    const autoExpand = options.forceAutoExpand || Boolean(searchTerm) || Boolean(specialty);
    let totalVisibleRows = 0;

    const specialtySections = document.querySelectorAll('.specialty-section');
    specialtySections.forEach(section => {
        const facultyId = section.dataset.specialtyId || '';
        if (specialty && facultyId !== specialty) {
            section.style.display = 'none';
        } else {
            section.style.display = '';
        }
    });

    document.querySelectorAll('.profession-section').forEach(section => {
        const parentSpecialty = section.closest('.specialty-section');
        if (specialty && parentSpecialty && parentSpecialty.dataset.specialtyId !== specialty) {
            section.style.display = 'none';
            const listToCollapse = section.querySelector('.subjects-list');
            if (listToCollapse && listToCollapse.dataset.manualExpanded !== 'true') {
                const toggleId = listToCollapse.dataset.toggleId;
                setExpanded(listToCollapse, toggleId ? document.getElementById(toggleId) : null, false);
                listToCollapse.dataset.openedByFilter = 'false';
            }
            return;
        }

        const list = section.querySelector('.subjects-list');
        const toggleId = list?.dataset.toggleId;
        const toggle = toggleId ? document.getElementById(toggleId) : section.querySelector('.profession-toggle');
        const rows = list ? Array.from(list.querySelectorAll('.subject-row')) : [];
        const emptyState = list ? list.querySelector('.empty-state') : null;

        let visibleInSection = 0;

        rows.forEach(row => {
            const rowCourse = row.dataset.course || '';
            const rowFaculty = row.dataset.facultyId || '';
            const rowText = (row.dataset.search || '').toLowerCase();

            const matchesCourse = !course || rowCourse === course || Boolean(searchTerm);
            const matchesSpecialty = !specialty || rowFaculty === specialty;
            const matchesSearch = !searchTerm || rowText.includes(searchTerm);

            if (matchesCourse && matchesSpecialty && matchesSearch) {
                row.style.display = '';
                row.classList.remove('hidden-by-filter');
                visibleInSection += 1;
            } else {
                row.style.display = 'none';
                row.classList.add('hidden-by-filter');
            }
        });

        if (visibleInSection > 0) {
            section.style.display = '';
            totalVisibleRows += visibleInSection;
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            if (autoExpand) {
                if (list && list.dataset.manualExpanded !== 'true') {
                    setExpanded(list, toggle, true);
                    list.dataset.openedByFilter = 'true';
                }
            } else if (list && list.dataset.openedByFilter === 'true' && list.dataset.manualExpanded !== 'true') {
                setExpanded(list, toggle, false);
                list.dataset.openedByFilter = 'false';
            } else if (list) {
                setExpanded(list, toggle, list.classList.contains('show'));
            }
        } else {
            if (searchTerm) {
                section.style.display = 'none';
            } else {
                section.style.display = '';
                if (emptyState) {
                    emptyState.style.display = '';
                }
            }
            if (list) {
                if (list.dataset.manualExpanded !== 'true') {
                    setExpanded(list, toggle, false);
                }
                list.dataset.openedByFilter = 'false';
            }
        }
    });

    specialtySections.forEach(section => {
        if (section.style.display === 'none') {
            return;
        }

        const content = section.querySelector('.specialty-content');
        const toggle = section.querySelector('.specialty-toggle');
        const hasVisibleProfessions = Array.from(section.querySelectorAll('.profession-section')).some(
            prof => prof.style.display !== 'none'
        );

        if (!hasVisibleProfessions) {
            if (searchTerm) {
                section.style.display = 'none';
            } else if (content) {
                if (content.dataset.manualExpanded !== 'true') {
                    setExpanded(content, toggle, false);
                }
                content.dataset.openedByFilter = 'false';
            }
            return;
        }

        if (autoExpand && hasVisibleProfessions) {
            if (content && content.dataset.manualExpanded !== 'true') {
                setExpanded(content, toggle, true);
                content.dataset.openedByFilter = 'true';
            }
        } else if (content && content.dataset.openedByFilter === 'true' && content.dataset.manualExpanded !== 'true') {
            setExpanded(content, toggle, false);
            content.dataset.openedByFilter = 'false';
        }
    });

    const emptyState = document.getElementById('searchResultsEmpty');
    if (emptyState) {
        const hasFilters = Boolean(searchTerm) || Boolean(specialty) || Boolean(course);
        emptyState.style.display = hasFilters && totalVisibleRows === 0 ? 'flex' : 'none';
    }
}

function closeSubjectFilterMenu() {
    const filterMenu = document.getElementById('subjectFilterMenu');
    if (filterMenu) {
        filterMenu.classList.remove('show');
    }
}

function resetSubjectFilters() {
    if (!window.currentFilters) {
        window.currentFilters = {};
    }

    window.currentFilters.search = '';
    window.currentFilters.specialty = '';
    window.currentFilters.course = '1';

    const searchInput = document.querySelector('#subjectSearchForm input[name="search"]');
    if (searchInput) {
        searchInput.value = '';
    }

    const hiddenCourse = document.getElementById('courseFilterInput');
    if (hiddenCourse) {
        hiddenCourse.value = '1';
    }

    setActiveCourseTab('1');
    updateCourseTitle('1');
    updateFilterBadge();

    const selectContainer = document.getElementById('subjectSpecialtySelect');
    if (selectContainer) {
        const hiddenSelect = selectContainer.querySelector('select');
        const trigger = selectContainer.querySelector('.select-trigger');
        const selectText = selectContainer.querySelector('.select-text');
        const options = selectContainer.querySelectorAll('.select-option');

        if (hiddenSelect) {
            hiddenSelect.value = '';
        }
        if (selectText) {
            selectText.textContent = 'Все специальности';
        }
        if (trigger) {
            trigger.classList.add('placeholder');
            trigger.classList.remove('active');
        }
        options.forEach(option => {
            option.classList.toggle('selected', option.dataset.value === '');
        });
    }

    const professionInput = document.getElementById('professionInput');
    const professionDataList = document.getElementById('professionOptions');
    if (professionInput) {
        professionInput.value = '';
        professionInput.disabled = true;
        professionInput.placeholder = 'Сначала выберите специальность';
    }
    if (professionDataList) {
        professionDataList.innerHTML = '';
    }

    updateSearchClearButton('');
    closeSubjectFilterMenu();
    updateSubjectUrl();
    applySubjectFilters();
}

function clearSubjectSearch() {
    const input = document.querySelector('#subjectSearchForm input[name="search"]');
    if (!window.currentFilters) {
        window.currentFilters = {};
    }
    window.currentFilters.search = '';
    if (input) {
        input.value = '';
        input.focus();
    }
    updateSearchClearButton('');
    updateSubjectUrl();
    applySubjectFilters();
}

function switchSubjectCourse(courseNumber, event) {
    if (event) {
        event.preventDefault();
    }

    if (!window.currentFilters) {
        window.currentFilters = {};
    }
    window.currentFilters.course = courseNumber;

    const hiddenCourse = document.getElementById('courseFilterInput');
    if (hiddenCourse) {
        hiddenCourse.value = courseNumber;
    }

    setActiveCourseTab(courseNumber);
    updateCourseTitle(courseNumber);
    updateSubjectUrl();
    const forceExpand = Boolean(window.currentFilters.search) || Boolean(window.currentFilters.specialty);
    applySubjectFilters({ forceAutoExpand: forceExpand });
}

function toggleSubjectSpecialty(facultyId) {
    const content = document.getElementById(`subject-content-${facultyId}`);
    const toggle = document.getElementById(`subject-toggle-${facultyId}`);
    if (!content || !toggle) {
        return;
    }

    const expand = !content.classList.contains('show');
    setExpanded(content, toggle, expand);
    content.dataset.manualExpanded = expand ? 'true' : 'false';
    if (!expand) {
        content.dataset.openedByFilter = 'false';
        content.querySelectorAll('.subjects-list').forEach(list => {
            if (list.dataset.manualExpanded !== 'true') {
                const toggleId = list.dataset.toggleId;
                setExpanded(list, toggleId ? document.getElementById(toggleId) : null, false);
                list.dataset.openedByFilter = 'false';
            }
        });
    }
}

function toggleSubjectProfession(facultyId, index) {
    const list = document.getElementById(`subject-prof-content-${facultyId}-${index}`);
    const toggle = document.getElementById(`subject-prof-toggle-${facultyId}-${index}`);
    if (!list || !toggle) {
        return;
    }

    const expand = !list.classList.contains('show');
    setExpanded(list, toggle, expand);
    list.dataset.manualExpanded = expand ? 'true' : 'false';
    if (!expand) {
        list.dataset.openedByFilter = 'false';
    }
}

let allSubjectsExpanded = false;
function toggleAllSubjectSpecialties(ev) {
    const button = ev ? ev.target.closest('button') : null;
    const expandAll = !allSubjectsExpanded;

    document.querySelectorAll('.specialty-content').forEach(content => {
        const toggle = content.parentElement.querySelector('.specialty-toggle');
        setExpanded(content, toggle, expandAll);
        content.dataset.manualExpanded = expandAll ? 'true' : 'false';
        content.dataset.openedByFilter = 'false';
    });

    document.querySelectorAll('.subjects-list').forEach(list => {
        const toggleId = list.dataset.toggleId;
        const toggle = toggleId ? document.getElementById(toggleId) : null;
        setExpanded(list, toggle, expandAll);
        list.dataset.manualExpanded = expandAll ? 'true' : 'false';
        list.dataset.openedByFilter = 'false';
    });

    allSubjectsExpanded = expandAll;
    if (button) {
        button.innerHTML = expandAll
            ? '<i class="bi bi-arrows-collapse"></i> Свернуть все'
            : '<i class="bi bi-arrows-expand"></i> Развернуть все';
    }
}

function bindSearchHandlers() {
    const searchForm = document.getElementById('subjectSearchForm');
    const searchInput = searchForm ? searchForm.querySelector('input[name="search"]') : null;
    const clearButton = document.getElementById('subjectClearSearch');

    if (searchForm) {
        searchForm.addEventListener('submit', event => {
            event.preventDefault();
            updateSubjectUrl();
            applySubjectFilters({ forceAutoExpand: Boolean(window.currentFilters?.search) });
        });
    }

    if (searchInput) {
        let debounceTimer = null;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            updateSearchClearButton(searchInput.value);
            debounceTimer = setTimeout(() => {
                if (!window.currentFilters) {
                    window.currentFilters = {};
                }
                window.currentFilters.search = searchInput.value;
                updateSubjectUrl();
                applySubjectFilters({ forceAutoExpand: Boolean(searchInput.value.trim()) });
            }, 300);
        });

        searchInput.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                if (!window.currentFilters) {
                    window.currentFilters = {};
                }
                window.currentFilters.search = searchInput.value;
                updateSubjectUrl();
                applySubjectFilters({ forceAutoExpand: Boolean(searchInput.value.trim()) });
            }
        });

        updateSearchClearButton(searchInput.value);
    } else {
        updateSearchClearButton('');
    }

    if (clearButton) {
        clearButton.addEventListener('click', event => {
            event.preventDefault();
            clearSubjectSearch();
        });
    }
}

function updateSearchClearButton(value) {
    const clearButton = document.getElementById('subjectClearSearch');
    if (!clearButton) {
        return;
    }
    if (value && value.trim().length) {
        clearButton.style.display = 'inline-flex';
    } else {
        clearButton.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!window.currentFilters) {
        window.currentFilters = {};
    }
    window.currentFilters.search = window.currentFilters.search || '';
    window.currentFilters.specialty = window.currentFilters.specialty || '';
    window.currentFilters.course = window.currentFilters.course || '1';

    const hiddenCourse = document.getElementById('courseFilterInput');
    if (hiddenCourse) {
        hiddenCourse.value = window.currentFilters.course;
    }

    initSubjectFilterSelect();
    initializeSubjectExpansionState();
    setActiveCourseTab(window.currentFilters.course);
    updateCourseTitle(window.currentFilters.course);
    bindSearchHandlers();
    updateFilterBadge();

    const filterTrigger = document.getElementById('subjectFilterTrigger');
    const filterMenu = document.getElementById('subjectFilterMenu');
    if (filterTrigger && filterMenu) {
        filterTrigger.addEventListener('click', event => {
            event.stopPropagation();
            filterMenu.classList.toggle('show');
        });
        filterMenu.addEventListener('click', event => event.stopPropagation());
        document.addEventListener('click', event => {
            if (!event.target.closest('.filter-dropdown')) {
                filterMenu.classList.remove('show');
            }
        });
    }

    const applyButton = document.getElementById('subjectApplyFilters');
    if (applyButton) {
        applyButton.addEventListener('click', () => {
            closeSubjectFilterMenu();
            updateSubjectUrl();
            const shouldExpand = Boolean(window.currentFilters?.specialty) || Boolean(window.currentFilters?.search);
            applySubjectFilters({ forceAutoExpand: shouldExpand });
        });
    }

    const resetButton = document.getElementById('subjectResetFilters');
    if (resetButton) {
        resetButton.addEventListener('click', resetSubjectFilters);
    }

    const hasInitialFilters = Boolean(window.currentFilters.search) || Boolean(window.currentFilters.specialty);
    applySubjectFilters({ forceAutoExpand: hasInitialFilters });
});

window.clearSubjectSearch = clearSubjectSearch;
window.switchSubjectCourse = switchSubjectCourse;
window.toggleSubjectSpecialty = toggleSubjectSpecialty;
window.toggleSubjectProfession = toggleSubjectProfession;
window.toggleAllSubjectSpecialties = toggleAllSubjectSpecialties;
window.resetSubjectFilters = resetSubjectFilters;
