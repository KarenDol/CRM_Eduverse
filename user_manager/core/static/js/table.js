document.addEventListener('DOMContentLoaded', function() {
    const search = document.querySelector('.input-group input'),
    table_headings = document.querySelectorAll('thead th');
    table_rows = document.querySelectorAll('tbody tr'),
    tableSection = document.getElementById('studentsTableBody');

    // --- sorting state ---
    let currentData = [];
    let sortState = { key: null, dir: 'asc' };

    // нормальная сортировка для RU/EN + цифр
    const collator = new Intl.Collator('ru', { sensitivity: 'base', numeric: true });

    const awardRank = (a) => {
        const m = { Gold: 3, Silver: 2, Bronze: 1 };
        return m[a] ?? 0;
    };

    function getSortValue(student, key) {
        switch (key) {
            case 'name':
            return `${student.surname ?? ''} ${student.name ?? ''}`.trim();
            case 'school':
            return student.school ?? '';
            case 'grade':
            // если grade строка вроде "10A" — collator нормально сравнит
            return String(student.grade ?? '');
            case 'points':
            return Number(student.points ?? 0);
            case 'award':
            return awardRank(student.award);
            default:
            return '';
        }
    }

    function sortData(data, key, dir) {
    const sign = dir === 'asc' ? 1 : -1;

    // не мутируем оригинал: делаем копию (FP-style)
    return [...data].sort((a, b) => {
        const va = getSortValue(a, key);
        const vb = getSortValue(b, key);

        // числа
        if (typeof va === 'number' && typeof vb === 'number') {
        return (va - vb) * sign;
        }

        // строки
        return collator.compare(String(va), String(vb)) * sign;
    });
    }

    function renderTable(data) {
        tableSection.innerHTML = '';
        data.forEach((student, idx) => addStudent(student, 0)); // у тебя чекбокс при index===0
        // после перерендера снова применим поиск (если в инпуте что-то есть)
        if (search.value.trim() !== '') {
            search.dispatchEvent(new Event('input'));
        }
    }


    const thToKey = {
        1: 'name',
        2: 'school',
        3: 'grade',
        4: 'points', // или 'ratio'
        5: 'award'
    };

    // search logic
    search.addEventListener('input', () => {
        //Necessary for the match with populate_table
        table_rows = document.querySelectorAll('tbody tr');
        table_rows.forEach((row, i) => {
            let table_data = row.textContent.toLowerCase(),
            search_data = search.value.toLowerCase();

            row.hidden = (table_data.indexOf(search_data) < 0);
        })

        document.querySelectorAll('tbody tr:not(.hide)').forEach((visible_row, i) => {
            visible_row.style.backgroundColor = (i % 2 == 0) ? 'transparent' : '#0000000b';
        });
    });

    //Sort Logic
    table_headings.forEach((th, idx) => {
        if (!(idx in thToKey)) return; // пропускаем '#'

        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
            const key = thToKey[idx];

            // toggle direction если кликаем по тому же столбцу
            if (sortState.key === key) {
            sortState.dir = (sortState.dir === 'asc') ? 'desc' : 'asc';
            } else {
            sortState.key = key;
            sortState.dir = 'asc';
            }

            const sorted = sortData(currentData, sortState.key, sortState.dir);
            renderTable(sorted);
        });
    });

});