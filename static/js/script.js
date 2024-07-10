document.addEventListener("DOMContentLoaded", function () {
  // Theme switcher
  const themeToggle = document.getElementById("themeToggle");

  themeToggle.addEventListener("click", function () {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
    themeToggle.textContent = newTheme === "light" ? "Dark Mode" : "Light Mode";
  });

  // Set initial theme
  const savedTheme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);
  themeToggle.textContent = savedTheme === "light" ? "Dark Mode" : "Light Mode";

  // Form submission
  const userTaskForm = document.getElementById("userTaskForm");
  const statusWindow = document.getElementById("statusWindow");
  const statusMessage = document.getElementById("statusMessage");
  const logContent = document.getElementById("logContent");
  const checkStatusContainer = document.getElementById("checkStatusContainer");
  const checkStatusButton = document.getElementById("checkStatusButton");
  const objectIdResult = document.getElementById("objectIdResult");
  const objectIdMessage = document.getElementById("objectIdMessage");

  userTaskForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const formData = new FormData(this);

    statusWindow.classList.remove("hidden");
    statusMessage.textContent = "Submitting task...";
    logContent.textContent = "";
    checkStatusContainer.classList.add("hidden");
    objectIdResult.classList.add("hidden");

    axios
      .post("/submit_task", formData)
      .then((response) => {
        const data = response.data;
        statusMessage.textContent = `${data.status}: ${data.message}`;
        if (data.taskId) {
          statusMessage.textContent += ` Task ID: ${data.taskId}`;
          checkStatusButton.dataset.taskName = data.taskName;
          checkStatusContainer.classList.remove("hidden");
        }
        logContent.textContent = data.log;
      })
      .catch((error) => {
        console.error("Error:", error);
        statusMessage.textContent = "Error: Failed to submit task";
        if (error.response && error.response.data) {
          logContent.textContent =
            error.response.data.log || "No log available";
        } else {
          logContent.textContent = "No log available";
        }
      });
  });

  // Check task status
  checkStatusButton.addEventListener("click", function () {
    const taskName = this.dataset.taskName;
    objectIdResult.classList.remove("hidden");
    objectIdMessage.textContent = "Retrieving object ID...";

    axios
      .post("/get_object_id", new URLSearchParams({ taskName: taskName }))
      .then((response) => {
        const data = response.data;
        objectIdMessage.textContent = data.message;
      })
      .catch((error) => {
        console.error("Error:", error);
        objectIdMessage.textContent = "Error: Failed to retrieve object ID";
      });
  });

  // Rewrite with Gemini
  const rewriteBtn = document.getElementById("rewriteBtn");
  const descriptionTextarea = document.getElementById("description");

  rewriteBtn.addEventListener("click", function () {
    const originalDescription = descriptionTextarea.value.trim();

    if (originalDescription === "") {
      showNotification("Please enter a description before rewriting.", "error");
      return;
    }

    rewriteBtn.setAttribute("aria-busy", "true");
    rewriteBtn.disabled = true;

    axios
      .post(
        "/rewrite_description",
        new URLSearchParams({ description: originalDescription })
      )
      .then((response) => {
        const data = response.data;
        if (data.status === "success") {
          descriptionTextarea.value = data.rewritten_description;
          showNotification("Description rewritten successfully!", "success");
        } else {
          showNotification("Error: " + data.message, "error");
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        if (error.response) {
          showNotification(`Error: ${error.response.data.message}`, "error");
        } else {
          showNotification(
            "An unexpected error occurred. Please try again.",
            "error"
          );
        }
      })
      .finally(() => {
        rewriteBtn.removeAttribute("aria-busy");
        rewriteBtn.disabled = false;
      });
  });

  // Function to show notification
  function showNotification(message, type) {
    const notification = document.getElementById("notification");
    notification.textContent = message;
    notification.className = type === "error" ? "error" : "";
    notification.classList.remove("hidden");
    setTimeout(() => {
      notification.classList.add("hidden");
    }, 3000);
  }
});
