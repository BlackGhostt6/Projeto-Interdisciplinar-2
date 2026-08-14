const darkModeToggle = document.getElementById("theme-toggle-btn");

if (darkModeToggle) {

    // Recupera o tema salvo
    const temaSalvo = localStorage.getItem("theme");

    if (temaSalvo === "dark") {
        document.body.classList.add("dark-mode");

        const label = darkModeToggle.querySelector("span");
        const icon = darkModeToggle.querySelector("i");

        if (label) {
            label.textContent = "Modo Claro";
        }

        if (icon) {
            icon.classList.remove("ph-moon");
            icon.classList.add("ph-sun");
        }
    }

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

        // Salva a preferência
        localStorage.setItem("theme", isDarkMode ? "dark" : "light");
    });
}

const canvas = document.getElementById("depositosChart");

async function carregarGrafico(id) {
    try {
        const resposta = await fetch("/api/depositos/" + id);
        const dados = await resposta.json();

        let acumulado = 0;
        const labels = [];
        const valores = [];

        dados.forEach(item => {
            labels.push(item[0]);
            acumulado += Number(item[1]);
            valores.push(acumulado);
        });

        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Guardado",
                    data: valores,
                    borderColor: "#3CAEA3",
                    backgroundColor: "rgba(60, 174, 163, 0.15)",
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return " R$ " + Number(context.raw).toLocaleString("pt-BR", {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return "R$ " + Number(value).toLocaleString("pt-BR");
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
    } catch (erro) {
        console.error("Erro no gráfico:", erro);
    }
}

const form = document.getElementById("id-viagem");
const select = form.querySelector("select");

carregarGrafico(select.value);