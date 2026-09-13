/**
 * CareHub Authenticated Patient AI Assistant — Client Script
 */
(function () {
  'use strict';

  let conversationHistory = [];
  let isProcessing = false;

  const launcher = document.getElementById('carehubPatientAiLauncher');
  const windowEl = document.getElementById('carehubPatientAiWindow');
  const closeBtn = document.getElementById('carehubPatientAiClose');
  const messagesEl = document.getElementById('carehubPatientAiMessages');
  const inputEl = document.getElementById('carehubPatientAiInput');
  const sendBtn = document.getElementById('carehubPatientAiSend');
  const actionsBar = document.getElementById('carehubPatientAiActionsBar');

  if (!launcher || !windowEl) return;

  function toggleChat() {
    const isOpen = windowEl.classList.toggle('open');
    launcher.classList.toggle('active', isOpen);
    if (isOpen) {
      launcher.setAttribute('aria-expanded', 'true');
      inputEl.focus();
      if (conversationHistory.length === 0) {
        initWelcomeMessage();
      }
    } else {
      launcher.setAttribute('aria-expanded', 'false');
    }
  }

  function initWelcomeMessage() {
    const welcomeText = "Hello! I am your CareHub Personal AI Assistant. I can help you **Book**, **Reschedule**, or **Cancel** your hospital appointments.";
    appendMessage('assistant', welcomeText);
  }

  function appendMessage(role, text) {
    conversationHistory.push({ role: role, content: text });

    const msgDiv = document.createElement('div');
    msgDiv.className = `carehub-patient-ai-msg ${role}`;

    // Markdown formatting
    let formatted = escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n- (.*?)/g, '<li>$1</li>')
      .replace(/\n/g, '<br>');

    if (formatted.includes('<li>')) {
      formatted = formatted.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    }

    msgDiv.innerHTML = `<p>${formatted}</p>`;
    messagesEl.appendChild(msgDiv);
    scrollToBottom();
  }

  function showTyping() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'carehub-patient-ai-typing';
    typingDiv.id = 'carehubPatientAiTyping';
    typingDiv.innerHTML = `
      <div class="carehub-patient-ai-typing-dot"></div>
      <div class="carehub-patient-ai-typing-dot"></div>
      <div class="carehub-patient-ai-typing-dot"></div>
    `;
    messagesEl.appendChild(typingDiv);
    scrollToBottom();
  }

  function hideTyping() {
    const typingDiv = document.getElementById('carehubPatientAiTyping');
    if (typingDiv) typingDiv.remove();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function handleSendMessage(textToSend) {
    const text = (textToSend || inputEl.value || '').trim();
    if (!text || isProcessing) return;

    inputEl.value = '';
    appendMessage('user', text);

    isProcessing = true;
    inputEl.disabled = true;
    sendBtn.disabled = true;
    showTyping();

    try {
      const response = await fetch('/api/ai/patient/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages: conversationHistory
        })
      });

      const data = await response.json();
      hideTyping();

      if (data.success && data.message && data.message.content) {
        appendMessage('assistant', data.message.content);
      } else {
        appendMessage('assistant', data.error || "I'm having trouble processing that right now. Please try again or use the appointments section.");
      }
    } catch (err) {
      hideTyping();
      appendMessage('assistant', "Network connection error. Please verify your connection and try again.");
    } finally {
      isProcessing = false;
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // Event Listeners
  launcher.addEventListener('click', toggleChat);
  closeBtn.addEventListener('click', toggleChat);

  sendBtn.addEventListener('click', function () {
    handleSendMessage();
  });

  inputEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && windowEl.classList.contains('open')) {
      toggleChat();
    }
  });

  // Action Bar Buttons (Book, Reschedule, Cancel)
  if (actionsBar) {
    actionsBar.addEventListener('click', function (e) {
      const btn = e.target.closest('.carehub-patient-action-btn');
      if (btn) {
        const actionType = btn.getAttribute('data-action');
        if (actionType === 'book') {
          handleSendMessage("I want to book a new appointment");
        } else if (actionType === 'reschedule') {
          handleSendMessage("I would like to reschedule an appointment");
        } else if (actionType === 'cancel') {
          handleSendMessage("I would like to cancel an appointment");
        }
      }
    });
  }

})();
