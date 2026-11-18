document.querySelectorAll(".cart-quantity input").forEach((input) => {
    input.addEventListener("input", () => {
        const max = Number(input.max);
        input.setCustomValidity(Number(input.value) > max ? `Only ${max} units are available.` : "");
    });
});