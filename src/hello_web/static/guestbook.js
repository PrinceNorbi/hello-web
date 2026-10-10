// Counts down a rate-limit notice and re-enables posting when the wait is over.
const notice = document.getElementById("rate-limit");

if (notice) {
  const button = document.querySelector("form button[type=submit]");
  const countdown = notice.querySelector(".countdown");
  const readyAt = Date.now() + Number(notice.dataset.retryAfter) * 1000;
  button.disabled = true;

  const tick = () => {
    const seconds = Math.ceil((readyAt - Date.now()) / 1000);
    if (seconds > 0) {
      countdown.textContent = `${seconds} second${seconds === 1 ? "" : "s"}`;
      setTimeout(tick, 250);
    } else {
      notice.textContent = "You can post again now.";
      notice.className = "notice";
      button.disabled = false;
    }
  };
  tick();
}
