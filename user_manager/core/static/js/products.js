let products;

async function fetchProducts() {
    try {
        const response = await fetch('/products/search');
        if (!response.ok) throw new Error('Failed to fetch products');
        
        products = await response.json();
        displayProducts();
    } catch (error) {
        console.error('Error fetching products:', error);
        document.getElementById('productsContainer').innerHTML = 
            '<div class="error">Failed to load products. Please try again.</div>';
    }
}

function attachTrashListeners() {
    const trashIcons = document.querySelectorAll('svg.trash');
    trashIcons.forEach(icon => {
        icon.addEventListener('click', function () {
            const productId = this.getAttribute('data-id');
            deleteProduct(productId);
        });
    });
}

async function deleteProduct(productId) {
    product = products.find(p => p.id === productId)
    const msg = product
        ? `Delete "${product.name}"? This cannot be undone.`
        : `Delete this product? This cannot be undone.`;

    if (!confirm(msg)) return;

    const response = await fetch(`/products/delete/${productId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
    });
    if (!response.ok) throw new Error('Failed to fetch products');

    alert("Product was successfully deleted");
    //Refresh list of products
    fetchProducts();
}

function attachEditListeners() {
    const editIcons = document.querySelectorAll('svg.edit');
    editIcons.forEach(icon => {
        icon.addEventListener('click', function () {
            const productId = this.getAttribute('data-id');
            const productCard = icon.closest(".product-card"); // Find the closest parent with class "product-card"
            // Replace content with inputs (values are set from existing elements)
            editProduct(productId, productCard);
        });
    });
}

function editProduct(productId, productCard) {
    productId = Number(productId);
    product = products.find(p => p.id === productId);

    // ✅ store original markup to restore on cancel
    const oldHtml = productCard.innerHTML;

    productCard.innerHTML = `
        <input class='product-edit' value='${product.name}' type='text'></input>
        <div class="product-clients">${product.clients} clients</div>
        <div class="icon-group">
            <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" class="cancel"><path fill="currentColor" d="m8.4 16.308l3.6-3.6l3.6 3.6l.708-.708l-3.6-3.6l3.6-3.6l-.708-.708l-3.6 3.6l-3.6-3.6l-.708.708l3.6 3.6l-3.6 3.6zM12.003 21q-1.866 0-3.51-.708q-1.643-.709-2.859-1.924t-1.925-2.856T3 12.003t.709-3.51Q4.417 6.85 5.63 5.634t2.857-1.925T11.997 3t3.51.709q1.643.708 2.859 1.922t1.925 2.857t.709 3.509t-.708 3.51t-1.924 2.859t-2.856 1.925t-3.509.709"/></svg>
            <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" class="save"><path fill="currentColor" d="M4 18.5v-5.154L9.846 12L4 10.654V5.5L19.423 12z"/></svg>
        </div>
    `;

    const input = productCard.querySelector(".product-edit");
    const cancelBtn = productCard.querySelector("svg.cancel");
    const saveBtn = productCard.querySelector("svg.save");

    cancelBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        productCard.innerHTML = oldHtml;   // ✅ restore
        attachTrashListeners();
        attachEditListeners();
    });

    saveBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const newName = input.value.trim();
        if (!newName) {
            alert("Name cannot be empty");
            return;
        }

        try {
            const resp = await fetch(`/products/edit/${productId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ name: newName }),
            });

            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || data.ok === false) {
                throw new Error(data.error || "Failed to save");
            }
            // ✅ update local array so UI matches immediately (optional)
            product.name = newName;

            // simplest: redraw everything
            displayProducts();
            
            alert("Product was successfully renamed");
        } catch (err) {
            console.error(err);
            alert(err.message || "Failed to save");
            // if save fails, you might keep edit mode, or restore:
            // productCard.innerHTML = oldHtml;
        }
    });
}

