/*
 * Rôle du fichier:
 * Pilote l'interface du dashboard côté client (état global, appels API, rendu des tables/charts, interactions UI).
 */

const appState = {
  token: localStorage.getItem("ems_token") || "",
  username: localStorage.getItem("ems_username") || "",
  role: localStorage.getItem("ems_role") || "",
  accountHolderName: localStorage.getItem("ems_account_holder_name") || "",
  accountHolderFunction: localStorage.getItem("ems_account_holder_function") || "",
  permissions: JSON.parse(localStorage.getItem("ems_permissions") || "[]"),
  mustChangePassword: localStorage.getItem("ems_must_change_password") === "1",
  roles: [],
  employees: [],
  employeeById: {},
  accounts: [],
  conversations: [],
  messageRecipients: [],
  activeChatUserId: null,
  activeChatRecipientEmployeeId: null,
  activeThreadMessages: [],
  oldestThreadMessageId: null,
  hasMoreThreadMessages: false,
  isLoadingOlderMessages: false,
  charts: {
    dept: null,
    leave: null,
    accountingMonthly: null,
    accountingCost: null,
    accountingDepartments: null,
  },
  feedbackModalHandlers: null,
  messagesAutoRefreshTimer: null,
};

const $ = (id) => document.getElementById(id);
const sectionTitleMap = {
  overview: "Vue d'ensemble",
  employees: "Employés",
  departments: "Départements",
  roles: "Rôles & Permissions",
  payrolls: "Salaires",
  attendances: "Présences",
  team: "Équipe",
  leaves: "Congés",
  contracts: "Contrats",
  messages: "Messagerie",
  accounts: "Comptes Agents",
  accounting: "Comptabilité",
  reports: "Reporting",
};

const sectionAccessRules = {
  overview: () => true,
  employees: () => can("Voir employés"),
  departments: () => can("Voir employés"),
  roles: () => can("Voir employés") && ["SuperAdmin", "Admin RH"].includes(appState.role),
  team: () => can("Voir équipe") || appState.role === "Manager",
  payrolls: () => can("Voir salaires"),
  attendances: () => can("Voir employés"),
  leaves: () => true,
  contracts: () => can("Voir employés"),
  messages: () => true,
  accounts: () => can("Modifier employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role),
  accounting: () => can("Voir comptabilité"),
  reports: () => can("Exporter rapports"),
};

const DEFAULT_PERMISSION_NAMES = [
  "Voir employés",
  "Modifier employés",
  "Voir salaires",
  "Voir comptabilité",
  "Exporter rapports",
  "Valider congés",
  // Manager / team-level
  "Voir équipe",
  "Valider congés équipe",
  "Attribuer tâches",
  "Gérer objectifs",
  "Gérer évaluations",
  "Voir performances",
  "Exporter rapports équipe",
];

function notify(message, isError = false) {
  const feedbackModal = $("feedbackModal");
  const feedbackCard = feedbackModal ? feedbackModal.querySelector(".feedback-card") : null;
  const titleElement = $("feedbackModalTitle");
  const messageElement = $("feedbackModalMessage");
  const closeButton = $("feedbackModalClose");

  if (feedbackModal && feedbackCard && titleElement && messageElement && closeButton) {
    titleElement.textContent = isError ? "Erreur" : "Succès";
    messageElement.textContent = message;
    feedbackCard.classList.remove("feedback-success", "feedback-error");
    feedbackCard.classList.add(isError ? "feedback-error" : "feedback-success");
    feedbackModal.classList.remove("hidden");

    const previousHandlers = appState.feedbackModalHandlers;
    if (previousHandlers) {
      closeButton.removeEventListener("click", previousHandlers.onCloseClick);
      feedbackModal.removeEventListener("click", previousHandlers.onBackdropClick);
      document.removeEventListener("keydown", previousHandlers.onEscape);
    }

    const close = () => {
      feedbackModal.classList.add("hidden");
      closeButton.removeEventListener("click", onCloseClick);
      feedbackModal.removeEventListener("click", onBackdropClick);
      document.removeEventListener("keydown", onEscape);
      appState.feedbackModalHandlers = null;
    };

    const onCloseClick = () => close();
    const onBackdropClick = (event) => {
      if (event.target === feedbackModal) {
        close();
      }
    };
    const onEscape = (event) => {
      if (event.key === "Escape") {
        close();
      }
    };

    closeButton.addEventListener("click", onCloseClick);
    feedbackModal.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", onEscape);
    appState.feedbackModalHandlers = { onCloseClick, onBackdropClick, onEscape };
    return;
  }

  const toast = $("toast");
  toast.textContent = message;
  toast.style.borderColor = isError ? "rgba(255,93,122,.85)" : "rgba(31,222,154,.85)";
  toast.classList.remove("hidden");
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.classList.add("hidden"), 250);
  }, 2200);
}

function can(permissionName) {
  return appState.permissions.includes(permissionName);
}

function renderOwnerAccountInfo() {
  const accountName = appState.accountHolderName || appState.username || "Utilisateur";
  const accountRole = appState.accountHolderFunction || appState.role || "Rôle non défini";

  const ownerName = $("ownerName");
  const ownerRole = $("ownerRole");
  if (ownerName) {
    ownerName.textContent = accountName;
  }
  if (ownerRole) {
    ownerRole.textContent = accountRole;
  }
}

function updateAccountHolderInfo(name, functionName) {
  appState.accountHolderName = String(name || "").trim();
  appState.accountHolderFunction = String(functionName || "").trim();
  localStorage.setItem("ems_account_holder_name", appState.accountHolderName);
  localStorage.setItem("ems_account_holder_function", appState.accountHolderFunction);
}

function clearAccountHolderInfo() {
  appState.accountHolderName = "";
  appState.accountHolderFunction = "";
  localStorage.removeItem("ems_account_holder_name");
  localStorage.removeItem("ems_account_holder_function");
}

function setMustChangePassword(value) {
  appState.mustChangePassword = !!value;
  localStorage.setItem("ems_must_change_password", value ? "1" : "0");
  const shouldShow = !!value && !$("appShell").classList.contains("hidden");
  $("passwordModal").classList.toggle("hidden", !shouldShow);
}

function ensureSectionAccess() {
  document.querySelectorAll(".menu-item").forEach((button) => {
    const section = button.dataset.section;
    const allowed = sectionAccessRules[section] ? sectionAccessRules[section]() : true;
    button.classList.toggle("hidden", !allowed);
    const sectionElement = $(`section-${section}`);
    if (sectionElement) {
      sectionElement.classList.toggle("hidden", !allowed);
    }
  });

  const activeButton = document.querySelector(".menu-item.active:not(.hidden)");
  if (!activeButton) {
    const firstVisible = document.querySelector(".menu-item:not(.hidden)");
    if (firstVisible) {
      firstVisible.click();
    }
  }
}

function applyFormPermissions() {
  const formPermissions = [
    { id: "employeeForm", allowed: can("Modifier employés") },
    { id: "departmentForm", allowed: can("Modifier employés") },
    { id: "roleForm", allowed: can("Modifier employés") && ["SuperAdmin", "Admin RH"].includes(appState.role) },
    { id: "payrollForm", allowed: can("Voir salaires") },
    { id: "attendanceForm", allowed: can("Voir employés") },
    { id: "leaveForm", allowed: true },
    { id: "contractForm", allowed: can("Modifier employés") },
  ];

  formPermissions.forEach(({ id, allowed }) => {
    const form = $(id);
    if (form) {
      form.classList.toggle("hidden", !allowed);
      const split = form.closest(".split");
      if (split) {
        const visibleChildren = Array.from(split.children).filter((child) => !child.classList.contains("hidden"));
        split.classList.toggle("single", visibleChildren.length === 1);
      }
    }
  });
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString("fr-FR", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function getFormJSON(form) {
  const formData = new FormData(form);
  const payload = {};
  for (const [key, value] of formData.entries()) {
    if (value === "") continue;
    payload[key] = value;
  }
  return payload;
}

function normalizePayload(payload, fieldsAsNumber = []) {
  const normalized = { ...payload };
  fieldsAsNumber.forEach((field) => {
    if (normalized[field] !== undefined) {
      normalized[field] = Number(normalized[field]);
    }
  });
  return normalized;
}

function openEditModal({ title, fields, submitLabel = "Enregistrer" }) {
  const modal = $("editModal");
  const titleElement = $("editModalTitle");
  const formElement = $("editModalForm");
  const cancelButton = $("editModalCancel");
  const submitButton = $("editModalSubmit");

  if (!modal || !titleElement || !formElement || !cancelButton || !submitButton) {
    return Promise.resolve(null);
  }

  titleElement.textContent = title || "Modifier";
  submitButton.textContent = submitLabel;
  formElement.innerHTML = "";

  const controls = {};
  fields.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field.label;

    let control;
    if (field.type === "select") {
      control = document.createElement("select");
      (field.options || []).forEach((option) => {
        const optionElement = document.createElement("option");
        optionElement.value = String(option.value);
        optionElement.textContent = option.label;
        control.appendChild(optionElement);
      });
      control.value = String(field.value ?? "");
    } else if (field.type === "textarea") {
      control = document.createElement("textarea");
      control.value = String(field.value ?? "");
      if (field.placeholder) {
        control.placeholder = field.placeholder;
      }
    } else {
      control = document.createElement("input");
      control.type = field.type || "text";
      control.value = String(field.value ?? "");
      if (field.placeholder) {
        control.placeholder = field.placeholder;
      }
      if (field.step) {
        control.step = String(field.step);
      }
      if (field.min !== undefined) {
        control.min = String(field.min);
      }
    }

    control.name = field.name;
    label.appendChild(control);
    formElement.appendChild(label);
    controls[field.name] = control;
  });

  modal.classList.remove("hidden");
  const firstControl = formElement.querySelector("input, select, textarea");
  if (firstControl) {
    firstControl.focus();
  }

  return new Promise((resolve) => {
    const close = (payload) => {
      modal.classList.add("hidden");
      cancelButton.removeEventListener("click", onCancel);
      submitButton.removeEventListener("click", onSubmit);
      modal.removeEventListener("click", onBackdropClick);
      document.removeEventListener("keydown", onEscape);
      resolve(payload);
    };

    const onCancel = () => close(null);

    const onSubmit = () => {
      try {
        const values = {};
        fields.forEach((field) => {
          const control = controls[field.name];
          const rawValue = control ? control.value : "";
          const trimmed = typeof rawValue === "string" ? rawValue.trim() : rawValue;

          if (field.required && !trimmed) {
            throw new Error(`Le champ ${field.label} est requis`);
          }

          if ((field.type === "number") && trimmed !== "") {
            const numberValue = Number(trimmed);
            if (Number.isNaN(numberValue)) {
              throw new Error(`${field.label} invalide`);
            }
            values[field.name] = numberValue;
          } else {
            values[field.name] = trimmed;
          }

          if (typeof field.parse === "function") {
            values[field.name] = field.parse(values[field.name]);
          }
        });
        close(values);
      } catch (error) {
        notify(error.message, true);
      }
    };

    const onBackdropClick = (event) => {
      if (event.target === modal) {
        close(null);
      }
    };

    const onEscape = (event) => {
      if (event.key === "Escape") {
        close(null);
      }
    };

    cancelButton.addEventListener("click", onCancel);
    submitButton.addEventListener("click", onSubmit);
    modal.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", onEscape);
  });
}

