document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements (оставляем твои id, чтобы не менять HTML)
  const inputEl = document.getElementById("phone-numbers") // emails textarea
  const parseButton = document.getElementById("parse-button")
  const inputSection = document.getElementById("phone-input-section")
  const listSection = document.getElementById("phone-list-section")
  const listEl = document.getElementById("phone-list")
  const editButton = document.getElementById("edit-numbers-button")
  const copyButton = document.getElementById("copy-numbers-button")
  const sendButton = document.getElementById("send-button")

  // email preview iframe
  const previewIframe = document.getElementById("email-preview")

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

  // IMPORTANT: send button click should not submit form / reload page
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
      alert("Пустой HTML письма (iframe).")
      return
    }

    sendButton.disabled = true
    const originalText = sendButton.innerText
    sendButton.innerText = "Отправка..."

    for (let i = 0; i < emails.length; i++) {
      // пропускаем невалидные
      if (emails[i].status === "invalid") continue

      emails[i].status = "sending"
      renderList()

      try {
        const res = await fetch("/email/send", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
          },
          body: JSON.stringify({
            email: emails[i].email,
            html: html,
            // subject можешь прокинуть сюда, если надо:
            // subject: "Новая заявка | Eduverse"
          }),
        })

        const data = await res.json().catch(() => ({}))

        // твой backend возвращает {status:"sent"} или {status:"error"}
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
