var sessionName = "";

function normalizeSessionName(name) {
    return name.trim().toLowerCase().replace(/\s+/g, " ");
}

function sessionUrl(path) {
    return path + "?session=" + encodeURIComponent(sessionName);
}

function sessionStorageKey(key) {
    return "cyberquest:" + sessionName + ":" + key;
}

function initializeSession(startSession) {
    const gate = document.getElementById("session_gate");
    const gameScreen = document.getElementById("game_screen");
    const form = document.getElementById("session_form");
    const input = document.getElementById("session_name_input");
    const currentSession = document.getElementById("current_session");
    const changeButton = document.getElementById("change_session_btn");

    function joinSession(rawName) {
        const normalizedName = normalizeSessionName(rawName);
        if (!normalizedName) {
            input.setCustomValidity("Please enter a session name.");
            input.reportValidity();
            return;
        }

        sessionName = normalizedName;
        localStorage.setItem("cyberquestSession", sessionName);
        currentSession.textContent = sessionName;
        gate.hidden = true;
        gameScreen.hidden = false;
        startSession();
    }

    form.addEventListener("submit", function(event) {
        event.preventDefault();
        input.setCustomValidity("");
        joinSession(input.value);
    });

    changeButton.addEventListener("click", function() {
        localStorage.removeItem("cyberquestSession");
        window.location.reload();
    });

    const storedSession = localStorage.getItem("cyberquestSession") || "";
    if (storedSession) {
        joinSession(storedSession);
    } else {
        gate.hidden = false;
        gameScreen.hidden = true;
        input.focus();
    }
}
