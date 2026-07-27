"use strict";


document.addEventListener("DOMContentLoaded", () => {
    const toggleButtons = document.querySelectorAll(
        "[data-password-toggle]"
    );


    toggleButtons.forEach((button) => {
        const targetId = button.dataset.target;
        const passwordInput = document.getElementById(targetId);


        if (!passwordInput) {
            return;
        }


        const openEye = button.querySelector(
            ".password-eye-open"
        );


        const closedEye = button.querySelector(
            ".password-eye-closed"
        );


        button.addEventListener("click", () => {
            const passwordIsVisible =
                passwordInput.type === "text";


            passwordInput.type = passwordIsVisible
                ? "password"
                : "text";


            const newLabel = passwordIsVisible
                ? "Show password"
                : "Hide password";


            button.setAttribute(
                "aria-pressed",
                String(!passwordIsVisible)
            );


            button.setAttribute("aria-label", newLabel);
            button.title = newLabel;


            if (openEye) {
                openEye.hidden = !passwordIsVisible;
            }


            if (closedEye) {
                closedEye.hidden = passwordIsVisible;
            }


            passwordInput.focus({ preventScroll: true });


            const textLength = passwordInput.value.length;
            passwordInput.setSelectionRange(
                textLength,
                textLength
            );
        });
    });
});





