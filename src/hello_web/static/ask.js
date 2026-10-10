import { countdown } from "./countdown.js";

const form = document.getElementById("ask-form");
const status = document.getElementById("ask-status");
const answer = document.getElementById("answer");
const button = form.querySelector("button[type=submit]");

function show(text, kind) {
  status.textContent = text;
  status.className = kind;
  status.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  answer.hidden = true;
  show("Thinking…", "notice");

  let response;
  try {
    response = await fetch("/ollama/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: form.elements.prompt.value }),
    });
  } catch {
    show("Could not reach the server.", "errors");
    button.disabled = false;
    return;
  }

  const data = await response.json().catch(() => ({}));
  if (response.ok) {
    status.hidden = true;
    // Model output is untrusted text: set textContent, never innerHTML.
    answer.querySelector("p").textContent = data.response;
    answer.hidden = false;
    button.disabled = false;
  } else if (response.status === 429) {
    countdown(status, button, Number(response.headers.get("Retry-After")));
  } else {
    show(typeof data.detail === "string" ? data.detail : "Something went wrong.", "errors");
    button.disabled = false;
  }
});