function confirmAction({ title, message, confirmLabel = "Confirmer" }) {
  const modal = $("confirmModal");
  const titleElement = $("confirmModalTitle");
  const messageElement = $("confirmModalMessage");
  const cancelButton = $("confirmModalCancel");
  const submitButton = $("confirmModalSubmit");

  if (!modal || !titleElement || !messageElement || !cancelButton || !submitButton) {
    return Promise.resolve(false);
  }

  titleElement.textContent = title || "Confirmation";
  messageElement.textContent = message || "Es-tu sûr de vouloir continuer ?";
  submitButton.textContent = confirmLabel;

  modal.classList.remove("hidden");

  return new Promise((resolve) => {
    const close = (accepted) => {
      modal.classList.add("hidden");
      cancelButton.removeEventListener("click", onCancel);
      submitButton.removeEventListener("click", onSubmit);
      modal.removeEventListener("click", onBackdropClick);
      document.removeEventListener("keydown", onEscape);
      resolve(accepted);
    };

    const onCancel = () => close(false);
    const onSubmit = () => close(true);

    const onBackdropClick = (event) => {
      if (event.target === modal) {
        close(false);
      }
    };

    const onEscape = (event) => {
      if (event.key === "Escape") {
        close(false);
      }
    };

    cancelButton.addEventListener("click", onCancel);
    submitButton.addEventListener("click", onSubmit);
    modal.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", onEscape);
  });
}

