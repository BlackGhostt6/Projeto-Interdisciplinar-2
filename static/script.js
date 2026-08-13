const darkModeToggle = document.getElementById("theme-toggle-btn");

if (darkModeToggle) {
    darkModeToggle.addEventListener("click", () => {
        document.body.classList.toggle("dark-mode");

        const isDarkMode = document.body.classList.contains("dark-mode");
        const label = darkModeToggle.querySelector("span");
        const icon = darkModeToggle.querySelector("i");

        if (label) {
            label.textContent = isDarkMode ? "Modo Claro" : "Modo Escuro";
        }

        if (icon) {
            icon.classList.toggle("ph-moon", !isDarkMode);
            icon.classList.toggle("ph-sun", isDarkMode);
        }
    });
}

const ctx = document.getElementById('depositosChart');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: [
            'Jun',
            'Jul',
            'Ago',
            'Set',
            'Out',
            'Nov'
        ],
        datasets: [
            {
                label: 'Guardado',
                data: [
                    2000,
                    4200,
                    6800,
                    8200,
                    10200,
                    12000
                ],
                borderColor: '#3CAEA3',
                backgroundColor: 'rgba(60, 174, 163, 0.15)',
                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.4,
                fill: true
            },
            {
                label: 'Meta',
                data: [
                    15000,
                    15000,
                    15000,
                    15000,
                    15000,
                    15000
                ],

                borderColor: '#94A3B8',
                borderWidth: 2,

                borderDash: [6, 6],

                pointRadius: 0,

                fill: false
            }
        ]
    },

    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return ' R$ ' +
                            context.raw.toLocaleString('pt-BR');
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    callback: function(value) {
                        return 'R$ ' +
                            value.toLocaleString('pt-BR');
                    }
                }
            },
            x: {
                grid: {
                    display: false
                }
            }
        }
    }
});