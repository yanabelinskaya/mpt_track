(() => {
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.scheduleInitialData) {
            return;
        }

        const config = window.scheduleInitialData;
        const state = {
            lessons: new Map(),
            selectedCellKey: null,
            selectedDayKey: null,
            weekStart: parseISODate(config.weekStart),
            weekEnd: parseISODate(config.weekEnd),
            selectedTeacherId: '',
            searchTerm: '',
            activeView: 'week',
        };

        const elements = {
            grid: document.getElementById('scheduleGrid'),
            subjectPool: document.getElementById('scheduleSubjectPool'),
            details: document.getElementById('scheduleSlotDetails'),
            deleteButton: document.querySelector('[data-action="delete-lesson"]'),
            clearDayButton: document.querySelector('[data-action="clear-day"]'),
            autoFillButton: document.querySelector('[data-action="auto-fill"]'),
            saveWeekButton: document.querySelector('[data-action="save-week"]'),
            message: document.getElementById('scheduleMessage'),
            weekRange: document.getElementById('scheduleWeekRange'),
            weekButtons: document.querySelectorAll('.week-switcher__btn'),
            viewTabs: document.querySelectorAll('[data-view-tab]'),
            viewPanels: document.querySelectorAll('[data-view-panel]'),
            facultySelect: document.getElementById('scheduleFacultySelect'),
            groupSelect: document.getElementById('scheduleGroupSelect'),
            teacherSelect: document.getElementById('scheduleTeacherSelect'),
            searchInput: document.getElementById('scheduleSearchInput'),
            dayBoard: document.getElementById('scheduleDayBoard'),
            semesterTimeline: document.getElementById('scheduleSemesterTimeline'),
        };

        const LESSON_TYPES = [
            { value: 'lesson', label: 'Пара' },
            { value: 'lecture', label: 'Лекция' },
            { value: 'practice', label: 'Практика' },
            { value: 'lab', label: 'Лабораторная' },
            { value: 'consultation', label: 'Консультация' },
            { value: 'other', label: 'Другое' },
        ];

        const subjectMap = new Map(config.subjects.map((subject) => [String(subject.id), subject]));
        const teacherMap = new Map(config.teachers.map((teacher) => [String(teacher.id), teacher]));

        const libraryItems = elements.subjectPool
            ? Array.from(elements.subjectPool.querySelectorAll('.library-item'))
            : [];
        const droppableCells = elements.grid
            ? Array.from(elements.grid.querySelectorAll('.grid-cell--droppable'))
            : [];
        const daySlotNodes = elements.dayBoard
            ? Array.from(elements.dayBoard.querySelectorAll('[data-day-slot]'))
            : [];
        const SEMESTER_WEEKS = 24;

        // ====== VIEW MANAGEMENT ======

        function switchView(view) {
            state.activeView = view;
            if (elements.viewTabs && elements.viewTabs.length) {
                elements.viewTabs.forEach((btn) => {
                    const isActive = (btn.dataset.viewTab || 'week') === view;
                    btn.classList.toggle('active', isActive);
                });
            }
            if (elements.viewPanels && elements.viewPanels.length) {
                elements.viewPanels.forEach((panel) => {
                    const isActive = panel.dataset.viewPanel === view;
                    panel.hidden = !isActive;
                });
            }

            if (view === 'day') {
                renderDayView();
                showMessage('Режим дня активен: смотрите расписание для каждого дня. Редактирование доступно в режиме «Неделя».', 'info');
            } else if (view === 'semester') {
                renderSemesterTimeline();
                showMessage('План на полгода: выберите неделю, чтобы перейти к редактированию.', 'info');
            } else {
                showMessage('Режим недели активен. Перетаскивайте предметы в сетку, чтобы заполнить расписание.', 'info');
            }
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
                const lesson = state.lessons.get(daySlotKey);
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
            const teacherName = getTeacherName(lesson.teacherId);
            const lessonTypeLabel = getLessonTypeLabel(lesson.type);
            const tags = [];

            if (lessonTypeLabel) {
                tags.push(`<span class="schedule-tag">${lessonTypeLabel}</span>`);
            }
            if (lesson.room) {
                tags.push(`<span class="schedule-tag schedule-tag--success">ауд. ${escapeHtml(lesson.room)}</span>`);
            }

            return `
                <div class="day-slot__lesson">
                    <div class="day-slot__lesson-title">${escapeHtml(lesson.subjectShort)}</div>
                    <div class="day-slot__lesson-meta">
                        <span>${escapeHtml(teacherName)}</span>
                        ${lesson.notes ? `<span>${escapeHtml(lesson.notes)}</span>` : ''}
                    </div>
                    ${
                        tags.length
                            ? `<div class="day-slot__tags">${tags.join('')}</div>`
                            : ''
                    }
                </div>
            `;
        }

        function renderSemesterTimeline() {
            if (!elements.semesterTimeline) {
                return;
            }
            const weeks = buildSemesterWeeks();
            const activeWeekIso = formatISODate(state.weekStart);
            elements.semesterTimeline.innerHTML = weeks
                .map((week) => {
                    const weekStartIso = formatISODate(week.start);
                    const isActive = weekStartIso === activeWeekIso;
                    const classes = ['semester-week'];
                    if (isActive) {
                        classes.push('semester-week--active');
                    }
                    return `
                        <button class="${classes.join(' ')}" type="button" data-week-start="${weekStartIso}">
                            <span class="semester-week__month">${week.month}</span>
                            <span class="semester-week__title">Неделя ${week.index}</span>
                            <span class="semester-week__dates">${formatRangeLabel(week.start, week.end)}</span>
                        </button>
                    `;
                })
                .join('');

            const buttons = elements.semesterTimeline.querySelectorAll('[data-week-start]');
            buttons.forEach((button) => {
                button.addEventListener('click', () => {
                    setActiveWeek(button.dataset.weekStart);
                });
            });
        }

        function buildSemesterWeeks() {
            const weeks = [];
            const base = new Date(state.weekStart);
            for (let index = 0; index < SEMESTER_WEEKS; index += 1) {
                const start = addDays(base, index * 7);
                const end = addDays(start, 5);
                const month = start.toLocaleDateString('ru-RU', { month: 'long' });
                weeks.push({
                    index: index + 1,
                    start,
                    end,
                    month: month.charAt(0).toUpperCase() + month.slice(1),
                });
            }
            return weeks;
        }

        function setActiveWeek(weekStartIso) {
            if (!weekStartIso) {
                return;
            }
            const newStart = parseISODate(weekStartIso);
            if (Number.isNaN(newStart.getTime())) {
                return;
            }
            state.weekStart = newStart;
            state.weekEnd = addDays(newStart, 5);
            updateWeekRange();
            renderSemesterTimeline();
            switchView('week');
            showMessage(
                `Выбрана неделя ${formatRangeLabel(state.weekStart, state.weekEnd)}. Можно редактировать занятия.`,
                'info'
            );
        }

        attachDragAndDrop();
        attachCellSelection();
        attachFilters();
        attachActions();
        updateWeekRange();
        applySubjectFilters();
        updateDeleteButton();
        renderDayView();
        renderSemesterTimeline();

        // ====== INIT HELPERS ======

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
                    event.dataTransfer.dropEffect = 'copy';
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
                if (!event.target.closest('.schedule-panel--grid') && !event.target.closest('.schedule-panel--details')) {
                    clearSelection();
                }
            });
        }

        function attachFilters() {
            if (elements.facultySelect) {
                const defaultGroupOption = elements.groupSelect ? elements.groupSelect.value : '';
                elements.facultySelect.addEventListener('change', () => {
                    const facultyId = elements.facultySelect.value;
                    filterGroupsByFaculty(facultyId);
                    showMessage(
                        facultyId ? 'Показаны группы выбранной специальности' : 'Отображаются все группы',
                        'info'
                    );
                    if (!facultyId && defaultGroupOption) {
                        elements.groupSelect.value = defaultGroupOption;
                    }
                });
            }

            if (elements.groupSelect) {
                elements.groupSelect.addEventListener('change', () => {
                    const option = elements.groupSelect.options[elements.groupSelect.selectedIndex];
                    const groupLabel = option ? option.textContent : 'Группа не выбрана';
                    showMessage(`Активна группа: ${groupLabel}`, 'info');
                });
            }

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
                elements.searchInput.addEventListener('input', () => {
                    state.searchTerm = elements.searchInput.value.trim().toLowerCase();
                    applySubjectFilters();
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

        function attachActions() {
            if (elements.deleteButton) {
                elements.deleteButton.addEventListener('click', () => {
                    if (!state.selectedCellKey) {
                        showMessage('Выберите занятие для удаления.', 'warning');
                        return;
                    }
                    deleteLesson(state.selectedCellKey);
                });
            }

            if (elements.clearDayButton) {
                elements.clearDayButton.addEventListener('click', () => {
                    if (!state.selectedDayKey) {
                        showMessage('Выберите ячейку дня, который нужно очистить.', 'warning');
                        return;
                    }
                    if (!confirm('Очистить все занятия выбранного дня?')) {
                        return;
                    }
                    clearDay(state.selectedDayKey);
                });
            }

            if (elements.autoFillButton) {
                elements.autoFillButton.addEventListener('click', () => {
                    showMessage('Автоматическое заполнение пока в разработке.', 'warning');
                });
            }

            if (elements.saveWeekButton) {
                elements.saveWeekButton.addEventListener('click', () => {
                    showMessage('Сохранение недели доступно после подключения серверной логики.', 'warning');
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
        }

        // ====== LESSON OPERATIONS ======

        function handleLessonDrop(cell, subjectId) {
            const dayKey = cell.dataset.day;
            const slotKey = cell.dataset.slot;
            if (!dayKey || !slotKey) {
                return;
            }

            const cellKey = buildCellKey(dayKey, slotKey);
            const subject = subjectMap.get(String(subjectId));
            if (!subject) {
                return;
            }

            const existingLesson = state.lessons.get(cellKey);
            if (existingLesson && existingLesson.subjectId !== subjectId) {
                const confirmReplace = confirm('Эта ячейка уже занята. Заменить занятие?');
                if (!confirmReplace) {
                    return;
                }
            }

            const teacherId = state.selectedTeacherId || '';
            const lesson = {
                subjectId: String(subject.id),
                subjectName: subject.name,
                subjectShort: subject.short_name || subject.name,
                teacherId,
                room: existingLesson ? existingLesson.room : '',
                type: existingLesson ? existingLesson.type : 'lesson',
                notes: existingLesson ? existingLesson.notes : '',
            };

            state.lessons.set(cellKey, lesson);
            renderLessonInCell(cell, lesson);
            selectCell(cell);
            showMessage(`Добавлена пара: ${lesson.subjectShort}`, 'success');
        }

        function renderLessonInCell(cell, lesson) {
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

            const teacherName = lesson.teacherId ? getTeacherName(lesson.teacherId) : 'Преподаватель не назначен';
            const lessonTypeLabel = getLessonTypeLabel(lesson.type);

            const tags = [];
            if (lessonTypeLabel) {
                tags.push(`<span class="schedule-tag">${lessonTypeLabel}</span>`);
            }
            if (lesson.room) {
                tags.push(`<span class="schedule-tag schedule-tag--success">ауд. ${escapeHtml(lesson.room)}</span>`);
            }

            lessonNode.innerHTML = `
                <div class="schedule-lesson__title">${escapeHtml(lesson.subjectShort)}</div>
                <div class="schedule-lesson__meta">
                    <span>${escapeHtml(teacherName)}</span>
                    ${lesson.notes ? `<span>${escapeHtml(lesson.notes)}</span>` : ''}
                </div>
                ${tags.length ? `<div class="schedule-lesson__tags">${tags.join('')}</div>` : ''}
            `;

            lessonNode.dataset.cellKey = buildCellKey(cell.dataset.day, cell.dataset.slot);
            lessonNode.addEventListener('click', (event) => {
                event.stopPropagation();
                selectCell(cell);
            });

            renderDayView();
        }

        function deleteLesson(cellKey) {
            const cell = findCellByKey(cellKey);
            if (!cell) {
                return;
            }
            state.lessons.delete(cellKey);
            cell.classList.remove('has-lesson', 'grid-cell--active');

            const placeholder = cell.querySelector('.grid-cell__placeholder');
            if (placeholder) {
                placeholder.style.display = '';
            }
            const lessonNode = cell.querySelector('.schedule-lesson');
            if (lessonNode) {
                lessonNode.remove();
            }

            renderDayView();
            showMessage('Занятие удалено.', 'success');
            clearSelection();
        }

        function clearDay(dayKey) {
            const keysToRemove = Array.from(state.lessons.keys()).filter((key) => key.startsWith(`${dayKey}__`));
            keysToRemove.forEach((key) => {
                const cell = findCellByKey(key);
                if (cell) {
                    cell.classList.remove('has-lesson', 'grid-cell--active');
                    const placeholder = cell.querySelector('.grid-cell__placeholder');
                    if (placeholder) {
                        placeholder.style.display = '';
                    }
                    const lessonNode = cell.querySelector('.schedule-lesson');
                    if (lessonNode) {
                        lessonNode.remove();
                    }
                }
                state.lessons.delete(key);
            });

            if (state.selectedDayKey === dayKey) {
                clearSelection();
            }

            renderDayView();
            showMessage('День очищен.', 'success');
        }

        // ====== SELECTION & DETAILS ======

        function selectCell(cell) {
            if (!cell) {
                return;
            }
            droppableCells.forEach((c) => c.classList.remove('grid-cell--active'));
            cell.classList.add('grid-cell--active');

            const dayKey = cell.dataset.day;
            const slotKey = cell.dataset.slot;
            const cellKey = buildCellKey(dayKey, slotKey);
            state.selectedCellKey = cellKey;
            state.selectedDayKey = dayKey;

            renderDetailsPanel(cellKey);
            updateDeleteButton();
        }

        function renderDetailsPanel(cellKey) {
            if (!elements.details) {
                return;
            }

            const lesson = state.lessons.get(cellKey);
            if (!lesson) {
                elements.details.innerHTML = `
                    <div class="details-placeholder">
                        <i class="bi bi-info-circle"></i>
                        <p>Выберите предмет или перетащите его в сетку, чтобы начать.</p>
                    </div>
                `;
                return;
            }

            const teacherOptions = Array.from(teacherMap.values())
                .map((teacher) => {
                    const selected = String(teacher.id) === lesson.teacherId ? 'selected' : '';
                    return `<option value="${teacher.id}" ${selected}>${escapeHtml(teacher.name)}</option>`;
                })
                .join('');

            const lessonTypeOptions = LESSON_TYPES.map((type) => {
                const selected = type.value === lesson.type ? 'selected' : '';
                return `<option value="${type.value}" ${selected}>${type.label}</option>`;
            }).join('');

            elements.details.innerHTML = `
                <form class="schedule-details-form" id="scheduleDetailsForm">
                    <div>
                        <label class="form-label">Предмет</label>
                        <input type="text" class="form-control" value="${escapeHtml(lesson.subjectName)}" readonly>
                    </div>
                    <div>
                        <label class="form-label" for="scheduleDetailsTeacher">Преподаватель</label>
                        <select id="scheduleDetailsTeacher" class="form-select">
                            <option value="">Не назначен</option>
                            ${teacherOptions}
                        </select>
                    </div>
                    <div class="row g-2">
                        <div class="col-6">
                            <label class="form-label" for="scheduleDetailsRoom">Аудитория</label>
                            <input id="scheduleDetailsRoom" type="text" class="form-control" value="${escapeHtml(lesson.room)}" placeholder="Например, 301">
                        </div>
                        <div class="col-6">
                            <label class="form-label" for="scheduleDetailsType">Тип занятия</label>
                            <select id="scheduleDetailsType" class="form-select">
                                ${lessonTypeOptions}
                            </select>
                        </div>
                    </div>
                    <div>
                        <label class="form-label" for="scheduleDetailsNotes">Комментарий</label>
                        <textarea id="scheduleDetailsNotes" class="form-control" rows="3" placeholder="Дополнительные материалы или заметки...">${escapeHtml(lesson.notes)}</textarea>
                    </div>
                    <div class="schedule-details-actions">
                        <button class="btn btn-outline-secondary" type="button" data-action="reset-details">Сбросить</button>
                        <button class="btn btn-primary" type="submit">Сохранить</button>
                    </div>
                </form>
            `;

            const form = document.getElementById('scheduleDetailsForm');
            const resetButton = form.querySelector('[data-action="reset-details"]');

            form.addEventListener('submit', (event) => {
                event.preventDefault();
                const updatedLesson = {
                    ...lesson,
                    teacherId: form.scheduleDetailsTeacher.value || '',
                    room: form.scheduleDetailsRoom.value.trim(),
                    type: form.scheduleDetailsType.value,
                    notes: form.scheduleDetailsNotes.value.trim(),
                };
                state.lessons.set(cellKey, updatedLesson);

                const cell = findCellByKey(cellKey);
                if (cell) {
                    renderLessonInCell(cell, updatedLesson);
                }
                showMessage('Детали занятия сохранены.', 'success');
            });

            if (resetButton) {
                resetButton.addEventListener('click', () => {
                    form.scheduleDetailsTeacher.value = lesson.teacherId;
                    form.scheduleDetailsRoom.value = lesson.room;
                    form.scheduleDetailsType.value = lesson.type;
                    form.scheduleDetailsNotes.value = lesson.notes;
                });
            }
        }

        function clearSelection() {
            state.selectedCellKey = null;
            state.selectedDayKey = null;
            droppableCells.forEach((cell) => cell.classList.remove('grid-cell--active'));
            renderDetailsPanel(null);
            updateDeleteButton();
        }

        function updateDeleteButton() {
            if (!elements.deleteButton) {
                return;
            }
            const disabled = !state.selectedCellKey || !state.lessons.has(state.selectedCellKey);
            elements.deleteButton.disabled = disabled;
        }

        // ====== FILTER HELPERS ======

        function filterGroupsByFaculty(facultyId) {
            if (!elements.groupSelect) {
                return;
            }
            const options = Array.from(elements.groupSelect.options);
            options.forEach((option) => {
                const optionFacultyId = option.dataset.faculty;
                if (!optionFacultyId) {
                    option.hidden = false;
                    return;
                }
                option.hidden = facultyId && optionFacultyId !== facultyId;
                if (option.hidden && option.selected) {
                    elements.groupSelect.value = '';
                }
            });
        }

        function applySubjectFilters() {
            const searchTerm = state.searchTerm;
            const teacherId = state.selectedTeacherId;

            libraryItems.forEach((item) => {
                const subjectId = item.dataset.subjectId;
                const text = item.textContent.toLowerCase();
                const matchesSearch = !searchTerm || text.includes(searchTerm);
                const teacher = teacherId ? teacherMap.get(String(teacherId)) : null;
                const teacherCanTeach =
                    !teacherId || (teacher && teacher.subjects.includes(Number(subjectId)));

                item.classList.toggle('library-item--hidden', !matchesSearch);
                item.classList.toggle('library-item--inactive', teacherId && !teacherCanTeach);
            });
        }

        // ====== WEEK NAVIGATION ======

        function shiftWeek(days) {
            state.weekStart = addDays(state.weekStart, days);
            state.weekEnd = addDays(state.weekStart, 5);
            updateWeekRange();
            renderSemesterTimeline();
            showMessage('Диапазон недели обновлён.', 'info');
        }

        function updateWeekRange() {
            if (!elements.weekRange) {
                return;
            }
            elements.weekRange.dataset.weekStart = formatISODate(state.weekStart);
            elements.weekRange.dataset.weekEnd = formatISODate(state.weekEnd);
            elements.weekRange.textContent = formatRangeLabel(state.weekStart, state.weekEnd);
        }

        // ====== UTILITIES ======

        function buildCellKey(dayKey, slotKey) {
            return `${dayKey}__${slotKey}`;
        }

        function findCellByKey(cellKey) {
            return droppableCells.find((cell) => buildCellKey(cell.dataset.day, cell.dataset.slot) === cellKey) || null;
        }

        function getTeacherName(teacherId) {
            const teacher = teacherMap.get(String(teacherId));
            return teacher ? teacher.name : 'Преподаватель не назначен';
        }

        function getLessonTypeLabel(type) {
            const item = LESSON_TYPES.find((lessonType) => lessonType.value === type);
            return item ? item.label : '';
        }

        function showMessage(text, type = 'info') {
            if (!elements.message) {
                return;
            }
            elements.message.textContent = text;
            elements.message.className = `schedule-message schedule-message--${type}`;
            elements.message.hidden = false;

            if (showMessage.timeoutId) {
                clearTimeout(showMessage.timeoutId);
            }
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
            const startLabel = start.toLocaleDateString('ru-RU', options);
            const endLabel = end.toLocaleDateString('ru-RU', options);
            return `${startLabel} – ${endLabel}`;
        }
    });
})();
