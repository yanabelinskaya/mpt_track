(() => {
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.scheduleInitialData) {
            return;
        }

        const config = window.scheduleInitialData;
        const endpoints = config.endpoints || {};
        const savedWeekLessons = config.weekLessons || {};
        const LESSON_TYPES = [
            { value: 'lesson', label: 'Пара' },
            { value: 'lecture', label: 'Лекция' },
            { value: 'practice', label: 'Практика' },
            { value: 'lab', label: 'Лабораторная' },
            { value: 'consultation', label: 'Консультация' },
            { value: 'other', label: 'Другое' },
        ];

        const BUILDING_OPTIONS = [
            { value: 'nakhimovsky', label: 'Нахимовский проспект', short: 'Нахимовский пр-т' },
            { value: 'nezhinskaya', label: 'Нежинская улица', short: 'Нежинская ул.' },
        ];
        const BUILDING_LOOKUP = BUILDING_OPTIONS.reduce((acc, option) => {
            acc[option.value] = option;
            return acc;
        }, {});
        const DEFAULT_BUILDING = BUILDING_OPTIONS[0].value;

        const state = {
            lessons: new Map(),
            weekLessons: {},
            weekBuildings: {},
            dayBuildings: {},
            selectedCellKey: null,
            weekStart: parseISODate(config.weekStart),
            weekEnd: parseISODate(config.weekEnd),
            currentWeekKey: config.weekStart,
            selectedTeacherId: '',
            searchTerm: '',
            activeView: 'week',
            changeLog: [],
            modalContext: null,
            currentWeekParity: 'numerator',
            semesterWeeks: [],
            semesterSelectionMode: false,
            semesterSelection: new Set(),
            dirtyWeeks: new Set(),
            isSaving: false,
        };

        const elements = {
            grid: document.getElementById('scheduleGrid'),
            subjectPool: document.getElementById('scheduleSubjectPool'),
            refreshPoolButton: document.querySelector('[data-action="refresh-pool"]'),
            clearWeekButton: document.querySelector('[data-action="clear-week"]'),
            saveWeekButton: document.querySelector('[data-action="save-week"]'),
            applySemesterButton: document.querySelector('[data-action="apply-semester"]'),
            message: document.getElementById('scheduleMessage'),
            weekRange: document.getElementById('scheduleWeekRange'),
            weekParityLabel: document.getElementById('scheduleWeekParityLabel'),
            weekButtons: document.querySelectorAll('.week-switcher__btn'),
            viewTabs: document.querySelectorAll('[data-view-tab]'),
            viewPanels: document.querySelectorAll('[data-view-panel]'),
            teacherSelect: document.getElementById('scheduleTeacherSelect'),
            searchInput: document.getElementById('scheduleSearchInput'),
            searchClearButton: document.getElementById('scheduleSearchClear'),
            dayBoard: document.getElementById('scheduleDayBoard'),
            semesterTimeline: document.getElementById('scheduleSemesterTimeline'),
            changeLogSection: document.getElementById('scheduleChangeLog'),
            changeLogList: document.getElementById('scheduleChangeLogList'),
            lessonModal: document.getElementById('scheduleLessonModal'),
            lessonModalForm: document.getElementById('scheduleLessonForm'),
            lessonModalSlot: document.getElementById('lessonModalSlot'),
            lessonSubjectName: document.getElementById('lessonSubjectName'),
            lessonSubjectShort: document.getElementById('lessonSubjectShort'),
            lessonTeacherSelectWrapper: document.getElementById('lessonTeacherSelectWrapper'),
            teacherSelectedText: document.getElementById('lessonTeacherSelected'),
            teacherOptionsContainer: document.getElementById('lessonTeacherOptions'),
            teacherRoomsContainer: document.getElementById('lessonTeacherRooms'),
            dayBuildingControls: Array.from(document.querySelectorAll('[data-building-day]')),
            dayBuildingBadges: Array.from(document.querySelectorAll('[data-building-badge]')),
            parityToggle: document.getElementById('lessonParityToggle'),
            lessonTypeSelectWrapper: document.getElementById('lessonTypeSelectWrapper'),
            lessonTypeSelect: document.getElementById('lessonTypeSelect'),
            lessonDeleteButton: document.getElementById('lessonDeleteButton'),
            saveWeekLabel: document.querySelector('[data-save-text]'),
            saveWeekIcon: document.querySelector('[data-save-icon]'),
            semesterButtonLabel: document.querySelector('[data-semester-text]'),
            semesterButtonIcon: document.querySelector('[data-semester-icon]'),
            conflictModal: document.getElementById('scheduleConflictModal'),
            conflictModalSubtitle: document.getElementById('conflictModalSubtitle'),
            conflictModalList: document.getElementById('conflictModalList'),
        };
        elements.modalCloseButtons = document.querySelectorAll('[data-modal-close]');
        elements.conflictCloseButtons = document.querySelectorAll('[data-conflict-close]');

        const subjectMap = new Map((config.subjects || []).map((subject) => [String(subject.id), subject]));
        const teacherMap = new Map((config.teachers || []).map((teacher) => [String(teacher.id), teacher]));
        const droppableCells = elements.grid
            ? Array.from(elements.grid.querySelectorAll('.grid-cell--droppable'))
            : [];
        const libraryItems = elements.subjectPool
            ? Array.from(elements.subjectPool.querySelectorAll('.library-item'))
            : [];
        const daySlotNodes = elements.dayBoard
            ? Array.from(elements.dayBoard.querySelectorAll('[data-day-slot]'))
            : [];
        const weekDayMap = new Map((config.weekdayOrder || []).map((day) => [day.key, day]));
        const timeSlotMap = new Map((config.timeSlots || []).map((slot) => [slot.id, slot]));
        const defaultDayBuildingPreset = createDefaultDayBuildings(config.dayBuildings);

        state.weekStart = startOfWeek(state.weekStart);
        state.weekEnd = addDays(state.weekStart, 5);
        state.currentWeekKey = formatISODate(state.weekStart);
        state.semesterWeeks = buildAcademicYearWeeks(state.weekStart);
        Object.keys(savedWeekLessons || {}).forEach((weekKey) => {
            const payload = savedWeekLessons[weekKey];
            state.weekLessons[weekKey] = lessonsMapFromObject(payload);
            if (payload && payload.dayBuildings && !state.weekBuildings[weekKey]) {
                state.weekBuildings[weekKey] = createDefaultDayBuildings(payload.dayBuildings);
            }
        });
        if (state.weekLessons[state.currentWeekKey]) {
            state.lessons = state.weekLessons[state.currentWeekKey];
        } else {
            state.weekLessons[state.currentWeekKey] = state.lessons;
        }
        if (config.weekBuildings && typeof config.weekBuildings === 'object') {
            Object.keys(config.weekBuildings).forEach((weekKey) => {
                const overrides = config.weekBuildings[weekKey];
                const preset = applyDayBuildingOverrides(cloneDayBuildings(defaultDayBuildingPreset), overrides);
                state.weekBuildings[weekKey] = preset;
            });
        }
        ensureDayBuildingsForCurrentWeek();
        state.currentWeekParity = calculateWeekParity(state.weekStart);

        hydrateGridFromLessons();
        renderDayView();
        updateWeekRange();
        updateWeekParityLabel();
        renderDayBuildingControls();
        updateBuildingBadges();
        applySubjectFilters();
        renderSemesterTimeline();
        renderChangeLog();
        updateSaveButtonState();
        updateSemesterButtonState();

        attachDragAndDrop();
        attachCellSelection();
        attachFilters();
        attachActions();
        attachModalEvents();
        attachConflictModalEvents();
        initTeacherPicker();
        initParityToggle();
        attachBuildingControls();

        switchView('week', { silent: true });

        if (config.activeGroup && config.activeGroup.code) {
            showMessage(`Редактирование расписания для группы ${config.activeGroup.code}.`, 'info');
        } else {
            showMessage('Режим недели активен. Перетащите предмет в сетку, чтобы добавить пару.', 'info');
        }

        function attachDragAndDrop() {
            libraryItems.forEach((item) => {
                item.addEventListener('dragstart', (event) => {
                    const subjectId = item.dataset.subjectId;
                    if (!subjectId) {
                        return;
                    }
                    event.dataTransfer.effectAllowed = 'copy';
                    event.dataTransfer.setData('text/plain', subjectId);
                    item.classList.add('dragging');
                });

                item.addEventListener('dragend', () => {
                    item.classList.remove('dragging');
                });
            });

            droppableCells.forEach((cell) => {
                cell.addEventListener('dragover', (event) => {
                    event.preventDefault();
                    cell.classList.add('drag-over');
                });

                cell.addEventListener('dragleave', (event) => {
                    if (!cell.contains(event.relatedTarget)) {
                        cell.classList.remove('drag-over');
                    }
                });

                cell.addEventListener('drop', (event) => {
                    event.preventDefault();
                    cell.classList.remove('drag-over');
                    const subjectId = event.dataTransfer.getData('text/plain');
                    if (!subjectId) {
                        return;
                    }
                    handleLessonDrop(cell, subjectId);
                });
            });
        }

        function attachCellSelection() {
            droppableCells.forEach((cell) => {
                cell.addEventListener('click', (event) => {
                    event.stopPropagation();
                    selectCell(cell);
                });
            });

            document.addEventListener('click', (event) => {
                if (!event.target.closest('.schedule-card--board')) {
                    clearSelection();
                }
            });
        }

        function attachFilters() {
            if (elements.teacherSelect) {
                elements.teacherSelect.addEventListener('change', () => {
                    state.selectedTeacherId = elements.teacherSelect.value || '';
                    applySubjectFilters();
                    if (state.selectedTeacherId) {
                        const teacher = teacherMap.get(String(state.selectedTeacherId));
                        const teacherName = teacher ? teacher.name : '';
                        showMessage(`Фильтр по преподавателю: ${teacherName}`, 'info');
                    } else {
                        showMessage('Фильтр по преподавателю отключен', 'info');
                    }
                });
            }

            if (elements.searchInput) {
                const syncClear = () => {
                    if (elements.searchClearButton) {
                        elements.searchClearButton.hidden = !elements.searchInput.value.trim();
                    }
                };

                elements.searchInput.addEventListener('input', () => {
                    state.searchTerm = elements.searchInput.value.trim().toLowerCase();
                    applySubjectFilters();
                    syncClear();
                });

                if (elements.searchClearButton) {
                    elements.searchClearButton.addEventListener('click', () => {
                        elements.searchInput.value = '';
                        state.searchTerm = '';
                        syncClear();
                        applySubjectFilters();
                        elements.searchInput.focus();
                    });
                }

                syncClear();
            }
        }

        function attachActions() {
            if (elements.clearWeekButton) {
                elements.clearWeekButton.addEventListener('click', () => {
                    clearWeek();
                });
            }

            if (elements.saveWeekButton) {
                elements.saveWeekButton.addEventListener('click', () => {
                    saveSchedule();
                });
            }

            if (elements.applySemesterButton) {
                elements.applySemesterButton.addEventListener('click', () => {
                    if (state.semesterSelectionMode) {
                        exitSemesterSelectionMode();
                    } else {
                        enterSemesterSelectionMode();
                    }
                });
            }

            if (elements.refreshPoolButton) {
                elements.refreshPoolButton.addEventListener('click', () => {
                    applySubjectFilters();
                    showMessage('Список предметов обновлён согласно текущим фильтрам.', 'success');
                });
            }

            elements.weekButtons.forEach((button) => {
                button.addEventListener('click', () => {
                    const action = button.dataset.action;
                    if (action === 'prev-week') {
                        shiftWeek(-7);
                    } else if (action === 'next-week') {
                        shiftWeek(7);
                    }
                });
            });

            if (elements.lessonDeleteButton) {
                elements.lessonDeleteButton.addEventListener('click', () => {
                    if (!state.modalContext || !state.modalContext.cellKey) {
                        return;
                    }
                    deleteLesson(state.modalContext.cellKey, { trackChange: true, parity: state.modalContext.parityKey || 'both' });
                    closeLessonModal();
                    showMessage('Занятие удалено.', 'success');
                });
            }

            if (elements.viewTabs && elements.viewTabs.length) {
                elements.viewTabs.forEach((btn) => {
                    btn.addEventListener('click', () => {
                        const view = btn.dataset.viewTab || 'week';
                        if (view === state.activeView) {
                            return;
                        }
                        switchView(view);
                    });
                });
            }
        }

        function saveSchedule() {
            if (state.isSaving) {
                return;
            }
            if (!endpoints.save) {
                showMessage('Сохранение недоступно: не задан адрес API.', 'error');
                return;
            }
            const selectedWeeks = state.semesterSelectionMode ? Array.from(state.semesterSelection) : [];
            const isSemesterSave = selectedWeeks.length > 0;
            if (state.semesterSelectionMode && !isSemesterSave) {
                showMessage('Выберите недели в календаре или отключите режим сохранения на полугодие.', 'warning');
                return;
            }
            if (isSemesterSave) {
                copyCurrentWeekToSelected(selectedWeeks);
            }
            if (!state.dirtyWeeks.size) {
                showMessage('Нет изменений для сохранения.', 'info');
                return;
            }
            const weeksToSave = Array.from(state.dirtyWeeks);
            const weeksPayload = {};
            weeksToSave.forEach((weekKey) => {
                let lessonMap = state.weekLessons[weekKey];
                if (!lessonMap) {
                    lessonMap = new Map();
                    state.weekLessons[weekKey] = lessonMap;
                }
                weeksPayload[weekKey] = {
                    lessons: lessonsMapToObject(lessonMap),
                    dayBuildings: cloneDayBuildings(state.weekBuildings[weekKey] || defaultDayBuildingPreset),
                };
            });
            setSavingState(true);
            fetch(endpoints.save, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                credentials: 'same-origin',
                body: JSON.stringify({ weeks: weeksPayload }),
            })
                .then(async (response) => {
                    let data = null;
                    try {
                        data = await response.json();
                    } catch (error) {
                        // ignore json parse errors
                    }
                    if (!response.ok || (data && data.success === false)) {
                        const error = new Error(data?.error || data?.message || 'Не удалось сохранить расписание.');
                        error.details = data;
                        throw error;
                    }
                    return data || { success: true };
                })
                .then((data) => {
                    const savedWeeks = Array.isArray(data.savedWeeks) && data.savedWeeks.length
                        ? data.savedWeeks
                        : weeksToSave;
                    savedWeeks.forEach((weekKey) => state.dirtyWeeks.delete(weekKey));
                    renderSemesterTimeline();
                    if (isSemesterSave) {
                        exitSemesterSelectionMode({ silent: true });
                    }
                    updateSaveButtonState();
                    showMessage(data.message || 'Расписание сохранено.', 'success');
                })
                .catch((error) => {
                    let message = error.message || 'Не удалось сохранить расписание.';
                    if (error.details?.conflicts?.length) {
                        const conflictText = error.details.conflicts
                            .slice(0, 3)
                            .map((conflict) => {
                                const teacher = conflict.teacher || 'Преподаватель';
                                const group = conflict.group ? `у группы ${conflict.group}` : '';
                                const dayInfo = weekDayMap.get(conflict.day);
                                const dayLabel = dayInfo ? dayInfo.label : (conflict.day || '');
                                const slotInfo = timeSlotMap.get(conflict.slot);
                                const slotLabel = slotInfo ? `${slotInfo.order} пара` : (conflict.slot || '');
                                const parityLabel = conflict.parity === 'numerator' ? 'числитель' : 'знаменатель';
                                return `${teacher} ${group} (${dayLabel}, ${slotLabel}, ${parityLabel})`;
                            })
                            .join('; ');
                        if (conflictText) {
                            message = `${message} ${conflictText}`.trim();
                        }
                    }
                    showMessage(message, 'error');
                })
                .finally(() => setSavingState(false));
        }

        function setSavingState(isSaving) {
            state.isSaving = Boolean(isSaving);
            if (elements.saveWeekButton) {
                elements.saveWeekButton.disabled = state.isSaving;
                elements.saveWeekButton.classList.toggle('is-loading', state.isSaving);
            }
            updateSaveButtonState();
        }

        function updateSaveButtonState() {
            if (!elements.saveWeekButton) {
                return;
            }
            const hasSelection = state.semesterSelectionMode && state.semesterSelection.size > 0;
            const label = hasSelection ? 'Сохранить полугодие' : 'Сохранить неделю';
            const icon = hasSelection ? 'bi-calendar-check' : 'bi-save';
            if (elements.saveWeekLabel) {
                elements.saveWeekLabel.textContent = state.isSaving ? 'Сохранение…' : label;
            }
            if (elements.saveWeekIcon) {
                elements.saveWeekIcon.className = `bi ${icon}`;
            }
        }

        function updateSemesterButtonState() {
            if (!elements.applySemesterButton) {
                return;
            }
            const isActive = state.semesterSelectionMode;
            const label = isActive ? 'Отменить выбор' : 'На полугодие';
            const icon = isActive ? 'bi-x-circle' : 'bi-calendar-range';
            if (elements.semesterButtonLabel) {
                elements.semesterButtonLabel.textContent = label;
            }
            if (elements.semesterButtonIcon) {
                elements.semesterButtonIcon.className = `bi ${icon}`;
            }
            elements.applySemesterButton.classList.toggle('is-active', isActive);
        }

        function getCsrfToken() {
            if (config.csrfToken) {
                return config.csrfToken;
            }
            const match = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
            return match ? decodeURIComponent(match[2]) : '';
        }

        function ensureNoTeacherConflicts({ teacherIds, dayKey, slotKey, parityKey }) {
            if (!endpoints.checkConflict || !Array.isArray(teacherIds) || !teacherIds.length) {
                return Promise.resolve();
            }
            const payload = {
                weekStart: state.currentWeekKey,
                dayKey,
                slotKey,
                parity: parityKey,
                teacherIds,
            };
            return fetch(endpoints.checkConflict, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            })
                .then(async (response) => {
                    let data = null;
                    try {
                        data = await response.json();
                    } catch (error) {
                        // ignore
                    }
                    if (!response.ok || (data && data.success === false)) {
                        const error = new Error(data?.error || 'Преподаватель уже занят в это время.');
                        error.details = data;
                        throw error;
                    }
                    return data;
                });
        }

        function showConflictModal(conflicts = [], message = '') {
            if (!elements.conflictModal) {
                if (message) {
                    showMessage(message, 'error');
                }
                return;
            }
            const info = message || 'Преподаватель уже назначен у другой группы в это время. Выберите другое окно или замените преподавателя.';
            if (elements.conflictModalSubtitle) {
                elements.conflictModalSubtitle.textContent = info;
            }
            if (elements.conflictModalList) {
                elements.conflictModalList.innerHTML = createConflictListMarkup(conflicts);
            }
            elements.conflictModal.removeAttribute('hidden');
            elements.conflictModal.classList.add('is-open');
            syncModalBodyState();
        }

        function closeConflictModal() {
            if (!elements.conflictModal) {
                return;
            }
            elements.conflictModal.classList.remove('is-open');
            elements.conflictModal.setAttribute('hidden', 'hidden');
            if (elements.conflictModalList) {
                elements.conflictModalList.innerHTML = '';
            }
            syncModalBodyState();
        }

        function createConflictListMarkup(conflicts = []) {
            if (!Array.isArray(conflicts) || !conflicts.length) {
                return `
                    <li class="conflict-list__item">
                        <span class="conflict-list__teacher"><i class="bi bi-info-circle"></i> Нет подробностей</span>
                        <span class="conflict-list__details">Попробуйте выбрать другое время или преподавателя.</span>
                    </li>
                `;
            }
            return conflicts.map((conflict) => createConflictListItem(conflict)).join('');
        }

        function createConflictListItem(conflict = {}) {
            const teacher = escapeHtml(conflict.teacher || 'Преподаватель');
            const groupLabel = conflict.group ? `Группа ${escapeHtml(conflict.group)}` : 'Другая группа';
            const dayLabel = escapeHtml(getConflictDayLabel(conflict.day));
            const slotLabel = escapeHtml(getConflictSlotLabel(conflict.slot));
            const parityLabel = formatParityLabel(conflict.parity);
            const weekLabel = formatConflictWeek(conflict.week);
            const details = [
                groupLabel,
                dayLabel,
                slotLabel,
                parityLabel,
                weekLabel,
            ]
                .filter(Boolean)
                .join(' • ');
            return `
                <li class="conflict-list__item">
                    <span class="conflict-list__teacher"><i class="bi bi-person-exclamation"></i>${teacher}</span>
                    <span class="conflict-list__details">${details}</span>
                </li>
            `;
        }

        function buildConflictMessage(conflicts) {
            if (!Array.isArray(conflicts) || !conflicts.length) {
                return '';
            }
            const summaries = conflicts.slice(0, 2).map((conflict) => {
                const teacher = conflict.teacher || 'Преподаватель';
                const group = conflict.group ? `у группы ${conflict.group}` : 'в другой группе';
                const dayLabel = getConflictDayLabel(conflict.day);
                const slotLabel = getConflictSlotLabel(conflict.slot);
                const parityLabel = (formatParityLabel(conflict.parity) || 'Всегда').toLowerCase();
                const parts = [group];
                if (dayLabel) {
                    parts.push(dayLabel);
                }
                if (slotLabel) {
                    parts.push(slotLabel);
                }
                return `${teacher} уже стоит ${parts.join(', ')} — ${parityLabel}`;
            });
            const suffix = conflicts.length > summaries.length ? '…' : '';
            return `Преподаватель занят: ${summaries.join('; ')}${suffix}`;
        }

        function getConflictDayLabel(dayKey) {
            if (!dayKey) {
                return '';
            }
            const data = weekDayMap.get(dayKey);
            return data ? data.label : dayKey;
        }

        function getConflictSlotLabel(slotKey) {
            if (!slotKey) {
                return '';
            }
            const slot = timeSlotMap.get(slotKey);
            if (!slot) {
                return slotKey;
            }
            return `${slot.order} пара (${slot.start} – ${slot.end})`;
        }

        function formatParityLabel(parity) {
            const labels = {
                both: 'Всегда',
                numerator: 'Числитель',
                denominator: 'Знаменатель',
            };
            return labels[parity] || labels.both;
        }

        function formatConflictWeek(weekIso) {
            if (!weekIso) {
                return '';
            }
            const start = parseISODate(weekIso);
            if (!(start instanceof Date) || Number.isNaN(start.getTime())) {
                return '';
            }
            const end = addDays(start, 5);
            return `Неделя ${formatRangeLabel(start, end)}`;
        }

        function syncModalBodyState() {
            const openModals = document.querySelectorAll('.schedule-modal.is-open');
            document.body.classList.toggle('schedule-modal-open', openModals.length > 0);
        }

        function attachModalEvents() {
            if (!elements.lessonModal || !elements.lessonModalForm) {
                return;
            }

            elements.lessonModalForm.addEventListener('submit', (event) => {
                event.preventDefault();
                saveLessonFromModal();
            });

            elements.modalCloseButtons.forEach((button) => {
                button.addEventListener('click', () => closeLessonModal());
            });

            elements.lessonModal.addEventListener('click', (event) => {
                if (event.target.closest('[data-modal-close]')) {
                    closeLessonModal();
                }
            });

            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape' && state.modalContext) {
                    closeLessonModal();
                }
            });
        }

        function attachConflictModalEvents() {
            if (!elements.conflictModal) {
                return;
            }
            elements.conflictCloseButtons?.forEach((button) => {
                button.addEventListener('click', () => closeConflictModal());
            });
            elements.conflictModal.addEventListener('click', (event) => {
                if (event.target.closest('[data-conflict-close]')) {
                    closeConflictModal();
                }
            });
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape' && elements.conflictModal.classList.contains('is-open')) {
                    closeConflictModal();
                }
            });
        }

        function handleLessonDrop(cell, subjectId) {
            const dayKey = cell.dataset.day;
            const slotKey = cell.dataset.slot;
            if (!dayKey || !slotKey) {
                return;
            }
            const cellKey = buildCellKey(dayKey, slotKey);
            const entry = getEntry(cellKey);
            const existingLesson = entry ? getLessonForDisplay(entry, state.currentWeekParity) : null;
            if (existingLesson && subjectId && existingLesson.subjectId !== subjectId) {
                const shouldReplace = confirm('Пара уже занята. Заменить занятие?');
                if (!shouldReplace) {
                    return;
                }
            }
            selectCell(cell);
            openLessonModal({
                cellKey,
                dayKey,
                slotKey,
                subjectId: subjectId || (existingLesson ? existingLesson.subjectId : undefined),
                lesson: existingLesson || null,
                forceSubject: subjectId,
            });
        }

        function selectCell(cell) {
            if (!cell) {
                return;
            }
            droppableCells.forEach((node) => node.classList.remove('grid-cell--active'));
            cell.classList.add('grid-cell--active');
            const dayKey = cell.dataset.day;
            const slotKey = cell.dataset.slot;
            state.selectedCellKey = buildCellKey(dayKey, slotKey);
        }

        function clearSelection() {
            state.selectedCellKey = null;
            droppableCells.forEach((node) => node.classList.remove('grid-cell--active'));
        }

        function clearWeek() {
            const keysToRemove = Array.from(state.lessons.keys());
            if (!keysToRemove.length) {
                showMessage('Эта неделя уже пустая.', 'info');
                return;
            }
            if (!confirm('Очистить все пары текущей недели?')) {
                return;
            }
            keysToRemove.forEach((cellKey) => {
                deleteLesson(cellKey, { parity: 'all', trackChange: true, silentMessage: true, skipDayView: true });
            });
            hydrateGridFromLessons();
            renderDayView();
            markWeekDirty(state.currentWeekKey);
            showMessage('Неделя очищена.', 'success');
        }

        function deleteLesson(cellKey, options = {}) {
            const entry = getEntry(cellKey);
            if (!entry) {
                return;
            }
            const parity = options.parity || 'both';
            const paritiesToRemove = parity === 'all' ? ['both', 'numerator', 'denominator'] : [parity];
            let removed = false;
            paritiesToRemove.forEach((key) => {
                if (entry[key]) {
                    if (options.trackChange) {
                        const { dayKey, slotKey } = splitCellKey(cellKey);
                        recordChange({ type: 'removed', dayKey, slotKey, fromLesson: entry[key], toLesson: null, parity: key });
                    }
                    entry[key] = null;
                    removed = true;
                }
            });
            if (!entryHasData(entry)) {
                state.lessons.delete(cellKey);
            }
            if (removed) {
                const cell = refreshCell(cellKey);
                if (options.trackChange && cell) {
                    markCellChange(cell, 'removed');
                }
                if (!options.skipDayView) {
                    renderDayView();
                }
                markWeekDirty(state.currentWeekKey);
                if (!options.silentMessage && !options.trackChange) {
                    showMessage('Занятие удалено.', 'success');
                }
            }
        }

        function openLessonModal({ cellKey, dayKey, slotKey, subjectId, lesson, forceSubject }) {
            if (!elements.lessonModal) {
                return;
            }

            const entry = getEntry(cellKey);
            let parityKey = 'both';
            if (!forceSubject && entry) {
                if (entry.both) {
                    parityKey = 'both';
                } else if (entry.numerator) {
                    parityKey = 'numerator';
                } else if (entry.denominator) {
                    parityKey = 'denominator';
                } else {
                    parityKey = state.currentWeekParity;
                }
            }

            const currentLesson = lesson || (parityKey === 'both' ? entry?.both : entry?.[parityKey]) || null;
            const subjectKey = forceSubject
                ? forceSubject
                : (currentLesson ? currentLesson.subjectId : (entry?.both?.subjectId || entry?.numerator?.subjectId || entry?.denominator?.subjectId || subjectId));
            const subject = subjectKey ? subjectMap.get(String(subjectKey)) : null;
            const subjectName = (subject && subject.name) || (currentLesson && currentLesson.subjectName) || 'Предмет не выбран';
            const subjectShort = (subject && subject.short_name) || (currentLesson && currentLesson.subjectShort) || subjectName;
            const slot = timeSlotMap.get(slotKey);
            const day = weekDayMap.get(dayKey);

            elements.lessonModalSlot.textContent = `${day ? day.label : dayKey} • ${slot ? `${slot.order} пара (${slot.start} – ${slot.end})` : ''}`;
            elements.lessonSubjectName.textContent = subjectName;
            elements.lessonSubjectShort.textContent = subjectShort;
            if (elements.lessonDeleteButton) {
                elements.lessonDeleteButton.hidden = !currentLesson;
            }

            state.modalContext = {
                cellKey,
                dayKey,
                slotKey,
                subjectId: subject ? String(subject.id) : (currentLesson ? currentLesson.subjectId : undefined),
                subjectName,
                subjectShort,
                parityKey,
            };

            setModalParity(parityKey);

            elements.lessonModal.removeAttribute('hidden');
            elements.lessonModal.classList.add('is-open');
            syncModalBodyState();
        }

        function closeLessonModal() {
            if (!elements.lessonModal) {
                return;
            }
            elements.lessonModal.classList.remove('is-open');
            elements.lessonModal.setAttribute('hidden', 'hidden');
            if (elements.lessonTeacherSelectWrapper) {
                elements.lessonTeacherSelectWrapper.classList.remove('open');
            }
            state.modalContext = null;
            syncModalBodyState();
        }

        async function saveLessonFromModal() {
            if (!state.modalContext) {
                return;
            }
            const { cellKey, dayKey, slotKey, subjectId, subjectName, subjectShort } = state.modalContext;
            const parityKey = state.modalContext.parityKey || 'both';
            const cell = findCellByKey(cellKey);
            const teacherIds = getSelectedTeacherIds();
            const teacherRooms = getTeacherRooms();
            const lessonType = elements.lessonTypeSelect ? elements.lessonTypeSelect.value || LESSON_TYPES[0].value : LESSON_TYPES[0].value;

            if (!teacherIds.length) {
                showMessage('Назначьте преподавателя для пары.', 'warning');
                return;
            }

            const updatedLesson = normalizeLesson({
                subjectId,
                subjectName,
                subjectShort,
                teacherIds,
                teacherRooms,
                type: lessonType,
            });

            try {
                await ensureNoTeacherConflicts({
                    teacherIds,
                    dayKey,
                    slotKey,
                    parityKey,
                });
            } catch (error) {
                const conflicts = error.details?.conflicts;
                const conflictMessage = buildConflictMessage(conflicts) || error.message || 'Преподаватель занят в это время.';
                showConflictModal(conflicts, conflictMessage);
                showMessage(conflictMessage, 'error');
                return;
            }

            const entry = ensureEntry(cellKey);
            const previousLesson = parityKey === 'both' ? entry.both : entry[parityKey];
            const isNew = !previousLesson;
            const hasChanges = isNew || !areLessonsEqual(previousLesson, updatedLesson);
            if (!hasChanges) {
                closeLessonModal();
                showMessage('Изменений не обнаружено.', 'info');
                return;
            }

            if (parityKey === 'both') {
                entry.both = updatedLesson;
                entry.numerator = null;
                entry.denominator = null;
            } else {
                entry.both = null;
                entry[parityKey] = updatedLesson;
            }
            state.lessons.set(cellKey, entry);

            const displayLesson = getLessonForDisplay(entry, state.currentWeekParity);
            if (cell) {
                if (displayLesson) {
                    renderLessonInCell(cell, displayLesson);
                } else {
                    const placeholder = cell.querySelector('.grid-cell__placeholder');
                    if (placeholder) {
                        placeholder.style.display = '';
                    }
                    const lessonNode = cell.querySelector('.schedule-lesson');
                    if (lessonNode) {
                        lessonNode.remove();
                    }
                }
                markCellChange(cell, isNew ? 'added' : 'updated');
            }
            renderDayView();

            recordChange({
                type: isNew ? 'added' : 'updated',
                dayKey,
                slotKey,
                fromLesson: previousLesson || null,
                toLesson: updatedLesson,
                parity: parityKey,
            });

            markWeekDirty(state.currentWeekKey);
            closeLessonModal();
            showMessage(isNew ? 'Пара добавлена.' : 'Пара обновлена.', 'success');
        }

        function buildTeacherOptions(subject, selectedIds = []) {
            const options = [];
            const seen = new Set();

            const addTeacher = (teacher) => {
                if (!teacher || seen.has(String(teacher.id))) {
                    return;
                }
                seen.add(String(teacher.id));
                options.push({ value: String(teacher.id), label: getTeacherShortName(teacher) });
            };

            if (subject && Array.isArray(subject.teacherIds) && subject.teacherIds.length) {
                subject.teacherIds.forEach((id) => {
                    const teacher = teacherMap.get(String(id));
                    if (teacher) {
                        addTeacher(teacher);
                    }
                });
            }

            if (!options.length) {
                teacherMap.forEach((teacher) => addTeacher(teacher));
            }

            selectedIds.forEach((id) => {
                if (!seen.has(String(id))) {
                    const teacher = teacherMap.get(String(id));
                    if (teacher) {
                        addTeacher(teacher);
                    }
                }
            });

            return options;
        }

        function setCustomSelectOptions(wrapper, options, selectedValue, placeholder) {
            if (!wrapper) {
                return;
            }
            const select = wrapper.querySelector('select');
            const trigger = wrapper.querySelector('.select-trigger');
            const dropdown = wrapper.querySelector('.select-dropdown');
            if (!select || !trigger || !dropdown) {
                return;
            }

            select.innerHTML = '';
            dropdown.innerHTML = '';

            options.forEach((option) => {
                const optionEl = document.createElement('option');
                optionEl.value = option.value;
                optionEl.textContent = option.label;
                if (option.value === selectedValue) {
                    optionEl.selected = true;
                }
                select.appendChild(optionEl);

                const dropdownOption = document.createElement('div');
                dropdownOption.className = 'select-option';
                dropdownOption.dataset.value = option.value;
                if (option.value === selectedValue) {
                    dropdownOption.classList.add('selected');
                }
                dropdownOption.innerHTML = `<div class="select-option-text">${option.label}</div>`;
                dropdown.appendChild(dropdownOption);
            });

            const textNode = trigger.querySelector('.select-text');
            const activeOption = options.find((option) => option.value === selectedValue);
            if (textNode) {
                textNode.textContent = activeOption ? activeOption.label : placeholder;
                textNode.title = textNode.textContent;
            }
            trigger.classList.toggle('placeholder', !selectedValue);

            delete wrapper.dataset.customSelectInitialized;
            if (window.CustomSelect && typeof window.CustomSelect.init === 'function') {
                window.CustomSelect.init(wrapper);
            }
            select.value = selectedValue || '';
        }

        function markCellChange(cell, type) {
            if (!cell) {
                return;
            }
            cell.classList.remove('grid-cell--changed-added', 'grid-cell--changed-updated', 'grid-cell--changed-removed');
            if (!type) {
                return;
            }
            cell.classList.add(`grid-cell--changed-${type}`);
            const badgeText = type === 'removed' ? 'Удалено' : type === 'added' ? 'Добавлено' : 'Изменено';
            let badge = cell.querySelector('.grid-cell__change');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'grid-cell__change';
                cell.appendChild(badge);
            }
            badge.textContent = badgeText;
            if (badge.dataset.timeoutId) {
                clearTimeout(Number(badge.dataset.timeoutId));
            }
            const timeoutId = window.setTimeout(() => {
                cell.classList.remove(`grid-cell--changed-${type}`);
                if (badge.parentElement === cell) {
                    badge.remove();
                }
            }, 4000);
            badge.dataset.timeoutId = String(timeoutId);
        }

        function recordChange({ type, dayKey, slotKey, fromLesson, toLesson, parity }) {
            const day = weekDayMap.get(dayKey);
            const slot = timeSlotMap.get(slotKey);
            const parityLabels = {
                both: 'Всегда',
                numerator: 'Числитель',
                denominator: 'Знаменатель',
            };
            const contextParts = [`${day ? day.label : dayKey} • ${slot ? `${slot.order} пара (${slot.start} – ${slot.end})` : ''}`];
            if (parity && parityLabels[parity]) {
                contextParts.push(parityLabels[parity]);
            }
            const context = contextParts.join(' — ');
            const entry = {
                id: `${Date.now()}-${Math.random()}`,
                type,
                context,
                from: fromLesson ? formatLessonSummary(fromLesson) : '',
                to: toLesson ? formatLessonSummary(toLesson) : '',
                timestamp: new Date(),
                parity,
            };
            state.changeLog.unshift(entry);
            if (state.changeLog.length > 8) {
                state.changeLog.pop();
            }
            renderChangeLog();
        }

        function renderChangeLog() {
            if (!elements.changeLogSection || !elements.changeLogList) {
                return;
            }
            if (!state.changeLog.length) {
                elements.changeLogSection.hidden = true;
                elements.changeLogList.innerHTML = '';
                return;
            }
            elements.changeLogSection.hidden = false;
            const typeLabels = {
                added: 'Добавлено',
                updated: 'Изменено',
                removed: 'Удалено',
            };
            const formatter = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' });
            elements.changeLogList.innerHTML = state.changeLog
                .map((entry) => {
                    const diff = entry.from && entry.to && entry.type !== 'added'
                        ? `<div class="change-log__diff"><span>Было: ${entry.from}</span><span>Стало: ${entry.to}</span></div>`
                        : `<div class="change-log__value">${entry.to || entry.from}</div>`;
                    return `
                        <li class="change-log__item change-log__item--${entry.type}">
                            <div class="change-log__head">
                                <span class="change-log__type">${typeLabels[entry.type] || 'Изменение'}</span>
                                <time>${formatter.format(entry.timestamp)}</time>
                            </div>
                            <p class="change-log__context">${entry.context}</p>
                            ${diff}
                        </li>
                    `;
                })
                .join('');
        }

        function applySubjectFilters() {
            const query = state.searchTerm;
            const selectedTeacherId = state.selectedTeacherId ? String(state.selectedTeacherId) : '';
            libraryItems.forEach((item) => {
                const name = (item.dataset.subjectName || '').toLowerCase();
                const shortName = (item.dataset.subjectShort || '').toLowerCase();
                const matchesSearch = !query || name.includes(query) || shortName.includes(query);
                const teacherIdsRaw = item.dataset.teacherIds || '';
                const teacherList = teacherIdsRaw
                    ? teacherIdsRaw.split(',').map((value) => value.trim()).filter(Boolean)
                    : [];
                const teacherMatches = !selectedTeacherId || teacherList.includes(selectedTeacherId);
                item.classList.toggle('library-item--hidden', !(matchesSearch && teacherMatches));
                item.classList.toggle('library-item--inactive', selectedTeacherId && !teacherMatches);
            });
        }

        function renderLessonInCell(cell, lesson) {
            if (!cell) {
                return;
            }
            cell.classList.add('has-lesson');
            const placeholder = cell.querySelector('.grid-cell__placeholder');
            if (placeholder) {
                placeholder.style.display = 'none';
            }
            let lessonNode = cell.querySelector('.schedule-lesson');
            if (!lessonNode) {
                lessonNode = document.createElement('div');
                lessonNode.className = 'schedule-lesson';
                cell.appendChild(lessonNode);
            }

            const teacherLines = formatTeacherLines(lesson);
            const lessonTypeLabel = getLessonTypeLabel(lesson.type);
            const tags = [];
            if (lessonTypeLabel) {
                tags.push(`<span class="schedule-tag">${lessonTypeLabel}</span>`);
            }

            lessonNode.innerHTML = `
                <div class="schedule-lesson__title">${escapeHtml(lesson.subjectShort)}</div>
                <div class="schedule-lesson__meta">${teacherLines.map((line) => `<span>${line}</span>`).join('')}</div>
                ${tags.length ? `<div class="schedule-lesson__tags">${tags.join('')}</div>` : ''}
            `;

            lessonNode.onclick = (event) => {
                event.stopPropagation();
                selectCell(cell);
                openLessonModal({
                    cellKey: buildCellKey(cell.dataset.day, cell.dataset.slot),
                    dayKey: cell.dataset.day,
                    slotKey: cell.dataset.slot,
                    subjectId: lesson.subjectId,
                    lesson,
                });
            };
        }

        function hydrateGridFromLessons() {
            droppableCells.forEach((cell) => {
                cell.classList.remove('has-lesson', 'grid-cell--changed-added', 'grid-cell--changed-updated', 'grid-cell--changed-removed');
                const placeholder = cell.querySelector('.grid-cell__placeholder');
                if (placeholder) {
                    placeholder.style.display = '';
                }
                const lessonNode = cell.querySelector('.schedule-lesson');
                if (lessonNode) {
                    lessonNode.remove();
                }
                const changeBadge = cell.querySelector('.grid-cell__change');
                if (changeBadge) {
                    changeBadge.remove();
                }
            });

            state.lessons.forEach((entry, cellKey) => {
                const cell = findCellByKey(cellKey);
                if (!cell) {
                    return;
                }
                const normalizedEntry = getEntry(cellKey);
                const lesson = getLessonForDisplay(normalizedEntry, state.currentWeekParity);
                if (lesson) {
                    renderLessonInCell(cell, lesson);
                }
            });
        }

        function renderDayView() {
            if (!daySlotNodes.length) {
                return;
            }
            daySlotNodes.forEach((slotNode) => {
                const daySlotKey = slotNode.dataset.daySlot;
                if (!daySlotKey) {
                    return;
                }
                const entry = getEntry(daySlotKey);
                const lesson = getLessonForDisplay(entry, state.currentWeekParity);
                if (lesson) {
                    slotNode.classList.add('day-slot__content--filled');
                    slotNode.innerHTML = createDayLessonMarkup(lesson);
                } else {
                    slotNode.classList.remove('day-slot__content--filled');
                    slotNode.innerHTML = `
                        <div class="day-slot__empty">
                            <i class="bi bi-calendar2-plus"></i>
                            <span>Свободно</span>
                        </div>
                    `;
                }
            });
        }

        function createDayLessonMarkup(lesson) {
            const teacherLines = formatTeacherLines(lesson);
            const lessonTypeLabel = getLessonTypeLabel(lesson.type);
            const tags = [];
            if (lessonTypeLabel) {
                tags.push(`<span class="schedule-tag">${lessonTypeLabel}</span>`);
            }
            return `
                <div class="day-slot__lesson">
                    <div class="day-slot__lesson-title">${escapeHtml(lesson.subjectShort)}</div>
                    <div class="day-slot__lesson-meta">${teacherLines.map((line) => `<span>${line}</span>`).join('')}</div>
                ${tags.length ? `<div class="day-slot__tags">${tags.join('')}</div>` : ''}
                </div>
            `;
        }

        function switchView(view, options = {}) {
            state.activeView = view;
            elements.viewTabs.forEach((btn) => {
                const isActive = (btn.dataset.viewTab || 'week') === view;
                btn.classList.toggle('active', isActive);
            });
            elements.viewPanels.forEach((panel) => {
                panel.hidden = panel.dataset.viewPanel !== view;
            });

            if (view === 'day') {
                renderDayView();
                if (!options.silent) {
                    showMessage('Режим дня активен. Для редактирования вернитесь в режим «Неделя».', 'info');
                }
            } else if (view === 'semester') {
                renderSemesterTimeline();
                if (!options.silent) {
                    showMessage('План на полгода: выберите неделю, чтобы перейти к редактированию.', 'info');
                }
            } else {
                if (!options.silent) {
                    showMessage('Режим недели активен. Перетащите предметы в сетку, чтобы заполнить занятия.', 'info');
                }
            }
        }

        function renderSemesterTimeline() {
            if (!elements.semesterTimeline) {
                return;
            }
            const weeks = getSemesterWeeks();
            const activeWeekIso = formatISODate(state.weekStart);
            const selectionMode = state.semesterSelectionMode;
            elements.semesterTimeline.innerHTML = weeks
                .map((week, index) => {
                    const weekStartIso = week.key;
                    const isActive = weekStartIso === activeWeekIso;
                    const hasLessons = Boolean(state.weekLessons[weekStartIso] && state.weekLessons[weekStartIso].size);
                    const isSelected = state.semesterSelection.has(weekStartIso);
                    const classes = ['semester-week'];
                    if (isActive) {
                        classes.push('semester-week--active');
                    }
                    if (hasLessons) {
                        classes.push('semester-week--filled');
                    }
                    if (selectionMode) {
                        classes.push('semester-week--selectable');
                    }
                    if (isSelected) {
                        classes.push('semester-week--selected');
                    }
                    return `
                        <button class="${classes.join(' ')}" type="button" data-week-start="${weekStartIso}">
                            <span class="semester-week__month">${week.month}</span>
                            <span class="semester-week__title">Неделя ${index + 1}</span>
                            <span class="semester-week__dates">${formatRangeLabel(week.start, week.end)}</span>
                        </button>
                    `;
                })
                .join('');

            const buttons = elements.semesterTimeline.querySelectorAll('[data-week-start]');
            buttons.forEach((button) => {
                button.addEventListener('click', () => {
                    handleSemesterWeekClick(button.dataset.weekStart);
                });
            });
        }

        function handleSemesterWeekClick(weekStartIso) {
            if (!weekStartIso) {
                return;
            }
            if (state.semesterSelectionMode) {
                toggleWeekSelection(weekStartIso);
            } else {
                setActiveWeek(weekStartIso);
            }
        }

        function toggleWeekSelection(weekStartIso) {
            if (!state.semesterSelectionMode || !weekStartIso) {
                return;
            }
            if (state.semesterSelection.has(weekStartIso)) {
                state.semesterSelection.delete(weekStartIso);
            } else {
                state.semesterSelection.add(weekStartIso);
            }
            renderSemesterTimeline();
            updateSaveButtonState();
        }

        function copyCurrentWeekToSelected(weekKeys) {
            if (!Array.isArray(weekKeys) || !weekKeys.length) {
                return;
            }
            const lessonSnapshot = cloneLessonsMap(state.lessons || new Map());
            const buildingSnapshot = cloneDayBuildings(state.dayBuildings || {});
            weekKeys.forEach((weekKey) => {
                state.weekLessons[weekKey] = cloneLessonsMap(lessonSnapshot);
                state.weekBuildings[weekKey] = cloneDayBuildings(buildingSnapshot);
                markWeekDirty(weekKey);
            });
            renderSemesterTimeline();
        }

        function enterSemesterSelectionMode() {
            if (state.semesterSelectionMode) {
                return;
            }
            state.semesterSelectionMode = true;
            state.semesterSelection.clear();
            renderSemesterTimeline();
            updateSaveButtonState();
            updateSemesterButtonState();
            showMessage('Выберите недели в календаре, на которые нужно перенести текущее расписание.', 'info');
        }

        function exitSemesterSelectionMode(options = {}) {
            if (!state.semesterSelectionMode) {
                return;
            }
            state.semesterSelectionMode = false;
            state.semesterSelection.clear();
            renderSemesterTimeline();
            updateSaveButtonState();
            updateSemesterButtonState();
            if (!options.silent) {
                showMessage('Режим выбора недель отключён.', 'info');
            }
        }

        function shiftWeek(days) {
            persistCurrentWeekLessons();
            const newStart = addDays(state.weekStart, days);
            switchToWeek(newStart);
            switchView('week', { silent: true });
            showMessage(`Вы выбрали неделю ${formatRangeLabel(state.weekStart, state.weekEnd)}.`, 'info');
        }

        function setActiveWeek(weekStartIso) {
            if (!weekStartIso) {
                return;
            }
            const newStart = parseISODate(weekStartIso);
            if (Number.isNaN(newStart.getTime())) {
                return;
            }
            persistCurrentWeekLessons();
            switchToWeek(newStart);
            switchView('week', { silent: true });
            showMessage(`Вы выбрали неделю ${formatRangeLabel(state.weekStart, state.weekEnd)}.`, 'info');
        }

        function persistCurrentWeekLessons() {
            state.weekLessons[state.currentWeekKey] = state.lessons;
            ensureDayBuildingsForCurrentWeek();
        }

        function switchToWeek(newStart) {
            const normalized = startOfWeek(newStart);
            state.weekStart = normalized;
            state.weekEnd = addDays(normalized, 5);
            state.currentWeekKey = formatISODate(normalized);
            ensureSemesterWeeks(state.weekStart);
            if (!state.weekLessons[state.currentWeekKey]) {
                state.weekLessons[state.currentWeekKey] = new Map();
            }
            state.lessons = state.weekLessons[state.currentWeekKey];
            ensureDayBuildingsForCurrentWeek();
            state.currentWeekParity = calculateWeekParity(state.weekStart);
            updateWeekParityLabel();
            clearSelection();
            hydrateGridFromLessons();
            renderDayView();
            updateWeekRange();
            renderSemesterTimeline();
            renderDayBuildingControls();
            updateBuildingBadges();
        }

        function updateWeekRange() {
            if (!elements.weekRange) {
                return;
            }
            elements.weekRange.dataset.weekStart = formatISODate(state.weekStart);
            elements.weekRange.dataset.weekEnd = formatISODate(state.weekEnd);
            elements.weekRange.textContent = formatRangeLabel(state.weekStart, state.weekEnd);
        }

        function findCellByKey(cellKey) {
            return droppableCells.find((cell) => buildCellKey(cell.dataset.day, cell.dataset.slot) === cellKey) || null;
        }

        function buildCellKey(dayKey, slotKey) {
            return `${dayKey}__${slotKey}`;
        }

        function splitCellKey(cellKey) {
            const [dayKey, slotKey] = cellKey.split('__');
            return { dayKey, slotKey };
        }

        function getLessonTypeLabel(type) {
            const item = LESSON_TYPES.find((lessonType) => lessonType.value === type);
            return item ? item.label : '';
        }

        function formatLessonSummary(lesson) {
            if (!lesson) {
                return '';
            }
            const teacherLines = formatTeacherLines(lesson);
            return [lesson.subjectShort, ...teacherLines].join(' • ');
        }

        function formatTeacherLines(lesson) {
            const ids = Array.isArray(lesson.teacherIds) ? lesson.teacherIds : [];
            if (!ids.length) {
                return ['Преподаватель не назначен'];
            }
            return ids.map((id) => {
                const teacher = teacherMap.get(String(id));
                const room = lesson.teacherRooms?.[id];
                const name = getTeacherShortName(teacher);
                return room ? `${escapeHtml(name)} — ауд. ${escapeHtml(room)}` : escapeHtml(name);
            });
        }

        function getTeacherShortName(teacher) {
            if (!teacher || !teacher.name) {
                return 'Преподаватель';
            }
            const parts = teacher.name.trim().split(/\s+/).filter(Boolean);
            if (!parts.length) {
                return 'Преподаватель';
            }
            const [lastName, ...rest] = parts;
            const initials = rest
                .map((segment) => segment.charAt(0).toUpperCase())
                .filter(Boolean)
                .map((letter) => `${letter}.`)
                .join('');
            return initials ? `${lastName} ${initials}` : lastName;
        }

        function createDefaultDayBuildings(overrides = null) {
            const defaults = {};
            (config.weekdayOrder || []).forEach((day) => {
                defaults[day.key] = DEFAULT_BUILDING;
            });
            return applyDayBuildingOverrides(defaults, overrides);
        }

        function applyDayBuildingOverrides(target, overrides) {
            if (!target || !overrides || typeof overrides !== 'object') {
                return target;
            }
            Object.keys(overrides).forEach((key) => {
                const value = overrides[key];
                if (value) {
                    target[key] = value;
                }
            });
            return target;
        }

        function cloneDayBuildings(source) {
            const clone = {};
            Object.keys(source || {}).forEach((key) => {
                clone[key] = source[key];
            });
            return clone;
        }

        function ensureDayBuildingsForCurrentWeek() {
            if (!state.weekBuildings[state.currentWeekKey]) {
                state.weekBuildings[state.currentWeekKey] = cloneDayBuildings(defaultDayBuildingPreset);
            }
            state.dayBuildings = state.weekBuildings[state.currentWeekKey];
            return state.dayBuildings;
        }

        function renderDayBuildingControls() {
            if (!elements.dayBuildingControls?.length) {
                return;
            }
            const currentDayBuildings = ensureDayBuildingsForCurrentWeek();
            elements.dayBuildingControls.forEach((control) => {
                const dayKey = control.dataset.buildingDay;
                const current = (currentDayBuildings && currentDayBuildings[dayKey]) || DEFAULT_BUILDING;
                control.querySelectorAll('.building-btn').forEach((button) => {
                    button.classList.toggle('active', button.dataset.building === current);
                });
            });
        }

        function updateBuildingBadges() {
            if (!elements.dayBuildingBadges?.length) {
                return;
            }
            const currentDayBuildings = ensureDayBuildingsForCurrentWeek();
            elements.dayBuildingBadges.forEach((badge) => {
                const dayKey = badge.dataset.buildingBadge;
                const value = (currentDayBuildings && currentDayBuildings[dayKey]) || DEFAULT_BUILDING;
                const data = BUILDING_LOOKUP[value];
                if (data) {
                    badge.textContent = data.short;
                    badge.title = data.label;
                    badge.hidden = false;
                } else {
                    badge.textContent = '';
                    badge.hidden = true;
                }
            });
        }

        function createEmptyEntry() {
            return { both: null, numerator: null, denominator: null };
        }

        function normalizeLesson(lesson = {}) {
            if (!lesson) {
                return null;
            }
            const teacherIdsRaw = Array.isArray(lesson.teacherIds)
                ? lesson.teacherIds
                : lesson.teacherId
                    ? [lesson.teacherId]
                    : [];
            const teacherIds = Array.from(new Set(teacherIdsRaw.map((id) => String(id)))).filter(Boolean);
            const teacherRoomsSource = lesson.teacherRooms || {};
            const teacherRooms = {};
            teacherIds.forEach((id) => {
                teacherRooms[id] = teacherRoomsSource[id] || '';
            });
            const subjectName = lesson.subjectName || 'Предмет';
            const subjectShort = lesson.subjectShort || subjectName;
            return {
                subjectId: lesson.subjectId,
                subjectName,
                subjectShort,
                teacherIds,
                teacherRooms,
                type: lesson.type || LESSON_TYPES[0].value,
            };
        }

        function getEntry(cellKey) {
            let entry = state.lessons.get(cellKey);
            if (!entry) {
                return null;
            }
            if (entry && entry.both === undefined && entry.numerator === undefined && entry.denominator === undefined) {
                const normalized = createEmptyEntry();
                normalized.both = normalizeLesson(entry);
                state.lessons.set(cellKey, normalized);
                entry = normalized;
            }
            return entry;
        }

        function ensureEntry(cellKey) {
            let entry = getEntry(cellKey);
            if (!entry) {
                entry = createEmptyEntry();
                state.lessons.set(cellKey, entry);
            }
            return entry;
        }

        function entryHasData(entry) {
            return Boolean(entry && (entry.both || entry.numerator || entry.denominator));
        }

        function getLessonForDisplay(entry, parity) {
            if (!entry) {
                return null;
            }
            return entry.both || entry[parity] || null;
        }

        function refreshCell(cellKey) {
            const cell = findCellByKey(cellKey);
            if (!cell) {
                return null;
            }
            const lesson = getLessonForDisplay(getEntry(cellKey), state.currentWeekParity);
            const placeholder = cell.querySelector('.grid-cell__placeholder');
            const lessonNode = cell.querySelector('.schedule-lesson');
            if (lesson) {
                if (placeholder) {
                    placeholder.style.display = 'none';
                }
                renderLessonInCell(cell, lesson);
            } else {
                if (placeholder) {
                    placeholder.style.display = '';
                }
                if (lessonNode) {
                    lessonNode.remove();
                }
            }
            return cell;
        }

        function renderTeacherOptions(options, selectedIds = [], existingRooms = {}) {
            if (!elements.teacherOptionsContainer) {
                return;
            }
            const selected = new Set((selectedIds || []).map(String));
            elements.teacherOptionsContainer.innerHTML = '';
            if (!options.length) {
                const empty = document.createElement('span');
                empty.className = 'teacher-multiselect__empty';
                empty.textContent = 'Нет доступных преподавателей';
                elements.teacherOptionsContainer.appendChild(empty);
                updateTeacherSelectionText([]);
                renderTeacherRooms([], {});
                return;
            }
            options.forEach((option) => {
                const label = document.createElement('label');
                label.className = 'teacher-checkbox';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.value = option.value;
                checkbox.checked = selected.has(option.value);
                checkbox.dataset.label = option.label;

                const span = document.createElement('span');
                span.textContent = option.label;

                label.appendChild(checkbox);
                label.appendChild(span);
                elements.teacherOptionsContainer.appendChild(label);
            });
            const selectedArray = Array.from(selected);
            updateTeacherSelectionText(selectedArray);
            renderTeacherRooms(selectedArray, existingRooms);
        }

        function getSelectedTeacherIds() {
            if (!elements.teacherOptionsContainer) {
                return [];
            }
            return Array.from(elements.teacherOptionsContainer.querySelectorAll('input[type="checkbox"]:checked'))
                .map((input) => input.value);
        }

        function updateTeacherSelectionText(selectedIds) {
            if (!elements.teacherSelectedText) {
                return;
            }
            const ids = selectedIds || getSelectedTeacherIds();
            const names = ids
                .map((id) => {
                    const teacher = teacherMap.get(String(id));
                    return teacher ? getTeacherShortName(teacher) : '';
                })
                .filter(Boolean);
            elements.teacherSelectedText.textContent = names.length ? names.join(', ') : 'Не назначен';
        }

        function renderTeacherRooms(selectedIds = [], previousRooms = {}) {
            if (!elements.teacherRoomsContainer) {
                return;
            }
            elements.teacherRoomsContainer.innerHTML = '';
            if (!selectedIds.length) {
                const empty = document.createElement('div');
                empty.className = 'teacher-multiselect__empty';
                empty.textContent = 'Выберите преподавателя, чтобы задать аудиторию.';
                elements.teacherRoomsContainer.appendChild(empty);
                return;
            }
            selectedIds.forEach((teacherId) => {
                const teacher = teacherMap.get(String(teacherId));
                const wrapper = document.createElement('div');
                wrapper.className = 'teacher-room';

                const label = document.createElement('label');
                label.textContent = getTeacherShortName(teacher);

                const input = document.createElement('input');
                input.type = 'text';
                input.dataset.teacherId = teacherId;
                input.placeholder = 'Аудитория';
                input.value = previousRooms[teacherId] || '';

                wrapper.appendChild(label);
                wrapper.appendChild(input);
                elements.teacherRoomsContainer.appendChild(wrapper);
            });
        }

        function getTeacherRooms() {
            if (!elements.teacherRoomsContainer) {
                return {};
            }
            const rooms = {};
            elements.teacherRoomsContainer.querySelectorAll('input[data-teacher-id]').forEach((input) => {
                rooms[input.dataset.teacherId] = input.value.trim();
            });
            return rooms;
        }

        function initTeacherPicker() {
            if (!elements.teacherOptionsContainer || !elements.lessonTeacherSelectWrapper || !elements.teacherRoomsContainer) {
                return;
            }
            elements.teacherOptionsContainer.addEventListener('change', (event) => {
                if (event.target.matches('input[type="checkbox"]')) {
                    const prevRooms = getTeacherRooms();
                    const selectedIds = getSelectedTeacherIds();
                    updateTeacherSelectionText(selectedIds);
                    renderTeacherRooms(selectedIds, prevRooms);
                }
            });

            elements.lessonTeacherSelectWrapper.addEventListener('click', (event) => {
                if (event.target.closest('[data-multiselect-trigger]')) {
                    elements.lessonTeacherSelectWrapper.classList.toggle('open');
                }
            });

            document.addEventListener('click', (event) => {
                if (!elements.lessonTeacherSelectWrapper.contains(event.target)) {
                    elements.lessonTeacherSelectWrapper.classList.remove('open');
                }
            });
        }

        function initParityToggle() {
            if (!elements.parityToggle) {
                return;
            }
            elements.parityToggle.addEventListener('click', (event) => {
                if (!state.modalContext) {
                    return;
                }
                const btn = event.target.closest('.parity-toggle__btn');
                if (!btn) {
                    return;
                }
                const value = btn.dataset.parityOption;
                if (value) {
                    setModalParity(value);
                }
            });
        }

        function setModalParity(parityKey) {
            if (!state.modalContext) {
                return;
            }
            state.modalContext.parityKey = parityKey;
            if (elements.parityToggle) {
                elements.parityToggle.querySelectorAll('.parity-toggle__btn').forEach((btn) => {
                    btn.classList.toggle('active', btn.dataset.parityOption === parityKey);
                });
            }
            if (elements.lessonTeacherSelectWrapper) {
                elements.lessonTeacherSelectWrapper.classList.remove('open');
            }
            loadLessonIntoForm();
        }

        function attachBuildingControls() {
            if (!elements.dayBuildingControls?.length) {
                return;
            }
            elements.dayBuildingControls.forEach((control) => {
                control.addEventListener('click', (event) => {
                    const button = event.target.closest('.building-btn');
                    if (!button) {
                        return;
                    }
                    const dayKey = control.dataset.buildingDay;
                    const building = button.dataset.building;
                    const currentBuildings = ensureDayBuildingsForCurrentWeek();
                    if (!dayKey || !building || currentBuildings[dayKey] === building) {
                        return;
                    }
                    setDayBuilding(dayKey, building);
                });
            });
        }

        function setDayBuilding(dayKey, building) {
            if (!dayKey || !building) {
                return;
            }
            const dayBuildings = ensureDayBuildingsForCurrentWeek();
            if (dayBuildings[dayKey] === building) {
                return;
            }
            dayBuildings[dayKey] = building;
            renderDayBuildingControls();
            updateBuildingBadges();
            markWeekDirty(state.currentWeekKey);
        }

        function markWeekDirty(weekKey = state.currentWeekKey) {
            if (!weekKey) {
                return;
            }
            state.dirtyWeeks.add(weekKey);
        }

        function loadLessonIntoForm() {
            if (!state.modalContext) {
                return;
            }
            const parityKey = state.modalContext.parityKey || 'both';
            const entry = getEntry(state.modalContext.cellKey);
            const lesson = entry ? (parityKey === 'both' ? entry.both : entry[parityKey]) : null;
            const subject = state.modalContext.subjectId ? subjectMap.get(String(state.modalContext.subjectId)) : null;
            const defaultTeacherIds = subject?.teacherIds?.length ? [String(subject.teacherIds[0])] : [];
            const selectedTeacherIds = lesson?.teacherIds?.map((id) => String(id)) || defaultTeacherIds;
            const teacherOptions = buildTeacherOptions(subject, selectedTeacherIds);
            renderTeacherOptions(teacherOptions, selectedTeacherIds, lesson?.teacherRooms || {});

            const lessonTypeOptions = [{ value: '', label: 'Тип занятия' }, ...LESSON_TYPES];
            const typeValue = lesson ? lesson.type : LESSON_TYPES[0].value;
            if (elements.lessonTypeSelectWrapper) {
                setCustomSelectOptions(
                    elements.lessonTypeSelectWrapper,
                    lessonTypeOptions,
                    typeValue,
                    'Тип занятия'
                );
            }

            if (elements.lessonDeleteButton) {
                elements.lessonDeleteButton.hidden = !lesson;
            }
        }

        function calculateWeekParity(weekStartDate) {
            ensureSemesterWeeks(weekStartDate);
            const current = startOfWeek(weekStartDate);
            const iso = formatISODate(current);
            const index = state.semesterWeeks.findIndex((week) => week.key === iso);
            if (index === -1) {
                const base = getAcademicYearStartWeek(weekStartDate);
                const diffMs = current.getTime() - base.getTime();
                const weeksDiff = Math.floor(diffMs / (7 * 24 * 60 * 60 * 1000));
                const normalizedDiff = Math.abs(weeksDiff);
                return normalizedDiff % 2 === 0 ? 'numerator' : 'denominator';
            }
            return index % 2 === 0 ? 'numerator' : 'denominator';
        }

        function startOfWeek(date) {
            const copy = new Date(date);
            const day = (copy.getDay() + 6) % 7;
            copy.setDate(copy.getDate() - day);
            copy.setHours(0, 0, 0, 0);
            return copy;
        }

        function getAcademicYearStartWeek(date) {
            const year = date.getMonth() >= 8 ? date.getFullYear() : date.getFullYear() - 1;
            const septemberFirst = new Date(year, 8, 1);
            return startOfWeek(septemberFirst);
        }

        function updateWeekParityLabel() {
            if (!elements.weekParityLabel) {
                return;
            }
            const labels = {
                numerator: 'Числитель',
                denominator: 'Знаменатель',
            };
            const label = labels[state.currentWeekParity] || '';
            elements.weekParityLabel.textContent = label;
            elements.weekParityLabel.hidden = !label;
        }

        function cloneLessonData(lesson) {
            if (!lesson) {
                return null;
            }
            return {
                ...lesson,
                teacherIds: Array.isArray(lesson.teacherIds) ? [...lesson.teacherIds] : [],
                teacherRooms: lesson.teacherRooms ? { ...lesson.teacherRooms } : {},
            };
        }

        function cloneEntry(entry) {
            const normalized = entry && entry.both === undefined && entry.numerator === undefined && entry.denominator === undefined
                ? { both: normalizeLesson(entry), numerator: null, denominator: null }
                : entry || createEmptyEntry();
            return {
                both: cloneLessonData(normalized?.both),
                numerator: cloneLessonData(normalized?.numerator),
                denominator: cloneLessonData(normalized?.denominator),
            };
        }

        function cloneLessonsMap(sourceMap) {
            const clone = new Map();
            sourceMap.forEach((entry, cellKey) => {
                clone.set(cellKey, cloneEntry(entry));
            });
            return clone;
        }

        function lessonsMapFromObject(source) {
            const map = new Map();
            if (!source || typeof source !== 'object') {
                return map;
            }
            const rawLessons = source.lessons && typeof source.lessons === 'object'
                ? source.lessons
                : source;
            Object.keys(rawLessons).forEach((cellKey) => {
                map.set(cellKey, normalizeEntryForState(rawLessons[cellKey]));
            });
            return map;
        }

        function normalizeEntryForState(entry) {
            const normalized = createEmptyEntry();
            if (!entry || typeof entry !== 'object') {
                return normalized;
            }
            ['both', 'numerator', 'denominator'].forEach((key) => {
                if (entry[key]) {
                    normalized[key] = normalizeLesson(entry[key]);
                }
            });
            return normalized;
        }

        function lessonsMapToObject(map) {
            const result = {};
            if (!map) {
                return result;
            }
            map.forEach((entry, cellKey) => {
                if (!entryHasData(entry)) {
                    return;
                }
                result[cellKey] = {
                    both: entry.both ? normalizeLesson(entry.both) : null,
                    numerator: entry.numerator ? normalizeLesson(entry.numerator) : null,
                    denominator: entry.denominator ? normalizeLesson(entry.denominator) : null,
                };
            });
            return result;
        }

        function ensureSemesterWeeks(referenceDate) {
            const target = startOfWeek(referenceDate);
            if (!state.semesterWeeks.length) {
                state.semesterWeeks = buildAcademicYearWeeks(target);
                return;
            }
            const firstWeek = state.semesterWeeks[0];
            const lastWeek = state.semesterWeeks[state.semesterWeeks.length - 1];
            if (target < firstWeek.start || target > lastWeek.end) {
                state.semesterWeeks = buildAcademicYearWeeks(target);
            }
        }

        function getSemesterWeeks(referenceDate = state.weekStart) {
            ensureSemesterWeeks(referenceDate);
            return state.semesterWeeks;
        }

        function buildAcademicYearWeeks(referenceDate) {
            const weeks = [];
            const year = referenceDate.getMonth() >= 8 ? referenceDate.getFullYear() : referenceDate.getFullYear() - 1;
            const fallStart = startOfWeek(new Date(year, 8, 1));
            const fallEnd = new Date(year, 11, 31);
            const springStart = startOfWeek(new Date(year + 1, 0, 8));
            const springEnd = new Date(year + 1, 6, 5);

            collectWeeksInRange(fallStart, fallEnd, weeks);
            collectWeeksInRange(springStart, springEnd, weeks);

            return weeks;
        }

        function collectWeeksInRange(rangeStart, rangeEnd, target) {
            if (!rangeStart || !rangeEnd) {
                return;
            }
            let cursor = startOfWeek(rangeStart);
            const limit = new Date(rangeEnd);
            limit.setHours(0, 0, 0, 0);
            while (cursor <= limit) {
                const start = new Date(cursor);
                const end = addDays(start, 5);
                const month = start.toLocaleDateString('ru-RU', { month: 'long' });
                target.push({
                    start,
                    end,
                    month: month.charAt(0).toUpperCase() + month.slice(1),
                    key: formatISODate(start),
                });
                cursor = addDays(start, 7);
            }
        }

        function areLessonsEqual(a, b) {
            if (!a || !b) {
                return false;
            }
            const teacherA = Array.isArray(a.teacherIds) ? a.teacherIds.map(String).sort() : [];
            const teacherB = Array.isArray(b.teacherIds) ? b.teacherIds.map(String).sort() : [];
            if (teacherA.length !== teacherB.length) {
                return false;
            }
            for (let index = 0; index < teacherA.length; index += 1) {
                if (teacherA[index] !== teacherB[index]) {
                    return false;
                }
            }
            return (
                a.subjectId === b.subjectId
                && a.type === b.type
                && teacherA.every((value) => (a.teacherRooms?.[value] || '') === (b.teacherRooms?.[value] || ''))
            );
        }

        function showMessage(text, type = 'info') {
            if (!elements.message) {
                return;
            }
            elements.message.textContent = text;
            elements.message.className = `schedule-message schedule-message--${type}`;
            elements.message.hidden = false;
            clearTimeout(showMessage.timeoutId);
            showMessage.timeoutId = setTimeout(() => {
                elements.message.hidden = true;
            }, 4000);
        }

        function escapeHtml(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function parseISODate(value) {
            const [year, month, day] = value.split('-').map(Number);
            return new Date(year, month - 1, day);
        }

        function formatISODate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }

        function addDays(date, days) {
            const copy = new Date(date);
            copy.setDate(copy.getDate() + days);
            return copy;
        }

        function formatRangeLabel(start, end) {
            const options = { day: '2-digit', month: '2-digit' };
            return `${start.toLocaleDateString('ru-RU', options)} – ${end.toLocaleDateString('ru-RU', options)}`;
        }
    });
})();
