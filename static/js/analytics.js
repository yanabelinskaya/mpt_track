(function() {
    let brandColors = [];
    document.addEventListener('DOMContentLoaded', () => {
        if (typeof Chart === 'undefined') {
            return;
        }

        const palette = {
            primary: getCssVar('--bs-primary', '#6366f1'),
            secondary: getCssVar('--bs-secondary', '#818cf8'),
            accent: getCssVar('--nav-link-color', '#94a3b8'),
            success: '#14b8a6',
            warning: '#fbbf24',
            info: '#22d3ee',
        };
        brandColors = buildBrandColors(palette);

        const charts = {};
        const facultyData = getJSONData('analyticsFacultyData');
        const gradeDistribution = getJSONData('analyticsGradeDistributionData');
        const teacherLoad = getJSONData('analyticsTeacherLoadData');

        charts.facultyStudentsChart = createFacultyChart('facultyStudentsChart', facultyData, palette);
        charts.attendanceRateChart = createAttendanceRateChart('attendanceRateChart', facultyData, palette);
        charts.gradeDistributionChart = createGradeDistributionChart('gradeDistributionChart', gradeDistribution, palette);
        charts.teacherLoadChart = createTeacherLoadChart('teacherLoadChart', teacherLoad, palette);

        initChartExport(charts);
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

    function createFacultyChart(canvasId, data, palette) {
        if (!Array.isArray(data) || !data.length) {
            return null;
        }
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            return null;
        }
        const labels = data.map(item => item.name);
        const colors = getSeriesColors(3);
        return new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Студенты',
                        backgroundColor: colors[0],
                        data: data.map(item => item.students_total || 0),
                    },
                    {
                        label: 'Активные',
                        backgroundColor: colors[2] || colors[0],
                        data: data.map(item => item.active_students || 0),
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                    },
                },
            },
        });
    }

    function createAttendanceRateChart(canvasId, data, palette) {
        if (!Array.isArray(data) || !data.length) {
            return null;
        }
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            return null;
        }
        const lineColor = getSeriesColors(1)[0] || palette.primary;
        return new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.map(item => item.name),
                datasets: [
                    {
                        label: 'Посещаемость %',
                        data: data.map(item => item.attendance_rate || 0),
                        borderColor: lineColor,
                        backgroundColor: `${lineColor}22`,
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: 100,
                        ticks: {
                            callback: (value) => `${value}%`,
                        },
                    },
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
                labels: data.map(item => item.grade),
                datasets: [
                    {
                        label: 'Количество оценок',
                        data: data.map(item => item.total || 0),
                        backgroundColor: getSeriesColors(data.length),
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                    },
                },
            },
        });
    }

    function createTeacherLoadChart(canvasId, data, palette) {
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
                labels: data.map(item => item.name),
                datasets: [
                    {
                        label: 'Групп',
                        data: data.map(item => item.groups_total || 0),
                        backgroundColor: colors[0],
                    },
                    {
                        label: 'Студентов',
                        data: data.map(item => item.students_total || 0),
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
        document.querySelectorAll('.export-chart-btn').forEach(button => {
            button.addEventListener('click', () => {
                const target = button.dataset.chart;
                const chart = charts[target];
                if (!chart) {
                    return;
                }
                const link = document.createElement('a');
                link.href = chart.toBase64Image('image/png', 1);
                link.download = `${target}_${new Date().toISOString().slice(0, 10)}.png`;
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
