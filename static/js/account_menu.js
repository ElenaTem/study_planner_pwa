"use strict";


document.addEventListener("DOMContentLoaded", () => {
    const accountMenu = document.getElementById("accountMenu");


    if (!accountMenu) {
        return;
    }


    const menuToggle = document.getElementById("accountMenuToggle");
    const dropdown = document.getElementById("accountDropdown");
    const deleteTrigger = document.getElementById(
        "openDeleteAccountDialog"
    );


    const deleteDialog = document.getElementById(
        "deleteAccountDialog"
    );
    const closeDialogButton = document.getElementById(
        "closeDeleteAccountDialog"
    );
    const cancelDeleteButton = document.getElementById(
        "cancelDeleteAccount"
    );
    const passwordInput = document.getElementById(
        "deleteAccountPassword"
    );
    const verifyPasswordButton = document.getElementById(
        "verifyDeleteAccountPassword"
    );
    const confirmDeleteButton = document.getElementById(
        "confirmDeleteAccount"
    );
    const deleteMessage = document.getElementById(
        "deleteAccountMessage"
    );


    let passwordVerified = false;
    let requestInProgress = false;




    function setDropdownOpen(isOpen) {
        dropdown.hidden = !isOpen;
        menuToggle.setAttribute(
            "aria-expanded",
            String(isOpen)
        );
        accountMenu.classList.toggle(
            "account-menu-open",
            isOpen
        );
    }




    function resetDeleteDialog() {
        passwordVerified = false;
        requestInProgress = false;
        passwordInput.value = "";
        passwordInput.disabled = false;
        verifyPasswordButton.disabled = true;
        verifyPasswordButton.textContent = "Confirm Password";
        confirmDeleteButton.disabled = true;
        confirmDeleteButton.textContent = "Delete Account";
        deleteMessage.textContent = "";
        deleteMessage.classList.remove(
            "account-delete-message-error"
        );
    }




    function closeDeleteDialog() {
        if (requestInProgress) {
            return;
        }


        deleteDialog.close();
        resetDeleteDialog();
    }




    async function requestJson(url, options) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                Accept: "application/json",
                ...(options.headers || {})
            }
        });


        const responseData = await response
            .json()
            .catch(() => ({}));


        if (response.status === 401) {
            window.location.href = accountMenu.dataset.loginUrl;
            throw new Error("Your login session has ended.");
        }


        if (!response.ok) {
            throw new Error(
                responseData.error ||
                "The request could not be completed."
            );
        }


        return responseData;
    }




    menuToggle.addEventListener("click", () => {
        setDropdownOpen(dropdown.hidden);
    });




    document.addEventListener("click", (event) => {
        if (
            !dropdown.hidden
            && !accountMenu.contains(event.target)
        ) {
            setDropdownOpen(false);
        }
    });




    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }


        if (deleteDialog.open) {
            closeDeleteDialog();
            return;
        }


        if (!dropdown.hidden) {
            setDropdownOpen(false);
            menuToggle.focus();
        }
    });




    deleteTrigger.addEventListener("click", () => {
        setDropdownOpen(false);
        resetDeleteDialog();
        deleteDialog.showModal();
        window.setTimeout(() => passwordInput.focus(), 0);
    });




    passwordInput.addEventListener("input", () => {
        passwordVerified = false;
        confirmDeleteButton.disabled = true;
        verifyPasswordButton.disabled = (
            passwordInput.value.length === 0
            || requestInProgress
        );
        deleteMessage.textContent = "";
        deleteMessage.classList.remove(
            "account-delete-message-error"
        );
    });




    passwordInput.addEventListener("keydown", (event) => {
        if (
            event.key === "Enter"
            && !verifyPasswordButton.disabled
        ) {
            event.preventDefault();
            verifyPasswordButton.click();
        }
    });




    verifyPasswordButton.addEventListener(
        "click",
        async () => {
            if (requestInProgress || !passwordInput.value) {
                return;
            }


            requestInProgress = true;
            verifyPasswordButton.disabled = true;
            verifyPasswordButton.textContent = "Checking...";
            deleteMessage.textContent = "";


            try {
                await requestJson(
                    accountMenu.dataset.verifyUrl,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            password: passwordInput.value
                        })
                    }
                );


                passwordVerified = true;
                passwordInput.disabled = true;
                confirmDeleteButton.disabled = false;
                deleteMessage.textContent = "Password confirmed.";
                verifyPasswordButton.textContent = "Confirmed";


            } catch (error) {
                passwordVerified = false;
                confirmDeleteButton.disabled = true;
                deleteMessage.textContent = error.message;
                deleteMessage.classList.add(
                    "account-delete-message-error"
                );
                verifyPasswordButton.textContent = "Confirm Password";
                passwordInput.select();


            } finally {
                requestInProgress = false;
                verifyPasswordButton.disabled = (
                    passwordVerified
                    || passwordInput.value.length === 0
                );
            }
        }
    );




    confirmDeleteButton.addEventListener(
        "click",
        async () => {
            if (!passwordVerified || requestInProgress) {
                return;
            }


            requestInProgress = true;
            confirmDeleteButton.disabled = true;
            confirmDeleteButton.textContent = "Deleting...";
            deleteMessage.textContent = (
                "Permanently deleting your account..."
            );


            try {
                await requestJson(
                    accountMenu.dataset.deleteUrl,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            password: passwordInput.value
                        })
                    }
                );


                sessionStorage.removeItem("activeStudySession");
                window.location.replace(
                    accountMenu.dataset.loginUrl
                );


            } catch (error) {
                requestInProgress = false;
                passwordVerified = false;
                passwordInput.disabled = false;
                confirmDeleteButton.disabled = true;
                confirmDeleteButton.textContent = "Delete Account";
                verifyPasswordButton.disabled = false;
                verifyPasswordButton.textContent = "Confirm Password";
                deleteMessage.textContent = error.message;
                deleteMessage.classList.add(
                    "account-delete-message-error"
                );
                passwordInput.focus();
                passwordInput.select();
            }
        }
    );




    closeDialogButton.addEventListener(
        "click",
        closeDeleteDialog
    );


    cancelDeleteButton.addEventListener(
        "click",
        closeDeleteDialog
    );


    deleteDialog.addEventListener("click", (event) => {
        if (event.target === deleteDialog) {
            closeDeleteDialog();
        }
    });
});



