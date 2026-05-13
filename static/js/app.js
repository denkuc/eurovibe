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