async function api(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };

  if (appState.token) {
    headers.Authorization = `Bearer ${appState.token}`;
  }

  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};

  if (!response.ok) {
    const errorPayload = payload.error;
    if (Array.isArray(errorPayload) && errorPayload.length > 0) {
      const firstError = errorPayload[0] || {};
      const errorMessage = firstError.msg || firstError.message || payload.message || `Erreur HTTP ${response.status}`;
      throw new Error(errorMessage);
    }

    const message = payload.error || payload.message || `Erreur HTTP ${response.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return payload;
}

function bindNavigation() {
  document.querySelectorAll(".menu-item").forEach((button) => {
    button.addEventListener("click", async () => {
      const section = button.dataset.section;
      document.querySelectorAll(".menu-item").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");

      document.querySelectorAll(".section").forEach((element) => element.classList.remove("active"));
      $(`section-${section}`).classList.add("active");
      $("sectionTitle").textContent = sectionTitleMap[section] || "Dashboard";

      if (section === "reports") {
        await loadReportsSection();
      }

      if (section === "accounting") {
        await loadAccountingSection();
      }

      if (section === "messages") {
        const query = ($("messagesSearch")?.value || "").trim();
        await loadMessageRecipients();
        await loadConversations(query);
        const firstConversation = (appState.conversations || [])[0];
        if (firstConversation && !appState.activeChatUserId) {
          await openConversation(firstConversation.user_id);
        } else if (appState.activeChatUserId) {
          await loadConversationThread(appState.activeChatUserId);
        } else {
          setActiveConversationInfo(null);
          renderChatThread([]);
        }
      }
    });
  });
}

function drawDeptChart(deptData = {}) {
  const labels = Object.keys(deptData);
  const values = Object.values(deptData);

  if (appState.charts.dept) {
    appState.charts.dept.destroy();
  }

  appState.charts.dept = new Chart($("deptChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Employés",
          data: values,
          backgroundColor: "rgba(33, 212, 253, .65)",
          borderColor: "rgba(33, 212, 253, 1)",
          borderWidth: 1,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#eaf0ff" } },
      },
      scales: {
        x: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
        y: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
      },
    },
  });
}

function drawLeaveChart(leaves = []) {
  const statusMap = leaves.reduce((acc, leave) => {
    acc[leave.status] = (acc[leave.status] || 0) + 1;
    return acc;
  }, {});

  if (appState.charts.leave) {
    appState.charts.leave.destroy();
  }

  appState.charts.leave = new Chart($("leaveChart"), {
    type: "doughnut",
    data: {
      labels: Object.keys(statusMap),
      datasets: [
        {
          data: Object.values(statusMap),
          backgroundColor: ["#6d8dff", "#1fde9a", "#ffb020", "#ff5d7a"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      plugins: {
        legend: { labels: { color: "#eaf0ff" } },
      },
    },
  });
}

function renderTable(containerId, headers, rows) {
  const container = $(containerId);
  const head = `<tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>`;
  const body = rows.length
    ? rows
        .map((row) => `<tr>${row.map((cell) => `<td>${cell ?? "-"}</td>`).join("")}</tr>`)
        .join("")
    : `<tr><td colspan="${headers.length}">Aucune donnée</td></tr>`;

  container.innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

function actionButtons(entity, id) {
  return `
    <div class="action-row">
      <button class="mini-btn" type="button" data-entity="${entity}" data-action="edit" data-id="${id}">Modifier</button>
      <button class="mini-btn" type="button" data-entity="${entity}" data-action="delete" data-id="${id}">Supprimer</button>
    </div>
  `;
}

function fillSelectOptions(selectId, options, includeEmpty = false) {
  const select = $(selectId);
  if (!select) return;

  const emptyOption = includeEmpty ? `<option value="">Non assigné</option>` : `<option value="">Sélectionner</option>`;
  select.innerHTML = `${emptyOption}${options
    .map((option) => `<option value="${option.value}">${option.label}</option>`)
    .join("")}`;
}

function employeeOptionLabel(employee) {
  return [
    `${employee.first_name} ${employee.last_name}`,
    employee.matricule || "N/A",
    employee.department || "Sans département",
    employee.role || "Sans rôle",
  ].join(" | ");
}

function accountOptionLabel(account) {
  return [
    account.employee_name || "Sans agent",
    account.username || "-",
    account.role || "Sans rôle",
    account.status || "Sans statut",
  ].join(" | ");
}

function messageRecipientOptionLabel(recipient) {
  return [
    recipient.name || "-",
    recipient.matricule || "N/A",
    recipient.department || "Sans département",
    recipient.role || "Sans rôle",
    recipient.username || "-",
  ].join(" | ");
}

function populateMessageRecipientSelect() {
  const select = $("newConversationRecipient");
  if (!select) return;

  const recipients = (appState.messageRecipients || []).filter((item) => Number(item.employee_id || 0) > 0);
  const options = recipients
    .map((recipient) => {
      const hasUserId = Number(recipient.user_id || 0) > 0;
      const value = hasUserId ? `u:${recipient.user_id}` : `e:${recipient.employee_id}`;
      return `<option value="${value}">${messageRecipientOptionLabel(recipient)}</option>`;
    })
    .join("");
  select.innerHTML = `<option value="">Choisir un agent...</option>${options}`;
}

function formatChatDateTime(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (_error) {
    return "";
  }
}

function updateMessagesUnreadBadgeFromConversations(conversations = []) {
  const total = (conversations || []).reduce((acc, item) => acc + Number(item.unread_count || 0), 0);
  setMessagesUnreadBadgeCount(total);
}

function renderConversations(conversations = []) {
  const container = $("messagesConversations");
  if (!container) return;

  if (!conversations.length) {
    container.innerHTML = '<div class="perm-empty" style="padding: 12px;">Aucune discussion trouvée.</div>';
    return;
  }

  container.innerHTML = conversations
    .map((conversation) => {
      const isActive = Number(appState.activeChatUserId || 0) === Number(conversation.user_id || 0);
      const unread = Number(conversation.unread_count || 0);
      return `
        <button class="chat-conversation-item ${isActive ? "active" : ""}" type="button" data-chat-userid="${conversation.user_id}">
          <div class="chat-row-top">
            <span class="chat-name">${conversation.display_name || conversation.username || "Utilisateur"}</span>
            <span class="chat-time">${formatChatDateTime(conversation.last_message_at)}</span>
          </div>
          <div class="chat-row-bottom">
            <span class="chat-preview">${conversation.last_message || ""}</span>
            ${unread > 0 ? `<span class="chat-unread">${unread > 99 ? "99+" : unread}</span>` : ""}
          </div>
        </button>
      `;
    })
    .join("");
}

function renderChatThread(messages = []) {
  const container = $("chatMessages");
  if (!container) return;

  if (!messages.length) {
    appState.activeThreadMessages = [];
    appState.oldestThreadMessageId = null;
    appState.hasMoreThreadMessages = false;
    container.innerHTML = '<div class="perm-empty">Aucun message dans cette discussion.</div>';
    return;
  }

  const previousScrollHeight = container.scrollHeight;
  const previousScrollTop = container.scrollTop;

  container.innerHTML = messages
    .map((message, index) => {
      const isMe = String(message.sender_username || "") === String(appState.username || "");
      const canEdit = !!message.can_edit;
      const canDelete = !!message.can_delete;
      const actionButtons = isMe && (canEdit || canDelete)
        ? `
            <div class="chat-actions">
              ${canEdit ? `<button class="chat-action-btn" type="button" data-chat-action="edit" data-message-id="${message.id}">Modifier</button>` : ""}
              ${canDelete ? `<button class="chat-action-btn danger" type="button" data-chat-action="delete" data-message-id="${message.id}">Supprimer</button>` : ""}
            </div>
          `
        : "";
      const editedLabel = message.edited_at ? " • modifié" : "";
      if (index === 0 && appState.hasMoreThreadMessages) {
        return `
          <div class="chat-load-more-wrap">
            <button id="chatLoadMoreBtn" class="chat-load-more-btn" type="button">Charger les anciens messages</button>
          </div>
          <div class="chat-bubble ${isMe ? "me" : "them"}">
            <div>${message.content || ""}</div>
            ${actionButtons}
            <span class="chat-meta">${formatChatDateTime(message.sent_at)}${editedLabel}${isMe ? (message.is_read ? " • lu" : " • envoyé") : ""}</span>
          </div>
        `;
      }
      return `
        <div class="chat-bubble ${isMe ? "me" : "them"}">
          <div>${message.content || ""}</div>
          ${actionButtons}
          <span class="chat-meta">${formatChatDateTime(message.sent_at)}${editedLabel}${isMe ? (message.is_read ? " • lu" : " • envoyé") : ""}</span>
        </div>
      `;
    })
    .join("");

  if (appState.isLoadingOlderMessages) {
    const newScrollHeight = container.scrollHeight;
    container.scrollTop = previousScrollTop + (newScrollHeight - previousScrollHeight);
  } else {
    container.scrollTop = container.scrollHeight;
  }
}

function setActiveConversationInfo(conversation) {
  const title = $("chatTitle");
  const subtitle = $("chatSubtitle");
  if (!title || !subtitle) return;

  if (!conversation) {
    title.textContent = "Sélectionne une discussion";
    subtitle.textContent = "Aucun message chargé";
    return;
  }

  title.textContent = conversation.display_name || conversation.username || "Discussion";
  subtitle.textContent = conversation.username ? `@${conversation.username}` : "Discussion interne";
}

function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function employeeSuggestionLabel(employee) {
  return employeeOptionLabel(employee);
}

function syncSelectFromQuery(queryText, selectId) {
  const select = $(selectId);
  if (!select) return;

  const normalizedQuery = normalizeSearchText(queryText);
  if (!normalizedQuery) {
    select.value = "";
    return;
  }

  const options = Array.from(select.options).filter((option) => option.value);
  const exact = options.find((option) => normalizeSearchText(option.textContent) === normalizedQuery);
  if (exact) {
    select.value = exact.value;
    return;
  }

  if (options.length === 1) {
    select.value = options[0].value;
  }
}

function populateEmployeeQuerySuggestions() {
  const datalist = $("employeeSuggestionsList");
  if (!datalist) return;

  const labels = (appState.employees || []).map((employee) => employeeSuggestionLabel(employee));
  const uniqueLabels = Array.from(new Set(labels));
  datalist.innerHTML = uniqueLabels.map((label) => `<option value="${label}"></option>`).join("");
}

function populateAccountQuerySuggestions() {
  const datalist = $("accountSuggestionsList");
  if (!datalist) return;

  const labels = (appState.accounts || []).map((account) => accountOptionLabel(account));
  const uniqueLabels = Array.from(new Set(labels));
  datalist.innerHTML = uniqueLabels.map((label) => `<option value="${label}"></option>`).join("");
}

function getEmployeeDisplay(employeeId) {
  const employee = appState.employeeById[String(employeeId)];
  if (!employee) {
    return "Agent non trouvé";
  }
  return `${employee.first_name} ${employee.last_name}${employee.matricule ? ` (${employee.matricule})` : ""}`;
}

function setReportsContent(value) {
  const reportsInfo = $("reportsInfo");
  const reportsCards = $("reportsCards");
  const reportsDepartments = $("reportsDepartments");
  if (!reportsInfo || !reportsCards || !reportsDepartments) return;

  if (typeof value === "string") {
    reportsInfo.textContent = value;
    reportsInfo.classList.remove("hidden");
    reportsCards.innerHTML = "";
    reportsDepartments.innerHTML = "";
    return;
  }

  reportsInfo.classList.add("hidden");

  const totalPayroll = Number(value.total_payroll || 0);
  const averageSalary = Number(value.average_salary || 0);
  const absenceRate = Number(value.absence_rate || 0);
  const departmentEntries = Object.entries(value.employees_by_department || {});

  reportsCards.innerHTML = [
    { title: "Masse salariale", metric: formatMoney(totalPayroll) },
    { title: "Salaire moyen", metric: formatMoney(averageSalary) },
    { title: "Taux d'absence", metric: `${absenceRate}%` },
    { title: "Départements", metric: String(departmentEntries.length) },
  ]
    .map(
      (card) => `
        <article class="kpi-card glass">
          <h3>${card.title}</h3>
          <p>${card.metric}</p>
        </article>
      `
    )
    .join("");

  renderTable(
    "reportsDepartments",
    ["Département", "Nombre d'employés"],
    departmentEntries.map(([departmentName, employeeCount]) => [departmentName, employeeCount])
  );
}

async function loadReportsSection() {
  if (!can("Exporter rapports")) {
    setReportsContent("Reporting avancé réservé aux rôles avec permission 'Exporter rapports'.");
    return;
  }

  setReportsContent("Chargement des statistiques...");
  try {
    const stats = await api("/api/reports/stats");
    setReportsContent(stats);
  } catch (error) {
    setReportsContent(`Impossible de charger le reporting: ${error.message}`);
  }
}

function drawAccountingMonthlyChart(monthly = {}) {
  const canvas = $("accountingMonthlyChart");
  if (!canvas) return;

  if (appState.charts.accountingMonthly) {
    appState.charts.accountingMonthly.destroy();
  }

  const labels = monthly.labels || [];
  appState.charts.accountingMonthly = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Brut",
          data: monthly.gross || [],
          borderColor: "rgba(33, 212, 253, 1)",
          backgroundColor: "rgba(33, 212, 253, .2)",
          tension: 0.3,
          fill: false,
        },
        {
          label: "Net",
          data: monthly.net || [],
          borderColor: "rgba(31, 222, 154, 1)",
          backgroundColor: "rgba(31, 222, 154, .2)",
          tension: 0.3,
          fill: false,
        },
        {
          label: "Impôts",
          data: monthly.taxes || [],
          borderColor: "rgba(255, 176, 32, 1)",
          backgroundColor: "rgba(255, 176, 32, .2)",
          tension: 0.3,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#eaf0ff" } },
      },
      scales: {
        x: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
        y: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
      },
    },
  });
}

function drawAccountingCostChart(costStructure = {}) {
  const canvas = $("accountingCostChart");
  if (!canvas) return;

  if (appState.charts.accountingCost) {
    appState.charts.accountingCost.destroy();
  }

  appState.charts.accountingCost = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: costStructure.labels || [],
      datasets: [
        {
          data: costStructure.values || [],
          backgroundColor: ["#6d8dff", "#ffb020", "#ff5d7a", "#1fde9a"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      plugins: {
        legend: { labels: { color: "#eaf0ff" } },
      },
    },
  });
}

function drawAccountingDepartmentsChart(departmentNet = {}) {
  const canvas = $("accountingDepartmentsChart");
  if (!canvas) return;

  if (appState.charts.accountingDepartments) {
    appState.charts.accountingDepartments.destroy();
  }

  appState.charts.accountingDepartments = new Chart(canvas, {
    type: "bar",
    data: {
      labels: departmentNet.labels || [],
      datasets: [
        {
          label: "Net par département",
          data: departmentNet.values || [],
          backgroundColor: "rgba(109, 141, 255, .65)",
          borderColor: "rgba(109, 141, 255, 1)",
          borderWidth: 1,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      indexAxis: "y",
      plugins: {
        legend: { labels: { color: "#eaf0ff" } },
      },
      scales: {
        x: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
        y: { ticks: { color: "#a9b5d6" }, grid: { color: "rgba(255,255,255,.08)" } },
      },
    },
  });
}

function setAccountingContent(value) {
  const accountingInfo = $("accountingInfo");
  const accountingCards = $("accountingCards");
  if (!accountingInfo || !accountingCards) return;

  if (typeof value === "string") {
    accountingInfo.textContent = value;
    accountingInfo.classList.remove("hidden");
    accountingCards.innerHTML = "";
    renderTable("accountingDepartmentsTable", ["Département", "Net"], []);
    return;
  }

  const totals = value.totals || {};
  const monthly = value.monthly || {};
  const departmentNet = value.department_net || {};
  const costStructure = value.cost_structure || {};

  accountingInfo.classList.add("hidden");
  accountingCards.innerHTML = [
    { title: "Masse salariale brute", metric: formatMoney(totals.gross_payroll || 0) },
    { title: "Masse salariale nette", metric: formatMoney(totals.net_payroll || 0) },
    { title: "Total impôts", metric: formatMoney(totals.taxes || 0) },
    { title: "Total déductions", metric: formatMoney(totals.deductions || 0) },
    { title: "Total primes", metric: formatMoney(totals.bonuses || 0) },
    { title: "Heures supplémentaires", metric: String(totals.overtime_hours || 0) },
  ]
    .map(
      (card) => `
        <article class="kpi-card glass">
          <h3>${card.title}</h3>
          <p>${card.metric}</p>
        </article>
      `
    )
    .join("");

  drawAccountingMonthlyChart(monthly);
  drawAccountingCostChart(costStructure);
  drawAccountingDepartmentsChart(departmentNet);

  renderTable(
    "accountingDepartmentsTable",
    ["Département", "Net"],
    (departmentNet.labels || []).map((departmentName, index) => [departmentName, formatMoney((departmentNet.values || [])[index] || 0)])
  );
}

async function loadAccountingSection() {
  if (!can("Voir comptabilité")) {
    setAccountingContent("Espace comptabilité réservé aux rôles avec permission 'Voir comptabilité'.");
    return;
  }

  setAccountingContent("Chargement des indicateurs comptables...");
  try {
    const stats = await api("/api/reports/accounting");
    setAccountingContent(stats);
  } catch (error) {
    setAccountingContent(`Impossible de charger la comptabilité: ${error.message}`);
  }
}

function populateEmployeeActionSelects() {
  const configs = [
    { selectId: "payrollEmployeeId", queryId: "payrollEmployeeQuery" },
    { selectId: "attendanceEmployeeId", queryId: "attendanceEmployeeQuery" },
    { selectId: "leaveEmployeeId", queryId: "leaveEmployeeQuery" },
    { selectId: "contractEmployeeId", queryId: "contractEmployeeQuery" },
  ];

  configs.forEach(({ selectId, queryId }) => {
    const queryText = ($(queryId)?.value || "").trim();
    const query = normalizeSearchText(queryText);
    const options = (appState.employees || [])
      .filter((employee) => {
        if (!query) return true;
        const haystack = [
          `${employee.first_name} ${employee.last_name}`,
          employee.matricule || "",
          employee.department || "",
          employee.role || "",
        ]
          .join(" ")
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase();
        return haystack.includes(query);
      })
      .map((employee) => ({
        value: employee.id,
        label: employeeOptionLabel(employee),
      }));

    fillSelectOptions(selectId, options, false);
    syncSelectFromQuery(queryText, selectId);
  });

  populateEmployeeQuerySuggestions();
}

function populateAccountActionSelect() {
  const queryText = ($("accountUserQuery")?.value || "").trim();
  const query = normalizeSearchText(queryText);
  const options = (appState.accounts || [])
    .filter((account) => {
      if (!query) return true;
      const haystack = [
        account.employee_name || "",
        account.username || "",
        account.matricule || "",
        account.role || "",
        account.status || "",
      ]
        .join(" ")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
      return haystack.includes(query);
    })
    .map((account) => ({
      value: account.id,
      label: accountOptionLabel(account),
    }));
  fillSelectOptions("accountUserId", options, false);
  syncSelectFromQuery(queryText, "accountUserId");
  populateAccountQuerySuggestions();
}

function renderPermissionChecklist(containerId, permissions = [], selectedValues = []) {
  const container = $(containerId);
  if (!container) return;

  if (!permissions || permissions.length === 0) {
    container.innerHTML = '<div class="perm-empty">Aucune permission disponible.</div>';
    return;
  }

  const selected = new Set(selectedValues || []);
  container.innerHTML = (permissions || [])
    .map(
      (permissionName) => `
        <label class="perm-item">
          <input type="checkbox" value="${permissionName}" ${selected.has(permissionName) ? "checked" : ""} />
          <span>${permissionName}</span>
        </label>
      `
    )
    .join("");
}

function getCheckedPermissions(containerId) {
  const container = $(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value);
}

function setCheckedPermissions(containerId, values = []) {
  const container = $(containerId);
  if (!container) return;
  const selectedValues = new Set(values || []);
  container.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = selectedValues.has(checkbox.value);
  });
}

async function loadOverview() {
  const [employees, leaves, departments, payrolls, attendances, stats] = await Promise.all([
    can("Voir employés") ? api("/api/employees") : Promise.resolve([]),
    can("Voir employés") ? api("/api/leaves") : Promise.resolve([]),
    can("Voir employés") ? api("/api/departments") : Promise.resolve([]),
    can("Voir salaires") ? api("/api/payrolls") : Promise.resolve([]),
    can("Voir employés") ? api("/api/attendances") : Promise.resolve([]),
    can("Exporter rapports") ? api("/api/reports/stats") : Promise.resolve(null),
  ]);

  setReportsContent(
    stats || "Reporting avancé réservé aux rôles avec permission 'Exporter rapports'."
  );

  const totalPayroll = stats ? stats.total_payroll : payrolls.reduce((acc, payroll) => acc + Number(payroll.net_salary || 0), 0);
  const averageSalary = stats
    ? stats.average_salary
    : payrolls.length
    ? totalPayroll / payrolls.length
    : 0;
  const absenceRate = stats
    ? stats.absence_rate
    : attendances.length
    ? ((attendances.filter((attendance) => attendance.is_absent).length / attendances.length) * 100).toFixed(2)
    : 0;

  const deptMap = stats
    ? stats.employees_by_department || {}
    : departments.reduce((acc, department) => {
        acc[department.name] = (department.employees || []).length;
        return acc;
      }, {});

  $("kpiPayroll").textContent = can("Voir salaires") ? formatMoney(totalPayroll || 0) : "-";
  $("kpiAvgSalary").textContent = can("Voir salaires") ? formatMoney(averageSalary || 0) : "-";
  $("kpiAbsence").textContent = can("Voir employés") ? `${absenceRate || 0}%` : "-";
  $("kpiEmployees").textContent = can("Voir employés") ? String(employees.length) : "-";

  drawDeptChart(deptMap);
  drawLeaveChart(leaves);
}

async function loadEmployees() {
  if (!can("Voir employés")) {
    return;
  }
  const employees = await api("/api/employees");
  appState.employees = employees || [];
  appState.employeeById = (appState.employees || []).reduce((acc, employee) => {
    acc[String(employee.id)] = employee;
    return acc;
  }, {});
  populateEmployeeActionSelects();
  const canModifyEmployees = can("Modifier employés");
  renderTable(
    "employeesTable",
    canModifyEmployees ? ["ID", "Nom", "Email", "Département", "Rôle", "Statut", "Actions"] : ["ID", "Nom", "Email", "Département", "Rôle", "Statut"],
    employees.map((employee) => [
      employee.id,
      `${employee.first_name} ${employee.last_name}`,
      employee.email,
      employee.department,
      employee.role,
      employee.status,
      ...(canModifyEmployees ? [actionButtons("employee", employee.id)] : []),
    ])
  );
}

async function loadDepartments() {
  if (!can("Voir employés")) {
    return;
  }
  const departments = await api("/api/departments");
  fillSelectOptions(
    "employeeDepartmentSelect",
    departments.map((department) => ({ value: department.id, label: `${department.name} (#${department.id})` })),
    true
  );
  const canModifyEmployees = can("Modifier employés");
  renderTable(
    "departmentsTable",
    canModifyEmployees ? ["ID", "Nom", "Budget", "Manager", "Nb employés", "Actions"] : ["ID", "Nom", "Budget", "Manager", "Nb employés"],
    departments.map((department) => [
      department.id,
      department.name,
      formatMoney(department.budget),
      department.manager_id || "-",
      (department.employees || []).length,
      ...(canModifyEmployees ? [actionButtons("department", department.id)] : []),
    ])
  );
}

