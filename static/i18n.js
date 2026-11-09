(function() {
    "use strict";

    const STORAGE_KEY = "cyberquestLanguage";
    const supportedLanguages = new Set(["en", "de-AT"]);
    const phrases = [
        ["CyberQuest Teacher", "CyberQuest Lehrperson"],
        ["CyberQuest Participant", "CyberQuest Teilnehmer:in"],
        ["CyberQuest Presenter", "CyberQuest Präsentation"],
        ["CyberQuest report", "CyberQuest Spielbericht"],
        ["Teacher", "Lehrperson"],
        ["Students", "Teilnehmende"],
        ["Presentation", "Präsentation"],
        ["Prepare, run, and review a game.", "Ein Spiel vorbereiten, durchführen und auswerten."],
        ["Join a live game.", "Einem laufenden Spiel beitreten."],
        ["Teacher area", "Lehrpersonenbereich"],
        ["Join game", "Spiel beitreten"],
        ["Open screen", "Präsentation öffnen"],
        ["Session:", "Sitzung:"],
        ["Device:", "Gerät:"],
        ["not connected", "nicht verbunden"],
        ["not assigned", "nicht zugewiesen"],
        ["Log out", "Abmelden"],
        ["Change", "Ändern"],
        ["Teacher session", "Lehrpersonensitzung"],
        ["Create a protected game or open one you prepared earlier.", "Ein geschütztes Spiel erstellen oder ein vorbereitetes Spiel öffnen."],
        ["Session ID", "Sitzungs-ID"],
        ["Private teacher PIN", "Privater Lehrpersonen-PIN"],
        ["Open", "Öffnen"],
        ["Create new", "Neu erstellen"],
        ["Live session", "Laufende Sitzung"],
        ["Join session", "Sitzung beitreten"],
        ["Students join with session ID", "Teilnehmende treten mit dieser Sitzungs-ID bei:"],
        ["Status", "Status"],
        ["Session status", "Sitzungsstatus"],
        ["Prepared", "Vorbereitet"],
        ["Live", "Läuft"],
        ["Finished", "Beendet"],
        ["AI token usage", "KI-Tokenverbrauch"],
        ["Last AI answer:", "Letzte KI-Antwort:"],
        ["Total this game:", "Gesamt in diesem Spiel:"],
        ["Connected devices", "Verbundene Geräte"],
        ["Current question", "Aktuelle Frage"],
        ["Answers", "Antworten"],
        ["Controls", "Steuerung"],
        ["Question", "Frage"],
        ["Show selected question on client screens", "Ausgewählte Frage auf den Geräten anzeigen"],
        ["Live game", "Live-Spiel"],
        ["Live game status", "Status des Live-Spiels"],
        ["Start game", "Spiel starten"],
        ["Stop game", "Spiel stoppen"],
        ["Participant interaction", "Interaktion der Teilnehmenden"],
        ["Suggest questions", "Fragen vorschlagen"],
        ["Answer questions", "Fragen beantworten"],
        ["AI mode", "KI-Modus"],
        ["Conversation", "Konversation"],
        ["Independent", "Unabhängig"],
        ["AI answer", "KI-Antwort"],
        ["Generate AI answer", "KI-Antwort erzeugen"],
        ["Generate report", "Bericht erstellen"],
        ["opens in a new window", "wird in einem neuen Fenster geöffnet"],
        ["OpenAI API key", "OpenAI-API-Schlüssel"],
        ["Enter a personal OpenAI API key", "Persönlichen OpenAI-API-Schlüssel eingeben"],
        ["Test", "Testen"],
        ["Save", "Speichern"],
        ["Remove", "Entfernen"],
        ["The key is encrypted for this game session and is never displayed again. Testing and saving each make a small billable OpenAI request.", "Der Schlüssel wird für diese Spielsitzung verschlüsselt und nie wieder angezeigt. Testen und Speichern führen jeweils eine kleine kostenpflichtige OpenAI-Anfrage aus."],
        ["Full state", "Vollständiger Zustand"],
        ["Update full state", "Vollständigen Zustand aktualisieren"],
        ["Using this game session’s personal OpenAI API key.", "Der persönliche OpenAI-API-Schlüssel dieser Spielsitzung wird verwendet."],
        ["Using the server’s OpenAI API key.", "Der OpenAI-API-Schlüssel des Servers wird verwendet."],
        ["No OpenAI API key is available.", "Es ist kein OpenAI-API-Schlüssel verfügbar."],
        ["Enter an OpenAI API key first.", "Bitte zuerst einen OpenAI-API-Schlüssel eingeben."],
        ["Checking the API key…", "Der API-Schlüssel wird überprüft …"],
        ["The API key works and was not stored.", "Der API-Schlüssel funktioniert und wurde nicht gespeichert."],
        ["The personal API key was encrypted and saved.", "Der persönliche API-Schlüssel wurde verschlüsselt gespeichert."],
        ["The personal API key was removed.", "Der persönliche API-Schlüssel wurde entfernt."],
        ["Remove the personal OpenAI API key from this game session?", "Den persönlichen OpenAI-API-Schlüssel aus dieser Spielsitzung entfernen?"],
        ["Start a new live run? Previous run data will be cleared.", "Ein neues Live-Spiel starten? Die Daten des vorherigen Durchgangs werden gelöscht."],
        ["Do you really want to stop the live game? Students will no longer be able to participate.", "Soll das Live-Spiel wirklich beendet werden? Die Teilnehmenden können danach nicht mehr mitmachen."],
        ["Invalid JSON", "Ungültiges JSON"],
        ["Request failed", "Anfrage fehlgeschlagen"],
        ["Enter your PIN to open this session.", "Bitte den PIN eingeben, um diese Sitzung zu öffnen."],
        ["Please enter a session name.", "Bitte einen Sitzungsnamen eingeben."],
        ["Unable to join this session.", "Der Beitritt zu dieser Sitzung ist nicht möglich."],
        ["Answer is required", "Eine Antwort ist erforderlich"],
        ["Enter an OpenAI API key", "Bitte einen OpenAI-API-Schlüssel eingeben"],
        ["Invalid AI mode", "Ungültiger KI-Modus"],
        ["Invalid question index", "Ungültiger Fragenindex"],
        ["Only a live game can be ended", "Nur ein laufendes Spiel kann beendet werden"],
        ["Session ID is required", "Eine Sitzungs-ID ist erforderlich"],
        ["Session not found", "Sitzung nicht gefunden"],
        ["Start the game before requesting AI answers", "Bitte das Spiel starten, bevor eine KI-Antwort angefordert wird"],
        ["Teacher login required", "Anmeldung als Lehrperson erforderlich"],
        ["That session ID already exists", "Diese Sitzungs-ID existiert bereits"],
        ["The OpenAI API key is too long", "Der OpenAI-API-Schlüssel ist zu lang"],
        ["The teacher PIN must contain at least 6 characters", "Der Lehrpersonen-PIN muss mindestens 6 Zeichen lang sein"],
        ["This session is not live", "Diese Sitzung läuft derzeit nicht"],
        ["Unknown session ID or incorrect PIN", "Unbekannte Sitzungs-ID oder falscher PIN"],
        ["Use 3–40 letters, numbers, hyphens, or underscores", "Bitte 3–40 Buchstaben, Zahlen, Bindestriche oder Unterstriche verwenden"],
        ["Personal API key storage is unavailable because API_KEY_ENCRYPTION_KEY is not configured", "Persönliche API-Schlüssel können nicht gespeichert werden, weil API_KEY_ENCRYPTION_KEY am Server nicht konfiguriert ist"],
        ["API_KEY_ENCRYPTION_KEY is invalid", "API_KEY_ENCRYPTION_KEY ist ungültig"],
        ["The stored personal API key cannot be decrypted with the configured encryption key", "Der gespeicherte persönliche API-Schlüssel kann mit dem konfigurierten Verschlüsselungsschlüssel nicht entschlüsselt werden"],
        ["No OpenAI API key is configured", "Es ist kein OpenAI-API-Schlüssel konfiguriert"],
        ["No devices connected.", "Keine Geräte verbunden."],
        ["No question selected.", "Keine Frage ausgewählt."],
        ["No answers yet.", "Noch keine Antworten."],
        ["Join a session", "Einer Sitzung beitreten"],
        ["Enter the shared session name before opening this screen.", "Bitte den gemeinsamen Sitzungsnamen eingeben, bevor diese Ansicht geöffnet wird."],
        ["Session name", "Sitzungsname"],
        ["Join session", "Sitzung beitreten"],
        ["Known device for session", "Bekanntes Gerät für Sitzung"],
        ["Loading...", "Wird geladen …"],
        ["Actions", "Aktionen"],
        ["Game over", "Spiel beendet"],
        ["The teacher has ended this game session.", "Die Lehrperson hat diese Spielsitzung beendet."],
        ["Session ended", "Sitzung beendet"],
        ["Thank you for participating.", "Danke fürs Mitmachen."],
        ["Welcome", "Willkommen"],
        ["Welcome! Ready to get started?", "Willkommen! Bereit loszulegen?"],
        ["Start", "Start"],
        ["Let's go!", "Los geht’s!"],
        ["Enter your question:", "Gebt eure Frage ein:"],
        ["Please suggest a question. The groups and an AI will answer it. Try to phrase it so that the answer helps you distinguish the AI from the other groups.", "Bitte schlagt eine Frage vor. Die Frage wird von den Gruppen und einer KI beantwortet. Formuliert sie so, dass ihr anhand der Antwort möglichst gut zwischen KI und anderen Gruppen unterscheiden könnt."],
        ["Your question", "Eure Frage"],
        ["Your question here...", "Eure Frage hier …"],
        ["Submit question", "Frage abschicken"],
        ["Edit your question", "Ändert eure Frage"],
        ["You can revise your question and check it for typing mistakes.", "Ihr könnt eure Frage noch ändern und etwa auf Tippfehler überprüfen."],
        ["Update", "Aktualisieren"],
        ["Here is the question:", "Hier ist die Frage:"],
        ["Your previous answers", "Eure bisherigen Antworten"],
        ["No answers yet.", "Noch keine Antworten."],
        ["Your answer?", "Eure Antwort?"],
        ["Your answer...", "Eure Antwort …"],
        ["Submit answer", "Antwort abschicken"],
        ["Your answer is sent to the teacher and appears above/left under “Your previous answers”.", "Eure Antwort wird an die Lehrperson gesendet und erscheint oben/links unter „Eure bisherigen Antworten“."],
        ["Task", "Aufgabe"],
        ["No actions available yet.", "Derzeit sind keine Aktionen verfügbar."],
        ["Collected questions", "Gesammelte Fragen"],
        ["Enter a question that makes it easy to distinguish the AI from the other groups!", "Gebt eine Frage ein, mit der ihr die KI möglichst gut von den anderen Gruppen unterscheiden könnt!"],
        ["Current question", "Aktuelle Frage"],
        ["Now enter your answer to this question!", "Gebt jetzt eure Antwort auf diese Frage ein!"],
        ["Please wait, retrieving data...", "Bitte warten, die Daten werden geladen …"],
        ["This session does not exist or is not live yet.", "Diese Sitzung existiert nicht oder läuft noch nicht."],
        ["Game report:", "Spielbericht:"],
        ["Print / Save as PDF", "Drucken / Als PDF speichern"],
        ["Overview", "Überblick"],
        ["Started:", "Begonnen:"],
        ["Ended:", "Beendet:"],
        ["Duration:", "Dauer:"],
        ["Participating devices:", "Teilnehmende Geräte:"],
        ["AI answers", "KI-Antworten"],
        ["All answers", "Alle Antworten"],
        ["Duplicates / multiples", "Doppelte / mehrfache Antworten"],
        ["None", "Keine"],
        ["min", "Min."],
        ["sec", "Sek."],
        ["participant", "Teilnehmer:in"],
        ["ai", "KI"]
    ];

    const indexes = { en: new Map(), "de-AT": new Map() };
    phrases.forEach(([english, german]) => {
        indexes.en.set(english, english);
        indexes.en.set(german, english);
        indexes["de-AT"].set(english, german);
        indexes["de-AT"].set(german, german);
    });

    function selectedLanguage() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (supportedLanguages.has(stored)) return stored;
        return navigator.language.toLowerCase().startsWith("de") ? "de-AT" : "en";
    }

    function translateValue(value, language = selectedLanguage()) {
        const source = String(value);
        const normalized = source.trim().replace(/\s+/g, " ");
        let translated = indexes[language].get(normalized);
        if (!translated) {
            const identical = normalized.match(/^(\d+) (?:identical answers|gleiche Antworten)$/);
            if (identical) {
                translated = language === "de-AT" ?
                    `${identical[1]} gleiche Antworten` : `${identical[1]} identical answers`;
            }
            const openAIError = normalized.match(/^(?:OpenAI rejected the API key|OpenAI hat den API-Schlüssel abgelehnt): (.+)$/);
            if (openAIError) {
                translated = language === "de-AT" ?
                    `OpenAI hat den API-Schlüssel abgelehnt: ${openAIError[1]}` :
                    `OpenAI rejected the API key: ${openAIError[1]}`;
            }
            const removeAnswer = normalized.match(/^(?:Remove answer|Antwort entfernen): (.+)$/);
            if (removeAnswer) {
                translated = language === "de-AT" ?
                    `Antwort entfernen: ${removeAnswer[1]}` : `Remove answer: ${removeAnswer[1]}`;
            }
            const duration = normalized.match(/^(\d+) (?:min|Min\.) (\d+) (?:sec|Sek\.)$/);
            if (duration) {
                translated = language === "de-AT" ?
                    `${duration[1]} Min. ${duration[2]} Sek.` : `${duration[1]} min ${duration[2]} sec`;
            }
        }
        if (!translated || translated === normalized) return value;
        const leadingWhitespace = source.match(/^\s*/)[0];
        const trailingWhitespace = source.match(/\s*$/)[0];
        return leadingWhitespace + translated + trailingWhitespace;
    }

    function translateElement(element) {
        if (element.closest("[data-i18n-ignore]")) return;
        element.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) {
                node.nodeValue = translateValue(node.nodeValue);
            }
        });
        ["placeholder", "title", "aria-label"].forEach(attribute => {
            if (element.hasAttribute(attribute)) {
                element.setAttribute(attribute, translateValue(element.getAttribute(attribute)));
            }
        });
    }

    function translatePage(root = document) {
        document.documentElement.lang = selectedLanguage();
        document.title = translateValue(document.title);
        if (root.nodeType === Node.ELEMENT_NODE) translateElement(root);
        root.querySelectorAll("*").forEach(translateElement);
    }

    function addSwitcher() {
        if (document.getElementById("language_switcher")) return;
        const select = document.createElement("select");
        select.id = "language_switcher";
        select.className = "language-switcher no-print";
        select.setAttribute("aria-label", "Language / Sprache");
        select.setAttribute("data-i18n-ignore", "");
        select.innerHTML = '<option value="en">English</option><option value="de-AT">Deutsch</option>';
        select.value = selectedLanguage();
        select.addEventListener("change", () => {
            localStorage.setItem(STORAGE_KEY, select.value);
            translatePage();
            window.dispatchEvent(new CustomEvent("languagechange", { detail: select.value }));
        });
        const target = document.querySelector(".session-status") || document.querySelector(".game-header");
        target.appendChild(select);
    }

    const nativeAlert = window.alert.bind(window);
    const nativeConfirm = window.confirm.bind(window);
    window.alert = message => nativeAlert(translateValue(message));
    window.confirm = message => nativeConfirm(translateValue(message));
    window.t = translateValue;
    window.getCyberQuestLanguage = selectedLanguage;

    document.addEventListener("DOMContentLoaded", () => {
        addSwitcher();
        translatePage();
        new MutationObserver(mutations => {
            mutations.forEach(mutation => mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE && node.parentElement) translateElement(node.parentElement);
                if (node.nodeType === Node.ELEMENT_NODE) translatePage(node);
            }));
        }).observe(document.body, { childList: true, subtree: true });
    });
})();
