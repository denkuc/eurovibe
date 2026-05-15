function setCopyButtonState(button, text) {
  const originalText = button.dataset.originalText || button.textContent;
  button.dataset.originalText = originalText;
  button.textContent = text;
  setTimeout(() => {
    button.textContent = originalText;
  }, 1400);
}

function fallbackCopy(source) {
  source.focus();
  source.select();
  source.setSelectionRange(0, source.value.length);
  return document.execCommand("copy");
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-button]");
  if (!button) {
    return;
  }

  const row = button.closest(".copy-row");
  const source = row ? row.querySelector("[data-copy-source]") : null;
  if (!source) {
    return;
  }

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(source.value);
    } else if (!fallbackCopy(source)) {
      throw new Error("Copy failed");
    }
    setCopyButtonState(button, "Скопійовано");
  } catch {
    fallbackCopy(source);
    setCopyButtonState(button, "Виділено");
  }
});

document.addEventListener("click", (event) => {
  const openButton = event.target.closest("[data-dialog-open]");
  if (openButton) {
    const dialog = document.getElementById(openButton.dataset.dialogOpen);
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
    }
    return;
  }

  const closeButton = event.target.closest("[data-dialog-close]");
  if (closeButton) {
    const dialog = closeButton.closest("dialog");
    if (dialog) {
      dialog.close();
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.isComposing || event.defaultPrevented) {
    return;
  }
  const target = event.target;
  if (!target || !target.form || target.matches("textarea, button, [type='submit']")) {
    return;
  }
  const submitButton = target.form.querySelector("button[type='submit'], input[type='submit']");
  if (!submitButton || submitButton.disabled) {
    return;
  }
  event.preventDefault();
  submitButton.click();
});