async function editEmployee(employeeId) {
  const employee = (appState.employees || []).find((entry) => entry.id === employeeId);
  if (!employee) {
    notify("Employé introuvable", true);
    return;
  }

  const payload = await openEditModal({
    title: "Modifier employé",
    fields: [
      { name: "first_name", label: "Prénom", value: employee.first_name || "", required: true },
      { name: "last_name", label: "Nom", value: employee.last_name || "", required: true },
      { name: "email", label: "Email", type: "email", value: employee.email || "", required: true },
      { name: "phone", label: "Téléphone", value: employee.phone || "" },
      { name: "address", label: "Adresse", value: employee.address || "" },
      {
        name: "status",
        label: "Statut",
        type: "select",
        value: employee.status || "Actif",
        options: [
          { value: "Actif", label: "Actif" },
          { value: "Suspendu", label: "Suspendu" },
          { value: "Démissionné", label: "Démissionné" },
        ],
        required: true,
      },
    ],
  });
  if (!payload) return;

  await api(`/api/employees/${employeeId}`, {
    method: "PUT",
    body: JSON.stringify({
      first_name: payload.first_name,
      last_name: payload.last_name,
      email: payload.email,
      phone: payload.phone,
      address: payload.address,
      status: payload.status,
      department_id: employee.department_id,
      role_id: employee.role_id,
    }),
  });

  notify("Employé modifié");
  await Promise.all([loadEmployees(), loadOverview(), loadAccounts()]);
}

