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
// ---------- Payroll page (Manage Performance par assignment + date) ----------
document.addEventListener("DOMContentLoaded", function () {
  const table = document.querySelector(".payroll-table");
  if (!table) return;

  console.log("🔧 Payroll init");

  // Modal & champs
  const modal = document.getElementById("editRecordModal");
  const form = document.getElementById("editRecordForm");
  const closeBtn = document.getElementById("closeModalBtn");
  const cancelBtn = document.getElementById("cancelModalBtn");

  const assignmentIdInput = document.getElementById("assignmentId");
  const contractDaysInput = document.getElementById("contractDays");
  const contractBaseSalaryInput = document.getElementById("contractBaseSalary");
  const contractStartInput = document.getElementById("contractStart");
  const contractEndInput = document.getElementById("contractEnd");

  const modalStaffName = document.getElementById("modalStaffName");
  const recordDateInput = document.getElementById("recordDate");
  const periodText = document.getElementById("periodText");

  const arrivalInput = document.getElementById("arrivalTime");
  const departureInput = document.getElementById("departureTime");
  const drinksInput = document.getElementById("drinksSold");
  const specialInput = document.getElementById("specialCommissions");
  const bonusInput = document.getElementById("bonus");
  const malusInput = document.getElementById("malus");

  const latenessPenaltyInput = document.getElementById("latenessPenalty");
  const commissionPaidInput = document.getElementById("commissionPaid");
  const proratedBaseInput = document.getElementById("proratedBase");
  const salaryPaidInput = document.getElementById("salaryPaid");
  const barProfitInput = document.getElementById("barProfit");

  const historyBox = document.getElementById("recordHistory");

  function openModal() { modal.classList.remove("hidden"); }
  function closeModal() { modal.classList.add("hidden"); }
  closeBtn?.addEventListener("click", closeModal);
  cancelBtn?.addEventListener("click", closeModal);

  // règles métier
  const DRINK_STAFF = 100; // commission staff/drink
  const DRINK_BAR = 120;   // part bar/drink
  const LATE_CUTOFF = "19:30"; // retard à partir de 19:31

  function computePenalty(arrival) {
    if (!arrival) return 0;
    const cutoff = new Date(`1970-01-01T${LATE_CUTOFF}:00`);
    const when = new Date(`1970-01-01T${arrival}:00`);
    if (when <= cutoff) return 0;
    const minutes = Math.round((when - cutoff) / 60000);
    return minutes * 5; // 5 THB/min
  }

  function recompute() {
    const drinks = parseFloat(drinksInput.value) || 0;
    const special = parseFloat(specialInput.value) || 0;
    const bonus = parseFloat(bonusInput.value) || 0;
    const malus = parseFloat(malusInput.value) || 0;

    const contractDays = parseInt(contractDaysInput.value || "1", 10);
    const baseSalary = parseFloat(contractBaseSalaryInput.value || "0");
    const baseDaily = contractDays > 0 ? (baseSalary / contractDays) : 0;

    const penalty = computePenalty(arrivalInput.value);
    latenessPenaltyInput.value = penalty.toFixed(0);

    const commissionStaff = drinks * DRINK_STAFF;
    commissionPaidInput.value = commissionStaff.toFixed(0);

    proratedBaseInput.value = baseDaily.toFixed(0);

    // Salary paid = Base daily + bonus - malus - lateness penalty
    const salaryPaid = baseDaily + bonus - malus - penalty;
    salaryPaidInput.value = salaryPaid.toFixed(0);

    // Bar Profit = (drinks x 120 + special) - salary paid
    const profit = (drinks * DRINK_BAR + special) - salaryPaid;
    barProfitInput.value = profit.toFixed(0);
  }

  [arrivalInput, departureInput, drinksInput, specialInput, bonusInput, malusInput].forEach(el => {
    el?.addEventListener("input", recompute);
  });

  async function loadRecord(assignmentId, ymd) {
    historyBox.innerHTML = "";
    try {
      const res = await fetch(`/api/performance/${assignmentId}/${ymd}`);
      const data = await res.json();

      if (data && data.record) {
        const r = data.record;
        arrivalInput.value = r.arrival_time || "";
        departureInput.value = r.departure_time || "";
        drinksInput.value = r.drinks_sold ?? 0;
        specialInput.value = r.special_commissions ?? 0;
        bonusInput.value = r.bonus ?? 0;
        malusInput.value = r.malus ?? 0;
        latenessPenaltyInput.value = r.lateness_penalty ?? 0;
      } else {
        // reset si aucun record
        arrivalInput.value = "";
        departureInput.value = "";
        drinksInput.value = 0;
        specialInput.value = 0;
        bonusInput.value = 0;
        malusInput.value = 0;
        latenessPenaltyInput.value = 0;
      }

      // petite histoire (5 derniers jours du même assignment)
      (data.history || []).forEach(h => {
        const d = new Date(h.record_date + "T00:00:00");
        const div = document.createElement("div");
        div.className = "history-item";
        div.innerHTML = `
          <div><span>Date:</span> <strong>${d.toLocaleDateString('en-GB')}</strong></div>
          <div><span>Drinks:</span> <strong>${h.drinks_sold}</strong></div>
          <div><span>Penalty:</span> <strong>${(h.lateness_penalty || 0)} THB</strong></div>
        `;
        historyBox.appendChild(div);
      });

    } catch (e) {
      console.error("loadRecord error", e);
      historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
    }

    // Après chargement, recalcule les totaux live
    recompute();
  }

  // Ouvrir le modal depuis la ligne du tableau
table.addEventListener("click", (e) => {
  const btn = e.target.closest(".manage-performance-btn");
  if (!btn) return;

  const tr = btn.closest("tr");
  const aId = tr.dataset.assignmentId;
  const staffName = tr.dataset.staffName;
  const startIso = tr.dataset.startDate;
  const endIso = tr.dataset.endDate;
  const baseSalary = parseFloat(tr.dataset.baseSalary || "0");
  const contractDays = parseInt(tr.dataset.contractDays || "1", 10);
  const contractType = (tr.dataset.contractType || "").trim(); // ✅

  // remplir les hidden (utiles pour calculs)
  assignmentIdInput.value = aId;
  contractDaysInput.value = contractDays;
  contractBaseSalaryInput.value = baseSalary.toString();
  contractStartInput.value = startIso;
  contractEndInput.value = endIso;

  modalStaffName.textContent = staffName || "";

  // borne du sélecteur de date
  recordDateInput.min = startIso;
  recordDateInput.max = endIso;
  recordDateInput.value = startIso;
  periodText.textContent = `${startIso} → ${endIso}`;

  // ===== Nouveau : style + badge contrat sur la modale =====
  const card = document.getElementById("performanceModalCard");
  const badge = document.getElementById("modalContractBadge");

  // reset classes
  card.classList.remove("contract-1jour", "contract-10jours", "contract-1mois");
  badge.classList.remove("badge-1jour", "badge-10jours", "badge-1mois");

  // applique la bonne classe si valide
  if (["1jour", "10jours", "1mois"].includes(contractType)) {
    card.classList.add(`contract-${contractType}`);
    badge.classList.add(`badge-${contractType}`);
    badge.textContent = contractType; // affiche "1jour" / "10jours" / "1mois"
  } else {
    badge.textContent = "—";
  }
  // ---------- Payroll page (Manage Performance + End/Delete) [FULL REPLACEMENT] ----------
document.addEventListener("DOMContentLoaded", function () {
  const table = document.querySelector(".payroll-table");
  if (!table) return;

  // Modal elements (IDs must match payroll.html)
  const modal = document.getElementById("editRecordModal");
  const form = document.getElementById("editRecordForm");
  const closeBtn = document.getElementById("closeModalBtn");
  const cancelBtn = document.getElementById("cancelModalBtn");

  const assignmentIdInput = document.getElementById("assignmentId");
  const contractDaysInput = document.getElementById("contractDays");
  const contractBaseSalaryInput = document.getElementById("contractBaseSalary");
  const contractStartInput = document.getElementById("contractStart");
  const contractEndInput = document.getElementById("contractEnd");

  const modalStaffName = document.getElementById("modalStaffName");
  const modalContractBadge = document.getElementById("modalContractBadge");

  const recordDateInput = document.getElementById("recordDate");
  const periodText = document.getElementById("periodText");

  const arrivalInput = document.getElementById("arrivalTime");
  const departureInput = document.getElementById("departureTime");
  const drinksInput = document.getElementById("drinksSold");
  const specialInput = document.getElementById("specialCommissions");
  const bonusInput = document.getElementById("bonus");
  const malusInput = document.getElementById("malus");

  const latenessPenaltyInput = document.getElementById("latenessPenalty");
  const commissionPaidInput = document.getElementById("commissionPaid");
  const proratedBaseInput = document.getElementById("proratedBase");
  const salaryPaidInput = document.getElementById("salaryPaid");
  const barProfitInput = document.getElementById("barProfit");

  const historyBox = document.getElementById("recordHistory");

  // Config
  const DRINK_STAFF = 100;
  const DRINK_BAR = 120;
  const LATE_CUTOFF = "19:30";

  function openModal() { modal.classList.remove("hidden"); }
  function closeModal() { modal.classList.add("hidden"); }
  closeBtn?.addEventListener("click", closeModal);
  cancelBtn?.addEventListener("click", closeModal);

  function computePenalty(arrival) {
    if (!arrival) return 0;
    const cutoff = new Date(`1970-01-01T${LATE_CUTOFF}:00`);
    const when = new Date(`1970-01-01T${arrival}:00`);
    if (when <= cutoff) return 0;
    const minutes = Math.round((when - cutoff) / 60000);
    return minutes * 5;
  }

  function recompute() {
    const drinks = parseFloat(drinksInput.value) || 0;
    const special = parseFloat(specialInput.value) || 0;
    const bonus = parseFloat(bonusInput.value) || 0;
    const malus = parseFloat(malusInput.value) || 0;

    const contractDays = parseInt(contractDaysInput.value || "1", 10);
    const baseSalary = parseFloat(contractBaseSalaryInput.value || "0");
    const baseDaily = contractDays > 0 ? (baseSalary / contractDays) : 0;

    const penalty = computePenalty(arrivalInput.value);
    latenessPenaltyInput.value = penalty.toFixed(0);

    const commissionStaff = drinks * DRINK_STAFF;
    commissionPaidInput.value = commissionStaff.toFixed(0);

    proratedBaseInput.value = baseDaily.toFixed(0);

    const salaryPaid = baseDaily + bonus - malus - penalty;
    salaryPaidInput.value = salaryPaid.toFixed(0);

    const profit = (drinks * DRINK_BAR + special) - salaryPaid;
    barProfitInput.value = profit.toFixed(0);
  }

  [arrivalInput, departureInput, drinksInput, specialInput, bonusInput, malusInput].forEach(el => {
    el?.addEventListener("input", recompute);
  });

  async function loadRecord(assignmentId, ymd) {
    historyBox.innerHTML = "";
    try {
      const res = await fetch(`/api/performance/${assignmentId}/${ymd}`);
      const data = await res.json();

      if (data && data.record) {
        const r = data.record;
        arrivalInput.value = r.arrival_time || "";
        departureInput.value = r.departure_time || "";
        drinksInput.value = r.drinks_sold ?? 0;
        specialInput.value = r.special_commissions ?? 0;
        bonusInput.value = r.bonus ?? 0;
        malusInput.value = r.malus ?? 0;
        latenessPenaltyInput.value = r.lateness_penalty ?? 0;
      } else {
        arrivalInput.value = "";
        departureInput.value = "";
        drinksInput.value = 0;
        specialInput.value = 0;
        bonusInput.value = 0;
        malusInput.value = 0;
        latenessPenaltyInput.value = 0;
      }

      (data.history || []).forEach(h => {
        const d = new Date(h.record_date + "T00:00:00");
        const div = document.createElement("div");
        div.className = "history-item";
        div.innerHTML = `
          <div><span>Date:</span> <strong>${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}</strong></div>
          <div><span>Drinks:</span> <strong>${h.drinks_sold}</strong></div>
          <div><span>Penalty:</span> <strong>${(h.lateness_penalty || 0)} THB</strong></div>
          <div><span>—</span> <strong>&nbsp;</strong></div>
        `;
        historyBox.appendChild(div);
      });
    } catch (e) {
      console.error("loadRecord error", e);
      historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
    }
    recompute();
  }

  // Single event delegation for all 3 buttons
  table.addEventListener("click", async (e) => {
    const tr = e.target.closest("tr[data-assignment-id]");
    if (!tr) return;

    // 1) Manage Performance
    if (e.target.closest(".manage-performance-btn")) {
      const aId = tr.dataset.assignmentId;
      const staffName = tr.dataset.staffName;
      const startIso = tr.dataset.startDate;
      const endIso = tr.dataset.endDate;
      const baseSalary = parseFloat(tr.dataset.baseSalary || "0");
      const contractDays = parseInt(tr.dataset.contractDays || "1", 10);
      const cType = tr.dataset.contractType;

      assignmentIdInput.value = aId;
      contractDaysInput.value = contractDays;
      contractBaseSalaryInput.value = baseSalary.toString();
      contractStartInput.value = startIso;
      contractEndInput.value = endIso;

      modalStaffName.textContent = staffName || "";

      // badge
      modalContractBadge.textContent =
        cType === "1jour" ? "1-day" : (cType === "10jours" ? "10-days" : "1-month");
      modalContractBadge.className = "contract-badge contract-" + cType;

      // date bounds
      recordDateInput.min = startIso;
      recordDateInput.max = endIso;
      recordDateInput.value = startIso;
      periodText.textContent = `${startIso} → ${endIso}`;

      openModal();
      loadRecord(aId, recordDateInput.value);
      return;
    }

    // 2) End now
    if (e.target.closest(".assignment-finish-btn")) {
      const name = tr.dataset.staffName || "this staff";
      if (!confirm(`End this contract now for "${name}"?`)) return;

      const id = tr.dataset.assignmentId;
      try {
        const res = await fetch(`/api/assignment/${id}/finish`, { method: "POST" });
        const data = await res.json().catch(()=>({}));
        if (!res.ok) throw new Error(data.message || "Server error");
        tr.style.transition = "opacity .25s ease";
        tr.style.opacity = "0";
        setTimeout(()=> tr.remove(), 250);
      } catch (err) {
        alert(err.message || "Network error");
      }
      return;
    }

    // 3) Delete
    if (e.target.closest(".assignment-delete-btn")) {
      const name = tr.dataset.staffName || "this staff";
      if (!confirm(`Delete this contract for "${name}"? This cannot be undone.`)) return;

      const id = tr.dataset.assignmentId;
      try {
        const res = await fetch(`/api/assignment/${id}/delete`, { method: "POST" });
        const data = await res.json().catch(()=>({}));
        if (!res.ok) throw new Error(data.message || "Server error");
        tr.style.transition = "opacity .25s ease";
        tr.style.opacity = "0";
        setTimeout(()=> tr.remove(), 250);
      } catch (err) {
        alert(err.message || "Network error");
      }
      return;
    }
  });

  // Save performance (upsert)
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      assignment_id: parseInt(assignmentIdInput.value, 10),
      record_date: recordDateInput.value,
      arrival_time: arrivalInput.value || null,
      departure_time: departureInput.value || null,
      drinks_sold: parseInt(drinksInput.value || "0", 10),
      special_commissions: parseFloat(specialInput.value || "0"),
      bonus: parseFloat(bonusInput.value || "0"),
      malus: parseFloat(malusInput.value || "0"),
    };

    try {
      const res = await fetch("/api/performance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.message || "Server error");
      closeModal();
    } catch (err) {
      alert(err.message || "Network error");
    }
  });

  // Change date -> reload that day
  recordDateInput.addEventListener("change", () => {
    const aId = assignmentIdInput.value;
    const day = recordDateInput.value;
    if (!aId || !day) return;
    loadRecord(aId, day);
  });
});

  // =========================================================

  openModal();
  loadRecord(aId, recordDateInput.value);
});

  // Changer de date => recharger ce jour
  recordDateInput.addEventListener("change", () => {
    const aId = assignmentIdInput.value;
    const day = recordDateInput.value;
    if (!aId || !day) return;
    loadRecord(aId, day);
  });

  // Save = upsert
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      assignment_id: parseInt(assignmentIdInput.value, 10),
      record_date: recordDateInput.value,
      arrival_time: arrivalInput.value || null,
      departure_time: departureInput.value || null,
      drinks_sold: parseInt(drinksInput.value || "0", 10),
      special_commissions: parseFloat(specialInput.value || "0"),
      bonus: parseFloat(bonusInput.value || "0"),
      malus: parseFloat(malusInput.value || "0"),
    };

    try {
      const res = await fetch("/api/performance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.message || "Server error");
      const d = new Date(recordDateInput.value + "T00:00:00");
const drinks = parseInt(drinksInput.value || "0", 10);
const penalty = parseInt(latenessPenaltyInput.value || "0", 10);

// crée (ou met à jour) l’item du jour courant en tête
const existingToday = historyBox.querySelector('.history-item[data-date="' + recordDateInput.value + '"]');
const html = `
  <div><span>Date:</span> <strong>${d.toLocaleDateString('en-GB')}</strong></div>
  <div><span>Drinks:</span> <strong>${drinks}</strong></div>
  <div><span>Penalty:</span> <strong>${penalty} THB</strong></div>
`;

if (existingToday) {
  existingToday.innerHTML = html;
  existingToday.classList.add('updated-item');
} else {
  const div = document.createElement("div");
  div.className = "history-item new-item";
  div.setAttribute("data-date", recordDateInput.value);
  div.innerHTML = html;
  historyBox.prepend(div);
}
      //closeModal();
      // Option: showToast("Saved!");
    } catch (err) {
      alert(err.message || "Network error");
    }
  });
});
// ===== Payroll: End Now & Delete (append this at the end of app.js) =====
document.addEventListener("DOMContentLoaded", function () {
  const table = document.querySelector(".payroll-table");
  if (!table) return;

  table.addEventListener("click", async (e) => {
    const endBtn   = e.target.closest(".end-contract-btn");
    const delBtn   = e.target.closest(".delete-contract-btn");
    const row      = e.target.closest("tr");

    // Rien à faire si on n'a pas cliqué sur un des deux nouveaux boutons
    if (!endBtn && !delBtn) return;
    if (!row) return;

    const assignmentId = row.dataset.assignmentId;
    if (!assignmentId) {
      alert("Missing assignment id on the row.");
      return;
    }

    // END NOW
    if (endBtn) {
      if (!confirm("End this contract now?")) return;

      endBtn.disabled = true;
      endBtn.textContent = "Ending...";

      try {
        // Backend à implémenter ensuite (étape suivante) :
        // POST /api/assignment/<id>/end  { ended_at: 'YYYY-MM-DD' }
        const payload = { ended_at: new Date().toISOString().slice(0, 10) };
        const res = await fetch(`/api/assignment/${assignmentId}/end`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) throw new Error(data.message || "Server error");

        // Option simple: on retire la ligne (le contrat n’est plus "ongoing")
        row.style.opacity = "0.5";
        setTimeout(() => row.remove(), 200);
      } catch (err) {
        console.error(err);
        alert(err.message || "Network error.");
      } finally {
        endBtn.disabled = false;
        endBtn.textContent = "End now";
      }
      return;
    }

    // DELETE
    if (delBtn) {
      if (!confirm("Delete this contract permanently? This cannot be undone.")) return;

      delBtn.disabled = true;
      delBtn.textContent = "Deleting...";

      try {
        // Backend à implémenter ensuite (étape suivante) :
        // DELETE /api/assignment/<id>
        const res = await fetch(`/api/assignment/${assignmentId}`, {
          method: "DELETE",
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) throw new Error(data.message || "Server error");

        row.style.opacity = "0.5";
        setTimeout(() => row.remove(), 200);
      } catch (err) {
        console.error(err);
        alert(err.message || "Network error.");
      } finally {
        delBtn.disabled = false;
        delBtn.textContent = "Delete";
      }
      return;
    }
  });
});