document.addEventListener("DOMContentLoaded", () => {
  const refreshTarget = document.querySelector("[data-poll-refresh]");
  if (!refreshTarget) {
    return;
  }

  const seconds = Number(refreshTarget.dataset.pollRefresh || 12);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return;
  }

  setTimeout(() => {
    if (document.visibilityState === "visible") {
      window.location.reload();
    }
  }, seconds * 1000);
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-voting-form]");
  if (!form) {
    return;
  }

  const board = form.querySelector(".entry-board");
  const mode = form.dataset.mode;
  let selectedPoint = null;
  let draggedPoint = null;

  const pointInputs = new Map(
    [...form.querySelectorAll("[data-point-input]")].map((input) => [Number(input.dataset.pointInput), input]),
  );
  const chips = new Map(
    [...form.querySelectorAll("[data-point-chip]")].map((chip) => [Number(chip.dataset.pointChip), chip]),
  );
  const cards = [...form.querySelectorAll("[data-entry-card]")];
  const submitButton = form.querySelector("[data-submit-button]");
  const progress = form.querySelector("[data-vote-progress]");

  function assignments() {
    const assigned = new Map();
    pointInputs.forEach((input, points) => {
      if (input.value) {
        assigned.set(points, input.value);
      }
    });
    return assigned;
  }

  function entryAssignedPoint(entryId) {
    for (const [points, assignedEntryId] of assignments()) {
      if (assignedEntryId === entryId) {
        return points;
      }
    }
    return null;
  }

  function clearEntry(entryId) {
    pointInputs.forEach((input) => {
      if (input.value === entryId) {
        input.value = "";
      }
    });
  }

  function setPoint(points, entryId) {
    clearEntry(entryId);
    const input = pointInputs.get(points);
    if (input) {
      input.value = entryId;
    }
  }

  function assignPoint(points, entryId) {
    setPoint(points, entryId);
    selectedPoint = null;
    render();
  }

  function isLocked(card) {
    return mode === "without_ukraine" && card.dataset.isUkraine === "true";
  }

  function showToast(message) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      const page = document.querySelector(".page-container");
      page.prepend(stack);
    }
    const toast = document.createElement("div");
    toast.className = "toast toast-warning";
    toast.textContent = message;
    stack.append(toast);
    setTimeout(() => toast.remove(), 2600);
  }

  function render() {
    const assigned = assignments();
    const assignedEntryIds = new Set(assigned.values());

    chips.forEach((chip, points) => {
      const isUsed = assigned.has(points);
      chip.classList.toggle("selected", selectedPoint === points);
      chip.classList.toggle("used", isUsed);
      chip.disabled = isUsed && selectedPoint !== points;
      chip.draggable = !isUsed;
      chip.setAttribute("aria-pressed", selectedPoint === points ? "true" : "false");
    });

    cards.forEach((card) => {
      const entryId = card.dataset.entryId;
      const points = entryAssignedPoint(entryId);
      const scoreCell = card.querySelector("[data-score-cell]");
      card.classList.toggle("assigned", Boolean(points));
      card.draggable = false;
      card.dataset.assignedPoints = points || "";
      if (points) {
        scoreCell.textContent = points;
      } else if (mode === "without_ukraine" && card.dataset.isUkraine === "true") {
        scoreCell.textContent = "♥";
      } else {
        scoreCell.textContent = "";
      }
    });

    const sorted = [...cards].sort((left, right) => {
      if (mode === "without_ukraine") {
        const leftIsUkraine = left.dataset.isUkraine === "true";
        const rightIsUkraine = right.dataset.isUkraine === "true";
        if (leftIsUkraine !== rightIsUkraine) {
          return leftIsUkraine ? -1 : 1;
        }
      }
      const leftPoints = Number(left.dataset.assignedPoints || 0);
      const rightPoints = Number(right.dataset.assignedPoints || 0);
      if (leftPoints || rightPoints) {
        if (!leftPoints) return 1;
        if (!rightPoints) return -1;
        return rightPoints - leftPoints;
      }
      return Number(left.dataset.runningOrder) - Number(right.dataset.runningOrder);
    });
    sorted.forEach((card) => board.append(card));

    const count = assignedEntryIds.size;
    progress.textContent = `${count} / 10`;
    submitButton.disabled = count !== 10;
  }

  chips.forEach((chip, points) => {
    chip.addEventListener("click", () => {
      if (assignments().has(points)) {
        return;
      }
      selectedPoint = selectedPoint === points ? null : points;
      render();
    });

    chip.addEventListener("dragstart", (event) => {
      if (assignments().has(points)) {
        event.preventDefault();
        return;
      }
      draggedPoint = points;
      event.dataTransfer.effectAllowed = "copy";
      event.dataTransfer.setData("text/plain", String(points));
    });

    chip.addEventListener("dragend", () => {
      draggedPoint = null;
    });
  });

  cards.forEach((card) => {
    card.addEventListener("dragover", (event) => {
      if (!draggedPoint || isLocked(card)) {
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    });

    card.addEventListener("drop", (event) => {
      if (!draggedPoint || isLocked(card)) {
        return;
      }
      event.preventDefault();
      assignPoint(draggedPoint, card.dataset.entryId);
      draggedPoint = null;
    });

    card.querySelector("[data-entry-button]").addEventListener("click", () => {
      const entryId = card.dataset.entryId;
      if (mode === "without_ukraine" && card.dataset.isUkraine === "true") {
        showToast("Ця група голосує без України, тому Україна не приймає бали в цьому режимі.");
        return;
      }
      if (selectedPoint) {
        assignPoint(selectedPoint, entryId);
        return;
      }
      if (entryAssignedPoint(entryId)) {
        clearEntry(entryId);
        render();
      }
    });
  });

  form.addEventListener("submit", (event) => {
    const submitter = event.submitter;
    if (submitter && submitter.dataset.draftButton !== undefined) {
      return;
    }
    if (submitButton.disabled) {
      event.preventDefault();
      return;
    }
    const confirmed = window.confirm("Після підтвердження бюлетень стане незмінним. Надіслати голосування?");
    if (!confirmed) {
      event.preventDefault();
    }
  });

  render();
});
