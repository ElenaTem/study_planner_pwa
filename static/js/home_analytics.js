"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const MINIMUM_GOAL_MINUTES = 15;
    const MAXIMUM_GOAL_MINUTES = 12 * 60;

    const dashboard =
        document.getElementById("homeDashboard");

    const studyGoalCard =
        document.getElementById("studyGoalCard");

    const goalHoursDisplay =
        document.getElementById("goalHoursDisplay");

    const goalMinutesDisplay =
        document.getElementById(
            "goalMinutesDisplay"
        );

    const goalChangeButtons =
        document.querySelectorAll(
            ".goal-change-button"
        );

    const goalSaveMessage =
        document.getElementById(
            "goalSaveMessage"
        );

    const dailyGoalPrompt =
        document.getElementById(
            "dailyGoalPrompt"
        );

    const goToGoalPickerButton =
        document.getElementById(
            "goToGoalPickerButton"
        );

    const todayStudySummary =
        document.getElementById(
            "todayStudySummary"
        );

    const todayGoalPercentage =
        document.getElementById(
            "todayGoalPercentage"
        );

    let currentGoalMinutes = 120;
    let goalExists = false;
    let todayStudiedSeconds = 0;

    let goalChart = null;
    let monthlyChart = null;

    let goalSaveTimeout = null;
    let goalSaveInProgress = false;


    function getLocalDateText(date = new Date()) {
        const year = date.getFullYear();

        const month = String(
            date.getMonth() + 1
        ).padStart(2, "0");

        const day = String(
            date.getDate()
        ).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }


    function formatSecondsAsHoursMinutes(
        totalSeconds
    ) {
        const totalMinutes = Math.floor(
            Math.max(0, totalSeconds) / 60
        );

        const hours = Math.floor(
            totalMinutes / 60
        );

        const minutes = totalMinutes % 60;

        return `${hours} hrs ${minutes} mins`;
    }


    function updateGoalPicker() {
        const hours = Math.floor(
            currentGoalMinutes / 60
        );

        const minutes =
            currentGoalMinutes % 60;

        goalHoursDisplay.textContent =
            String(hours).padStart(2, "0");

        goalMinutesDisplay.textContent =
            String(minutes).padStart(2, "0");

        goalChangeButtons.forEach((button) => {
            const change = Number(
                button.dataset.change
            );

            button.disabled = (
                change < 0
                && currentGoalMinutes
                    <= MINIMUM_GOAL_MINUTES
            ) || (
                change > 0
                && currentGoalMinutes
                    >= MAXIMUM_GOAL_MINUTES
            );
        });
    }


    function changeGoal(changeInMinutes) {
        currentGoalMinutes += changeInMinutes;
    
        currentGoalMinutes = Math.max(
            MINIMUM_GOAL_MINUTES,
            Math.min(
                MAXIMUM_GOAL_MINUTES,
                currentGoalMinutes
            )
        );
    
        updateGoalPicker();

        if (goalExists) {
            updateGoalChart();
        }
    
        scheduleGoalSave();
    }


    function createGoalChart() {
        const chartCanvas =
            document.getElementById(
                "todayGoalChart"
            );

        goalChart = new Chart(
            chartCanvas,
            {
                type: "doughnut",

                data: {
                    labels: [
                        "Completed",
                        "Remaining"
                    ],

                    datasets: [{
                        data: [0, 1],

                        backgroundColor: [
                            "#69A4E8",
                            "#DCEAF8"
                        ],

                        borderWidth: 0
                    }]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    rotation: -90,
                    circumference: 180,
                    cutout: "72%",

                    plugins: {
                        legend: {
                            display: false
                        },

                        tooltip: {
                            enabled: false
                        }
                    },

                    animation: {
                        duration: 400
                    }
                }
            }
        );
    }


    function updateGoalChart() {
        if (!goalChart) {
            return;
        }

        if (!goalExists) {
            goalChart.data.datasets[0].data =
                [0, 1];

            todayStudySummary.textContent =
                "Set a goal to begin";

            todayGoalPercentage.textContent = "";

            goalChart.update();

            return;
        }

        const goalSeconds =
            currentGoalMinutes * 60;

        const completedGaugeSeconds = Math.min(
            todayStudiedSeconds,
            goalSeconds
        );

        const remainingSeconds = Math.max(
            0,
            goalSeconds - completedGaugeSeconds
        );

        goalChart.data.datasets[0].data = [
            completedGaugeSeconds,
            remainingSeconds
        ];

        const percentage = Math.round(
            (
                todayStudiedSeconds
                / goalSeconds
            ) * 100
        );

        todayStudySummary.textContent =
            `${
                formatSecondsAsHoursMinutes(
                    todayStudiedSeconds
                )
            } of ${
                formatSecondsAsHoursMinutes(
                    goalSeconds
                )
            }`;

        if (percentage >= 100) {
            const extraSeconds =
                todayStudiedSeconds - goalSeconds;

            todayGoalPercentage.textContent =
                `Goal achieved — ${
                    formatSecondsAsHoursMinutes(
                        extraSeconds
                    )
                } above goal`;

        } else {
            todayGoalPercentage.textContent =
                `${percentage}% of today’s goal`;
        }

        goalChart.update();
    }


    async function loadDailyGoal() {
        const localDate = getLocalDateText();

        const requestUrl = new URL(
            dashboard.dataset.goalUrl,
            window.location.origin
        );

        requestUrl.searchParams.set(
            "date",
            localDate
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
                    "The daily goal could not be loaded."
                );
            }

            goalExists = responseData.exists;

            if (goalExists) {
                currentGoalMinutes =
                    responseData.goal_minutes;

                updateGoalPicker();
                updateGoalChart();

            } else {
                updateGoalChart();

                if (!dailyGoalPrompt.open) {
                    dailyGoalPrompt.showModal();
                }
            }

        } catch (error) {
            goalSaveMessage.textContent =
                error.message;
        }
    }

    function scheduleGoalSave() {
        /*
         * Cancel the previous scheduled save when the
         * user presses another arrow quickly.
         */
        window.clearTimeout(goalSaveTimeout);
    
        goalSaveMessage.textContent = "Saving...";
    
        /*
         * Wait 600 milliseconds after the user's most
         * recent click before saving.
         */
        goalSaveTimeout = window.setTimeout(
            saveDailyGoal,
            600
        );
    }


    async function saveDailyGoal() {
        if (goalSaveInProgress) {
            return;
        }
    
        goalSaveInProgress = true;
        goalSaveMessage.textContent = "Saving...";
    
        try {
            const response = await fetch(
                dashboard.dataset.goalUrl,
                {
                    method: "POST",
    
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
    
                    body: JSON.stringify({
                        date: getLocalDateText(),
                        goal_minutes:
                            currentGoalMinutes
                    })
                }
            );
    
            const responseData =
                await response.json();
    
            if (!response.ok) {
                throw new Error(
                    responseData.error ||
                    "The goal could not be saved."
                );
            }
    
            goalExists = true;
    
            currentGoalMinutes =
                responseData.goal_minutes;
    
            updateGoalPicker();
            updateGoalChart();
    
            goalSaveMessage.textContent =
                "Today’s goal has been saved.";
    
            if (dailyGoalPrompt.open) {
                dailyGoalPrompt.close();
            }
    
        } catch (error) {
            goalSaveMessage.textContent =
                error.message;
    
            console.error(error);
    
        } finally {
            goalSaveInProgress = false;
        }
    }


    function getMonthInformation() {
        const now = new Date();

        const year = now.getFullYear();
        const month = now.getMonth();

        const daysInMonth = new Date(
            year,
            month + 1,
            0
        ).getDate();

        const labels = [];
        const boundaries = [];

        for (
            let day = 1;
            day <= daysInMonth;
            day += 1
        ) {
            labels.push(String(day));

            boundaries.push(
                new Date(
                    year,
                    month,
                    day
                ).getTime()
            );
        }

        boundaries.push(
            new Date(
                year,
                month + 1,
                1
            ).getTime()
        );

        return {
            labels,
            boundaries,
            currentDay: now.getDate()
        };
    }


    function createMonthlyChart(
        labels,
        chartHours,
        originalDailySeconds
    ) {
        const monthlyCanvas =
            document.getElementById(
                "monthlyStudyChart"
            );

        monthlyChart = new Chart(
            monthlyCanvas,
            {
                type: "bar",

                data: {
                    labels,

                    datasets: [{
                        label: "Hours Studied",
                        data: chartHours,
                        backgroundColor: "#A8B8F2",
                        borderRadius: 4
                    }]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    plugins: {
                        legend: {
                            display: false
                        },

                        tooltip: {
                            callbacks: {
                                label(context) {
                                    const seconds =
                                        originalDailySeconds[
                                            context.dataIndex
                                        ];

                                    return (
                                        "Studied: "
                                        + formatSecondsAsHoursMinutes(
                                            seconds
                                        )
                                    );
                                }
                            }
                        }
                    },

                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: "Day"
                            },

                            grid: {
                                display: false
                            }
                        },

                        y: {
                            beginAtZero: true,

                            title: {
                                display: true,
                                text: "Hours"
                            }
                        }
                    }
                }
            }
        );
    }


    async function loadMonthlyAnalytics() {
        const monthInformation =
            getMonthInformation();

        try {
            const response = await fetch(
                dashboard.dataset.monthUrl,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        day_boundaries_ms:
                            monthInformation.boundaries
                    })
                }
            );

            const responseData =
                await response.json();

            if (!response.ok) {
                throw new Error(
                    responseData.error ||
                    "Monthly analytics could not be loaded."
                );
            }

            const dailySeconds =
                responseData.daily_seconds;

            todayStudiedSeconds =
                dailySeconds[
                    monthInformation.currentDay - 1
                ] || 0;

            const chartHours = dailySeconds.map(
                (seconds, index) => {
                    const dayNumber = index + 1;

                    if (
                        dayNumber
                        > monthInformation.currentDay
                    ) {
                        return null;
                    }

                    return Number(
                        (
                            seconds / 3600
                        ).toFixed(2)
                    );
                }
            );

            createMonthlyChart(
                monthInformation.labels,
                chartHours,
                dailySeconds
            );

            updateGoalChart();

        } catch (error) {
            console.error(
                "Monthly analytics error:",
                error
            );
        
            todayStudySummary.textContent =
                "Study time could not be loaded";
        
            todayGoalPercentage.textContent =
                error.message;
        }
    }


    goalChangeButtons.forEach((button) => {
        button.addEventListener(
            "click",
            () => {
                changeGoal(
                    Number(
                        button.dataset.change
                    )
                );
            }
        );
    });

    goToGoalPickerButton.addEventListener(
        "click",
        async () => {
            dailyGoalPrompt.close();
    
            studyGoalCard.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
    
            /*
             * Save the currently displayed value, even
             * when the user has not pressed an arrow.
             */
            await saveDailyGoal();
        }
    );


    


    createGoalChart();
    updateGoalPicker();

    loadDailyGoal();
    loadMonthlyAnalytics();
});