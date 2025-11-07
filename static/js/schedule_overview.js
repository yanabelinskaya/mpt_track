(() => {
    function parseJSONScript(id) {
        const node = document.getElementById(id);
        if (!node) {
            return null;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            console.warn(`schedule_overview: не удалось распарсить JSON из #${id}`, error);
            return null;
        }
    }

    function setSectionExpanded(content, icon, expand) {
        if (!content) {
            return;
        }
        if (expand) {
            content.classList.add('show');
            if (icon) {
                icon.classList.add('rotated');
            }
        } else {
            content.classList.remove('show');
            if (icon) {
                icon.classList.remove('rotated');
            }
        }
    }

    function updateRowVisibility(row) {
        const shouldHide = row.classList.contains('hidden-by-course') || row.classList.contains('hidden-by-search');
        row.style.display = shouldHide ? 'none' : '';
    }

    function expandAncestors(row) {
        const professionContent = row.closest('.groups-list');
        const professionToggle = professionContent?.previousElementSibling?.querySelector('.profession-toggle');
        if (professionContent) {
            setSectionExpanded(professionContent, professionToggle, true);
        }
        const specialtyContent = row.closest('.specialty-content');
        const specialtyToggle = specialtyContent?.previousElementSibling?.querySelector('.specialty-toggle');
        if (specialtyContent) {
            setSectionExpanded(specialtyContent, specialtyToggle, true);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('scheduleFiltersForm');
        if (!form) {
            return;
        }

        const filterTrigger = document.getElementById('scheduleFilterTrigger');
        const filterMenu = document.getElementById('scheduleFilterMenu');
        const facultySelect = document.getElementById('scheduleFacultyFilter');
        const professionSelect = document.getElementById('scheduleProfessionFilter');
        const professionWrapper = document.getElementById('scheduleProfessionSelect');
        const statusRadios = form.querySelectorAll('input[name="status"]');
        const searchInput = document.getElementById('scheduleSearchInput');
        const searchSubmitButton = document.getElementById('scheduleSearchSubmit');
        const searchClearButton = document.getElementById('scheduleSearchClear');
        const searchEmptyState = document.getElementById('scheduleSearchEmpty');
        const courseInput = document.getElementById('scheduleCourseInput');
        const courseTabs = Array.from(document.querySelectorAll('.course-tab'));
        const toggleAllButton = document.getElementById('scheduleToggleAll');
        const specialtySections = Array.from(document.querySelectorAll('.specialty-section'));
        const groupsLists = Array.from(document.querySelectorAll('.groups-list'));
        const groupRows = Array.from(document.querySelectorAll('.group-row'));

        const facultyProfessions = parseJSONScript('scheduleFacultyProfessions') || {};
        const currentFilters = parseJSONScript('scheduleCurrentFilters') || {};

        const state = {
            activeCourse: '',
            currentSearch: '',
            currentSearchNormalized: '',
        };

        let allExpanded = false;
        const SEARCH_DEBOUNCE_MS = 350;
        let searchDebounceId = null;

        if (window.CustomSelect?.init) {
            window.CustomSelect.init(form);
        }

        const toggleFilterMenu = (forceState) => {
            if (!filterMenu) {
                return;
            }
            const shouldShow = typeof forceState === 'boolean'
                ? forceState
                : !filterMenu.classList.contains('show');
            if (shouldShow) {
                filterMenu.classList.add('show');
            } else {
                filterMenu.classList.remove('show');
            }
        };

        if (filterTrigger && filterMenu) {
            filterTrigger.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleFilterMenu();
            });

            filterMenu.addEventListener('click', (event) => {
                event.stopPropagation();
            });

            document.addEventListener('click', () => toggleFilterMenu(false));
        }

        const updateCourseInHistory = (course) => {
            const url = new URL(window.location.href);
            if (course) {
                url.searchParams.set('course', course);
            } else {
                url.searchParams.delete('course');
            }
            window.history.replaceState({}, '', url.toString());
        };

        const updateSearchInHistory = (query) => {
            const url = new URL(window.location.href);
            if (query) {
                url.searchParams.set('search', query);
            } else {
                url.searchParams.delete('search');
            }
            window.history.replaceState({}, '', url.toString());
        };

        const ensureCourseEmptyState = (list) => {
            let emptyNode = list.querySelector('.empty-state-course');
            if (!emptyNode) {
                emptyNode = document.createElement('div');
                emptyNode.className = 'empty-state empty-state-course';
                emptyNode.innerHTML = `
                    <h4>Нет данных</h4>
                    <p>Для выбранного курса пока нет расписания по этой профессии.</p>
                `;
                list.appendChild(emptyNode);
            }
            return emptyNode;
        };

        const populateProfessions = (facultyId, selectedValue) => {
            if (!professionSelect) {
                return;
            }

            const professions = facultyProfessions[String(facultyId)] || [];
            const normalizedSelected = (selectedValue || '').trim().toLowerCase();

            professionSelect.innerHTML = '';
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Все профессии';
            professionSelect.appendChild(defaultOption);

            professions.forEach((profession) => {
                const option = document.createElement('option');
                option.value = profession;
                option.textContent = profession;
                if (normalizedSelected && profession.toLowerCase() === normalizedSelected) {
                    option.selected = true;
                }
                professionSelect.appendChild(option);
            });

            if (!professions.length) {
                professionSelect.value = '';
            }

            if (professionWrapper) {
                const dropdown = professionWrapper.querySelector('.select-dropdown');
                const trigger = professionWrapper.querySelector('.select-trigger');
                const textElement = trigger?.querySelector('.select-text');

                if (dropdown) {
                    dropdown.innerHTML = '';

                    const renderOption = (value, label, selected) => {
                        const optionDiv = document.createElement('div');
                        optionDiv.className = `select-option${selected ? ' selected' : ''}`;
                        optionDiv.dataset.value = value;

                        const textDiv = document.createElement('div');
                        textDiv.className = 'select-option-text';
                        textDiv.textContent = label;

                        optionDiv.appendChild(textDiv);
                        dropdown.appendChild(optionDiv);
                    };

                    renderOption('', 'Все профессии', !normalizedSelected);
                    professions.forEach((profession) => {
                        const selected = normalizedSelected && profession.toLowerCase() === normalizedSelected;
                        renderOption(profession, profession, selected);
                    });
                }

                if (textElement) {
                    const currentLabel = professionSelect.value ? professionSelect.value : 'Все профессии';
                    textElement.textContent = currentLabel;
                    textElement.title = currentLabel;
                }

                if (trigger) {
                    if (professionSelect.value) {
                        trigger.classList.remove('placeholder');
                    } else {
                        trigger.classList.add('placeholder');
                    }
                }

                if (professionWrapper.dataset.customSelectInitialized) {
                    delete professionWrapper.dataset.customSelectInitialized;
                }

                if (window.CustomSelect?.init) {
                    window.CustomSelect.init(professionWrapper);
                }
            }
        };

        const setActiveCourseTab = (course) => {
            courseTabs.forEach((tab) => {
                if (tab.dataset.course === course) {
                    tab.classList.add('active');
                } else {
                    tab.classList.remove('active');
                }
            });
        };

        const refreshVisibility = ({ expandMatches = false } = {}) => {
            let firstMatchedCourse = '';
            let matchCount = 0;

            groupsLists.forEach((list) => {
                const rows = Array.from(list.querySelectorAll('.group-row'));
                let visibleInSearch = 0;
                let visibleInCourse = 0;

                rows.forEach((row) => {
                    updateRowVisibility(row);

                    const hiddenByCourse = row.classList.contains('hidden-by-course');
                    const hiddenBySearch = row.classList.contains('hidden-by-search');

                    if (!hiddenByCourse) {
                        visibleInCourse += 1;
                    }

                    if (!hiddenByCourse && !hiddenBySearch) {
                        visibleInSearch += 1;
                        matchCount += 1;
                        if (!firstMatchedCourse) {
                            firstMatchedCourse = row.dataset.groupCourse || '';
                        }
                        if (expandMatches) {
                            expandAncestors(row);
                        }
                    }
                });

                const table = list.querySelector('.groups-table');
                if (table) {
                    table.style.display = visibleInSearch ? '' : 'none';
                }

                const emptyCourseNode = ensureCourseEmptyState(list);
                emptyCourseNode.hidden = visibleInSearch > 0;

                const professionSection = list.closest('.profession-section');
                if (professionSection) {
                    professionSection.classList.toggle('hidden-by-course', Boolean(state.activeCourse) && visibleInCourse === 0);
                    professionSection.classList.toggle('hidden-by-search', Boolean(state.currentSearchNormalized) && visibleInSearch === 0);
                }
            });

            specialtySections.forEach((section) => {
                const visibleInCourse = section.querySelectorAll('.group-row:not(.hidden-by-course)').length;
                const visibleInSearch = section.querySelectorAll('.group-row:not(.hidden-by-course):not(.hidden-by-search)').length;
                section.classList.toggle('hidden-by-course', Boolean(state.activeCourse) && visibleInCourse === 0);
                section.classList.toggle('hidden-by-search', Boolean(state.currentSearchNormalized) && visibleInSearch === 0);
            });

            if (searchEmptyState) {
                searchEmptyState.hidden = !state.currentSearchNormalized || matchCount > 0;
            }

            return firstMatchedCourse;
        };

        const applyCourseFilter = (course, options = {}) => {
            const selectedCourse = (course || '').trim();
            state.activeCourse = selectedCourse;

            if (courseInput) {
                courseInput.value = selectedCourse;
            }
            if (currentFilters) {
                currentFilters.course = selectedCourse;
            }

            if (options.updateHistory !== false) {
                updateCourseInHistory(selectedCourse);
            }

            setActiveCourseTab(selectedCourse);

            groupRows.forEach((row) => {
                const rowCourse = row.dataset.groupCourse || '';
                const matches = !selectedCourse || rowCourse === selectedCourse;
                row.classList.toggle('hidden-by-course', !matches);
            });

            return refreshVisibility({ expandMatches: options.expandMatches === true });
        };

        const applySearch = (value, options = {}) => {
            state.currentSearch = (value || '').trim();
            state.currentSearchNormalized = state.currentSearch.toLowerCase();

            if (searchInput) {
                searchInput.value = state.currentSearch;
            }
            if (searchClearButton) {
                searchClearButton.style.display = state.currentSearch ? '' : 'none';
            }

            if (options.updateHistory !== false) {
                updateSearchInHistory(state.currentSearch);
            }

            groupRows.forEach((row) => {
                const haystack = (row.dataset.search || '').toLowerCase();
                const matches = !state.currentSearchNormalized || haystack.includes(state.currentSearchNormalized);
                row.classList.toggle('hidden-by-search', !matches);
            });

            const firstMatchCourse = refreshVisibility({ expandMatches: options.expand !== false });

            if (state.currentSearch && options.autoCourse !== false && firstMatchCourse && firstMatchCourse !== state.activeCourse) {
                applyCourseFilter(firstMatchCourse, { updateHistory: true });
                refreshVisibility({ expandMatches: options.expand !== false });
            }
        };

        const queueAutoSearch = (value) => {
            window.clearTimeout(searchDebounceId);
            searchDebounceId = window.setTimeout(() => {
                applySearch(value, { autoCourse: true, expand: true });
            }, SEARCH_DEBOUNCE_MS);
        };

        const bindSectionToggles = () => {
            specialtySections.forEach((section) => {
                const header = section.querySelector('.specialty-header');
                const content = section.querySelector('.specialty-content');
                const icon = section.querySelector('.specialty-toggle');
                if (!header || !content) {
                    return;
                }
                header.addEventListener('click', (event) => {
                    event.preventDefault();
                    if (section.classList.contains('hidden-by-course') || section.classList.contains('hidden-by-search')) {
                        return;
                    }
                    const expanded = content.classList.contains('show');
                    setSectionExpanded(content, icon, !expanded);
                });
            });

            groupsLists.forEach((list) => {
                const header = list.previousElementSibling;
                const icon = header?.querySelector('.profession-toggle');
                if (!header) {
                    return;
                }
                header.addEventListener('click', (event) => {
                    event.preventDefault();
                    const section = header.closest('.profession-section');
                    if (section?.classList.contains('hidden-by-course') || section?.classList.contains('hidden-by-search')) {
                        return;
                    }
                    const expanded = list.classList.contains('show');
                    setSectionExpanded(list, icon, !expanded);
                });
            });
        };

        if (facultySelect) {
            populateProfessions(
                facultySelect.value || currentFilters.faculty,
                currentFilters.profession,
            );

            facultySelect.addEventListener('change', () => {
                populateProfessions(facultySelect.value, '');
                form.submit();
            });
        }

        if (professionSelect) {
            professionSelect.addEventListener('change', () => {
                form.submit();
            });
        }

        statusRadios.forEach((radio) => {
            radio.addEventListener('change', () => form.submit());
        });

        courseTabs.forEach((tab) => {
            if (tab.classList.contains('disabled')) {
                return;
            }
            tab.addEventListener('click', (event) => {
                event.preventDefault();
                if (tab.classList.contains('active')) {
                    return;
                }
                const course = tab.dataset.course;
                applyCourseFilter(course, { updateHistory: true });
            });
        });

        if (toggleAllButton) {
            toggleAllButton.addEventListener('click', (event) => {
                event.preventDefault();
                allExpanded = !allExpanded;

                specialtySections.forEach((section) => {
                    if (section.classList.contains('hidden-by-course') || section.classList.contains('hidden-by-search')) {
                        return;
                    }
                    const content = section.querySelector('.specialty-content');
                    const icon = section.querySelector('.specialty-toggle');
                    setSectionExpanded(content, icon, allExpanded);
                });

                groupsLists.forEach((list) => {
                    const professionSection = list.closest('.profession-section');
                    if (!professionSection || professionSection.classList.contains('hidden-by-course') || professionSection.classList.contains('hidden-by-search')) {
                        return;
                    }
                    const icon = list.previousElementSibling?.querySelector('.profession-toggle');
                    setSectionExpanded(list, icon, allExpanded);
                });

                toggleAllButton.innerHTML = allExpanded
                    ? '<i class="bi bi-arrows-collapse"></i> Свернуть все'
                    : '<i class="bi bi-arrows-expand"></i> Развернуть все';
            });
        }

        bindSectionToggles();

        if (searchClearButton) {
            searchClearButton.addEventListener('click', () => {
                window.clearTimeout(searchDebounceId);
                applySearch('', { autoCourse: false });
                if (searchInput) {
                    searchInput.focus();
                }
            });
        }

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const value = searchInput.value;
                if (searchClearButton) {
                    searchClearButton.style.display = value.trim() ? '' : 'none';
                }
                queueAutoSearch(value);
            });
        }

        form.addEventListener('submit', (event) => {
            const submitter = event.submitter;
            const isSearchSubmit = submitter === searchSubmitButton
                || (!submitter && document.activeElement === searchInput);

            if (!isSearchSubmit) {
                return;
            }

            event.preventDefault();
            window.clearTimeout(searchDebounceId);
            applySearch(searchInput ? searchInput.value : '', { autoCourse: true, expand: true });
        });

        let initialCourse = courseInput?.value || currentFilters.course || '';
        if (!initialCourse) {
            const activeTab = courseTabs.find((tab) => tab.classList.contains('active'));
            if (activeTab) {
                initialCourse = activeTab.dataset.course || '';
            }
        }

        applyCourseFilter(initialCourse, { updateHistory: false });

        const initialSearch = searchInput ? searchInput.value : '';
        applySearch(initialSearch, { autoCourse: true, expand: Boolean(initialSearch), updateHistory: false });

        if (searchClearButton) {
            searchClearButton.style.display = initialSearch ? '' : 'none';
        }
    });
})();