function attachCardListeners() {
    const productsContainerEl = document.getElementById('productsContainer');

    productsContainerEl.addEventListener('click', (e) => {
        const card = e.target.closest('.product-card');
        if (!card) return;

        // ignore clicks on edit/trash/cancel/save icons area
        if (e.target.closest('.icon-group')) return;

        // ignore clicks while in edit mode (input exists)
        if (card.querySelector('.product-edit')) return;

        const chosenProductName = card.dataset.name;
        localStorage.setItem('chosenProduct', chosenProductName);
        chooseProduct(card.dataset.id);
    });
}

async function chooseProduct(productId) {
    try {
        const resp = await fetch('/products/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: Number(productId) }),
        credentials: 'same-origin',
        });

        if (!resp.ok) {
            const text = await resp.text().catch(() => '');
            throw new Error(text || `HTTP ${resp.status}`);
        }

        // if you return JSON {redirect: "/"} this will use it, otherwise fallback to "/"
        const data = await resp.json().catch(() => ({}));
        window.location.href = data.redirect || '/';
    } catch (err) {
        console.error(err);
        alert(err.message || 'Произошла ошибка!');
    }
}

// Display products in the grid
function displayProducts() {
    const container = document.getElementById('productsContainer');
    container.innerHTML = '';

    console.log(products);
    // Add product cards
    products.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.dataset.id = product.id;
        card.dataset.name = product.name;
        card.innerHTML = `
            <div class="product-name">${product.name}</div>
            <div class="product-clients">${product.clients} clients</div>
            <div class="icon-group">
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" class="edit" data-id="${product.id}">
                    <path fill="currentColor" d="M22 7.24a1 1 0 0 0-.29-.71l-4.24-4.24a1 1 0 0 0-.71-.29a1 1 0 0 0-.71.29l-2.83 2.83L2.29 16.05a1 1 0 0 0-.29.71V21a1 1 0 0 0 1 1h4.24a1 1 0 0 0 .76-.29l10.87-10.93L21.71 8a1.2 1.2 0 0 0 .22-.33a1 1 0 0 0 0-.24a.7.7 0 0 0 0-.14ZM6.83 20H4v-2.83l9.93-9.93l2.83 2.83ZM18.17 8.66l-2.83-2.83l1.42-1.41l2.82 2.82Z"/>
                </svg>
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" class="trash" data-id="${product.id}">>
                    <path fill="currentColor" d="M7 21q-.825 0-1.412-.587T5 19V6q-.425 0-.712-.288T4 5t.288-.712T5 4h4q0-.425.288-.712T10 3h4q.425 0 .713.288T15 4h4q.425 0 .713.288T20 5t-.288.713T19 6v13q0 .825-.587 1.413T17 21zM17 6H7v13h10zm-7 11q.425 0 .713-.288T11 16V9q0-.425-.288-.712T10 8t-.712.288T9 9v7q0 .425.288.713T10 17m4 0q.425 0 .713-.288T15 16V9q0-.425-.288-.712T14 8t-.712.288T13 9v7q0 .425.288.713T14 17M7 6v13z"/>
                </svg>
            </div>
        `;
        container.appendChild(card);
    });

    //Add listeners
    attachTrashListeners();
    attachEditListeners();
    attachCardListeners();

    // Add the "+" card for adding new products
    const addCard = document.createElement('div');
    addCard.className = 'add-card';
    addCard.innerHTML = '<div class="plus-icon">+</div>';
    addCard.onclick = handleAddProduct;
    container.appendChild(addCard);
}

// Handle adding a new product
async function handleAddProduct() {
    const productName = prompt('Enter product name:');
    
    if (!productName || productName.trim() === '') {
        return;
    }

    try {
        const response = await fetch('/products/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name: productName.trim() })
        });

        if (!response.ok) throw new Error('Failed to add product');

        // Refresh the products list
        await fetchProducts();
    } catch (error) {
        console.error('Error adding product:', error);
        alert('Failed to add product. Please try again.');
    }
}

// Load products on page load
fetchProducts();