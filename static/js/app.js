// ===== static/js/app.js (FULL REPLACEMENT) =====
(function () {
  console.log("✅ app.js loaded");

  // ---------- Helpers ----------
  const showToast = (msg) => alert(msg);

  // petit util pour trouver un attribut data-id / data-name proprement
  function getTargetData(el) {
    const btn = el.closest(".card-delete-button, .button.button-danger");
    if (!btn) return null;
    let id = btn.dataset.id;
    let name = btn.dataset.name;
    // fallback si pas de data-name
    if (!name) {
      const card = btn.closest("[data-id]");
      if (card) {
        const h3 = card.querySelector(".staff-card-name h3, strong");
        if (h3) name = h3.textContent.trim();
      }
    }
    return { btn, id, name };
  }

  // ---------- Delete (corbeille et bouton rouge) ----------
  document.addEventListener("click", function (e) {
    const info = getTargetData(e.target);
    if (!info) return;

    e.preventDefault();

    const { id, name } = info;
    if (!id) {
      console.warn("⚠️ Delete: data-id manquant");
      return;
    }

    if (!confirm(`Delete "${name || "this profile"}"? This cannot be undone.`)) {
      return;
    }

    fetch(`/api/profile/${id}/delete`, { method: "POST" })
      .then((r) => r.json().catch(() => ({})).then((d) => ({ ok: r.ok, data: d })))
      .then(({ ok, data }) => {
        if (!ok || data.status !== "success") {
          throw new Error(data.message || "Server error");
        }
        // Si on est sur la page détail du même profil -> redirect liste
        if (window.location.pathname === `/profile/${id}` || window.location.pathname === `/profile/${id}/`) {
          window.location.href = "/staff";
          return;
        }
        // Sinon, retirer la carte de la liste si elle existe
        const card = document.querySelector(`.staff-card[data-id="${id}"]`);
        if (card) {
          card.style.transition = "opacity .25s ease";
          card.style.opacity = "0";
          setTimeout(() => card.remove(), 250);
        }
      })
      .catch((err) => {
        console.error(err);
        showToast("Error deleting profile.");
      });
  });

  // ---------- Staff list: Sortable sur .staff-grid ----------
  document.addEventListener("DOMContentLoaded", function () {
    const grid = document.querySelector(".staff-grid");
    if (grid) {
      if (window.Sortable) {
        console.log("🔧 Initializing Sortable on .staff-grid");
        new Sortable(grid, {
          animation: 150,
          ghostClass: "sortable-ghost",
          dragClass: "sortable-drag",
        });
      } else {
        console.warn("⚠️ SortableJS not found. Check <script src='...Sortable.min.js'> in base.html");
      }
    }
  });

  // ---------- Dispatch board: DnD + modal assignment ----------
  document.addEventListener("DOMContentLoaded", function () {
    const lists = document.querySelectorAll(".dispatch-list");
    if (!lists.length) return;

    if (!window.Sortable) {
      console.warn("⚠️ SortableJS not found on dispatch page.");
      return;
    }

    console.log("🔧 Initializing Sortable on .dispatch-list");

    let originalList = null;

    lists.forEach((list) => {
      new Sortable(list, {
        group: "dispatch",
        animation: 150,
        ghostClass: "dispatch-card-ghost",
        dragClass: "dispatch-card-drag",
        onStart(evt) {
          originalList = evt.from;
        },
        onEnd(evt) {
          const item = evt.item;
          const profileId = item?.dataset?.id;
          const newVenue = evt.to?.dataset?.venue;
          const staffName = item?.querySelector("strong")?.textContent || "Staff";

          if (!profileId || !newVenue) {
            if (originalList) originalList.appendChild(item);
            return;
          }

          if (newVenue === "available") {
            // On n’implémente pas le retour "available" pour l’instant : on annule
            if (originalList) originalList.appendChild(item);
            alert("De-assignment will be added later. For now, you cannot move back to 'Available'.");
            return;
          }

          // ouvrir le modal d’Assignment
          if (typeof window.openAssignmentModal === "function") {
            window.openAssignmentModal(profileId, staffName, newVenue);
          } else {
            alert("Assignment modal not found.");
          }

          // on annule visuellement le move (la page rechargera après création)
          if (originalList) originalList.appendChild(item);
        },
      });
    });

    // ----- Modal assignment -----
    const assignmentModal = document.getElementById("assignmentModal");
    if (!assignmentModal) return;

    const form = document.getElementById("assignmentForm");
    const closeBtn = document.getElementById("closeAssignmentModalBtn");
    const cancelBtn = document.getElementById("cancelAssignmentModalBtn");
    const staffNameSpan = document.getElementById("assignmentStaffName");
    const staffIdInput = document.getElementById("assignmentStaffId");
    const venueInput = document.getElementById("assignmentVenue");
    const startDateInput = document.getElementById("startDate");

    function openModal(staffId, staffName, venue) {
      staffIdInput.value = staffId;
      staffNameSpan.textContent = staffName;
      venueInput.value = venue;
      startDateInput.value = new Date().toISOString().split("T")[0];
      assignmentModal.classList.remove("hidden");
    }
    function closeModal() {
      assignmentModal.classList.add("hidden");
    }
    window.openAssignmentModal = openModal;
    closeBtn?.addEventListener("click", closeModal);
    cancelBtn?.addEventListener("click", closeModal);

    form?.addEventListener("submit", async function (e) {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating...";

      const payload = {
        staff_id: staffIdInput.value,
        venue: venueInput.value,
        contract_type: document.getElementById("contractType").value,
        start_date: startDateInput.value,
        base_salary: document.getElementById("baseSalary").value,
      };

      try {
        const res = await fetch("/api/assignment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.message || "Server error");
        closeModal();
        window.location.reload();
      } catch (err) {
        alert(err.message || "Network error.");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Assignment";
      }
    });
  });
})();
