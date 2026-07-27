document.addEventListener("DOMContentLoaded", function () {
  const notepad = document.getElementById("notepad");
  const list = document.getElementById("myList");
  const itemInput = document.getElementById("itemInput");
  const addTaskButton =
    document.getElementById("addTaskButton");

  /*
   * This file may be loaded on another page that does not
   * contain the notepad. In that situation, stop safely.
   */
  if ( !notepad || !list || !itemInput || !addTaskButton) {
    return;
  }

  const apiUrl = notepad.dataset.apiUrl;

  if (!apiUrl) {
    console.error("The notepad API URL is missing.");
    return;
  }

  /*
   * Delete the old browser-wide IndexedDB database.
   *
   * The new notepad system no longer uses IndexedDB.
   * All new items are stored in SQLite by user account.
   */
  if ("indexedDB" in window) {
    const deleteRequest = indexedDB.deleteDatabase("MyListDB");

    deleteRequest.onerror = function () {
      console.warn(
        "The old IndexedDB notepad could not be removed."
      );
    };

    deleteRequest.onblocked = function () {
      console.warn(
        "Close other tabs using the website to remove the old notepad."
      );
    };
  }

  /**
   * Send a request to the Flask notepad API.
   */
  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {})
      }
    });

    const responseData = await response
      .json()
      .catch(function () {
        return {};
      });

    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Your login session has ended.");
    }

    if (!response.ok) {
      throw new Error(
        responseData.error || "The request was unsuccessful."
      );
    }

    return responseData;
  }

  /**
   * Resize the new-item textarea as text wraps.
   */
  function resizeInput() {
    itemInput.style.height = "auto";

    const maximumHeight = 72;

    itemInput.style.height =
      Math.min(itemInput.scrollHeight, maximumHeight) + "px";
  }

  /**
   * Display an error inside the list.
   */
  function showListError(message) {
    list.innerHTML = "";

    const errorItem = document.createElement("li");
    errorItem.className = "notepad-error";
    errorItem.textContent = message;

    list.appendChild(errorItem);
  }

  /**
   * Create and display one saved notepad item.
   */
  function renderItem(item) {
    const listItem = document.createElement("li");
    listItem.dataset.itemId = item.id;

    const row = document.createElement("div");
    row.className = "item-row";

    const bullet = document.createElement("span");
    bullet.className = "bullet";
    bullet.textContent = "•";
    bullet.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "item-text";
    text.textContent = item.text;
    text.contentEditable = "true";
    text.spellcheck = true;
    text.setAttribute("role", "textbox");
    text.setAttribute(
      "aria-label",
      "Edit to-do list item"
    );

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-item-button";
    deleteButton.textContent = "✕";
    deleteButton.setAttribute(
      "aria-label",
      "Delete to-do list item"
    );

    let savedText = item.text;
    let deletingItem = false;

    /*
     * Pressing Enter while editing saves the item.
     * Long text will wrap automatically without needing Enter.
     */
    text.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        text.blur();
      }
    });

    /*
     * Save the edited item when the user clicks away.
     */
    text.addEventListener("blur", async function () {
      if (deletingItem) {
        return;
      }

      const updatedText = text.textContent
        .replace(/\u00A0/g, " ")
        .trim();

      if (updatedText === savedText) {
        text.textContent = savedText;
        return;
      }

      try {
        const result = await requestJson(
          `${apiUrl}/${item.id}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              text: updatedText
            })
          }
        );

        /*
         * Flask deletes the item when all its text
         * has been removed.
         */
        if (result.deleted) {
          listItem.remove();
          return;
        }

        savedText = result.text;
        text.textContent = result.text;
      } catch (error) {
        console.error(error);

        /*
         * Restore the previous text if saving failed.
         */
        text.textContent = savedText;
      }
    });

    /*
     * pointerdown happens before the editable text loses focus.
     * This prevents an unnecessary edit request immediately
     * before the delete request.
     */
    deleteButton.addEventListener(
      "pointerdown",
      function () {
        deletingItem = true;
      }
    );

    deleteButton.addEventListener(
      "click",
      async function () {
        try {
          await requestJson(
            `${apiUrl}/${item.id}`,
            {
              method: "DELETE"
            }
          );

          listItem.remove();
        } catch (error) {
          deletingItem = false;
          console.error(error);
        }
      }
    );

    row.appendChild(bullet);
    row.appendChild(text);
    row.appendChild(deleteButton);

    listItem.appendChild(row);
    list.appendChild(listItem);
  }

  /**
   * Load only the signed-in user's items.
   */
  async function loadItems() {
    try {
      const data = await requestJson(apiUrl);

      list.innerHTML = "";

      data.items.forEach(function (item) {
        renderItem(item);
      });
    } catch (error) {
      console.error(error);

      showListError(
        "Your to-do list could not be loaded."
      );
    }
  }

  let creatingItem = false;

  /**
   * Make the Add Task button available only when
   * the textarea contains non-whitespace text.
   */
  function updateAddButtonState() {
    const hasText =
      itemInput.value.trim().length > 0;

    addTaskButton.disabled =
      !hasText || creatingItem;
  }

  /**
   * Create a new task using either the Enter key
   * or the Add Task button.
   */
  async function createTask() {
    const newText = itemInput.value.trim();

    /*
    * Ignore empty submissions and prevent duplicate
    * requests while an item is already being saved.
    */
    if (!newText || creatingItem) {
      return;
    }

    creatingItem = true;
    itemInput.disabled = true;
    updateAddButtonState();

    try {
      const newItem = await requestJson(
        apiUrl,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            text: newText
          })
        }
      );

      /*
      * Add the new item to the bottom of the list.
      */
      renderItem(newItem);

      itemInput.value = "";
      resizeInput();

      /*
      * When the list is internally scrollable,
      * move down so the new task is visible.
      */
      list.scrollTo({
        top: list.scrollHeight,
        behavior: "smooth"
      });
    } catch (error) {
      console.error(error);
    } finally {
      creatingItem = false;
      itemInput.disabled = false;

      updateAddButtonState();

      /*
      * Return the typing cursor to the empty textarea.
      */
      itemInput.focus();
    }
  }

  /**
   * Enter adds the task.
   * Shift + Enter inserts a new line.
   */
  itemInput.addEventListener(
    "keydown",
    function (event) {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        createTask();
      }
    }
  );

  /**
   * Clicking the button also adds the task.
   */
  addTaskButton.addEventListener(
    "click",
    createTask
  );

  /**
   * Resize the textarea and update the button
   * whenever the user types.
   */
  itemInput.addEventListener(
    "input",
    function () {
      resizeInput();
      updateAddButtonState();
    }
  );

  updateAddButtonState();
  resizeInput();
  loadItems();
});