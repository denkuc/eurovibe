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
    await navigator.clipboard.writeText(source.value);
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = "Copy";
    }, 1400);
  } catch {
    source.focus();
    source.select();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-voting-form]");
  if (!form) {
    return;
  }

  const board = form.querySelector(".entry-board");
  const mode = form.dataset.mode;
  const pointOrder = [12, 10, 8, 7, 6, 5, 4, 3, 2, 1];
  const allowedPoints = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12];
  let selectedPoint = null;

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

  function assignPoint(points, entryId) {
    clearEntry(entryId);
    const input = pointInputs.get(points);
    if (input) {
      input.value = entryId;
    }
    selectedPoint = null;
    render();
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
      chip.setAttribute("aria-pressed", selectedPoint === points ? "true" : "false");
    });

    cards.forEach((card) => {
      const entryId = card.dataset.entryId;
      const points = entryAssignedPoint(entryId);
      const scoreCell = card.querySelector("[data-score-cell]");
      card.classList.toggle("assigned", Boolean(points));
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
  });

  cards.forEach((card) => {
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
    if (submitButton.disabled) {
      event.preventDefault();
      return;
    }
    const confirmed = window.confirm("Після підтвердження бюлетень стане незмінним. Надіслати голосування?");
    if (!confirmed) {
      event.preventDefault();
    }
  });

  function applySortableOrder() {
    const assignedCards = [...board.querySelectorAll("[data-entry-card].assigned")];
    assignedCards.forEach((card, index) => {
      clearEntry(card.dataset.entryId);
      const points = pointOrder[index];
      if (points) {
        pointInputs.get(points).value = card.dataset.entryId;
      }
    });
    render();
  }

  if (window.Sortable && board) {
    window.Sortable.create(board, {
      animation: 150,
      draggable: "[data-entry-card].assigned",
      onEnd: applySortableOrder,
    });
  }

  allowedPoints.forEach((points) => {
    const input = pointInputs.get(points);
    if (input && input.value) {
      input.value = "";
    }
  });
  render();
});
