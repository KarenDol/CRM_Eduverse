document.addEventListener('DOMContentLoaded', async function() {
    const search = document.querySelector('.input-group input'),
    table_headings = document.querySelectorAll('thead th');
    table_rows = document.querySelectorAll('tbody tr'),
    tableSection = document.getElementById('studentsTableBody');
    const selectMenu = document.querySelector(".select-menu"),
    selectBtn = selectMenu.querySelector(".select-btn"),
    optionsContainer = selectMenu.querySelector(".options"),
    sBtn_text = selectMenu.querySelector(".sBtn-text");
    const email = document.querySelector('.email svg')
    const whatsapp = document.getElementById('whatsapp');
    const checked = document.getElementById('checked');
    let checked_state = false;
    const buttons_wa = document.getElementById('buttons_wa');
    const actionButtons = document.querySelector(".action-buttons");
    const cancel = document.getElementById('cancel');
    const send = document.getElementById('send');
    const register = document.getElementById('register');

    // Dictionaries
    const status_dict = {
        'Лид': 'Лиды',
        'Дум': 'Думает',
        'Акт': 'Подтвердили',
        'Арх': 'Отказали'
    }

    const competitions_dict = { 0: "Выберите competition" };

    const competitions = await getCompetitions();

    competitions.forEach(c => {
        competitions_dict[c.id] = c.title;
    });

    const MODES = {
        DEFAULT: {
            optionsDict: status_dict,
            show: { buttons_wa: false, actionButtons: true },
            headings: ["#", "Фамилия", "Имя", "Школа", "Класс", "Номер"],
            async getRows(selected) {
            return clients.filter(s => s.status === selected);
            },
            rowHtml(student, index) {
            return `
                <td>${index}</td>
                <td><a href="/client/${student.id}">${student.last_name}</a></td>
                <td>${student.first_name}</td>
                <td>${student.school}</td>
                <td>${student.grade}</td>
                <td>${student.phone}</td>
            `;
            },
            rowId(student) { return student.id; },
            hasCheckbox: false,
        },
        EMAIL: {
            optionsDict: status_dict,
            show: { buttons_wa: true, actionButtons: false },
            headings: ["[_]", "Фамилия", "Имя", "Класс", "Школа", "e-mail"],
            async getRows(selected) {
            return clients.filter(s => s.status === selected);
            },
            rowHtml(student) {
            return `
                <td><input type="checkbox"></td>
                <td>${student.last_name}</td>
                <td>${student.first_name}</td>
                <td>${student.school}</td>
                <td>${student.grade}</td>
                <td>${student.email}</td>
            `;
            },
            rowId(student) { return student.id; },
            hasCheckbox: true,
        }, 
        WHATS_APP: {
            optionsDict: status_dict,
            show: { buttons_wa: true, actionButtons: false },
            headings: ["[_]", "Фамилия", "Имя", "Класс", "Школа", "Номер"],
            async getRows(selected) {
            return clients.filter(s => s.status === selected);
            },
            rowHtml(student) {
            return `
                <td><input type="checkbox"></td>
                <td>${student.last_name}</td>
                <td>${student.first_name}</td>
                <td>${student.school}</td>
                <td>${student.grade}</td>
                <td>${student.phone}</td>
            `;
            },
            rowId(student) { return student.id; },
            hasCheckbox: true,
        },

        ADD_MODE: {
            optionsDict: competitions_dict,
            show: { buttons_wa: true, actionButtons: false },
            headings: ["[_]", "Фамилия Имя", "Школа", "Класс", "Результат", "Award"],
            async getRows(selectedCompetitionId) {
                if (selectedCompetitionId === "0") return [];
                return await window.get_results(selectedCompetitionId);
            },
            rowHtml(student) {
            return `
                <td><input type="checkbox"></td>
                <td>${student.surname} ${student.name}</td>
                <td>${student.school}</td>
                <td>${student.grade}</td>
                <td>${student.points}/${student.maxPoints}</td>
                <td>${student.award}</td>
            `;
            },
            rowId(student) { return student.participantId; },
            hasCheckbox: true,
        }
    };

    // Default for page on load
    const state = {
        mode: "DEFAULT",                 // DEFAULT | WHATS_APP | ADD_MODE
        selected: "Лид",                 // status OR competition id
        checkedAll: false,
    };

    await render();

    //Functions 
    async function setMode(mode = state.mode, selected = state.selected) {
        state.mode = mode;
        state.selected = selected;
        await render();
    }

    async function render() {
        const cfg = MODES[state.mode];

        // select Button Text
        sBtn_text.innerText = cfg.optionsDict[state.selected];

        //populate options Menu
        populateSelectMenu(cfg.optionsDict);

        // show/hide blocks
        buttons_wa.style.display = cfg.show.buttons_wa ? "flex" : "none";
        actionButtons.style.display = cfg.show.actionButtons ? "flex" : "none";

        // headings
        table_headings.forEach((th, i) => th.innerText = cfg.headings[i] ?? "");

        // reset check-all state when entering checkbox modes
        state.checkedAll = false;
        
        // remove first (safe even if not added)
        table_headings[0].removeEventListener('click', checkedHandler);

        // only checkbox modes
        if (state.mode === "ADD_MODE" || state.mode === "WHATS_APP" || state.mode === "EMAIL") {
            table_headings[0].addEventListener('click', checkedHandler);
        }

        // rows
        const rows = await cfg.getRows(state.selected);

        // render rows with a single DOM write
        tableSection.innerHTML = rows.map((student, idx) => {
            const id = cfg.rowId(student);
            const indexCell = state.mode === "DEFAULT" ? (idx + 1) : 0; // cfg decides anyway
            return `<tr data-id="${id}">${cfg.rowHtml(student, indexCell || (idx + 1))}</tr>`;
        }).join("");
    }

    register.addEventListener("click", async () => {
        await setMode("ADD_MODE", "0");
    });

    whatsapp.addEventListener("click", async () => {
        await setMode("WHATS_APP", state.selected);
    });

    email.addEventListener("click", async () => {
        await setMode("EMAIL", state.selected);
    });

    cancel.addEventListener("click", async () => {
        await setMode("DEFAULT", "Лид");
    });

    //Listeners for options
    const options = selectMenu.querySelectorAll(".option");
    optionsContainer.addEventListener("click", async (e) => {
        const option = e.target.closest(".option");
        if (!option) return;

        const title = option.querySelector(".option-text").innerText;
        const id = option.dataset.id;

        // UI
        sBtn_text.innerText = title;

        const selectedClassInput = document.getElementById("selectedClassInput");
        selectedClassInput.value = id;

        // close dropdown
        optionsContainer.animate(
            [
                { opacity: 1, visibility: "visible" },
                { opacity: 0, visibility: "hidden" }
            ],
            { duration: 100, fill: "forwards" }
        );

        selectMenu.classList.remove("active");

        // 🔥 передаём ID
        await setMode(state.mode, id);
    });


    // select menu logic
    function populateSelectMenu(dict) {
        optionsContainer.innerHTML = "";

        Object.entries(dict)
            .sort((a, b) => String(a[1]).localeCompare(String(b[1]), "ru", { sensitivity: "base" }))
            .forEach(([id, title]) => addSelectMenuOption(id, title));
    }

    function addSelectMenuOption(id, title) {
        const li = document.createElement('li');
        li.classList.add('option');

        li.dataset.id = id;

        const span = document.createElement('span');
        span.classList.add('option-text');
        span.textContent = title;

        li.appendChild(span);
        optionsContainer.appendChild(li);
    }

    async function getCompetitions() {
        const cached = localStorage.getItem("competitions");

        if (cached) {
            return JSON.parse(cached);
        }

        const competitions = await window.get_competitions();
        localStorage.setItem("competitions", JSON.stringify(competitions));

        return competitions;
    }

    selectBtn.addEventListener("click", () => {
        if (selectMenu.classList.contains("active")) {
            selectMenu.classList.remove("active");
            let optionsContainer = selectMenu.querySelector(".options");
            optionsContainer.animate([
                { opacity: 1, visibility: "visible" },
                { opacity: 0, visibility: "hidden" }
            ], {
                duration: 150,
                fill: "forwards"
            });
        } else {
            selectMenu.classList.add("active");
            
            optionsContainer.animate([
                { opacity: 0, visibility: "hidden" },
                { opacity: 1, visibility: "visible" }
            ], {
                duration: 150,
                fill: "forwards"
            });
        }
    });


    if (search) {
        search.addEventListener("input", () => {
        const q = search.value.trim().toLowerCase();
        const rows = tableSection.querySelectorAll("tr");
        rows.forEach((tr) => {
            const text = tr.innerText.toLowerCase();
            tr.hidden = q && !text.includes(q);
        });
        });
    }

    function checkedHandler() {
        const checkboxes = document.querySelectorAll('tbody tr:not([hidden]) input[type="checkbox"]');

        if (checked_state){
            checked_state = false;
            checked.innerText = '[_]'
            checkboxes.forEach(c => c.checked = false);
        } else {
            checked_state = true;        
            checked.innerText = '[v]'
            checkboxes.forEach(c => c.checked = true);
        }
    }

    function buildAddLeadsMessage(data, checkedStudentsCount) {
        const ok = Boolean(data?.ok);

        const productId = data?.product_id ?? "—";
        const createdClients = Number(data?.created_clients ?? 0);
        const createdDeals = Number(data?.created_deals ?? 0);
        const skipped = Number(data?.skipped ?? 0);

        // сколько получилось “обработано” (по твоим полям это created+skipped, но обновление существующих сделок не считается отдельно)
        const processed = createdDeals + skipped;

        const lines = [];

        if (ok) {
            lines.push("✅ Новые лиды обработаны!");
        } else {
            lines.push("❌ Не удалось добавить лиды.");
        }

        lines.push("");
        lines.push("📦 Детали операции:");
        lines.push(`• Product ID (из сессии): ${productId}`);
        lines.push(`• Competition ID (выбранный): ${state.selected ?? "—"}`);
        lines.push(`• Выбрано учеников: ${checkedStudentsCount}`);

        lines.push("");
        lines.push("📊 Результат:");
        lines.push(`• Создано клиентов (Client): ${createdClients}`);
        lines.push(`• Создано сделок (Deal): ${createdDeals}`);
        lines.push(`• Пропущено (skipped): ${skipped}`);

        // маленькая подсказка что значит skipped
        if (skipped > 0) {
            lines.push("");
            lines.push("ℹ️ Почему могло быть skipped:");
            lines.push("• participantId нет в registrants или results по competition");
            lines.push("• в ответах API отсутствуют карточки участника");
        }

        // sanity check / полезная инфа
        lines.push("");
        lines.push("🧮 Проверка:");
        lines.push(`• Итог обработано (created_deals + skipped): ${processed}`);
        lines.push(`• Ожидалось обработать (выбрано): ${checkedStudentsCount}`);
        if (processed !== checkedStudentsCount) {
            lines.push("⚠️ Внимание: числа не сходятся — возможно, были дубликаты participantId или бэкенд не считает обновления отдельно.");
        }

        return lines.join("\n");
    }

    send.addEventListener('click', () => {
        // Get all checkboxes in the table
        const checkboxes = document.querySelectorAll('tbody input[type="checkbox"]');
        
        // Initialize an array to hold the data of checked students
        const checkedStudents = [];

        // Loop through checkboxes and find the checked ones
        checkboxes.forEach((checkbox, index) => {
            if (checkbox.checked) {
                // Get the row corresponding to the checkbox
                const row = checkbox.closest('tr');
                
                // Extract data from the row cells
                const id = row.dataset.id;
                    
                // Add the student IIN to the array
                checkedStudents.push(id);
            }
        });

        switch (state.mode) {
            case "ADD_MODE": {
                if (checkedStudents.length === 0) {
                    alert("Выберите хотя бы одного ученика.");
                    return;
                }

                fetch("/product/clients/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                    competition: state.selected,
                    students: checkedStudents,
                    }),
                })
                    .then(async (res) => {
                    if (!res.ok) {
                        const text = await res.text().catch(() => "");
                        throw new Error(`HTTP ${res.status}. ${text}`);
                    }
                    return res.json().catch(() => ({}));
                    })
                    .then((data) => {
                    const msg = buildAddLeadsMessage(data, checkedStudents.length);

                    alert(msg);

                    // 🔥 refresh AFTER success
                    window.location.reload();
                    })
                    .catch((error) => {
                    console.error("Error:", error);

                    alert(
                        [
                        "❌ Произошла ошибка при добавлении лидов.",
                        "",
                        `Competition ID: ${state.selected ?? "—"}`,
                        `Выбрано учеников: ${checkedStudents.length}`,
                        "",
                        `Ошибка: ${error.message}`,
                        ].join("\n")
                    );
                    });

                break;
            }
            case "WHATS_APP": {
                fetch('/clients/get_numbers', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value // Include CSRF token if using Django
                    },
                    body: JSON.stringify({ 
                        checkedClients: checkedStudents,
                    })
                })
                .then(async (res) => {
                    if (!res.ok) {
                        const text = await res.text().catch(() => '');
                        throw new Error(`HTTP ${res.status}. ${text}`);
                    }
                    return res.json().catch(() => ({}));
                })
                .then(data => {
                    window.location.href = "/whatsapp";
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Произошла ошибка!');
                });
                break;
            }
            case "EMAIL": {
                fetch('/clients/get_emails', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value // Include CSRF token if using Django
                    },
                    body: JSON.stringify({ 
                        checkedClients: checkedStudents,
                    })
                })
                .then(async (res) => {
                    if (!res.ok) {
                        const text = await res.text().catch(() => '');
                        throw new Error(`HTTP ${res.status}. ${text}`);
                    }
                    return res.json().catch(() => ({}));
                })
                .then(data => {
                    window.location.href = "http://email.a1s.kz";
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Произошла ошибка!');
                });
                break;
            }
        }
    });
});