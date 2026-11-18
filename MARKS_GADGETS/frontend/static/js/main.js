document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-confirm]");
    if (form && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
    }
});

document.querySelectorAll("input[type='number'][max]").forEach((input) => {
    input.addEventListener("change", () => {
        const maximum = Number(input.max);
        if (maximum > 0 && Number(input.value) > maximum) input.value = String(maximum);
        if (Number(input.value) < Number(input.min || 1)) input.value = input.min || "1";
    });
});