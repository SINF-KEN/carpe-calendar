const colors = {};

const accessibilityList = ["blind_friendly", "deaf_friendly", "pmr_friendly", "neurodiversity_friendly"];

const randomColors = [
    "#E8ADB6",
    "#CBADCC",
    "#A0ACC6",
    "#F75A3B",
    "#3F4EB5",
    "#8AC7AD",
    "#8AC7AD",
    "#9F63C4",
];

// UCLouvain week system, edited in the admin (AcademicPeriod)
const academicPeriods = JSON.parse(document.getElementById("academic-periods").textContent).map((period) => ({
    ...period,
    start: parseLocalDate(period.start),
    end: parseLocalDate(period.end),
}));

function parseLocalDate(isoDate) {
    const [year, month, day] = isoDate.split("-").map(Number);
    return new Date(year, month - 1, day);
}

const getWeekNumber = (d) => {
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const period = academicPeriods.find((p) => p.start <= day && day <= p.end);
    if (!period) {
        return "-";
    }
    if (!period.numbered) {
        return period.name;
    }
    // Round to absorb daylight saving time shifts
    const weeks = Math.floor(Math.round((day - period.start) / 86400000) / 7);
    return period.name + (period.first_week_number + weeks).toString();
}

function initPlaceColors() {
    for (place of places) {
        colors[place] = randomColors[Math.floor(Math.random() * randomColors.length)];
        const dot = document.getElementById("dot-" + place);
        dot.style.backgroundColor = colors[place];
    }
}

function createCalendar() {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        themeSystem: 'bootstrap5',
        initialView: screen.width > 800 ? 'dayGridWeek' : 'dayGridDay',
        customButtons: {
            addEvent: {
                text: 'Ajouter un événement',
                click: function() {
                    location.href = "/add-event";
                }
            },
            today: {
                text: 'Aujourd\'hui',
                click: function() {
                    calendar.today();
                }
            }
        },
        locale: 'fr',
        firstDay: 1,
        headerToolbar: {
            left: 'addEvent',
            center: 'title',
            right: 'dayGridDay,dayGridWeek,dayGridMonth,listMonth prev,today,next',
        },
        buttonText: {
            month: 'Mois',
            listMonth: "Liste",
            week: 'Semaine',
            day: 'Jour',
            today: 'Aujourd\'hui',

        },
        navLinks: true,
        nextDayThreshold: '06:00:00',
        weekNumbers: true,
        weekNumberContent: function(obj) {
            return getWeekNumber(obj.date);
        },
        navLinkDayClick: function(date) {
            calendar.changeView('dayGridDay', date.toISOString());
        },
        height: 'auto',
        eventBorderColor: 'black',
        titleFormat: { day: 'numeric', year: 'numeric', month: 'long' },
        eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: false },
        eventDisplay: 'block',
        eventBorderColor: 'gray',
        eventSources : [
            {
                url: "/events",
            }
        ],
        eventClick: function(info) {
            location.href = "/event/" + info.event.id;
        },
        eventDidMount: function(arg) {
            const element = document.getElementById("checkbox-" + arg.event.extendedProps.category.name);
            const placeElement = document.getElementById("checkbox-place-" + arg.event.extendedProps.saved_location.name);
            let display = false;
            let atLeastOneChecked = false;
            for (accessibility of accessibilityList) {
                const accessibilityElement = document.getElementById("checkbox-" + accessibility);
                atLeastOneChecked |= accessibilityElement.checked;
                if (arg.event.extendedProps[accessibility] && accessibilityElement.checked) {
                    display = true;
                }
            }
            display |= !atLeastOneChecked;
            display &= (element.checked && placeElement.checked);
            if (!display) {
                arg.el.style.display = "none";
            }

            const dotEl = arg.el.getElementsByClassName('fc-list-event-dot')[0];
            if (dotEl) {
                dotEl.style.borderColor = colors[arg.event.extendedProps.saved_location.name];
                // dotEl.style.backgroundColor = colors[arg.event.extendedProps.saved_location.name];
            }
            else {
                arg.el.style.backgroundColor = colors[arg.event.extendedProps.saved_location.name];
            }

            if (screen.width > 900 && arg.view.type !== "listMonth") {
                const span = document.createElement("span");
                span.textContent = "📍" + arg.event.extendedProps.location;
                arg.el.getElementsByClassName("fc-event-main-frame")[0].append(span);
            }
            arg.el.style.cursor = "pointer";

            if (window.matchMedia("(hover: hover)").matches) {
                const tooltip = document.createElement("div");
                for (const line of [arg.event.title, "📍" + arg.event.extendedProps.location, arg.event.extendedProps.organizer]) {
                    const lineEl = document.createElement("div");
                    lineEl.textContent = line;
                    tooltip.append(lineEl);
                }
                new mdb.Tooltip(arg.el, { title: tooltip, html: true, placement: "top" });
            }
        },
        eventWillUnmount: function(arg) {
            mdb.Tooltip.getInstance(arg.el)?.dispose();
        },
    });
    calendar.render();
    for (category of categories) {
        document.getElementById("checkbox-" + category).addEventListener("change", function() {
            calendar.refetchEvents();
        });
    }
    for (place of places) {
        document.getElementById("checkbox-place-" + place).addEventListener("change", function() {
            calendar.refetchEvents();
        });
    }

    for (accessibility of accessibilityList) {
        document.getElementById("checkbox-" + accessibility).addEventListener("change", function() {
            calendar.refetchEvents();
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initPlaceColors();
    createCalendar();
});