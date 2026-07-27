"use strict";


document.addEventListener("DOMContentLoaded", () => {
    const manager = document.getElementById("subjectManager");


    if (!manager) {
        return;
    }


    const addSubjectForm = document.getElementById(
        "addSubjectForm"
    );
    const newSubjectName = document.getElementById(
        "newSubjectName"
    );
    const addSubjectButton = document.getElementById(
        "addSubjectButton"
    );
    const activeSubjectsList = document.getElementById(
        "activeSubjectsList"
    );
    const inactiveSubjectsList = document.getElementById(
        "inactiveSubjectsList"
    );
    const subjectMessage = document.getElementById(
        "subjectMessage"
    );
    const continueButton = document.getElementById(
        "continueButton"
    );


    const deleteSubjectDialog = document.getElementById(
        "deleteSubjectDialog"
    );
    const deleteSubjectDescription = document.getElementById(
        "deleteSubjectDescription"
    );
    const cancelDeleteSubject = document.getElementById(
        "cancelDeleteSubject"
    );
    const confirmDeleteSubject = document.getElementById(
        "confirmDeleteSubject"
    );


    const isOnboarding = (
        manager.dataset.onboarding === "true"
    );


    let activeSubjects = [];
    let inactiveSubjects = [];
    let requestInProgress = false;
    let subjectPendingDeletion = null;


    const icons = {
        edit: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z" />
                <path d="m13.8 6.7 3.5 3.5" />
            </svg>
        `,
        remove: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14" />
            </svg>
        `,
        restore: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 8v5h5" />
                <path d="M5.5 13a7 7 0 1 0 1.7-6.5L4 9" />
            </svg>
        `,
        delete: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
            </svg>
        `,
        save: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m5 12 4 4 10-10" />
            </svg>
        `,
        cancel: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m6 6 12 12M18 6 6 18" />
            </svg>
        `
    };




    async function requestJson(url, options = {}) {
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
            window.location.href = "/login";
            throw new Error("Your login session has ended.");
        }


        if (!response.ok) {
            throw new Error(
                responseData.error ||
                "The request was unsuccessful."
            );
        }


        return responseData;
    }




    function showMessage(message, isError = false) {
        subjectMessage.textContent = message;
        subjectMessage.classList.toggle(
            "subject-message-error",
            isError
        );
    }




    function createIconButton(
        iconName,
        label,
        className,
        onClick
    ) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `subject-icon-button ${className}`;
        button.innerHTML = icons[iconName];
        button.dataset.tooltip = label;
        button.setAttribute("aria-label", label);
        button.addEventListener("click", onClick);
        return button;
    }




    function createSubjectRow(subject, isActive) {
        const row = document.createElement("article");
        row.className = "subject-row";


        const details = document.createElement("div");
        details.className = "subject-row-details";


        const name = document.createElement("strong");
        name.textContent = subject.subject_name;
        details.appendChild(name);


        const actions = document.createElement("div");
        actions.className = "subject-row-actions";


        if (isActive) {
            actions.appendChild(createIconButton(
                "edit",
                "Rename subject",
                "subject-edit-button",
                () => beginRename(subject, row)
            ));


            actions.appendChild(createIconButton(
                "remove",
                "Move to previous subjects",
                "subject-remove-button",
                () => updateSubject(subject, {
                    action: "deactivate"
                })
            ));
        } else {
            actions.appendChild(createIconButton(
                "restore",
                "Restore subject",
                "subject-restore-button",
                () => updateSubject(subject, {
                    action: "reactivate"
                })
            ));


            actions.appendChild(createIconButton(
                "delete",
                "Delete permanently",
                "subject-delete-button",
                () => openDeleteSubjectDialog(subject)
            ));
        }


        row.appendChild(details);
        row.appendChild(actions);


        return row;
    }




    function beginRename(subject, row) {
        if (requestInProgress) {
            return;
        }


        const details = row.querySelector(
            ".subject-row-details"
        );
        const actions = row.querySelector(
            ".subject-row-actions"
        );


        details.innerHTML = "";
        actions.innerHTML = "";
        row.classList.add("subject-row-editing");


        const input = document.createElement("input");
        input.type = "text";
        input.maxLength = 100;
        input.value = subject.subject_name;
        input.className = "subject-rename-input";
        input.setAttribute(
            "aria-label",
            `Rename ${subject.subject_name}`
        );


        const saveButton = createIconButton(
            "save",
            "Save subject name",
            "subject-save-button",
            async () => {
                await updateSubject(subject, {
                    action: "rename",
                    subject_name: input.value
                });
            }
        );


        const cancelButton = createIconButton(
            "cancel",
            "Cancel rename",
            "subject-cancel-button",
            renderSubjects
        );


        details.appendChild(input);
        actions.appendChild(saveButton);
        actions.appendChild(cancelButton);


        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                saveButton.click();
            }


            if (event.key === "Escape") {
                renderSubjects();
            }
        });


        input.focus();
        input.select();
    }




    function renderEmptyState(container, text) {
        const message = document.createElement("p");
        message.className = "empty-subject-message";
        message.textContent = text;
        container.appendChild(message);
    }




    function renderSubjects() {
        activeSubjectsList.innerHTML = "";
        inactiveSubjectsList.innerHTML = "";


        activeSubjects.forEach((subject) => {
            activeSubjectsList.appendChild(
                createSubjectRow(subject, true)
            );
        });


        inactiveSubjects.forEach((subject) => {
            inactiveSubjectsList.appendChild(
                createSubjectRow(subject, false)
            );
        });


        if (activeSubjects.length === 0) {
            renderEmptyState(
                activeSubjectsList,
                isOnboarding
                    ? "Add at least one subject to continue."
                    : "No active subjects. Focus is still available for every study session."
            );
        }


        if (inactiveSubjects.length === 0) {
            renderEmptyState(
                inactiveSubjectsList,
                "No previous subjects."
            );
        }


        continueButton.disabled = (
            isOnboarding
            && activeSubjects.length === 0
        );
    }




    async function loadSubjects() {
        try {
            const data = await requestJson(
                manager.dataset.apiUrl
            );


            activeSubjects = data.active_subjects;
            inactiveSubjects = data.inactive_subjects;
            renderSubjects();
        } catch (error) {
            showMessage(error.message, true);
        }
    }




    async function addSubject(event) {
        event.preventDefault();


        const subjectName = newSubjectName.value.trim();


        if (!subjectName || requestInProgress) {
            return;
        }


        requestInProgress = true;
        addSubjectButton.disabled = true;
        showMessage("Saving subject...");


        try {
            await requestJson(
                manager.dataset.apiUrl,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        subject_name: subjectName
                    })
                }
            );


            newSubjectName.value = "";
            showMessage("Subject added.");
            await loadSubjects();
            newSubjectName.focus();
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            requestInProgress = false;
            addSubjectButton.disabled = false;
        }
    }




    async function updateSubject(subject, requestBody) {
        if (requestInProgress) {
            return;
        }


        requestInProgress = true;
        showMessage("Saving changes...");


        try {
            await requestJson(
                `${manager.dataset.apiUrl}/${subject.subject_id}`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(requestBody)
                }
            );


            showMessage("Subject changes saved.");
            await loadSubjects();
        } catch (error) {
            showMessage(error.message, true);
            renderSubjects();
        } finally {
            requestInProgress = false;
        }
    }




    function openDeleteSubjectDialog(subject) {
        subjectPendingDeletion = subject;
        deleteSubjectDescription.textContent = (
            `Permanently delete ${subject.subject_name}? ` +
            "Its previous study sessions will be changed to Focus. " +
            "This cannot be undone."
        );
        deleteSubjectDialog.showModal();
        confirmDeleteSubject.focus();
    }




    function closeDeleteSubjectDialog() {
        if (requestInProgress) {
            return;
        }


        subjectPendingDeletion = null;
        deleteSubjectDialog.close();
        confirmDeleteSubject.disabled = false;
        confirmDeleteSubject.textContent = "Delete Subject";
    }




    async function permanentlyDeleteSubject() {
        if (!subjectPendingDeletion || requestInProgress) {
            return;
        }


        requestInProgress = true;
        confirmDeleteSubject.disabled = true;
        confirmDeleteSubject.textContent = "Deleting...";
        showMessage("Deleting subject...");


        try {
            await requestJson(
                `${manager.dataset.apiUrl}/${subjectPendingDeletion.subject_id}`,
                {method: "DELETE"}
            );


            subjectPendingDeletion = null;
            deleteSubjectDialog.close();
            showMessage(
                "Subject deleted. Its study history is now recorded as Focus."
            );
            await loadSubjects();
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            requestInProgress = false;
            confirmDeleteSubject.disabled = false;
            confirmDeleteSubject.textContent = "Delete Subject";
        }
    }




    async function continueFromPage() {
        if (!isOnboarding) {
            window.location.href = manager.dataset.homeUrl;
            return;
        }


        if (activeSubjects.length === 0) {
            showMessage(
                "Please add at least one subject to finish account setup.",
                true
            );
            return;
        }


        if (requestInProgress) {
            return;
        }


        requestInProgress = true;
        continueButton.disabled = true;
        continueButton.textContent = "Finishing setup...";


        try {
            await requestJson(
                manager.dataset.completeUrl,
                {method: "POST"}
            );


            window.location.href = manager.dataset.homeUrl;
        } catch (error) {
            requestInProgress = false;
            continueButton.disabled = false;
            continueButton.textContent = "Continue to Dashboard";
            showMessage(error.message, true);
        }
    }




    addSubjectForm.addEventListener("submit", addSubject);
    continueButton.addEventListener("click", continueFromPage);
    cancelDeleteSubject.addEventListener(
        "click",
        closeDeleteSubjectDialog
    );
    confirmDeleteSubject.addEventListener(
        "click",
        permanentlyDeleteSubject
    );


    deleteSubjectDialog.addEventListener("click", (event) => {
        if (event.target === deleteSubjectDialog) {
            closeDeleteSubjectDialog();
        }
    });


    document.addEventListener("keydown", (event) => {
        if (
            event.key === "Escape"
            && deleteSubjectDialog.open
        ) {
            event.preventDefault();
            closeDeleteSubjectDialog();
        }
    });


    loadSubjects();
});



