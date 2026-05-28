/**
 * VerifyNews — Fake News Detector Frontend Logic
 * Handles form submission, API communication, and result rendering
 */

(function () {
    "use strict";

    // ---- DOM Refs ----
    const inputSection   = document.getElementById("input-section");
    const loadingSection = document.getElementById("loading-section");
    const resultSection  = document.getElementById("result-section");

    const headlineInput  = document.getElementById("headline-input");
    const analyzeBtn     = document.getElementById("analyze-btn");
    const resetBtn       = document.getElementById("reset-btn");

    const scanningDiv    = document.getElementById("scanning-sources");

    const verdictBadge   = document.getElementById("verdict-badge");
    const verdictIcon    = document.getElementById("verdict-icon");
    const verdictText    = document.getElementById("verdict-text");

    const headlineText   = document.getElementById("headline-text");
    const probabilityVal = document.getElementById("probability-value");
    const progressBar    = document.getElementById("progress-bar");
    const progressGlow   = document.getElementById("progress-glow");
    const sourceList     = document.getElementById("source-list");

    // ---- Config ----
    const API_URL = "/analyze";

    const SOURCE_NAMES = [
        "BBC", "Reuters", "Al Jazeera", "NDTV",
        "Times of India", "AP News", "The Hindu", "Hindustan Times"
    ];

    // ---- Error Toast ----
    function showError(msg) {
        let toast = document.querySelector(".error-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "error-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        // Force reflow then show
        toast.classList.remove("visible");
        void toast.offsetWidth;
        toast.classList.add("visible");
        setTimeout(() => toast.classList.remove("visible"), 4000);
    }

    // ---- State Transitions ----
    function showLoading() {
        inputSection.classList.add("hidden");
        resultSection.classList.add("hidden");
        loadingSection.classList.remove("hidden");

        // Build scanning source tags
        scanningDiv.innerHTML = "";
        SOURCE_NAMES.forEach((name, i) => {
            const tag = document.createElement("span");
            tag.className = "scanning-tag";
            tag.textContent = name;
            tag.style.animationDelay = `${i * 0.15}s`;
            scanningDiv.appendChild(tag);
        });

        // Animate tags one by one
        let idx = 0;
        const interval = setInterval(() => {
            const tags = scanningDiv.querySelectorAll(".scanning-tag");
            if (idx < tags.length) {
                tags[idx].classList.add("active");
                idx++;
            } else {
                clearInterval(interval);
            }
        }, 800);
        // Store interval so we can clean up
        loadingSection._scanInterval = interval;
    }

    function showResults(data) {
        if (loadingSection._scanInterval) {
            clearInterval(loadingSection._scanInterval);
        }
        loadingSection.classList.add("hidden");
        resultSection.classList.remove("hidden");

        // ---- Verdict Badge ----
        verdictBadge.className = "verdict-badge"; // reset
        let verdictClass, icon;
        switch (data.verdict) {
            case "REAL":
                verdictClass = "real";
                icon = "✅";
                break;
            case "POSSIBLY REAL":
                verdictClass = "possibly";
                icon = "⚠️";
                break;
            default:
                verdictClass = "fake";
                icon = "🚫";
        }
        verdictBadge.classList.add(verdictClass);
        verdictIcon.textContent = icon;
        verdictText.textContent = data.verdict;

        // ---- Headline ----
        headlineText.textContent = `"${data.headline_used}"`;

        // ---- Probability Bar ----
        const pct = data.probability;
        probabilityVal.textContent = `${pct}%`;

        // Reset bar then animate
        progressBar.style.width = "0%";
        progressGlow.style.width = "0%";
        progressBar.className = "progress-bar " + verdictClass;
        progressGlow.className = "progress-glow " + verdictClass;

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                progressBar.style.width  = pct + "%";
                progressGlow.style.width = pct + "%";
            });
        });

        // Animate the percentage number
        animateCounter(probabilityVal, 0, pct, 1200);

        // ---- Source List ----
        sourceList.innerHTML = "";
        data.searched_sources.forEach((src, i) => {
            const li = document.createElement("li");
            li.className = `source-item ${src.matched ? "matched" : "unmatched"}`;
            li.style.animationDelay = `${i * 0.07}s`;

            const iconSpan = document.createElement("span");
            iconSpan.className = `source-icon ${src.matched ? "check" : "cross"}`;
            iconSpan.textContent = src.matched ? "✓" : "✕";

            const nameSpan = document.createElement("span");
            nameSpan.className = "source-name";
            nameSpan.textContent = src.name;

            const scoreSpan = document.createElement("span");
            scoreSpan.className = "source-score";
            scoreSpan.textContent = src.score > 0 ? `${src.score}%` : "—";

            li.appendChild(iconSpan);
            li.appendChild(nameSpan);
            li.appendChild(scoreSpan);
            sourceList.appendChild(li);
        });
    }

    function resetToInput() {
        resultSection.classList.add("hidden");
        loadingSection.classList.add("hidden");
        inputSection.classList.remove("hidden");
        headlineInput.value = "";
        headlineInput.focus();
    }

    // ---- Counter Animation ----
    function animateCounter(el, from, to, duration) {
        const start = performance.now();
        function tick(now) {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(from + (to - from) * eased * 10) / 10;
            el.textContent = current.toFixed(1) + "%";
            if (progress < 1) {
                requestAnimationFrame(tick);
            } else {
                el.textContent = to + "%";
            }
        }
        requestAnimationFrame(tick);
    }

    // ---- API Call ----
    async function analyze() {
        const input = headlineInput.value.trim();
        if (!input) {
            showError("Please enter a headline or paste a URL.");
            headlineInput.focus();
            return;
        }

        analyzeBtn.disabled = true;
        showLoading();

        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ input }),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || `Server error (${response.status})`);
            }

            const data = await response.json();
            showResults(data);
        } catch (err) {
            showError(err.message || "Failed to reach the server. Is it running?");
            loadingSection.classList.add("hidden");
            inputSection.classList.remove("hidden");
        } finally {
            analyzeBtn.disabled = false;
        }
    }

    // ---- Event Listeners ----
    analyzeBtn.addEventListener("click", analyze);

    headlineInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            analyze();
        }
    });

    resetBtn.addEventListener("click", resetToInput);
})();
