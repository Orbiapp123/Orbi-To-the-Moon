console.log("Orbi website loaded");

document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector("button");

  if (button) {
    button.addEventListener("click", () => {
      alert("Wallet connect coming soon");
    });
  }
});
