"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById(
        "activeStudySessionApp"
    );

    const dailyStudyTotal =
    document.getElementById("dailyStudyTotal");

    const countdownDisplay = document.getElementById(
        "countdownDisplay"
    );

    const progressTrack = document.getElementById(
        "progressTrack"
    );

    const progressFill = document.getElementById(
        "progressFill"
    );

    const elapsedTimeLabel = document.getElementById(
        "elapsedTimeLabel"
    );


    const nextGrowthMessage = document.getElementById(
        "nextGrowthMessage"
    );

    const activeStudyTree = document.getElementById(
        "activeStudyTree"
    );

    const endSessionButton = document.getElementById(
        "endSessionButton"
    );

    const endSessionDialog = document.getElementById(
        "endSessionDialog"
    );

    const continueSessionButton =
        document.getElementById(
            "continueSessionButton"
        );

    const confirmEndSessionButton =
        document.getElementById(
            "confirmEndSessionButton"
        );

    const completionDialog = document.getElementById(
        "completionDialog"
    );

    const redirectCountdown = document.getElementById(
        "redirectCountdown"
    );

    const returnHomeButton = document.getElementById(
        "returnHomeButton"
    );

    const treeImageUrls = JSON.parse(
        document.getElementById(
            "treeImageUrls"
        ).textContent
    );

    const storedSessionText = sessionStorage.getItem(
        "activeStudySession"
    );

    if (!storedSessionText) {
        window.location.replace(app.dataset.timerUrl);
        return;
    }

    let activeSession;

    try {
        activeSession = JSON.parse(
            storedSessionText
        );
    } catch {
        sessionStorage.removeItem(
            "activeStudySession"
        );

        window.location.replace(app.dataset.timerUrl);
        return;
    }

    const studySessionId =
        activeSession.studySessionId;

    const totalDurationSeconds =
        activeSession.plannedDurationSeconds;
    
    const totalDurationMilliseconds =
        totalDurationSeconds * 1000;
    const endTimeMs =
        activeSession.endTimeMs;

    const startTimeMs =
        activeSession.startTimeMs;

    let savedStudySecondsToday = 0;
    let loadedDayStartMs = null;
    let loadedDayEndMs = null;
    let dailyTotalRequestRunning = false;

    const useHours =
        totalDurationSeconds >= 60 * 60;

    let timerInterval = null;
    let sessionHasEnded = false;


    function formatTime(seconds, includeHours) {
        const safeSeconds = Math.max(
            0,
            Math.floor(seconds)
        );

        const hours = Math.floor(
            safeSeconds / 3600
        );

        const minutes = Math.floor(
            (safeSeconds % 3600) / 60
        );

        const remainingSeconds =
            safeSeconds % 60;

        if (includeHours) {
            return [
                String(hours).padStart(2, "0"),
                String(minutes).padStart(2, "0"),
                String(remainingSeconds)
                    .padStart(2, "0")
            ].join(":");
        }

        const totalMinutes = Math.floor(
            safeSeconds / 60
        );

        return [
            String(totalMinutes).padStart(2, "0"),
            String(remainingSeconds)
                .padStart(2, "0")
        ].join(":");
    }


    function updateTree(currentTimeMs) {
        const elapsedMilliseconds = Math.min(
            totalDurationMilliseconds,
            Math.max(
                0,
                currentTimeMs - startTimeMs
            )
        );
    
        const progress =
            elapsedMilliseconds /
            totalDurationMilliseconds;
    
        /*
         * Divides the complete session into
         * seven equal tree-growth stages.
         */
        const treeStageIndex = Math.min(
            6,
            Math.floor(progress * 7)
        );
    
        activeStudyTree.src =
            treeImageUrls[treeStageIndex];
    
        /*
         * Stage 7 is the final tree, so there
         * is no next growth stage.
         */
        if (treeStageIndex === 6) {
            nextGrowthMessage.textContent =
                "Your tree has reached its final growth stage.";
    
            return;
        }
    
        /*
         * Calculate the exact timestamp at which
         * the next tree stage should appear.
         */
        const nextStageProgress =
            (treeStageIndex + 1) / 7;
    
        const nextStageTimeMs =
            startTimeMs +
            (
                totalDurationMilliseconds *
                nextStageProgress
            );
    
        const secondsUntilNextStage = Math.max(
            0,
            Math.ceil(
                (
                    nextStageTimeMs -
                    currentTimeMs
                ) / 1000
            )
        );
    
        const stageCountdownUsesHours =
            secondsUntilNextStage >= 3600;
    
        nextGrowthMessage.textContent =
            `Time until next growth stage: ${
                formatTime(
                    secondsUntilNextStage,
                    stageCountdownUsesHours
                )
            }`;
    }

    function getLocalDayBoundaries() {
        const dayStart = new Date();
    
        dayStart.setHours(
            0,
            0,
            0,
            0
        );
    
        const dayEnd = new Date(dayStart);
    
        dayEnd.setDate(
            dayEnd.getDate() + 1
        );
    
        return {
            startMs: dayStart.getTime(),
            endMs: dayEnd.getTime()
        };
    }
    
    
    function formatDailyStudyTime(totalSeconds) {
        const totalMinutes = Math.floor(
            Math.max(0, totalSeconds) / 60
        );
    
        const hours = Math.floor(
            totalMinutes / 60
        );
    
        const minutes =
            totalMinutes % 60;
    
        const hourText =
            hours === 1 ? "hr" : "hrs";
    
        const minuteText =
            minutes === 1 ? "min" : "mins";
    
        return (
            `${hours} ${hourText} ` +
            `${minutes} ${minuteText}`
        );
    }
    
    
    async function loadSavedDailyStudyTotal() {
        if (dailyTotalRequestRunning) {
            return;
        }
    
        dailyTotalRequestRunning = true;
    
        const dayBoundaries =
            getLocalDayBoundaries();
    
        const requestUrl = new URL(
            app.dataset.dailyTotalUrl,
            window.location.origin
        );
    
        requestUrl.searchParams.set(
            "day_start_ms",
            String(dayBoundaries.startMs)
        );
    
        requestUrl.searchParams.set(
            "day_end_ms",
            String(dayBoundaries.endMs)
        );
    
        try {
            const response = await fetch(
                requestUrl
            );
    
            const responseData =
                await response.json();
    
            if (!response.ok) {
                throw new Error(
                    responseData.error ||
                    "Today's study total could not be loaded."
                );
            }
    
            savedStudySecondsToday =
                responseData.total_seconds;
    
            loadedDayStartMs =
                dayBoundaries.startMs;
    
            loadedDayEndMs =
                dayBoundaries.endMs;
    
            updateDailyStudyCounter();
    
        } catch (error) {
            console.error(error);
    
            dailyStudyTotal.textContent =
                "Unavailable";
    
        } finally {
            dailyTotalRequestRunning = false;
        }
    }
    
    
    function updateDailyStudyCounter() {
        const currentDayBoundaries =
            getLocalDayBoundaries();
    
        /*
         * Reload the saved total if the date changed
         * while a long session was running.
         */
        if (
            loadedDayStartMs !==
            currentDayBoundaries.startMs
        ) {
            loadSavedDailyStudyTotal();
            return;
        }
    
        const currentTimeMs = Math.min(
            Date.now(),
            endTimeMs,
            loadedDayEndMs
        );
    
        const activeStudyStartMs = Math.max(
            startTimeMs,
            loadedDayStartMs
        );
    
        const activeSecondsToday = Math.max(
            0,
            (
                currentTimeMs -
                activeStudyStartMs
            ) / 1000
        );
    
        const totalSecondsToday =
            savedStudySecondsToday +
            activeSecondsToday;
    
        dailyStudyTotal.textContent =
            formatDailyStudyTime(
                totalSecondsToday
            );
    }


    function updateDisplay() {
        /*
         * One clock reading is used for every
         * timer calculation during this update.
         */
        const currentTimeMs = Date.now();
    
        const remainingMilliseconds = Math.max(
            0,
            endTimeMs - currentTimeMs
        );
    
        const elapsedMilliseconds = Math.min(
            totalDurationMilliseconds,
            Math.max(
                0,
                currentTimeMs - startTimeMs
            )
        );
    
        const remainingSeconds = Math.ceil(
            remainingMilliseconds / 1000
        );
    
        const elapsedSeconds =
            elapsedMilliseconds / 1000;
    
        const progress = Math.min(
            1,
            elapsedMilliseconds /
            totalDurationMilliseconds
        );
    
        const progressPercentage =
            progress * 100;
    
        countdownDisplay.textContent =
            formatTime(
                remainingSeconds,
                useHours
            );
    
        elapsedTimeLabel.textContent =
            `Studied: ${
                formatTime(
                    elapsedSeconds,
                    useHours
                )
            }`;
    
        progressFill.style.width =
            `${progressPercentage}%`;
    
        progressTrack.setAttribute(
            "aria-valuenow",
            String(
                Math.round(progressPercentage)
            )
        );
    
        /*
         * Pass the exact same clock reading used
         * by the main countdown.
         */
        updateTree(currentTimeMs);
    
        updateDailyStudyCounter();
    
        if (remainingMilliseconds <= 0) {
            completeStudySession();
        }
    }


    async function sendFinishRequest(status) {
        const response = await fetch(
            `/api/study-sessions/${studySessionId}/finish`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    status
                }),
                keepalive: true
            }
        );

        const responseData =
            await response.json();

        if (!response.ok) {
            throw new Error(
                responseData.error ||
                "The study session could not be saved."
            );
        }

        return responseData;
    }


    async function completeStudySession() {
        if (sessionHasEnded) {
            return;
        }

        sessionHasEnded = true;

        window.clearInterval(timerInterval);

        countdownDisplay.textContent =
            formatTime(0, useHours);

        progressFill.style.width = "100%";

        progressTrack.setAttribute(
            "aria-valuenow",
            "100"
        );

        activeStudyTree.src =
            treeImageUrls[6];

        nextGrowthMessage.textContent =
            "Your tree has fully grown!";

        try {
            await sendFinishRequest("completed");

            sessionStorage.removeItem(
                "activeStudySession"
            );

            completionDialog.showModal();

            beginHomeRedirect();

        } catch (error) {
            sessionHasEnded = false;

            window.alert(error.message);
        }
    }


    function beginHomeRedirect() {
        let secondsRemaining = 30;

        redirectCountdown.textContent =
            String(secondsRemaining);

        const redirectInterval =
            window.setInterval(() => {
                secondsRemaining -= 1;

                redirectCountdown.textContent =
                    String(secondsRemaining);

                if (secondsRemaining <= 0) {
                    window.clearInterval(
                        redirectInterval
                    );

                    window.location.replace(
                        app.dataset.homeUrl
                    );
                }
            }, 1000);
    }


    async function endSessionEarly() {
        confirmEndSessionButton.disabled = true;
        confirmEndSessionButton.textContent =
            "Saving...";

        try {
            sessionHasEnded = true;

            window.clearInterval(timerInterval);

            await sendFinishRequest(
                "ended_early"
            );

            sessionStorage.removeItem(
                "activeStudySession"
            );

            window.location.replace(
                app.dataset.homeUrl
            );

        } catch (error) {
            sessionHasEnded = false;

            confirmEndSessionButton.disabled =
                false;

            confirmEndSessionButton.textContent =
                "End Session";

            window.alert(error.message);
        }
    }


    async function cancelForNavigation(destination) {
        if (sessionHasEnded) {
            window.location.href = destination;
            return;
        }

        try {
            sessionHasEnded = true;

            window.clearInterval(timerInterval);

            await sendFinishRequest(
                "cancelled_navigation"
            );

            sessionStorage.removeItem(
                "activeStudySession"
            );

            window.location.href = destination;

        } catch (error) {
            sessionHasEnded = false;

            window.alert(
                `${error.message} Navigation was cancelled so your study time is not lost.`
            );

            timerInterval = window.setInterval(
                updateDisplay,
                250
            );
        }
    }


    endSessionButton.addEventListener(
        "click",
        () => {
            endSessionDialog.showModal();
        }
    );


    continueSessionButton.addEventListener(
        "click",
        () => {
            endSessionDialog.close();
        }
    );


    confirmEndSessionButton.addEventListener(
        "click",
        endSessionEarly
    );


    returnHomeButton.addEventListener(
        "click",
        () => {
            window.location.replace(
                app.dataset.homeUrl
            );
        }
    );


    document
        .querySelectorAll(
            ".session-navigation-link"
        )
        .forEach((navigationLink) => {
            navigationLink.addEventListener(
                "click",
                (event) => {
                    event.preventDefault();

                    cancelForNavigation(
                        navigationLink.href
                    );
                }
            );
        });

    loadSavedDailyStudyTotal();

    updateDisplay();
    
    timerInterval = window.setInterval(
        updateDisplay,
        250
    );
    updateDisplay();

    timerInterval = window.setInterval(
        updateDisplay,
        250
    );
});