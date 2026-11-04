// Renaming a topic (task 209): open, the field takes the focus; Esc closes it and puts the title back.
for (const box of document.querySelectorAll("details.rename")) {
  const field = box.querySelector("input[name=new_title]");
  box.addEventListener("toggle", () => {
    if (box.open) {
      field.focus();
      field.select();
    } else {
      field.value = field.defaultValue;
    }
  });
  field.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      box.open = false;
      box.querySelector("summary").focus();
    }
  });
}
