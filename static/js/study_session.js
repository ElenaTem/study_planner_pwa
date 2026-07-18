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


    startStudyButton.addEventListener(
        "click",
        async () => {
            selectedStudyDurationMinutes =
                currentDurationMinutes;
    
            startStudyButton.disabled = true;
            startStudyButton.textContent =
                "Starting Session...";
    
            try {
                const response = await fetch(
                    startStudyButton.dataset.startUrl,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify({
                            duration_minutes:
                                selectedStudyDurationMinutes
                        })
                    }
                );
    
                const responseData =
                    await response.json();
    
                if (!response.ok) {
                    throw new Error(
                        responseData.error ||
                        "The session could not be started."
                    );
                }
    
                const activeSessionData = {
                    studySessionId:
                        responseData.study_session_id,
    
                    plannedDurationSeconds:
                        responseData
                            .planned_duration_seconds,
    
                    startTimeMs:
                        responseData.start_time_ms,
    
                    endTimeMs:
                        responseData.end_time_ms
                };
    
                sessionStorage.setItem(
                    "activeStudySession",
                    JSON.stringify(activeSessionData)
                );
    
                window.location.href =
                    startStudyButton.dataset.sessionUrl;
    
            } catch (error) {
                window.alert(error.message);
    
                startStudyButton.disabled = false;
                startStudyButton.textContent =
                    "Start Studying!";
            }
        }
    );


    /*
     * Show the starting time when the page loads.
     */
    updateDisplayedTime();
});