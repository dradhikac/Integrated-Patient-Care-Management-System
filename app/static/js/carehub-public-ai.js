/**
 * CareHub Public AI Appointment Assistant — Client Script
 */
(function () {
  'use strict';

  let conversationHistory = [];
  let isProcessing = false;

  const launcher = document.getElementById('carehubPublicAiLauncher');
  const windowEl = document.getElementById('carehubPublicAiWindow');
  const closeBtn = document.getElementById('carehubPublicAiClose');
  const messagesEl = document.getElementById('carehubPublicAiMessages');
  const inputEl = document.getElementById('carehubPublicAiInput');
  const sendBtn = document.getElementById('carehubPublicAiSend');
  const chipContainer = document.getElementById('carehubPublicAiChips');

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
    const welcomeText = "Hi! I'm Maya, your CareHub Booking Concierge. I can help you find and book an appointment.\n\nHave you used CareHub before?\n[Yes, I'm already a CareHub patient] [No, I'm new to CareHub]";
    appendMessage('assistant', welcomeText);
  }

  function appendMessage(role, text) {
    conversationHistory.push({ role: role, content: text });

    const msgDiv = document.createElement('div');
    msgDiv.className = `carehub-ai-msg ${role}`;

    // Simple markdown formatting
    let formatted = escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n[•\-] (.*?)/g, '<li>$1</li>')
      .replace(/\n/g, '<br>');

    if (formatted.includes('<li>')) {
      formatted = formatted.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    }

    // Convert bracketed options [Option Label] into clickable choice pills in assistant messages
    if (role === 'assistant') {
      formatted = formatted.replace(/\[([^[\]\n]{1,60})\]/g, '<button type="button" class="carehub-ai-choice-btn" data-choice="$1">$1</button>');
    }

    msgDiv.innerHTML = `<p>${formatted}</p>`;
    messagesEl.appendChild(msgDiv);
    scrollToBottom();
  }

  function showTyping() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'carehub-ai-typing';
    typingDiv.id = 'carehubPublicAiTyping';
    typingDiv.innerHTML = `
      <div class="carehub-ai-typing-dot"></div>
      <div class="carehub-ai-typing-dot"></div>
      <div class="carehub-ai-typing-dot"></div>
    `;
    messagesEl.appendChild(typingDiv);
    scrollToBottom();
  }

  function hideTyping() {
    const typingDiv = document.getElementById('carehubPublicAiTyping');
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
      const response = await fetch('/api/ai/public/chat', {
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
        appendMessage('assistant', data.error || "I'm having trouble processing that right now. Please try again or check our Doctors directory.");
      }
    } catch (err) {
      hideTyping();
      appendMessage('assistant', "Network connection error. Please verify your internet connection and try again.");
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

  // Handle choice button clicks inside chat messages
  messagesEl.addEventListener('click', function (e) {
    const btn = e.target.closest('.carehub-ai-choice-btn');
    if (btn) {
      const choice = btn.getAttribute('data-choice');
      if (choice && !isProcessing) {
        handleSendMessage(choice);
      }
    }
  });

  // Chip quick action buttons
  if (chipContainer) {
    chipContainer.addEventListener('click', function (e) {
      if (e.target.classList.contains('carehub-ai-chip') || e.target.closest('.carehub-ai-chip')) {
        const chip = e.target.classList.contains('carehub-ai-chip') ? e.target : e.target.closest('.carehub-ai-chip');
        const query = chip.getAttribute('data-query');
        if (query) {
          handleSendMessage(query);
        }
      }
    });
  }

})();
