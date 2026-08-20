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

async function apiRequest(url, method, body) {
    const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.erro || "Não foi possível concluir a operação.");
    }
    return response;
}

document.querySelectorAll(".edit-note-btn").forEach((button) => {
    button.addEventListener("click", () => {
        const note = button.closest("[data-note-id]");
        const modal = document.getElementById("edit-note-modal");
        document.getElementById("edit-note-id").value = note.dataset.noteId;
        document.getElementById("edit-note-text").value = note.querySelector("p").textContent.trim();
        modal.showModal();
    });
});

document.querySelectorAll(".delete-note-btn").forEach((button) => {
    button.addEventListener("click", async () => {
        const note = button.closest("[data-note-id]");
        if (!confirm("Excluir esta anotação?")) return;
        try {
            await apiRequest(`/api/anotacao/${note.dataset.noteId}`, "DELETE");
            location.reload();
        } catch (error) {
            alert(error.message);
        }
    });
});

const editNoteForm = document.getElementById("edit-note-form");
if (editNoteForm) {
    editNoteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await apiRequest(`/api/anotacao/${document.getElementById("edit-note-id").value}`, "PUT", {
                anotacao: document.getElementById("edit-note-text").value.trim()
            });
            location.reload();
        } catch (error) {
            alert(error.message);
        }
    });
}

document.querySelectorAll(".edit-trip-btn").forEach((button) => {
    button.addEventListener("click", () => {
        const trip = button.closest("[data-trip-id]");
        document.getElementById("edit-trip-id").value = trip.dataset.tripId;
        document.getElementById("edit-destino").value = trip.dataset.destination;
        document.getElementById("edit-data-viagem").value = trip.dataset.start;
        document.getElementById("edit-data-volta").value = trip.dataset.end;
        document.getElementById("edit-trip-modal").showModal();
    });
});

document.querySelectorAll(".delete-trip-btn").forEach((button) => {
    button.addEventListener("click", async () => {
        const trip = button.closest("[data-trip-id]");
        if (!confirm("Excluir esta viagem e todas as suas anotações e movimentações?")) return;
        try {
            await apiRequest(`/api/viagem/${trip.dataset.tripId}`, "DELETE");
            location.href = "/";
        } catch (error) {
            alert(error.message);
        }
    });
});

const editTripForm = document.getElementById("edit-trip-form");
if (editTripForm) {
    editTripForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await apiRequest(`/api/viagem/${document.getElementById("edit-trip-id").value}`, "PUT", {
                destino: document.getElementById("edit-destino").value,
                data_viagem: document.getElementById("edit-data-viagem").value,
                data_volta: document.getElementById("edit-data-volta").value
            });
            location.reload();
        } catch (error) {
            alert(error.message);
        }
    });
}

const profileForm = document.getElementById("profile-form");
if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await apiRequest(`/api/usuario/${profileForm.dataset.userId}`, "PUT", {
                nome: document.getElementById("profile-name").value.trim(),
                email: document.getElementById("profile-email").value.trim(),
                senha: document.getElementById("profile-password").value
            });
            location.reload();
        } catch (error) {
            alert(error.message);
        }
    });
}

const deleteAccountButton = document.getElementById("delete-account-btn");
if (deleteAccountButton) {
    deleteAccountButton.addEventListener("click", async () => {
        if (!confirm("Excluir sua conta, viagens e anotações permanentemente?")) return;
        try {
            await apiRequest(`/api/usuario/${deleteAccountButton.dataset.userId}`, "DELETE");
            location.href = "/login";
        } catch (error) {
            alert(error.message);
        }
    });
}