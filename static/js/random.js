/* list notepad*/
let db;

const request = indexedDB.open("MyListDB", 1);

request.onupgradeneeded = function (event) {
  db = event.target.result;

  if (!db.objectStoreNames.contains("items")) {
    db.createObjectStore("items", {
      keyPath: "id",
      autoIncrement: true
    });
  }
};

request.onsuccess = function (event) {
  db = event.target.result;
  displayItems();
};

request.onerror = function () {
  console.error("IndexedDB failed to open");
};

function addItem(text) {
  const tx = db.transaction("items", "readwrite");
  const store = tx.objectStore("items");

  store.add({ text });

  tx.oncomplete = function () {
    displayItems();
  };
}

function displayItems() {
  const ul = document.getElementById("myList");
  ul.innerHTML = "";

  const tx = db.transaction("items", "readonly");
  const store = tx.objectStore("items");
  const request = store.getAll();

  request.onsuccess = function () {
    request.result.forEach(item => {
      const li = document.createElement("li");

      const row = document.createElement("div");
      row.className = "item-row";

      const bullet = document.createElement("span");
      bullet.className = "bullet";
      bullet.textContent = "•";

      const span = document.createElement("span");
      span.className = "item-text";
      span.textContent = item.text;
      span.contentEditable = "true";

      span.addEventListener("blur", () => {
        updateItem(item.id, span.textContent.trim());
      });

      const del = document.createElement("button");
      del.textContent = "✕";
      del.onclick = () => deleteItem(item.id);

      row.appendChild(bullet);
      row.appendChild(span);
      row.appendChild(del);
      li.appendChild(row);
      ul.appendChild(li);
    });
  };
}

function updateItem(id, text) {
  const tx = db.transaction("items", "readwrite");
  const store = tx.objectStore("items");
  store.put({ id, text });
}

function deleteItem(id) {
  const tx = db.transaction("items", "readwrite");
  const store = tx.objectStore("items");

  store.delete(id);

  tx.oncomplete = function () {
    displayItems();
  };
}

document.getElementById("itemInput").addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    const text = this.value.trim();

    if (text !== "") {
      addItem(text);
      this.value = "";
    }
  }
});