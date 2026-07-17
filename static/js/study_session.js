"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const MINIMUM_DURATION_MINUTES = 15;
    const MAXIMUM_DURATION_MINUTES = 12 * 60;

    /*
     * The duration currently displayed to the user.
     * It starts at 30 minutes.
     */
    let currentDurationMinutes = 30;

    /*
     * The final duration is saved here when the user
     * presses Start Studying.
     */
    let selectedStudyDurationMinutes = null;

    const hoursDisplay =
        document.getElementById("hoursDisplay");

    const minutesDisplay =
        document.getElementById("minutesDisplay");

    const increaseHoursButton =
        document.getElementById("increaseHours");

    const decreaseHoursButton =
        document.getElementById("decreaseHours");

    const increaseMinutesButton =
        document.getElementById("increaseMinutes");

    const decreaseMinutesButton =
        document.getElementById("decreaseMinutes");

    const startStudyButton =
        document.getElementById("startStudyButton");


    function updateDisplayedTime() {
        const hours =
            Math.floor(currentDurationMinutes / 60);

        const minutes =
            currentDurationMinutes % 60;

        hoursDisplay.textContent =
            String(hours).padStart(2, "0");

        minutesDisplay.textContent =
            String(minutes).padStart(2, "0");

        /*
         * Prevent the user going below 15 minutes
         * or above 12 hours.
         */
        const minimumReached =
            currentDurationMinutes <=
            MINIMUM_DURATION_MINUTES;

        const maximumReached =
            currentDurationMinutes >=
            MAXIMUM_DURATION_MINUTES;

        decreaseHoursButton.disabled = minimumReached;
        decreaseMinutesButton.disabled = minimumReached;

        increaseHoursButton.disabled = maximumReached;
        increaseMinutesButton.disabled = maximumReached;
    }


    function changeDuration(amountInMinutes) {
        let newDuration =
            currentDurationMinutes + amountInMinutes;

        /*
         * Keep the duration between 15 minutes
         * and 12 hours.
         */
        if (newDuration < MINIMUM_DURATION_MINUTES) {
            newDuration = MINIMUM_DURATION_MINUTES;
        }

        if (newDuration > MAXIMUM_DURATION_MINUTES) {
            newDuration = MAXIMUM_DURATION_MINUTES;
        }

        currentDurationMinutes = newDuration;

        /*
         * Update what the user can see immediately.
         */
        updateDisplayedTime();
    }


    increaseHoursButton.addEventListener("click", () => {
        changeDuration(60);
    });


    decreaseHoursButton.addEventListener("click", () => {
        changeDuration(-60);
    });


    increaseMinutesButton.addEventListener("click", () => {
        changeDuration(15);
    });


    decreaseMinutesButton.addEventListener("click", () => {
        changeDuration(-15);
    });


    startStudyButton.addEventListener("click", () => {
        /*
         * Save the duration selected by the user.
         */
        selectedStudyDurationMinutes =
            currentDurationMinutes;

        console.log(
            `Saved study duration: ${selectedStudyDurationMinutes} minutes`
        );
    });


    /*
     * Show the starting time when the page loads.
     */
    updateDisplayedTime();
});