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
const textarea = document.getElementById("new-note");
const params = new URLSearchParams(window.location.search);
const idViagem = params.get("viagem");
textarea.addEventListener("keydown", async (event) => {
    console.log("tecla:", event.key);

    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        const anotacao = textarea.value.trim();
        console.log("anotacao:", anotacao);
        console.log("id viagem:", idViagem)
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