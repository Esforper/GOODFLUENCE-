document.getElementById("data-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("name").value;

    const response = await fetch("/api/data", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ name }),
    });

    const data = await response.json();
    document.getElementById("response").textContent = data.message;
});
