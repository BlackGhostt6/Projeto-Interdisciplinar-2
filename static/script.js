const themeButtons = document.querySelectorAll("#theme-toggle-btn, #login-theme-btn");

function syncThemeButton(button, isDarkMode) {
    const icon = button.querySelector("i");
    const label = button.querySelector("span");

    if (button.id === "theme-toggle-btn") {
        if (label) {
            label.textContent = isDarkMode ? "Modo Claro" : "Modo Escuro";
        }

        if (icon) {
            icon.classList.toggle("ph-moon", !isDarkMode);
            icon.classList.toggle("ph-sun", isDarkMode);
            icon.classList.toggle("fa-moon", !isDarkMode);
            icon.classList.toggle("fa-sun", isDarkMode);
        }
    }

    if (button.id === "login-theme-btn") {
        if (icon) {
            icon.classList.toggle("fa-moon", !isDarkMode);
            icon.classList.toggle("fa-sun", isDarkMode);
        }
    }
}

function applyTheme(isDarkMode) {
    document.body.classList.toggle("dark-mode", isDarkMode);
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");

    themeButtons.forEach((button) => {
        syncThemeButton(button, isDarkMode);
    });
}

const savedTheme = localStorage.getItem("theme");
const shouldUseDarkTheme = savedTheme === "dark" || (!savedTheme && window.matchMedia("(prefers-color-scheme: dark)").matches);

applyTheme(shouldUseDarkTheme);

themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const nextTheme = !document.body.classList.contains("dark-mode");
        applyTheme(nextTheme);
    });
});

document.querySelectorAll("[command='show-modal']").forEach((button) => {
    button.addEventListener("click", () => {
        const modalId = button.getAttribute("commandfor");
        const modal = modalId ? document.getElementById(modalId) : null;

        if (modal) {
            modal.showModal();
        }
    });
});

document.querySelectorAll(".close[command='close']").forEach((button) => {
    button.addEventListener("click", () => {
        const modalId = button.getAttribute("commandfor");
        const modal = modalId ? document.getElementById(modalId) : null;

        if (modal) {
            modal.close();
        }
    });
});

const textarea = document.getElementById("new-note");
if (textarea) {
    const params = new URLSearchParams(window.location.search);
    const idViagem = params.get("viagem");

    textarea.addEventListener("keydown", async (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            const anotacao = textarea.value.trim();
            if (!anotacao) return;
            const resposta = await fetch("/api/anotacao", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    id_viagem: idViagem,
                    anotacao: anotacao
                })
            });
            if (resposta.ok) {
                textarea.value = "";
                location.reload();
            }
        }
    });
}