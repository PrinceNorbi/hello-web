// Shows the rate-limit notice in `notice`, counts down, and re-enables `button` when the wait is over.
export function countdown(notice, button, seconds) {
  const readyAt = Date.now() + seconds * 1000;
  const remaining = document.createElement("strong");
  notice.replaceChildren(
    "You've reached the limit of one post per minute. You can post again in ",
    remaining,
    ".",
  );
  notice.className = "errors";
  notice.hidden = false;
  button.disabled = true;

  const tick = () => {
    const left = Math.ceil((readyAt - Date.now()) / 1000);
    if (left > 0) {
      remaining.textContent = `${left} second${left === 1 ? "" : "s"}`;
      setTimeout(tick, 250);
    } else {
      notice.textContent = "You can post again now.";
      notice.className = "notice";
      button.disabled = false;
    }
  };
  tick();
}
