document.addEventListener("DOMContentLoaded", () => {
  const inputEl = document.getElementById("phone-numbers")
  const parseButton = document.getElementById("parse-button")
  const inputSection = document.getElementById("phone-input-section")
  const listSection = document.getElementById("phone-list-section")
  const listEl = document.getElementById("phone-list")
  const editButton = document.getElementById("edit-numbers-button")
  const copyButton = document.getElementById("copy-numbers-button")
  const sendButton = document.getElementById("send-button")
  const subjectInput = document.getElementById("email-subject")
  const fileInput = document.getElementById("file-input")
  const fileButton = document.getElementById("file-button")
  const filesListEl = document.getElementById("files-list")
  const previewIframe = document.getElementById("email-preview")
  const templatesListEl = document.getElementById("templates-list")
  const buildNewBtn = document.getElementById("build-new-btn")

  let attachments = []

  const builderUrl = (typeof window.EMAIL_BUILDER_URL !== "undefined" && window.EMAIL_BUILDER_URL) ? window.EMAIL_BUILDER_URL : "https://email.a1s.kz"

  function updateMainPreview(html) {
    if (typeof window.updatePreview === "function") {
      window.updatePreview(html)
    } else if (previewIframe) {
      const doc = previewIframe.contentDocument || previewIframe.contentWindow.document
      doc.open()
      doc.write(html || "<p style='padding:1rem;color:#666;'>Пусто.</p>")
      doc.close()
    }
  }

  async function loadTemplates() {
    try {
      const res = await fetch("/email/templates/", { headers: { "Accept": "application/json" } })
      if (res.ok) {
        const data = await res.json()
        return Array.isArray(data) ? data : []
      }
    } catch (e) { console.warn("Failed to fetch templates", e) }
    return Array.isArray(window.email_templates) ? window.email_templates : []
  }

  function renderTemplatePreview(iframe, html) {
    if (!iframe || !html) return
    try {
      const doc = iframe.contentDocument || iframe.contentWindow.document
      doc.open()
      doc.write(html)
      doc.close()
      const scale = 200 / 600
      iframe.style.width = "600px"
      iframe.style.height = "420px"
      iframe.style.transform = `scale(${scale})`
      iframe.style.transformOrigin = "0 0"
    } catch (e) { /* ignore */ }
  }

  let contextMenuTemplate = null
  const contextMenu = document.createElement("div")
  contextMenu.className = "template-context-menu"
  contextMenu.id = "template-context-menu"
  const menuActions = [
    { key: "use", label: "Использовать", fn: (t) => { updateMainPreview(t.html) } },
    { key: "edit", label: "В конструкторе", fn: (t) => { window.open(builderUrl + "?templateId=" + encodeURIComponent(t.id), "_blank") } },
    { key: "rename", label: "Переименовать", fn: async (t) => {
      const name = prompt("Название шаблона:", t.name)
      if (name === null) return
      try {
        const res = await fetch("/email/templates/" + encodeURIComponent(t.id) + "/update/", {
          method: "PUT",
          headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
          body: JSON.stringify({ title: (name || "").trim() }),
        })
        if (!res.ok) throw new Error(await res.text())
        loadTemplates().then(renderTemplatesList)
      } catch (e) {
        alert("Ошибка: " + (e.message || String(e)))
      }
    }},
    { key: "delete", label: "Удалить", deleteStyle: true, fn: (t) => {
      if (!confirm('Удалить шаблон «' + t.name + '»?')) return
      fetch("/email/templates/" + encodeURIComponent(t.id) + "/delete/", {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
      })
        .then((res) => { if (!res.ok) throw new Error(res.statusText); return res.json() })
        .then(() => loadTemplates().then(renderTemplatesList))
        .catch((err) => alert("Ошибка удаления: " + (err.message || String(err))))
    }},
  ]
  menuActions.forEach((a) => {
    const btn = document.createElement("button")
    btn.type = "button"
    btn.textContent = a.label
    if (a.deleteStyle) btn.classList.add("context-menu-delete")
    btn.addEventListener("click", (e) => {
      e.stopPropagation()
      contextMenu.classList.remove("open")
      if (contextMenuTemplate) a.fn(contextMenuTemplate)
      contextMenuTemplate = null
    })
    contextMenu.appendChild(btn)
  })
  document.body.appendChild(contextMenu)
  document.addEventListener("click", () => {
    contextMenu.classList.remove("open")
    contextMenuTemplate = null
  })

  function renderTemplatesList(templates) {
    if (!templatesListEl) return
    templatesListEl.innerHTML = ""
    templates.forEach((t) => {
      const card = document.createElement("div")
      card.className = "template-card"
      const previewDiv = document.createElement("div")
      previewDiv.className = "template-card-preview"
      const miniIframe = document.createElement("iframe")
      miniIframe.title = t.name
      previewDiv.appendChild(miniIframe)
      const body = document.createElement("div")
      body.className = "template-card-body"
      const nameEl = document.createElement("div")
      nameEl.className = "template-card-name"
      nameEl.textContent = t.name
      body.appendChild(nameEl)
      card.appendChild(previewDiv)
      card.appendChild(body)
      card.addEventListener("contextmenu", (e) => {
        e.preventDefault()
        contextMenuTemplate = t
        contextMenu.style.left = e.clientX + "px"
        contextMenu.style.top = e.clientY + "px"
        contextMenu.classList.add("open")
      })
      templatesListEl.appendChild(card)
      renderTemplatePreview(miniIframe, t.html)
    })
  }

  loadTemplates().then(renderTemplatesList)

  buildNewBtn?.addEventListener("click", () => {
    window.open(builderUrl, "_blank")
  })

  renderAttachments()

  // State
  let emails = [] // [{ email, status }]

  const initial = Array.isArray(window.emails_from_server) ? window.emails_from_server : []
  if (initial.length) {
    emails = initial.map(e => ({ email: String(e).trim(), status: "waiting" }))
  }

  // Init
  inputHandler()
  if (emails.length) {
    renderList()
    inputSection.classList.add("hidden")
    listSection.classList.remove("hidden")
  }
  updateSendButton()

  // Events
  inputEl.addEventListener("input", inputHandler)
  parseButton.addEventListener("click", parseEmails)
  editButton.addEventListener("click", editEmails)
  copyButton.addEventListener("click", copyEmails)

  sendButton.addEventListener("click", (e) => {
    e.preventDefault()
    sendEmails()
  })

  // Helpers
  function getCsrf() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || ""
  }

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i.test(email)
  }

  function inputHandler() {
    inputEl.value = inputEl.value.replace(/[^\w@.+\- ,]/g, "")
    parseButton.disabled = inputEl.value.trim() === ""
  }

  function unique(arr) {
    const s = new Set()
    const out = []
    for (const x of arr) {
      const key = x.toLowerCase()
      if (s.has(key)) continue
      s.add(key)
      out.push(x)
    }
    return out
  }

  function getStatusText(status) {
    switch (status) {
      case "waiting": return "Ожидание"
      case "invalid": return "Неверный email"
      case "sending": return "Отправка..."
      case "sent": return "Отправлено"
      case "error": return "Ошибка"
      // оставил, если захочешь проверку exists:
      case "checking": return "Проверка..."
      case "exist": return "Email существует"
      case "not-exist": return "Email не найден"
      default: return "—"
    }
  }

  function renderList() {
    listEl.innerHTML = ""
    emails.forEach((item) => {
      const row = document.createElement("div")
      row.className = "phone-item"

      const emailSpan = document.createElement("span")
      emailSpan.textContent = item.email

      const statusSpan = document.createElement("span")
      statusSpan.className = `status-${item.status}`
      statusSpan.textContent = getStatusText(item.status)

      row.appendChild(emailSpan)
      row.appendChild(statusSpan)
      listEl.appendChild(row)
    })
  }

  function updateSendButton() {
    // можно отправлять если есть хотя бы один валидный email
    const hasValid = emails.some(x => x.status !== "invalid")
    sendButton.disabled = !hasValid
  }

  function getEmailHtmlFromIframe() {
    if (!previewIframe) return ""
    const doc = previewIframe.contentDocument || previewIframe.contentWindow?.document
    // full HTML страницы из iframe:
    return doc ? doc.documentElement.outerHTML : ""
  }

  // Main: parse
  async function parseEmails() {
    const input = inputEl.value.trim()
    if (!input) return

    const rawList = input
      .split(",")
      .map(x => x.trim())
      .filter(Boolean)

    const cleaned = unique(rawList)

    emails = cleaned.map(e => ({
      email: e,
      status: isValidEmail(e) ? "waiting" : "invalid",
    }))

    renderList()
    inputSection.classList.add("hidden")
    listSection.classList.remove("hidden")
    updateSendButton()

    // если хочешь обратно проверку "exists" — вставишь сюда цикл
  }

  function renderAttachments() {
    if (!filesListEl) return
    filesListEl.innerHTML = ""

    if (!attachments.length) {
      filesListEl.innerHTML = `<div style="opacity:.7;">Файлы не выбраны</div>`
      return
    }

    attachments.forEach((file, idx) => {
      const row = document.createElement("div")
      row.style.display = "flex"
      row.style.justifyContent = "space-between"
      row.style.alignItems = "center"
      row.style.padding = "6px 8px"
      row.style.border = "1px solid #ddd"
      row.style.borderRadius = "6px"
      row.style.marginBottom = "6px"

      const left = document.createElement("div")
      left.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`

      const removeBtn = document.createElement("button")
      removeBtn.type = "button"
      removeBtn.className = "button outline"
      removeBtn.textContent = "Удалить"
      removeBtn.addEventListener("click", () => {
        attachments.splice(idx, 1)
        renderAttachments()
      })

      row.appendChild(left)
      row.appendChild(removeBtn)
      filesListEl.appendChild(row)
    })
  }

  fileButton.addEventListener("click", () => fileInput.click())

  fileInput.addEventListener("change", () => {
    const picked = Array.from(fileInput.files || [])
    if (!picked.length) return

    // add, but avoid duplicates by name+size+lastModified
    const existingKeys = new Set(attachments.map(f => `${f.name}-${f.size}-${f.lastModified}`))
    for (const f of picked) {
      const key = `${f.name}-${f.size}-${f.lastModified}`
      if (!existingKeys.has(key)) attachments.push(f)
    }

    // reset input so selecting same file again triggers change
    fileInput.value = ""

    renderAttachments()
  })

  function editEmails() {
    inputEl.value = emails.map(x => x.email).join(", ")
    inputHandler()

    listSection.classList.add("hidden")
    inputSection.classList.remove("hidden")

    emails = []
    updateSendButton()
    renderList()
  }

  function copyEmails() {
    const text = emails.map(x => x.email).join(", ")
    navigator.clipboard.writeText(text)

    const orig = copyButton.textContent
    copyButton.textContent = "Скопировано!"
    setTimeout(() => (copyButton.textContent = orig), 2000)
  }

  // ✅ SEND: call your Django POST /send_email/
  async function sendEmails() {
    const html = getEmailHtmlFromIframe()

    if (!html || !html.trim()) {
      alert("Пустой HTML письма. Выберите шаблон или создайте письмо в конструкторе.")
      return
    }

    sendButton.disabled = true
    const originalText = sendButton.innerText
    sendButton.innerText = "Отправка..."

    for (let i = 0; i < emails.length; i++) {
      if (emails[i].status === "invalid") continue

      emails[i].status = "sending"
      renderList()

      try {
        const form = new FormData()
        form.append("email", emails[i].email)
        form.append("html", html)
        
        const subject = subjectInput?.value?.trim() || "Новое письмо | Eduverse"

        form.append("email", emails[i].email)
        form.append("html", html)
        form.append("subject", subject)
        // optional:
        // form.append("subject", "Новая заявка | Eduverse")

        // add all attachments
        for (const f of attachments) {
          form.append("attachments", f) // "attachments" is a multi field
        }

        const res = await fetch("/email/send", {
          method: "POST",
          headers: {
            "X-CSRFToken": getCsrf(),
            // DO NOT set Content-Type here. Browser sets boundary automatically.
          },
          body: form,
        })

        const data = await res.json().catch(() => ({}))
        emails[i].status = data.status === "sent" ? "sent" : "error"
      } catch {
        emails[i].status = "error"
      }

      renderList()
    }

    sendButton.disabled = false
    sendButton.innerText = originalText
    updateSendButton()
  }
})