async function deleteEmployee(employeeId) {
  const accepted = await confirmAction({
    title: "Supprimer employé",
    message: "Confirmer la suppression de cet employé ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) {
    return;
  }

  await api(`/api/employees/${employeeId}`, {
    method: "DELETE",
  });

  notify("Employé supprimé");
  await Promise.all([loadEmployees(), loadOverview(), loadAccounts(), loadDepartments()]);
}

async function editDepartment(departmentId) {
  const departments = await api("/api/departments");
  const department = (departments || []).find((entry) => entry.id === departmentId);
  if (!department) {
    notify("Département introuvable", true);
    return;
  }

  const payload = await openEditModal({
    title: "Modifier département",
    fields: [
      { name: "name", label: "Nom du département", value: department.name || "", required: true },
      { name: "budget", label: "Budget", type: "number", value: department.budget ?? 0, step: "0.01", required: true },
    ],
  });
  if (!payload) return;

  await api(`/api/departments/${departmentId}`, {
    method: "PUT",
    body: JSON.stringify({
      name: payload.name,
      budget: payload.budget,
      manager_id: department.manager_id,
    }),
  });

  notify("Département modifié");
  await Promise.all([loadDepartments(), loadOverview(), loadEmployees()]);
}

async function deleteDepartment(departmentId) {
  const accepted = await confirmAction({
    title: "Supprimer département",
    message: "Confirmer la suppression de ce département ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) {
    return;
  }

  await api(`/api/departments/${departmentId}`, {
    method: "DELETE",
  });

  notify("Département supprimé");
  await Promise.all([loadDepartments(), loadOverview(), loadEmployees()]);
}

async function loadRoles() {
  if (!(can("Voir employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role))) {
    return;
  }
  const roles = await api("/api/roles");
  let permissions = [];
  try {
    permissions = await api("/api/roles/permissions");
  } catch (_error) {
    permissions = [];
  }
  appState.roles = roles || [];

  const permissionsFromRoles = (roles || []).flatMap((role) => role.permissions || []);
  const availablePermissions = Array.from(
    new Set([...(permissions || []), ...DEFAULT_PERMISSION_NAMES, ...permissionsFromRoles])
  ).sort((left, right) => left.localeCompare(right, "fr", { sensitivity: "base" }));

  renderPermissionChecklist("rolePermissionsChecklist", availablePermissions, []);

  fillSelectOptions(
    "employeeRoleSelect",
    roles.map((role) => ({ value: role.id, label: `${role.name} (#${role.id})` })),
    false
  );
  fillSelectOptions(
    "accountRoleId",
    roles.map((role) => ({ value: role.id, label: `${role.name} (#${role.id})` })),
    false
  );

  fillSelectOptions(
    "rolePermissionRoleId",
    roles.map((role) => ({ value: role.id, label: `${role.name} (#${role.id})` })),
    false
  );

  const selectedRoleId = Number($("rolePermissionRoleId")?.value || 0);
  if (selectedRoleId) {
    const currentRole = appState.roles.find((role) => role.id === selectedRoleId);
    renderPermissionChecklist("updateRolePermissionsChecklist", availablePermissions, currentRole?.permissions || []);
  } else {
    renderPermissionChecklist("updateRolePermissionsChecklist", availablePermissions, []);
  }

  renderTable(
    "rolesTable",
    ["ID", "Rôle", "Permissions"],
    roles.map((role) => [role.id, role.name, (role.permissions || []).join(", ")])
  );
}

async function updateRolePermissions() {
  const roleId = Number($("rolePermissionRoleId")?.value || 0);
  const permissionNames = getCheckedPermissions("updateRolePermissionsChecklist");

  if (!roleId) {
    notify("Sélectionne un rôle", true);
    return;
  }

  await api(`/api/roles/${roleId}/permissions`, {
    method: "PATCH",
    body: JSON.stringify({ permission_names: permissionNames }),
  });

  notify("Permissions du rôle mises à jour");
  await Promise.all([loadRoles(), loadEmployees(), loadAccounts()]);
}

async function loadPayrolls() {
  if (!can("Voir salaires")) {
    return;
  }
  const payrolls = await api("/api/payrolls");
  const canManage = can("Voir salaires");
  renderTable(
    "payrollsTable",
    canManage
      ? ["ID", "Employé", "Mois", "Base", "Prime", "Déductions", "Impôts", "Net", "Date", "Actions"]
      : ["ID", "Employé", "Mois", "Base", "Prime", "Déductions", "Impôts", "Net", "Date"],
    payrolls.map((payroll) => [
      payroll.id,
      payroll.employee_name,
      payroll.payroll_month || "-",
      formatMoney(payroll.base_salary),
      formatMoney(payroll.bonus),
      formatMoney(payroll.deductions),
      formatMoney(payroll.taxes),
      formatMoney(payroll.net_salary),
      new Date(payroll.paid_at).toLocaleString("fr-FR"),
      ...(canManage ? [actionButtons("payroll", payroll.id)] : []),
    ])
  );
}

async function loadAttendances() {
  if (!can("Voir employés")) {
    return;
  }
  const attendances = await api("/api/attendances");
  const canManage = can("Voir employés");
  renderTable(
    "attendancesTable",
    canManage
      ? ["ID", "Employé", "Entrée", "Sortie", "Heures", "Retard", "Absence", "Actions"]
      : ["ID", "Employé", "Entrée", "Sortie", "Heures", "Retard", "Absence"],
    attendances.map((attendance) => [
      attendance.id,
      getEmployeeDisplay(attendance.employee_id),
      new Date(attendance.check_in).toLocaleString("fr-FR"),
      attendance.check_out ? new Date(attendance.check_out).toLocaleString("fr-FR") : "-",
      attendance.worked_hours,
      attendance.late_minutes,
      attendance.is_absent ? "Oui" : "Non",
      ...(canManage ? [actionButtons("attendance", attendance.id)] : []),
    ])
  );
}

async function loadAttendanceMonthlySummary(month) {
  if (!month) {
    throw new Error("Sélectionne un mois");
  }

  const summary = await api(`/api/attendances/summary/monthly?month=${encodeURIComponent(month)}`);
  renderTable(
    "attendanceSummaryTable",
    ["Employé", "Mois", "Présences", "Absences", "Absences non justifiées"],
    (summary || []).map((item) => [
      item.employee_name,
      item.month,
      item.presence_days,
      item.absence_days,
      item.unjustified_absence_days,
    ])
  );
}

async function loadLeaves() {
  // Allow all authenticated users to request and view their own leaves.
  // Server filters results: HR (permission 'Valider congés') will receive all leaves.
  const leaves = await api("/api/leaves");
  const canManage = can("Valider congés");
  renderTable(
    "leavesTable",
    canManage ? ["ID", "Employé", "Période", "Motif", "Statut", "Actions"] : ["ID", "Employé", "Période", "Motif", "Statut"],
    leaves.map((leave) => [
      leave.id,
      getEmployeeDisplay(leave.employee_id),
      `${leave.start_date} → ${leave.end_date}`,
      leave.reason,
      leave.status,
      ...(canManage ? [actionButtons("leave", leave.id)] : []),
    ])
  );
}

async function loadContracts() {
  if (!can("Voir employés")) {
    return;
  }
  const contracts = await api("/api/contracts");
  const canManage = can("Modifier employés");
  renderTable(
    "contractsTable",
    canManage
      ? ["ID", "Employé", "Type", "Début", "Fin", "Salaire", "Actions"]
      : ["ID", "Employé", "Type", "Début", "Fin", "Salaire"],
    contracts.map((contract) => [
      contract.id,
      getEmployeeDisplay(contract.employee_id),
      contract.contract_type,
      contract.start_date,
      contract.end_date || "-",
      formatMoney(contract.contractual_salary),
      ...(canManage ? [actionButtons("contract", contract.id)] : []),
    ])
  );
}

async function editPayroll(payrollId) {
  const payrolls = await api("/api/payrolls");
  const payroll = (payrolls || []).find((entry) => entry.id === payrollId);
  if (!payroll) throw new Error("Paie introuvable");

  const payload = await openEditModal({
    title: "Modifier paie",
    fields: [
      { name: "bonus", label: "Prime", type: "number", value: payroll.bonus ?? 0, step: "0.01", required: true },
      { name: "deductions", label: "Déductions", type: "number", value: payroll.deductions ?? 0, step: "0.01", required: true },
      { name: "taxes", label: "Impôts", type: "number", value: payroll.taxes ?? 0, step: "0.01", required: true },
    ],
  });
  if (!payload) return;

  await api(`/api/payrolls/${payrollId}`, {
    method: "PUT",
    body: JSON.stringify({
      bonus: payload.bonus,
      deductions: payload.deductions,
      taxes: payload.taxes,
    }),
  });

  notify("Paie modifiée");
  await Promise.all([loadPayrolls(), loadOverview()]);
}

async function deletePayroll(payrollId) {
  const accepted = await confirmAction({
    title: "Supprimer paie",
    message: "Confirmer la suppression de cette paie ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) return;
  await api(`/api/payrolls/${payrollId}`, { method: "DELETE" });
  notify("Paie supprimée");
  await Promise.all([loadPayrolls(), loadOverview()]);
}

async function editAttendance(attendanceId) {
  const attendances = await api("/api/attendances");
  const attendance = (attendances || []).find((entry) => entry.id === attendanceId);
  if (!attendance) throw new Error("Pointage introuvable");

  const payload = await openEditModal({
    title: "Modifier pointage",
    fields: [
      { name: "late_minutes", label: "Retard (minutes)", type: "number", value: attendance.late_minutes ?? 0, min: 0, required: true },
      {
        name: "is_absent",
        label: "Absence non justifiée",
        type: "select",
        value: attendance.is_absent ? "oui" : "non",
        options: [
          { value: "non", label: "Non" },
          { value: "oui", label: "Oui" },
        ],
        required: true,
      },
    ],
  });
  if (!payload) return;

  await api(`/api/attendances/${attendanceId}`, {
    method: "PUT",
    body: JSON.stringify({
      late_minutes: payload.late_minutes,
      is_absent: normalizeSearchText(payload.is_absent) === "oui",
    }),
  });

  notify("Pointage modifié");
  await Promise.all([loadAttendances(), loadOverview()]);
}

async function deleteAttendance(attendanceId) {
  const accepted = await confirmAction({
    title: "Supprimer pointage",
    message: "Confirmer la suppression de ce pointage ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) return;
  await api(`/api/attendances/${attendanceId}`, { method: "DELETE" });
  notify("Pointage supprimé");
  await Promise.all([loadAttendances(), loadOverview()]);
}

async function editLeave(leaveId) {
  const leaves = await api("/api/leaves");
  const leave = (leaves || []).find((entry) => entry.id === leaveId);
  if (!leave) throw new Error("Congé introuvable");

  const payload = await openEditModal({
    title: "Modifier congé",
    fields: [
      {
        name: "status",
        label: "Statut",
        type: "select",
        value: leave.status || "En attente",
        options: [
          { value: "En attente", label: "En attente" },
          { value: "Approuvé", label: "Approuvé" },
          { value: "Rejeté", label: "Rejeté" },
        ],
        required: true,
      },
      {
        name: "decision_comment",
        label: "Justification (optionnel)",
        type: "textarea",
        value: leave.decision_comment || "",
        placeholder: "Ajouter une justification (ex: raison du refus)",
      },
    ],
  });
  if (!payload) return;

  await api(`/api/leaves/${leaveId}`, {
    method: "PUT",
    body: JSON.stringify({ status: payload.status, decision_comment: payload.decision_comment }),
  });
  notify("Congé mis à jour");
  await Promise.all([loadLeaves(), loadOverview()]);
}

async function deleteLeave(leaveId) {
  const accepted = await confirmAction({
    title: "Supprimer congé",
    message: "Confirmer la suppression de ce congé ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) return;
  await api(`/api/leaves/${leaveId}`, { method: "DELETE" });
  notify("Congé supprimé");
  await Promise.all([loadLeaves(), loadOverview()]);
}

async function editContract(contractId) {
  const contracts = await api("/api/contracts");
  const contract = (contracts || []).find((entry) => entry.id === contractId);
  if (!contract) throw new Error("Contrat introuvable");

  const payload = await openEditModal({
    title: "Modifier contrat",
    fields: [
      {
        name: "contractual_salary",
        label: "Salaire contractuel",
        type: "number",
        value: contract.contractual_salary ?? 0,
        step: "0.01",
        min: 0,
        required: true,
      },
    ],
  });
  if (!payload) return;

  await api(`/api/contracts/${contractId}`, {
    method: "PUT",
    body: JSON.stringify({ contractual_salary: payload.contractual_salary }),
  });
  notify("Contrat modifié");
  await Promise.all([loadContracts(), loadOverview()]);
}

async function deleteContract(contractId) {
  const accepted = await confirmAction({
    title: "Supprimer contrat",
    message: "Confirmer la suppression de ce contrat ?",
    confirmLabel: "Supprimer",
  });
  if (!accepted) return;
  await api(`/api/contracts/${contractId}`, { method: "DELETE" });
  notify("Contrat supprimé");
  await Promise.all([loadContracts(), loadOverview()]);
}

async function loadAccounts() {
  if (!(can("Modifier employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role))) {
    return;
  }
  const accounts = await api("/api/accounts");
  appState.accounts = accounts || [];
  populateAccountActionSelect();
  renderTable(
    "accountsTable",
    ["ID", "Username", "Agent", "Matricule", "Rôle", "Statut", "Reset requis"],
    accounts.map((account) => [
      account.id,
      account.username,
      account.employee_name || "-",
      account.matricule || "-",
      account.role || "-",
      account.status || "-",
      account.must_change_password ? "Oui" : "Non",
    ])
  );
}

function updateMessagesUnreadBadge(messages = []) {
  const badge = $("messagesUnreadBadge");
  if (!badge) return;

  const unreadCount = (messages || []).filter((message) => !message.is_read).length;
  if (unreadCount <= 0) {
    badge.classList.add("hidden");
    badge.textContent = "0";
    return;
  }

  badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
  badge.classList.remove("hidden");
}

function setMessagesUnreadBadgeCount(unreadCount) {
  const badge = $("messagesUnreadBadge");
  if (!badge) return;

  const count = Number(unreadCount || 0);
  if (count <= 0) {
    badge.classList.add("hidden");
    badge.textContent = "0";
    return;
  }

  badge.textContent = count > 99 ? "99+" : String(count);
  badge.classList.remove("hidden");
}

function isMessagesSectionActive() {
  const section = $("section-messages");
  return !!section && section.classList.contains("active");
}

function isAccountingSectionActive() {
  const section = $("section-accounting");
  return !!section && section.classList.contains("active");
}

async function loadMessageRecipients() {
  const recipients = await api("/api/messages/recipients");
  appState.messageRecipients = recipients || [];
  populateMessageRecipientSelect();
}

async function loadConversations(query = "") {
  const conversations = await api(`/api/messages/conversations?q=${encodeURIComponent(query || "")}`);
  appState.conversations = conversations || [];
  updateMessagesUnreadBadgeFromConversations(appState.conversations);
  renderConversations(appState.conversations);
}

async function loadConversationThread(userId, options = {}) {
  const { beforeId = null } = options;
  if (!userId) {
    renderChatThread([]);
    return;
  }

  const limit = 40;
  const queryParams = new URLSearchParams({ limit: String(limit) });
  if (beforeId) {
    queryParams.set("before_id", String(beforeId));
  }

  const messages = await api(`/api/messages/thread/${userId}?${queryParams.toString()}`);
  const chunk = messages || [];

  if (beforeId) {
    appState.activeThreadMessages = [...chunk, ...(appState.activeThreadMessages || [])];
  } else {
    appState.activeThreadMessages = chunk;
  }

  const firstMessage = (appState.activeThreadMessages || [])[0];
  appState.oldestThreadMessageId = firstMessage ? Number(firstMessage.id) : null;
  appState.hasMoreThreadMessages = chunk.length >= limit && !!appState.oldestThreadMessageId;
  renderChatThread(appState.activeThreadMessages || []);
}

async function loadOlderThreadMessages() {
  if (!appState.activeChatUserId || !appState.hasMoreThreadMessages || appState.isLoadingOlderMessages) {
    return;
  }

  appState.isLoadingOlderMessages = true;
  const button = $("chatLoadMoreBtn");
  if (button) {
    button.disabled = true;
    button.textContent = "Chargement...";
  }

  try {
    await loadConversationThread(appState.activeChatUserId, { beforeId: appState.oldestThreadMessageId });
  } finally {
    appState.isLoadingOlderMessages = false;
  }
}

async function loadMessagesUnreadCount() {
  const result = await api("/api/messages/unread-count");
  setMessagesUnreadBadgeCount(result?.unread_count || 0);
}

async function refreshMessagesSilently() {
  try {
    if (isMessagesSectionActive()) {
      const query = ($("messagesSearch")?.value || "").trim();
      await loadConversations(query);
      if (appState.activeChatUserId) {
        await loadConversationThread(appState.activeChatUserId);
      }
    } else {
      await loadMessagesUnreadCount();
    }
  } catch (_error) {}
}

function stopMessagesAutoRefresh() {
  if (appState.messagesAutoRefreshTimer) {
    clearInterval(appState.messagesAutoRefreshTimer);
    appState.messagesAutoRefreshTimer = null;
  }
}

function startMessagesAutoRefresh() {
  stopMessagesAutoRefresh();
  appState.messagesAutoRefreshTimer = setInterval(() => {
    if (!appState.token || appState.mustChangePassword) {
      return;
    }
    refreshMessagesSilently();
  }, 30000);
}

async function openConversation(userId) {
  const conversationId = Number(userId || 0);
  if (!conversationId) return;
  appState.activeChatUserId = conversationId;
  appState.activeChatRecipientEmployeeId = null;

  renderConversations(appState.conversations || []);
  const selectedConversation = (appState.conversations || []).find((item) => Number(item.user_id) === conversationId);
  setActiveConversationInfo(selectedConversation || null);
  await loadConversationThread(conversationId);

  const query = ($("messagesSearch")?.value || "").trim();
  await loadConversations(query);
}

async function startNewConversation() {
  const select = $("newConversationRecipient");
  if (!select) return;

  const selectedValue = String(select.value || "").trim();
  if (!selectedValue) {
    throw new Error("Sélectionne un agent pour démarrer la discussion");
  }

  const [kind, rawId] = selectedValue.split(":");
  const parsedId = Number(rawId || 0);
  if (!parsedId) {
    throw new Error("Sélection invalide");
  }

  const recipient = (appState.messageRecipients || []).find((item) => {
    if (kind === "u") {
      return Number(item.user_id || 0) === parsedId;
    }
    return Number(item.employee_id || 0) === parsedId;
  });

  if (!recipient) {
    throw new Error("Destinataire introuvable");
  }

  const userId = Number(recipient.user_id || 0);
  const employeeId = Number(recipient.employee_id || 0);

  if (userId) {
    const existingConversation = (appState.conversations || []).find((item) => Number(item.user_id) === userId);
    if (existingConversation) {
      await openConversation(userId);
      return;
    }

    appState.activeChatUserId = userId;
    appState.activeChatRecipientEmployeeId = null;
  } else {
    appState.activeChatUserId = null;
    appState.activeChatRecipientEmployeeId = employeeId || null;
  }
  appState.activeThreadMessages = [];
  appState.oldestThreadMessageId = null;
  appState.hasMoreThreadMessages = false;

  setActiveConversationInfo(
    recipient
      ? {
          user_id: userId || null,
          username: recipient.username,
          display_name: recipient.name,
        }
      : {
          user_id: userId,
          display_name: "Nouvelle discussion",
        }
  );
  renderConversations(appState.conversations || []);
  renderChatThread([]);
  $("chatMessageInput")?.focus();
}

async function editOwnMessage(messageId) {
  const id = Number(messageId || 0);
  if (!id) return;

  const message = (appState.activeThreadMessages || []).find((item) => Number(item.id) === id);
  if (!message) {
    throw new Error("Message introuvable");
  }

  if (!message.can_edit) {
    throw new Error("Le délai de modification est dépassé");
  }

  const payload = await openEditModal({
    title: "Modifier le message",
    submitLabel: "Mettre à jour",
    fields: [
      {
        name: "content",
        label: "Message",
        type: "text",
        value: message.content || "",
        required: true,
      },
    ],
  });

  if (!payload) return;
  await api(`/api/messages/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ content: payload.content }),
  });

  if (appState.activeChatUserId) {
    await openConversation(appState.activeChatUserId);
  }
}

async function deleteOwnMessage(messageId) {
  const id = Number(messageId || 0);
  if (!id) return;

  const message = (appState.activeThreadMessages || []).find((item) => Number(item.id) === id);
  if (!message) {
    throw new Error("Message introuvable");
  }

  if (!message.can_delete) {
    throw new Error("Le délai de suppression est dépassé");
  }

  const confirmed = await confirmAction({
    title: "Supprimer le message",
    message: "Ce message sera supprimé définitivement. Continuer ?",
    confirmLabel: "Supprimer",
  });
  if (!confirmed) return;

  await api(`/api/messages/${id}`, { method: "DELETE" });
  if (appState.activeChatUserId) {
    await openConversation(appState.activeChatUserId);
  }
}

async function loadAccountLogs() {
  if (!(can("Modifier employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role))) {
    return;
  }

  const query = buildLogFiltersQuery();
  const logs = await api(`/api/accounts/activity${query ? `?${query}` : ""}`);
  renderTable(
    "accountLogsTable",
    ["ID", "Utilisateur", "Action", "Date"],
    logs.map((log) => [
      log.id,
      log.username,
      log.action,
      new Date(log.created_at).toLocaleString("fr-FR"),
    ])
  );
}

function buildLogFiltersQuery() {
  const username = ($("logUsername")?.value || "").trim();
  const action = ($("logAction")?.value || "").trim();
  const startDate = ($("logStartDate")?.value || "").trim();
  const endDate = ($("logEndDate")?.value || "").trim();

  const params = new URLSearchParams();
  if (username) params.set("username", username);
  if (action) params.set("action", action);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);

  return params.toString();
}

async function exportAccountLogs(format) {
  if (!(can("Modifier employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role))) {
    notify("Accès refusé", true);
    return;
  }

  const query = buildLogFiltersQuery();
  const endpoint = `/api/accounts/activity/export.${format}${query ? `?${query}` : ""}`;

  const response = await fetch(endpoint, {
    headers: {
      Authorization: `Bearer ${appState.token}`,
    },
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      errorMessage = data.error || data.message || errorMessage;
    } catch (_error) {}
    throw new Error(errorMessage);
  }

  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `activity_logs.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
}

async function refreshAll() {
  if (appState.mustChangePassword) {
    return;
  }
  const messageQuery = ($("messagesSearch")?.value || "").trim();
  const jobs = [loadOverview(), loadLeaves(), loadConversations(messageQuery), loadMessageRecipients()];
  if (can("Voir employés")) {
    await loadEmployees();
    jobs.push(loadDepartments(), loadAttendances(), loadContracts());
  }
  if (can("Voir salaires")) {
    jobs.push(loadPayrolls());
  }
  if (can("Voir employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role)) {
    jobs.push(loadRoles());
  }
  if (can("Modifier employés") && ["SuperAdmin", "Admin RH", "RH"].includes(appState.role)) {
    jobs.push(loadAccounts(), loadAccountLogs());
  }
  await Promise.all(jobs);

  if (isAccountingSectionActive()) {
    await loadAccountingSection();
  }

  if (appState.activeChatUserId && isMessagesSectionActive()) {
    await loadConversationThread(appState.activeChatUserId);
  }
}

async function updateAccountRole() {
  const userId = Number($("accountUserId").value);
  const roleId = Number($("accountRoleId").value);
  if (!userId || !roleId) {
    notify("Sélectionne un agent et un rôle", true);
    return;
  }
  await api(`/api/accounts/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role_id: roleId }),
  });
  notify("Rôle du compte mis à jour");
  await Promise.all([loadAccounts(), loadAccountLogs(), loadRoles(), loadEmployees()]);
}

async function updateAccountStatus() {
  const userId = Number($("accountUserId").value);
  const status = $("accountStatus").value;
  if (!userId || !status) {
    notify("Sélectionne un agent et un statut", true);
    return;
  }
  await api(`/api/accounts/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  notify("Statut du compte mis à jour");
  await Promise.all([loadAccounts(), loadAccountLogs(), loadEmployees()]);
}

async function resetAccountPassword() {
  const userId = Number($("accountUserId").value);
  if (!userId) {
    notify("Sélectionne un agent", true);
    return;
  }
  await api(`/api/accounts/${userId}/reset-password`, {
    method: "PATCH",
  });
  notify("Mot de passe réinitialisé (mot de passe par défaut)");
  await Promise.all([loadAccounts(), loadAccountLogs()]);
}

function bindForms() {
  $("employeeForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), ["role_id", "department_id"]);
      await api("/api/employees", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Employé créé avec succès");
      await Promise.all([loadEmployees(), loadOverview()]);
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("departmentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), ["budget"]);
      await api("/api/departments", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Département créé");
      await Promise.all([loadDepartments(), loadOverview()]);
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("roleForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = getFormJSON(event.target);
      const selectedPermissions = getCheckedPermissions("rolePermissionsChecklist");

      await api("/api/roles", {
        method: "POST",
        body: JSON.stringify({
          name: payload.name,
          permission_names: selectedPermissions,
        }),
      });
      event.target.reset();
      setCheckedPermissions("rolePermissionsChecklist", []);
      notify("Rôle créé");
      await loadRoles();
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("payrollForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), [
        "employee_id",
        "base_salary",
        "bonus",
        "overtime_hours",
        "deductions",
        "taxes",
      ]);
      if (!payload.employee_id) {
        throw new Error("Sélectionne un employé valide dans la liste");
      }
      await api("/api/payrolls", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Fiche de paie créée");
      await Promise.all([loadPayrolls(), loadOverview()]);
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("attendanceForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), ["employee_id", "late_minutes"]);
      if (!payload.employee_id) {
        throw new Error("Sélectionne un employé valide dans la liste");
      }

      payload.is_absent = String(payload.is_absent || "false") === "true";
      await api("/api/attendances/checkin", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Pointage d'entrée enregistré");
      await Promise.all([loadAttendances(), loadOverview()]);
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("leaveForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), ["employee_id"]);
      if (!payload.employee_id) {
        throw new Error("Sélectionne un employé valide dans la liste");
      }
      await api("/api/leaves", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Demande de congé envoyée");
      await Promise.all([loadLeaves(), loadOverview()]);
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("contractForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = normalizePayload(getFormJSON(event.target), ["employee_id", "contractual_salary"]);
      if (!payload.employee_id) {
        throw new Error("Sélectionne un employé valide dans la liste");
      }
      await api("/api/contracts", { method: "POST", body: JSON.stringify(payload) });
      event.target.reset();
      notify("Contrat créé");
      await loadContracts();
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("chatComposerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const activeUserId = Number(appState.activeChatUserId || 0);
      const activeRecipientEmployeeId = Number(appState.activeChatRecipientEmployeeId || 0);
      if (!activeUserId && !activeRecipientEmployeeId) {
        throw new Error("Sélectionne d'abord une discussion");
      }

      const payload = getFormJSON(event.target);
      if (!String(payload.content || "").trim()) {
        throw new Error("Le message ne peut pas être vide");
      }

      if (activeUserId) {
        await api(`/api/messages/thread/${activeUserId}`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } else {
        const createdMessage = await api(`/api/messages`, {
          method: "POST",
          body: JSON.stringify({
            recipient_employee_id: activeRecipientEmployeeId,
            content: payload.content,
          }),
        });
        appState.activeChatUserId = Number(createdMessage?.recipient_user_id || 0) || null;
        appState.activeChatRecipientEmployeeId = null;
      }

      event.target.reset();
      await loadMessageRecipients();
      if (appState.activeChatUserId) {
        await openConversation(appState.activeChatUserId);
      } else {
        const query = ($("messagesSearch")?.value || "").trim();
        await loadConversations(query);
      }
    } catch (error) {
      notify(error.message, true);
    }
  });
}

function bindPasswordModal() {
  $("passwordUpdateForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = getFormJSON(event.target);
      const currentPassword = (payload.current_password || "").trim();
      const newPassword = (payload.new_password || "").trim();
      const confirmNewPassword = (payload.confirm_new_password || "").trim();

      if (currentPassword.length < 6 || newPassword.length < 6 || confirmNewPassword.length < 6) {
        throw new Error("Le mot de passe doit contenir au moins 6 caractères");
      }

      if (currentPassword === newPassword) {
        throw new Error("Le nouveau mot de passe doit être différent de l'actuel");
      }

      if (newPassword !== confirmNewPassword) {
        throw new Error("La confirmation du nouveau mot de passe ne correspond pas");
      }

      const response = await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (response.access_token) {
        appState.token = response.access_token;
        localStorage.setItem("ems_token", response.access_token);
      }
      setMustChangePassword(false);
      event.target.reset();
      notify("Mot de passe mis à jour");
      await refreshAll();
    } catch (error) {
      notify(error.message, true);
    }
  });
}

function setupAuthFlow() {
  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const username = $("username").value.trim();
      const password = $("password").value;
      const loginResult = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });

      appState.token = loginResult.access_token;

      localStorage.setItem("ems_token", appState.token);

      const me = await api("/api/auth/me");
      appState.username = me.username || loginResult.username || "";
      appState.role = me.role || loginResult.role || "";
      appState.permissions = me.permissions || loginResult.permissions || [];
      updateAccountHolderInfo(
        me.account_holder_name || loginResult.account_holder_name || appState.username,
        me.account_holder_function || loginResult.account_holder_function || appState.role
      );

      localStorage.setItem("ems_username", appState.username);
      localStorage.setItem("ems_role", appState.role);
      localStorage.setItem("ems_permissions", JSON.stringify(appState.permissions));

      renderOwnerAccountInfo();
      ensureSectionAccess();
      applyFormPermissions();
      $("loginScreen").classList.add("hidden");
      $("appShell").classList.remove("hidden");
      setMustChangePassword(!!(me.must_change_password ?? loginResult.must_change_password));
      await loadReportsSection();
      notify("Connexion réussie");
      if (!appState.mustChangePassword) {
        await refreshAll();
      }
      startMessagesAutoRefresh();
    } catch (error) {
      notify(error.message, true);
    }
  });

  $("logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("ems_token");
    localStorage.removeItem("ems_username");
    localStorage.removeItem("ems_role");
    localStorage.removeItem("ems_permissions");
    localStorage.removeItem("ems_must_change_password");
    appState.token = "";
    appState.username = "";
    appState.role = "";
    appState.permissions = [];
    clearAccountHolderInfo();
    renderOwnerAccountInfo();
    setMustChangePassword(false);
    stopMessagesAutoRefresh();
    $("appShell").classList.add("hidden");
    $("loginScreen").classList.remove("hidden");
    notify("Déconnecté");
  });

  if (appState.token) {
    api("/api/auth/me")
      .then(async (me) => {
        appState.username = me.username || appState.username;
        appState.role = me.role || appState.role;
        appState.permissions = me.permissions || [];
        updateAccountHolderInfo(
          me.account_holder_name || appState.username,
          me.account_holder_function || appState.role
        );
        localStorage.setItem("ems_username", appState.username);
        localStorage.setItem("ems_role", appState.role);
        localStorage.setItem("ems_permissions", JSON.stringify(appState.permissions));

        renderOwnerAccountInfo();
        ensureSectionAccess();
        applyFormPermissions();
        $("loginScreen").classList.add("hidden");
        $("appShell").classList.remove("hidden");
        setMustChangePassword(!!me.must_change_password);
        await loadReportsSection();
        if (!appState.mustChangePassword) {
          await refreshAll();
        }
        startMessagesAutoRefresh();
      })
      .catch((error) => {
        localStorage.removeItem("ems_token");
        localStorage.removeItem("ems_username");
        localStorage.removeItem("ems_role");
        localStorage.removeItem("ems_permissions");
        localStorage.removeItem("ems_must_change_password");
        appState.token = "";
        appState.username = "";
        appState.role = "";
        appState.permissions = [];
        clearAccountHolderInfo();
        renderOwnerAccountInfo();
        setMustChangePassword(false);
        stopMessagesAutoRefresh();
        $("appShell").classList.add("hidden");
        $("loginScreen").classList.remove("hidden");
        notify(`Session expirée: ${error.message}`, true);
      });
  }
}

function setupActions() {
  $("refreshBtn").addEventListener("click", async () => {
    try {
      await refreshAll();
      notify("Données rafraîchies");
    } catch (error) {
      notify(error.message, true);
    }
  });

  const roleButton = $("btnAccountRole");
  const statusButton = $("btnAccountStatus");
  const resetButton = $("btnAccountReset");

  if (roleButton) {
    roleButton.addEventListener("click", async () => {
      try {
        await updateAccountRole();
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (statusButton) {
    statusButton.addEventListener("click", async () => {
      try {
        await updateAccountStatus();
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", async () => {
      try {
        await resetAccountPassword();
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  const logsFilterButton = $("btnLogsFilter");
  const logsClearButton = $("btnLogsClear");
  const logsExportCsvButton = $("btnLogsExportCsv");
  const logsExportPdfButton = $("btnLogsExportPdf");
  const rolePermissionsButton = $("btnRolePermissions");
  const rolePermissionsRoleSelect = $("rolePermissionRoleId");
  const attendanceCheckoutButton = $("btnAttendanceCheckout");
  const attendanceSummaryButton = $("btnAttendanceSummary");
  const messagesRefreshButton = $("btnMessagesRefresh");
  const messagesSearchInput = $("messagesSearch");
  const newConversationButton = $("btnNewConversation");
  const chatMessagesContainer = $("chatMessages");

  ["payrollEmployeeQuery", "attendanceEmployeeQuery", "leaveEmployeeQuery", "contractEmployeeQuery"].forEach((queryId) => {
    const input = $(queryId);
    if (!input) return;
    input.addEventListener("input", () => {
      populateEmployeeActionSelects();
    });
  });

  const accountUserQuery = $("accountUserQuery");
  if (accountUserQuery) {
    accountUserQuery.addEventListener("input", () => {
      populateAccountActionSelect();
    });
  }

  if (logsFilterButton) {
    logsFilterButton.addEventListener("click", async () => {
      try {
        await loadAccountLogs();
        notify("Filtres de logs appliqués");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (logsClearButton) {
    logsClearButton.addEventListener("click", async () => {
      if ($("logUsername")) $("logUsername").value = "";
      if ($("logAction")) $("logAction").value = "";
      if ($("logStartDate")) $("logStartDate").value = "";
      if ($("logEndDate")) $("logEndDate").value = "";
      try {
        await loadAccountLogs();
        notify("Filtres de logs réinitialisés");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (logsExportCsvButton) {
    logsExportCsvButton.addEventListener("click", async () => {
      try {
        await exportAccountLogs("csv");
        notify("Export CSV lancé");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (logsExportPdfButton) {
    logsExportPdfButton.addEventListener("click", async () => {
      try {
        await exportAccountLogs("pdf");
        notify("Export PDF lancé");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (rolePermissionsRoleSelect) {
    rolePermissionsRoleSelect.addEventListener("change", () => {
      const roleId = Number(rolePermissionsRoleSelect.value || 0);
      const role = appState.roles.find((entry) => entry.id === roleId);
      setCheckedPermissions("updateRolePermissionsChecklist", role?.permissions || []);
    });
  }

  if (rolePermissionsButton) {
    rolePermissionsButton.addEventListener("click", async () => {
      try {
        await updateRolePermissions();
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (attendanceCheckoutButton) {
    attendanceCheckoutButton.addEventListener("click", async () => {
      try {
        const employeeId = Number($("attendanceEmployeeId")?.value || 0);
        const checkOut = $("attendanceCheckOutAt")?.value || "";
        if (!employeeId) {
          throw new Error("Sélectionne un employé");
        }
        if (!checkOut) {
          throw new Error("Saisis la date/heure de sortie");
        }

        await api("/api/attendances/checkout-employee", {
          method: "POST",
          body: JSON.stringify({ employee_id: employeeId, check_out: checkOut }),
        });

        notify("Pointage de sortie enregistré");
        await Promise.all([loadAttendances(), loadOverview()]);
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (attendanceSummaryButton) {
    attendanceSummaryButton.addEventListener("click", async () => {
      try {
        const month = $("attendanceSummaryMonth")?.value || "";
        await loadAttendanceMonthlySummary(month);
        notify("Synthèse mensuelle chargée");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (messagesRefreshButton) {
    messagesRefreshButton.addEventListener("click", async () => {
      try {
        const query = ($("messagesSearch")?.value || "").trim();
        await loadConversations(query);
        if (appState.activeChatUserId) {
          await loadConversationThread(appState.activeChatUserId);
        }
        notify("Messagerie actualisée");
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (messagesSearchInput) {
    messagesSearchInput.addEventListener("input", async () => {
      try {
        await loadConversations((messagesSearchInput.value || "").trim());
      } catch (_error) {}
    });
  }

  if (newConversationButton) {
    newConversationButton.addEventListener("click", async () => {
      try {
        await startNewConversation();
      } catch (error) {
        notify(error.message, true);
      }
    });
  }

  if (chatMessagesContainer) {
    chatMessagesContainer.addEventListener("scroll", () => {
      if (chatMessagesContainer.scrollTop <= 24) {
        loadOlderThreadMessages().catch(() => {});
      }
    });
  }

  document.addEventListener("click", async (event) => {
    const loadMoreButton = event.target.closest("#chatLoadMoreBtn");
    if (loadMoreButton) {
      try {
        await loadOlderThreadMessages();
      } catch (error) {
        notify(error.message, true);
      }
      return;
    }

    const chatConversationButton = event.target.closest("[data-chat-userid]");
    if (chatConversationButton) {
      const userId = Number(chatConversationButton.dataset.chatUserid || 0);
      if (!userId) return;
      try {
        await openConversation(userId);
      } catch (error) {
        notify(error.message, true);
      }
      return;
    }

    const chatActionButton = event.target.closest("[data-chat-action][data-message-id]");
    if (chatActionButton) {
      const action = String(chatActionButton.dataset.chatAction || "").trim();
      const messageId = Number(chatActionButton.dataset.messageId || 0);
      if (!messageId) return;

      try {
        if (action === "edit") {
          await editOwnMessage(messageId);
          notify("Message modifié");
        } else if (action === "delete") {
          await deleteOwnMessage(messageId);
          notify("Message supprimé");
        }
      } catch (error) {
        notify(error.message, true);
      }
      return;
    }

    const actionButton = event.target.closest("[data-entity][data-action][data-id]");
    if (!actionButton) return;

    const entity = actionButton.dataset.entity;
    const action = actionButton.dataset.action;
    const id = Number(actionButton.dataset.id || 0);
    if (!id) return;

    try {
      if (entity === "employee" && action === "edit") {
        await editEmployee(id);
      } else if (entity === "employee" && action === "delete") {
        await deleteEmployee(id);
      } else if (entity === "department" && action === "edit") {
        await editDepartment(id);
      } else if (entity === "department" && action === "delete") {
        await deleteDepartment(id);
      } else if (entity === "payroll" && action === "edit") {
        await editPayroll(id);
      } else if (entity === "payroll" && action === "delete") {
        await deletePayroll(id);
      } else if (entity === "attendance" && action === "edit") {
        await editAttendance(id);
      } else if (entity === "attendance" && action === "delete") {
        await deleteAttendance(id);
      } else if (entity === "leave" && action === "edit") {
        await editLeave(id);
      } else if (entity === "leave" && action === "delete") {
        await deleteLeave(id);
      } else if (entity === "contract" && action === "edit") {
        await editContract(id);
      } else if (entity === "contract" && action === "delete") {
        await deleteContract(id);
      }
    } catch (error) {
      notify(error.message, true);
    }
  });

}

function init() {
  setReportsContent("Ouvre cette section pour charger le reporting.");
  setAccountingContent("Ouvre cette section pour charger la comptabilité.");
  renderOwnerAccountInfo();
  bindNavigation();
  bindForms();
  bindPasswordModal();
  setupAuthFlow();
  setupActions();
  ensureSectionAccess();
  applyFormPermissions();
  setMustChangePassword(appState.mustChangePassword);
}

init();
