(() => {
    const shell = document.getElementById("adminShell");
    const toggle = document.getElementById("adminMenuToggle");
    const backdrop = document.getElementById("adminSidebarBackdrop");
    const sidebar = document.getElementById("adminSidebar");
    if (!shell || !toggle || !backdrop || !sidebar) return;

    const mobile = window.matchMedia("(max-width: 780px)");
    const collapsedKey = "marks-gadgets-admin-sidebar-collapsed";

    try {
        if (window.localStorage.getItem(collapsedKey) === "true") {
            shell.classList.add("is-collapsed");
        }
    } catch (error) {
        console.warn("Admin sidebar preference could not be loaded.", error);
    }

    const setExpanded = (expanded) => {
        toggle.setAttribute("aria-expanded", String(expanded));
        if (mobile.matches) {
            sidebar.setAttribute("aria-hidden", String(!expanded));
            sidebar.inert = !expanded;
        } else {
            sidebar.removeAttribute("aria-hidden");
            sidebar.inert = false;
        }
    };

    const closeMobileSidebar = () => {
        shell.classList.remove("is-mobile-open");
        setExpanded(false);
    };

    setExpanded(!mobile.matches && !shell.classList.contains("is-collapsed"));

    toggle.addEventListener("click", () => {
        if (mobile.matches) {
            const isOpen = shell.classList.toggle("is-mobile-open");
            setExpanded(isOpen);
            return;
        }

        const isCollapsed = shell.classList.toggle("is-collapsed");
        setExpanded(!isCollapsed);
        try {
            window.localStorage.setItem(collapsedKey, String(isCollapsed));
        } catch (error) {
            console.warn("Admin sidebar preference could not be saved.", error);
        }
    });

    backdrop.addEventListener("click", closeMobileSidebar);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && shell.classList.contains("is-mobile-open")) {
            closeMobileSidebar();
            toggle.focus();
        }
    });
    mobile.addEventListener("change", () => {
        shell.classList.remove("is-mobile-open");
        setExpanded(!mobile.matches && !shell.classList.contains("is-collapsed"));
    });
})();
