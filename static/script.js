const links = document.querySelectorAll(".links");
const darkModeToggle = document.getElementById("dark-mode-toggle");

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

links.forEach(link => {
    link.addEventListener("click", () => {

        links.forEach(item => {
            item.classList.remove("ativo");
        });

        link.classList.add("ativo");
    });
});