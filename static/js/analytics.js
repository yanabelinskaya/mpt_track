(function () {
  let brandColors = [];
  document.addEventListener('DOMContentLoaded', () => {
    const palette = {
      primary: getCssVar('--bs-primary', '#6366f1'),
      secondary: getCssVar('--bs-secondary', '#818cf8'),
      accent: getCssVar('--nav-link-color', '#94a3b8'),
      success: '#14b8a6',
      warning: '#fbbf24',
      info: '#22d3ee',
    };
    brandColors = buildBrandColors(palette);

    const facultyData = getJSONData('analyticsFacultyData');
    const courseData = getJSONData('analyticsCourseSummaryData');
    const groupData = getJSONData('analyticsGroupSummaryData');
    const teacherLoad = getJSONData('analyticsTeacherLoadData');

    const charts = {
      teacherLoadChart: createTeacherLoadChart('teacherLoadChart', teacherLoad),
    };

    initTabs(charts);
    initChartExport(charts);
    initTableExports({
      faculties: facultyData,
      courses: courseData,
      groups: groupData,
      teachers: teacherLoad,
    });
  });

  function getJSONData(id) {
    const element = document.getElementById(id);
    if (!element) {
      return [];
    }
    try {
      return JSON.parse(element.textContent);
    } catch (error) {
      console.warn('Ошибка разбора данных', id, error);
      return [];
    }
  }

  function getCssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return value ? value.trim() : fallback;
  }

  function buildBrandColors(palette) {
    return [
      palette.primary,
      '#4f46e5',
      palette.secondary,
      palette.info,
      '#0ea5e9',
      palette.success,
      palette.accent,
      '#a5b4fc',
    ].filter(Boolean);
  }

  function getSeriesColors(count) {
    if (!brandColors.length) {
      return [];
    }
    return Array.from({ length: count }, (_, index) => brandColors[index % brandColors.length]);
  }

  function createTeacherLoadChart(canvasId, data) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    const colors = getSeriesColors(2);
    return new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map((item) => item.name),
        datasets: [
          {
            label: 'Групп',
            data: data.map((item) => item.groups_total || 0),
            backgroundColor: colors[0],
          },
          {
            label: 'Студентов',
            data: data.map((item) => item.students_total || 0),
            backgroundColor: colors[1] || colors[0],
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: {
          legend: { position: 'bottom' },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    });
  }

  function initChartExport(charts) {
    document.querySelectorAll('.export-chart-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.dataset.chart;
        const chart = charts[target];
        if (!chart) {
          return;
        }
        const link = document.createElement('a');
        link.href = chart.toBase64Image('image/png', 1);
        link.download = `${target}_${new Date().toISOString().split('T')[0]}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      });
    });
  }

  function initTabs(charts) {
    const tabButtons = Array.from(document.querySelectorAll('.stats-tab-btn'));
    const panels = Array.from(document.querySelectorAll('[data-tab-panel]'));
    if (!tabButtons.length) {
      return;
    }

    const activate = (name) => {
      tabButtons.forEach((button) => {
        const isActive = button.dataset.tab === name;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-selected', String(isActive));
      });
      panels.forEach((panel) => {
        const isActive = panel.dataset.tabPanel === name;
        panel.classList.toggle('is-active', isActive);
        panel.hidden = !isActive;
        if (isActive) {
          panel.classList.add('is-active');
        } else {
          panel.classList.remove('is-active');
        }
      });
    };

    tabButtons.forEach((button, index) => {
      button.addEventListener('click', () => {
        if (button.classList.contains('is-active')) {
          return;
        }
        activate(button.dataset.tab);
      });
      button.addEventListener('keydown', (event) => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
          return;
        }
        event.preventDefault();
        const offset = event.key === 'ArrowRight' ? 1 : -1;
        const nextIndex = (index + offset + tabButtons.length) % tabButtons.length;
        const targetButton = tabButtons[nextIndex];
        targetButton.focus();
        activate(targetButton.dataset.tab);
      });
    });

    const initial = document.querySelector('.stats-tab-btn.is-active') || tabButtons[0];
    if (initial) {
      activate(initial.dataset.tab);
    }
  }

  function initTableExports(datasets) {
    const map = datasets || {};
    const modal = document.getElementById('analyticsExportModal');
    const confirmBtn = document.getElementById('analyticsExportConfirm');
    const closeButtons = modal ? modal.querySelectorAll('[data-export-close]') : [];
    let pendingTarget = null;

    const closeModal = () => {
      pendingTarget = null;
      if (modal) {
        modal.setAttribute('hidden', 'hidden');
      }
    };

    document.querySelectorAll('.table-export-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.dataset.export;
        const data = map[target] || [];
        if (!Array.isArray(data) || !data.length) {
          alert('Нет данных для экспорта.');
          return;
        }
        pendingTarget = target;
        if (modal) {
          modal.removeAttribute('hidden');
        } else {
          exportData(target, data);
        }
      });
    });

    closeButtons.forEach((btn) => btn.addEventListener('click', closeModal));

    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => {
        if (!pendingTarget) {
          closeModal();
          return;
        }
        const data = map[pendingTarget] || [];
        exportData(pendingTarget, data);
        closeModal();
      });
    }

    function exportData(target, data) {
      const csv = buildCsv(target, data);
      if (!csv) {
        alert('Не удалось подготовить файл.');
        return;
      }
      const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().split('T')[0];
      link.href = url;
      link.download = `analytics_${target}_${timestamp}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  }

  function buildCsv(type, data) {
    const headersMap = {
      faculties: ['Специальность', 'Код', 'Студентов', 'Активных', 'Средний балл', 'Посещаемость %'],
      courses: ['Курс', 'Групп', 'Студентов', 'Активных', 'Средний размер'],
      groups: ['Группа', 'Специальность', 'Профессия', 'Курс', 'Студентов', 'Активных', 'Статус'],
      teachers: ['Преподаватель', 'Групп', 'Предметов', 'Студентов'],
    };
    const header = headersMap[type];
    if (!header) {
      return '';
    }
    const rows = data.map((item) => {
      switch (type) {
        case 'faculties':
          return [
            item.name || '',
            item.code || '',
            item.students_total || 0,
            item.active_students || 0,
            item.avg_grade || 0,
            item.attendance_rate || 0,
          ];
        case 'courses':
          return [
            `${item.course || 0} курс`,
            item.groups_total || 0,
            item.students_total || 0,
            item.active_students_total || 0,
            item.avg_group_size || 0,
          ];
        case 'groups':
          return [
            item.code || '',
            item.faculty || '',
            item.profession || '',
            `${item.course || 0} курс`,
            item.students_total || 0,
            item.active_students_total || 0,
            item.status || '',
          ];
        case 'teachers':
          return [
            item.name || '',
            item.groups_total || 0,
            item.subjects_total || 0,
            item.students_total || 0,
          ];
        default:
          return [];
      }
    });

    const lines = [toCsvLine(header)];
    rows.forEach((row) => lines.push(toCsvLine(row)));
    return lines.join('\n');
  }

  function toCsvLine(values) {
    return values
      .map((value) => {
        const str = String(value ?? '').replace(/"/g, '""');
        return `"${str}"`;
      })
      .join(';');
  }
})();
