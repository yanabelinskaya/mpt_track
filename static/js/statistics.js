(function () {
  let brandColors = [];
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof Chart === 'undefined') {
      return;
    }

    const palette = {
      primary: getCssVar('--bs-primary', '#6366f1'),
      secondary: getCssVar('--bs-secondary', '#818cf8'),
      accent: getCssVar('--nav-link-color', '#a6a6a6ff'),
      success: '#14b8a6',
      warning: '#fbbf24',
      info: '#e6c1f6ff',
      danger: '#f472b6',
    };
    brandColors = buildBrandColors(palette);

    const datasets = {
      attendanceTrend: getJSONData('attendanceTrendData'),
      faculty: getJSONData('facultyDistributionData'),
      statuses: getJSONData('statusDistributionData'),
      gradeDistribution: getJSONData('gradeDistributionData'),
      topSubjects: getJSONData('topSubjectsData'),
      attendanceSummary: getJSONData('attendanceSummaryData', {}),
    };

    const charts = {
      facultyDistributionChart: createFacultyChart('facultyDistributionChart', datasets.faculty, palette),
      statusDistributionChart: createStatusChart('statusDistributionChart', datasets.statuses, palette),
      attendanceTrendChart: createAttendanceTrendChart('attendanceTrendChart', datasets.attendanceTrend, palette),
      gradeDistributionChart: createGradeDistributionChart('gradeDistributionChart', datasets.gradeDistribution, palette),
      topSubjectsChart: createTopSubjectsChart('topSubjectsChart', datasets.topSubjects, palette),
      attendanceStatusChart: createAttendanceStatusChart('attendanceStatusChart', datasets.attendanceSummary, palette),
    };

    initTabs(charts);
    initChartExport(charts);
  });

  function getJSONData(id, fallback = []) {
    const element = document.getElementById(id);
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent);
    } catch (error) {
      console.warn('Ошибка парсинга данных графика', id, error);
      return fallback;
    }
  }

  function getCssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return value ? value.trim() : fallback;
  }

  function createFacultyChart(canvasId, data, palette) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    return new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map((item) => item.code || item.name || '—'),
        datasets: [
          {
            label: 'Студентов',
            data: data.map((item) => item.total || 0),
            backgroundColor: getSeriesColors(data.length),
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: {
              autoSkip: false,
              maxRotation: 40,
              minRotation: 0,
            },
          },
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function createStatusChart(canvasId, data, palette) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    const colors = getSeriesColors(data.length);
    return new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: data.map((item) => item.label),
        datasets: [
          {
            data: data.map((item) => item.total || 0),
            backgroundColor: colors,
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        cutout: '55%',
        plugins: { legend: { position: 'bottom' } },
        radius: '60%',
      },
    });
  }

  function createAttendanceTrendChart(canvasId, data, palette) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    return new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map((item) => item.label),
        datasets: [
          {
            label: 'Отсутствия',
            data: data.map((item) => item.absent || 0),
            backgroundColor: '#ba1414ff',
          },
          {
            label: 'Опоздания',
            data: data.map((item) => item.late || 0),
            backgroundColor: palette.warning,
          },
          {
            label: 'Уважительная причина',
            data: data.map((item) => item.excused || 0),
            backgroundColor: palette.info,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function createGradeDistributionChart(canvasId, data, palette) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    return new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map((item) => item.grade),
        datasets: [
          {
            label: 'Количество оценок',
            data: data.map((item) => item.total || 0),
            backgroundColor: getSeriesColors(data.length),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function createTopSubjectsChart(canvasId, data, palette) {
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    return new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map((item) => item.subject),
        datasets: [
          {
            label: 'Средний балл',
            data: data.map((item) => item.avg || 0),
            backgroundColor: getSeriesColors(data.length),
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: {
              maxRotation: 40,
              minRotation: 0,
              autoSkip: false,
            },
          },
          y: {
            beginAtZero: true,
            suggestedMax: 5,
          },
        },
      },
    });
  }

  function createAttendanceStatusChart(canvasId, summary, palette) {
    if (!summary || typeof summary !== 'object' || !summary.total) {
      return null;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    const present = summary.present || 0;
    const chartData = [
      { label: 'Присутствовали', value: present, color: palette.primary },
      { label: 'Отсутствовали', value: summary.absent || 0, color: palette.danger },
      { label: 'Опоздали', value: summary.late || 0, color: palette.warning },
      { label: 'Уважительная причина', value: summary.excused || 0, color: palette.info },
    ];

    return new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: chartData.map((item) => item.label),
        datasets: [
          {
            data: chartData.map((item) => item.value),
            backgroundColor: chartData.map((item) => item.color),
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        cutout: '50%',
        plugins: { legend: { position: 'bottom' } },
        radius: '55%',
      },
    });
  }

  function initTabs(charts) {
    const tabButtons = Array.from(document.querySelectorAll('[data-tab]'));
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
      });
      requestAnimationFrame(() => {
        Object.values(charts).forEach((chart) => chart && chart.resize && chart.resize());
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
        if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
          return;
        }
        event.preventDefault();
        const offset = event.key === 'ArrowRight' ? 1 : -1;
        const nextIndex = (index + offset + tabButtons.length) % tabButtons.length;
        const nextButton = tabButtons[nextIndex];
        nextButton.focus();
        activate(nextButton.dataset.tab);
      });
    });

    const initial = document.querySelector('[data-tab].is-active') || tabButtons[0];
    if (initial) {
      activate(initial.dataset.tab);
    }
  }

  function initChartExport(charts) {
    document.querySelectorAll('.export-chart-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const chartId = button.dataset.chart;
        const chart = charts[chartId];
        if (!chart) {
          return;
        }
        const link = document.createElement('a');
        link.href = chart.toBase64Image('image/png', 1);
        link.download = `${chartId}_${new Date().toISOString().slice(0, 10)}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      });
    });
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
})();
