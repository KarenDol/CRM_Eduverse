document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const phoneInput = document.getElementById("phone-numbers")
    const parseButton = document.getElementById("parse-button")
    const phoneInputSection = document.getElementById("phone-input-section")
    const phoneListSection = document.getElementById("phone-list-section")
    const phoneList = document.getElementById("phone-list")
    const editNumbersButton = document.getElementById("edit-numbers-button")
    const copyNumbersButton = document.getElementById("copy-numbers-button")
    const messageInput = document.getElementById("message")
    const fileButton = document.getElementById("file-button")
    const fileInput = document.getElementById("file-input")
    const fileName = document.getElementById("file-name")
    const sendButton = document.getElementById("send-button")
  
    // State
    // var phoneNumbers = JSON.parse('{{ phone_numbers|escapejs }}');
    let selectedFile = null
  
    // Initialize
    updateSendButton()
    loadNumbers()

    // Event Listeners
    phoneInput.addEventListener("input", inputHandler)
    parseButton.addEventListener("click", parsePhoneNumbers)
    editNumbersButton.addEventListener("click", editPhoneNumbers)
    copyNumbersButton.addEventListener("click", copyPhoneNumbers)
    fileButton.addEventListener("click", () => fileInput.click())
    fileInput.addEventListener("change", handleFileChange)
    sendButton.addEventListener("click", sendMessages)
    messageInput.addEventListener("input", updateSendButton)
  
    // Functions
    function inputHandler() {
        phoneInput.value = phoneInput.value.replace(/[^\d,\s]/g, '');

        if (phoneInput.value === ''){
            parseButton.disabled = true;
        } else {
            parseButton.disabled = false;
        }
    }

    async function parsePhoneNumbers() {
      const input = phoneInput.value.trim()
      if (!input) return

      // Step 1: create list immediately
      phoneNumbers = input
          .split(",")
          .map(n => n.trim())
          .filter(Boolean)
          .map(n => ({
              number: n,
              status: "wait"
          }))

      renderPhoneList()
      phoneInputSection.classList.add("hidden")
      phoneListSection.classList.remove("hidden")

      // Step 2: check WhatsApp existence ONE BY ONE
      for (let i = 0; i < phoneNumbers.length; i++) {
          const phone = phoneNumbers[i]

          try {
              const response = await fetch("/wa_exists_one/", {
                  method: "POST",
                  headers: {
                      "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
                  },
                  body: JSON.stringify({ phone: phone.number }),
              })

              const data = await response.json()
              phoneNumbers[i].status = data.exists ? "exist" : "not-exist"
          } catch {
              phoneNumbers[i].status = "error"
          }

          renderPhoneList()
      }

      updateSendButton()
    }

  
    function renderPhoneList() {
      phoneList.innerHTML = ""
      phoneNumbers.forEach((phone) => {
        const item = document.createElement("div")
        item.className = "phone-item"
  
        const numberSpan = document.createElement("span")
        if (phone.number.length == 11){
          num = phone.number
          numberSpan.textContent = `+${num[0]}(${num.slice(1, 4)})${num.slice(4, 7)}-${num.slice(7, 9)}-${num.slice(9, 11)}`
        } else {
          numberSpan.textContent = phone.number
        }
        
        const statusSpan = document.createElement("span")
        statusSpan.className = `status-${phone.status}`
        statusSpan.textContent = getStatusText(phone.status)
  
        item.appendChild(numberSpan)
        item.appendChild(statusSpan)
        phoneList.appendChild(item)
      })
    }
  
    function getStatusText(status) {
      switch (status) {
        case "sent":
          return "Отправлено"
        case "wait":
          return "Waiting"
        case "not-exist":
          return "WhatsApp не доступен"
        case "exist":
          return "WhatsApp доступен"
        case "error":
          return "Ошибка"
        default:
          return "Pending"
      }
    }
  
    function editPhoneNumbers() {
      phoneListSection.classList.add("hidden")
      phoneInputSection.classList.remove("hidden")
      phoneNumbers = []
      updateSendButton()
    }
  
    function copyPhoneNumbers() {
      navigator.clipboard.writeText(phoneInput.value)
  
      // Show a temporary tooltip or feedback
      const originalText = copyNumbersButton.textContent
      copyNumbersButton.textContent = "Скопировано!"
      setTimeout(() => {
        copyNumbersButton.textContent = originalText
      }, 2000)
    }

    function loadNumbers() {
      phoneInput.value = phoneNumbers.join(', ')
      inputHandler()
    }
  
    function handleFileChange(e) {
      if (e.target.files && e.target.files[0]) {
        selectedFile = e.target.files[0]
        fileName.textContent = selectedFile.name
      }
    }
  
    function updateSendButton() {
      const isValid = phoneNumbers.length > 0 && messageInput.value.trim() !== ""
      sendButton.disabled = !isValid
    }
  
    async function sendMessages() {
      sendButton.disabled = true
      sendButton.innerText = "Отправка..."

      const file = fileInput.files[0] || null

      for (let i = 0; i < phoneNumbers.length; i++) {
          const phone = phoneNumbers[i]

          if (phone.status === "not-exist") continue

          phone.status = "wait"
          renderPhoneList()

          const formData = new FormData()
          formData.append("number", phone.number)
          formData.append("waText", messageInput.value)

          if (file) {
              formData.append("file", file)
          }

          try {
              const response = await fetch("/whatsapp/send_one/", {
                  method: "POST",
                  headers: {
                      "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
                  },
                  body: formData
              })

              const data = await response.json()
              phoneNumbers[i].status = data.status
          } catch {
              phoneNumbers[i].status = "error"
          }

          renderPhoneList()
      }

      sendButton.disabled = false
      sendButton.innerText = "Отправить Сейчас"
    }

})