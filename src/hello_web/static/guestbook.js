import { countdown } from "./countdown.js";

const notice = document.getElementById("rate-limit");
if (notice) {
  countdown(notice, document.querySelector("form button[type=submit]"), Number(notice.dataset.retryAfter));
}
