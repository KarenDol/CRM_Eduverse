async function get_competitions() {
  try {
    const res = await fetch("/api/competitions/get/", {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
      },
    });

    if (!res.ok) {
      throw new Error("Failed to get token");
    }

    const data = await res.json();

    return data;
  } catch (err) {
    console.error("Token error:", err);
    throw err;
  }
}

async function get_results(competition_id) {
  try {
    const res = await fetch(`/api/competitions/results/${competition_id}`, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
      },
    });

    if (!res.ok) {
      throw new Error("Failed to get token");
    }

    const data = await res.json();

    return data;
  } catch (err) {
    console.error("Token error:", err);
    throw err;
  }
}